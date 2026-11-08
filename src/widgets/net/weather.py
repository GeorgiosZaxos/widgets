"""Weather widget with a provider seam (FR-WEATHER-001..009). Layer L3.

PRIVACY: the location text you enter is sent to a third-party service (Open-Meteo's geocoding and
forecast APIs by default) (FR-WEATHER-009). Pass your own ``WeatherProvider`` to use another one.
"""

from __future__ import annotations

import json
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Protocol, cast
from urllib.parse import urlencode

from widgets.base_elements.events import KeyEvent
from widgets.base_elements.interactive import InteractiveWidget
from widgets.base_elements.widget_types import DEFAULT_STYLE, RGB, Style, WidgetId
from widgets.display._common import clip_cells
from widgets.errors import FeedError, LocationNotFoundError, WeatherError
from widgets.net._jobs import Jobs
from widgets.net.http import HttpTransport, UrllibTransport
from widgets.render.buffer import Canvas
from widgets.render.sanitize import sanitize_text

WMO = {
    0: ("Clear sky", "☀", "*"),
    1: ("Mainly clear", "🌤", "*"),
    2: ("Partly cloudy", "⛅", "~"),
    3: ("Overcast", "☁", "="),
    45: ("Fog", "🌫", "="),
    48: ("Rime fog", "🌫", "="),
    51: ("Light drizzle", "🌦", ","),
    53: ("Drizzle", "🌦", ","),
    55: ("Dense drizzle", "🌧", ","),
    56: ("Freezing drizzle", "🌧", ","),
    57: ("Freezing drizzle", "🌧", ","),
    61: ("Light rain", "🌦", "/"),
    63: ("Rain", "🌧", "/"),
    65: ("Heavy rain", "🌧", "/"),
    66: ("Freezing rain", "🌧", "/"),
    67: ("Freezing rain", "🌧", "/"),
    71: ("Light snow", "🌨", "*"),
    73: ("Snow", "❄", "*"),
    75: ("Heavy snow", "❄", "*"),
    77: ("Snow grains", "❄", "*"),
    80: ("Rain showers", "🌦", "/"),
    81: ("Rain showers", "🌧", "/"),
    82: ("Violent showers", "🌧", "/"),
    85: ("Snow showers", "🌨", "*"),
    86: ("Snow showers", "🌨", "*"),
    95: ("Thunderstorm", "⛈", "!"),
    96: ("Thunderstorm, hail", "⛈", "!"),
    99: ("Thunderstorm, hail", "⛈", "!"),
}
COMPASS = ("N", "NE", "E", "SE", "S", "SW", "W", "NW")
NA = "n/a"


def describe_code(code: int | None) -> str:
    """Return a short text description for a WMO weather code."""
    return WMO.get(code, ("Unknown", "?", "?"))[0] if code is not None else NA


def symbol(code: int | None, ascii_only: bool = False) -> str:
    """Return a symbol for a WMO weather code (ASCII when ``ascii_only``)."""
    if code is None:
        return "?"
    entry = WMO.get(code, ("Unknown", "?", "?"))
    return entry[2] if ascii_only else entry[1]


@dataclass(frozen=True, slots=True)
class Location:
    name: str
    latitude: float
    longitude: float
    country: str = ""
    admin: str = ""

    @property
    def label(self) -> str:
        return ", ".join(p for p in (self.name, self.admin, self.country) if p)


@dataclass(frozen=True, slots=True)
class Current:
    temperature: float | None = None
    apparent: float | None = None
    humidity: float | None = None
    wind_speed: float | None = None
    wind_direction: float | None = None
    precipitation: float | None = None
    code: int | None = None


@dataclass(frozen=True, slots=True)
class Day:
    date: str
    code: int | None = None
    t_max: float | None = None
    t_min: float | None = None
    precipitation: float | None = None


@dataclass(frozen=True, slots=True)
class Weather:
    location: Location
    current: Current
    days: tuple[Day, ...]
    units: str = "metric"


class WeatherProvider(Protocol):
    """Protocol for weather data sources."""

    def geocode(self, name: str) -> list[Location]: ...

    def forecast(self, location: Location, days: int, units: str) -> Weather: ...


def _as_dict(value: object) -> dict[str, object]:
    return value if isinstance(value, dict) else {}


def _as_list(value: object) -> list[object]:
    return value if isinstance(value, list) else []


def _num(value: object) -> float | None:
    return float(value) if isinstance(value, int | float) and not isinstance(value, bool) else None


def _code(value: object) -> int | None:
    n = _num(value)
    return int(n) if n is not None else None


class OpenMeteoProvider:
    """Weather provider using the Open-Meteo geocoding and forecast APIs."""

    GEO = "https://geocoding-api.open-meteo.com/v1/search"
    API = "https://api.open-meteo.com/v1/forecast"

    def __init__(self, transport: HttpTransport | None = None, timeout: float = 10.0) -> None:
        self.transport = transport or UrllibTransport()
        self.timeout = timeout

    def _json(self, url: str) -> dict[str, object]:
        try:
            resp = self.transport.get(url, timeout=self.timeout, max_bytes=2 << 20)
            data = json.loads(resp.body.decode("utf-8"))
        except FeedError as exc:
            raise WeatherError(f"weather service unavailable: {exc}") from exc
        except (ValueError, UnicodeDecodeError) as exc:
            raise WeatherError(f"weather service returned invalid data: {exc}") from exc
        if not isinstance(data, dict):
            raise WeatherError("weather service returned an unexpected document")
        return data

    def geocode(self, name: str) -> list[Location]:
        data = self._json(
            f"{self.GEO}?{urlencode({'name': name, 'count': 5, 'language': 'en', 'format': 'json'})}"
        )
        out: list[Location] = []
        for raw in _as_list(data.get("results")):
            r = _as_dict(raw)
            lat, lon = _num(r.get("latitude")), _num(r.get("longitude"))
            if lat is None or lon is None:
                continue
            out.append(
                Location(
                    sanitize_text(str(r.get("name", name))),
                    lat,
                    lon,
                    sanitize_text(str(r.get("country", ""))),
                    sanitize_text(str(r.get("admin1", ""))),
                )
            )
        return out

    def forecast(self, location: Location, days: int, units: str) -> Weather:
        imperial = units == "imperial"
        query = {
            "latitude": location.latitude,
            "longitude": location.longitude,
            "forecast_days": days,
            "current": "temperature_2m,apparent_temperature,relative_humidity_2m,wind_speed_10m,wind_direction_10m,precipitation,weather_code",
            "daily": "weather_code,temperature_2m_max,temperature_2m_min,precipitation_sum",
            "timezone": "auto",
        }
        if imperial:
            query.update(
                temperature_unit="fahrenheit", wind_speed_unit="mph", precipitation_unit="inch"
            )
        data = self._json(f"{self.API}?{urlencode(query)}")
        cur = _as_dict(data.get("current"))
        daily = _as_dict(data.get("daily"))
        times = _as_list(daily.get("time"))

        def col(key: str, i: int) -> object:
            seq = _as_list(daily.get(key))
            return seq[i] if i < len(seq) else None

        return Weather(
            location,
            Current(
                _num(cur.get("temperature_2m")),
                _num(cur.get("apparent_temperature")),
                _num(cur.get("relative_humidity_2m")),
                _num(cur.get("wind_speed_10m")),
                _num(cur.get("wind_direction_10m")),
                _num(cur.get("precipitation")),
                _code(cur.get("weather_code")),
            ),
            tuple(
                Day(
                    str(t),
                    _code(col("weather_code", i)),
                    _num(col("temperature_2m_max", i)),
                    _num(col("temperature_2m_min", i)),
                    _num(col("precipitation_sum", i)),
                )
                for i, t in enumerate(times)
            ),
            units,
        )


def fmt(value: float | None, unit: str = "", digits: int = 0) -> str:
    """Format a value with ``digits`` decimals and ``unit``; ``n/a`` when ``value`` is ``None``."""
    return NA if value is None else f"{value:.{digits}f}{unit}"


def compass(degrees: float | None) -> str:
    """Return the 16-point compass name for a bearing in degrees (``n/a`` when unknown)."""
    return NA if degrees is None else COMPASS[int((degrees % 360) / 45 + 0.5) % 8]


@dataclass(slots=True)
class _Cache:
    weather: Weather
    fetched: float
    key: tuple[str, int, str] = ("", 0, "")


class WeatherWidget(InteractiveWidget):
    """Keys: r refresh | u switch units | l change location | left/right switch day."""

    def __init__(
        self,
        x: int = 0,
        y: int = 0,
        width: int = 60,
        height: int = 14,
        *,
        location: str = "",
        units: str = "metric",
        days: int = 5,
        cache_ttl: float = 600.0,
        provider: WeatherProvider | None = None,
        transport: HttpTransport | None = None,
        clock: Callable[[], float] = time.monotonic,
        ascii_only: bool = False,
        name: WidgetId | None = None,
    ) -> None:
        super().__init__(x, y, width, height, name=name)
        if units not in ("metric", "imperial"):
            raise ValueError("units must be 'metric' or 'imperial'")
        if not 1 <= days <= 16:
            raise ValueError("days must be in 1..16")
        self.provider: WeatherProvider = provider or OpenMeteoProvider(transport)
        self.units, self.days, self.cache_ttl, self.ascii_only = units, days, cache_ttl, ascii_only
        self._clock = clock
        self.location_name = location
        self.candidates: list[Location] = []
        self.location: Location | None = None
        self.weather: Weather | None = None
        self.stale = False
        self.error: str | None = None
        self.loading = False
        self.day_index = 0
        self.editing = False
        self.edit_text = ""
        self._cache: dict[tuple[str, int, str], _Cache] = {}
        self._jobs = Jobs()
        self._token = 0

    # -- control ---------------------------------------------------------------------------
    def set_location(self, name: str) -> None:
        """Change the location and refresh asynchronously (FR-WEATHER-006)."""
        self.location_name = name.strip()
        self.location = None
        self.refresh(force=True)

    def set_units(self, units: str) -> None:
        if units not in ("metric", "imperial"):
            raise ValueError("units must be 'metric' or 'imperial'")
        self.units = units
        self.refresh()

    def refresh(self, force: bool = False) -> None:
        """Fetch (or serve from cache) off the UI thread; ``force`` bypasses the cache."""
        if not self.location_name:
            self.error = "no location set"
            return
        key = (self.location_name.casefold(), self.days, self.units)
        cached = self._cache.get(key)
        if cached and not force and self._clock() - cached.fetched < self.cache_ttl:
            self.weather, self.location, self.stale, self.error = (
                cached.weather,
                cached.weather.location,
                False,
                None,
            )
            return
        self.loading = True
        self._token += 1
        token, name, loc, days, units = (
            self._token,
            self.location_name,
            self.location,
            self.days,
            self.units,
        )

        def work() -> tuple[list[Location], Weather]:
            cands = [loc] if loc else self.provider.geocode(name)
            if not cands:
                raise LocationNotFoundError(f"no location found for {name!r}")
            return cands, self.provider.forecast(cands[0], days, units)

        def done(value: object, error: BaseException | None) -> None:
            if token != self._token:
                return  # superseded by a newer request
            self.loading = False
            if error is not None:
                self.error = str(error)
                self.stale = self.weather is not None
                return
            cands_l, weather_v = cast("tuple[list[Location], Weather]", value)
            self.candidates, self.location, self.weather = cands_l, cands_l[0], weather_v
            self.stale, self.error = False, None
            self._cache[key] = _Cache(weather_v, self._clock(), key)
            self.day_index = min(self.day_index, max(0, len(weather_v.days) - 1))

        self._jobs.submit(work, done)

    def update(self, dt: float) -> None:
        self._jobs.drain()

    def on_close(self) -> None:
        self._jobs.close()

    def handle_key(self, event: KeyEvent) -> bool:
        if not self.effective_enabled:
            return False
        key = event.key
        if self.editing:
            if key == "enter":
                self.editing = False
                if self.edit_text.strip():
                    self.set_location(self.edit_text)
            elif key == "escape":
                self.editing = False
            elif key == "backspace":
                self.edit_text = self.edit_text[:-1]
            elif event.char and event.char.isprintable():
                self.edit_text += event.char
            else:
                return False
            return True
        if key == "r":
            self.refresh(force=True)
        elif key == "u":
            self.set_units("imperial" if self.units == "metric" else "metric")
        elif key == "l":
            self.editing, self.edit_text = True, ""
        elif key in ("left", "right") and self.weather:
            self.day_index = (self.day_index + (1 if key == "right" else -1)) % max(
                1, len(self.weather.days)
            )
        else:
            return False
        return True

    # -- rendering ---------------------------------------------------------------------------
    def render(self, canvas: Canvas) -> None:
        w = canvas.width
        row = 0
        if self.editing:
            canvas.write_text(0, 0, f"Location: {self.edit_text}_"[:w], Style(reverse=True))
            canvas.write_text(1, 0, "(sent to a third-party weather service)"[:w], Style(dim=True))
            return
        t_unit, s_unit, p_unit = (
            ("°F", "mph", "in") if self.units == "imperial" else ("°C", "km/h", "mm")
        )
        if self.ascii_only:
            t_unit = t_unit.replace("°", "")
        if self.weather is None:
            msg = self.error or ("loading…" if self.loading else "press 'l' to choose a location")
            canvas.write_text(
                0,
                0,
                clip_cells(msg, w),
                Style(fg=RGB(230, 70, 70)) if self.error else Style(dim=True),
            )
            return
        wx = self.weather
        title = (
            wx.location.label
            + ("  [stale]" if self.stale else "")
            + ("  …" if self.loading else "")
        )
        canvas.write_text(row, 0, clip_cells(title, w), Style(bold=True))
        c = wx.current
        canvas.write_text(
            1,
            0,
            f"{symbol(c.code, self.ascii_only)} {fmt(c.temperature, t_unit)}  {describe_code(c.code)}",
            DEFAULT_STYLE,
        )
        canvas.write_text(
            2,
            0,
            clip_cells(
                f"feels {fmt(c.apparent, t_unit)} | humidity {fmt(c.humidity, '%')} | wind {fmt(c.wind_speed, ' ' + s_unit)} "
                f"{compass(c.wind_direction)} | precip {fmt(c.precipitation, ' ' + p_unit, 1)}",
                w,
            ),
            Style(dim=True),
        )
        for i, d in enumerate(wx.days[: max(0, canvas.height - 5)]):
            sel = i == self.day_index
            line = f"{'>' if sel else ' '} {d.date}  {symbol(d.code, self.ascii_only)} {describe_code(d.code):<18} {fmt(d.t_min, t_unit):>6} / {fmt(d.t_max, t_unit):>6}  {fmt(d.precipitation, ' ' + p_unit, 1)}"
            canvas.write_text(4 + i, 0, clip_cells(line, w), Style(bold=sel))
        if self.error:
            canvas.write_text(
                canvas.height - 1, 0, clip_cells(f"! {self.error}", w), Style(fg=RGB(230, 70, 70))
            )
        elif len(self.candidates) > 1:
            canvas.write_text(
                canvas.height - 1,
                0,
                clip_cells(f"{len(self.candidates)} matches; showing the first", w),
                Style(dim=True),
            )

    def describe(self) -> str:
        if self.weather is None:
            return f"WeatherWidget({self.location_name!r}, no data)"
        c = self.weather.current
        return f"WeatherWidget({self.weather.location.label}: {fmt(c.temperature)} {describe_code(c.code)}{', stale' if self.stale else ''})"


__all__ = [
    "Location",
    "OpenMeteoProvider",
    "Weather",
    "WeatherError",
    "WeatherProvider",
    "WeatherWidget",
]
_ = field
