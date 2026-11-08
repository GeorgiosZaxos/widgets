"""Live gallery of the M6 network widgets (RSS reader, weather).

    python examples/net_gallery.py [--live] [--page N] [--duration S]

Runs OFFLINE by default using a fake transport with simulated latency and an occasional failure,
so it works without internet. ``--live`` uses real HTTP (Open-Meteo for weather; feed URLs below).
NOTE: with --live, the location text you type is sent to a third-party service (Open-Meteo).

F1 RSS reader (arrows, tab = next feed, v = cycle list/marquee/box, r = refresh, +/- speed)
F2 Weather   (r refresh, u units, l change location, left/right day).  F10 or Ctrl+Q quits.
"""

from __future__ import annotations

import argparse
import itertools
import json
import time
from collections.abc import Mapping

from widgets.base_elements.base import Widget
from widgets.base_elements.events import Event, KeyEvent
from widgets.base_elements.layout import Screen
from widgets.base_elements.widget_types import RGB, Style
from widgets.errors import FeedConnectionError
from widgets.net.http import HttpResponse, HttpTransport, UrllibTransport
from widgets.net.rss import FeedSource, RssReader
from widgets.net.weather import WeatherWidget
from widgets.render.buffer import Canvas
from widgets.render.run import run_app

W, H = 100, 28
BAR = Style(fg=RGB(255, 255, 255), bg=RGB(40, 60, 140), bold=True)
GREEK_FEEDS = [
    FeedSource("Αθλητισμός", "https://www.gazzetta.gr/rss.xml", "ΑΘλητικά"),
    FeedSource("SDNA", "https://www.sdna.gr/latest.xml", "ΑΘλητικά"),
]
LIVE_FEEDS = [
    *GREEK_FEEDS,
    FeedSource("Python Insider", "https://blog.python.org/feeds/posts/default", "Python"),
    FeedSource("NASA", "https://www.nasa.gov/rss/dyn/breaking_news.rss", "Science"),
]
VIEWS = ["list", "marquee", "box"]


def _rss(title: str, n: int, stamp: int) -> bytes:
    items = "".join(
        f"<item><title>{title} headline #{i + 1} (rev {stamp})</title><link>https://example.org/{i}</link>"
        f"<description>&lt;p&gt;Summary of <![CDATA[<b>story</b>]]> number {i + 1} &amp; more.&lt;/p&gt;</description>"
        f"<pubDate>Mon, 02 Nov 2026 {8 + i % 10:02d}:00:00 GMT</pubDate></item>"
        for i in range(n)
    )
    return f"<rss version='2.0'><channel><title>{title}</title>{items}</channel></rss>".encode()


class DemoTransport:
    """Offline transport: serves canned feeds/weather, adds latency, fails every 5th feed call."""

    def __init__(self) -> None:
        self.n = itertools.count(1)

    def get(
        self,
        url: str,
        *,
        headers: Mapping[str, str] | None = None,
        timeout: float = 10.0,
        max_bytes: int = 1 << 20,
    ) -> HttpResponse:
        time.sleep(0.4)
        k = next(self.n)
        if "geocoding" in url:
            return HttpResponse(
                200,
                json.dumps(
                    {
                        "results": [
                            {
                                "name": "Demoville",
                                "latitude": 1.0,
                                "longitude": 2.0,
                                "country": "Freedonia",
                                "admin1": "North",
                            },
                            {
                                "name": "Demoville",
                                "latitude": 3.0,
                                "longitude": 4.0,
                                "country": "Sylvania",
                            },
                        ]
                    }
                ).encode(),
            )
        if "open-meteo" in url:
            imperial = "fahrenheit" in url

            def f(c: float | None) -> float | None:
                if c is None or not imperial:
                    return c
                return round(c * 9 / 5 + 32, 1)

            return HttpResponse(
                200,
                json.dumps(
                    {
                        "current": {
                            "temperature_2m": f(18.4),
                            "apparent_temperature": f(17.0),
                            "relative_humidity_2m": 64,
                            "wind_speed_10m": 12,
                            "wind_direction_10m": 250,
                            "precipitation": 0.0,
                            "weather_code": 2,
                        },
                        "daily": {
                            "time": [f"2026-11-{7 + i:02d}" for i in range(5)],
                            "weather_code": [2, 61, 63, 3, 0],
                            "temperature_2m_max": [f(c) for c in (19, 16, 14, 17, None)],
                            "temperature_2m_min": [f(c) for c in (9, 8, 7, 8, 6)],
                            "precipitation_sum": [0, 2.4, 6.1, 0.3, 0],
                        },
                    }
                ).encode(),
            )
        if "flaky" in url and k % 5 == 0:
            raise FeedConnectionError("simulated outage")
        if "gazzetta" in url or "sdna" in url:
            site = "Gazzetta" if "gazzetta" in url else "SDNA"
            return HttpResponse(
                200,
                _rss(f"{site} Αθλητικά (demo)", 14, k).replace(b"headline", "ειδήσεις".encode()),
                {"etag": f'"{k}"'},
            )
        name = url.rsplit("/", 1)[-1].title()
        return HttpResponse(200, _rss(name, 14, k), {"etag": f'"{k}"'})


class Bar(Widget):
    def __init__(self, y: int, kind: str) -> None:
        super().__init__(0, y, W, 1)
        self.kind, self.page, self.msg = kind, 0, ""

    def render(self, canvas: Canvas) -> None:
        if self.kind == "head":
            text = "  ".join(
                f"[F{i + 1}] {p}" if i == self.page else f" F{i + 1}  {p}"
                for i, p in enumerate(("RSS", "Weather"))
            )
            canvas.write_text(0, 0, text.ljust(canvas.width), BAR)
        else:
            canvas.write_text(
                0,
                0,
                f" {self.msg}   | F10 quit"[: canvas.width].ljust(canvas.width),
                Style(dim=True),
            )


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--live", action="store_true")
    ap.add_argument("--page", type=int, default=1)
    ap.add_argument("--duration", type=float, default=None)
    args = ap.parse_args()
    transport: HttpTransport = UrllibTransport() if args.live else DemoTransport()
    sources = (
        LIVE_FEEDS
        if args.live
        else [
            FeedSource("World", "https://demo.test/world", "News"),
            FeedSource("Sport", "https://demo.test/sport", "News"),
            FeedSource("Gadgets", "https://demo.test/tech", "Tech"),
            FeedSource("Flaky", "https://demo.test/flaky", "Tech"),
            *GREEK_FEEDS,
        ]
    )
    rss = RssReader(
        1,
        2,
        W - 2,
        H - 4,
        sources=sources,
        transport=transport,
        min_refresh_interval=5.0 if not args.live else 60.0,
    )
    wx = WeatherWidget(
        1, 2, W - 2, H - 4, location="Demoville" if not args.live else "Athens", transport=transport
    )
    screen = Screen(W, H)
    head, foot = Bar(0, "head"), Bar(H - 1, "foot")
    for w in (rss, wx, head, foot):
        screen.add(w)
    pages = [rss, wx]
    cur = {"i": 0}

    def show(i: int) -> None:
        cur["i"] = i
        for k, w in enumerate(pages):
            w.visible = k == i
            (w.focus if k == i else w.blur)()
        head.page = i

    rss.refresh()
    wx.refresh()
    show(max(0, min(1, args.page - 1)))

    def on_event(event: Event) -> None:
        if not isinstance(event, KeyEvent):
            return
        if event.key in ("f1", "f2"):
            show(int(event.key[1]) - 1)
            return
        if cur["i"] == 0:
            if event.key == "v":
                rss.view = VIEWS[(VIEWS.index(rss.view) + 1) % 3]
                return
            if event.key in ("+", "-"):
                rss.set_speed(max(2.0, rss._marquee.speed + (4.0 if event.key == "+" else -4.0)))
                return
            rss.handle_key(event)
            foot.msg = rss.status_text()
        else:
            wx.handle_key(event)
            foot.msg = (wx.error or "") or wx.describe()

    run_app(
        screen,
        fps=30,
        duration=args.duration,
        quit_keys=("ctrl+q", "f10"),
        on_event=on_event,
        title="widgets network gallery",
    )


if __name__ == "__main__":
    main()
