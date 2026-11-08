"""Calendar, clock and countdown (FR-CAL-001..003). Layer L3."""

from __future__ import annotations

import calendar as _calendar
import contextlib
import datetime as dt
import sys
from collections.abc import Callable
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from widgets.base_elements.base import Widget
from widgets.base_elements.effects import Clock, MonotonicClock
from widgets.base_elements.events import KeyEvent
from widgets.base_elements.interactive import InteractiveWidget
from widgets.base_elements.widget_types import DEFAULT_STYLE, Style, WidgetId
from widgets.display.vprint import clock_text, countdown_text
from widgets.render.buffer import Canvas

_DAYS = ("Mo", "Tu", "We", "Th", "Fr", "Sa", "Su")


def make_date(year: int, month: int, day: int = 1) -> dt.date:
    """Return ``date(year, month, day)``; raises ``ValueError`` for an invalid date."""
    try:
        return dt.date(year, month, day)
    except (ValueError, TypeError) as exc:
        raise ValueError(f"invalid date {year!r}-{month!r}-{day!r}: {exc}") from exc


class CalendarWidget(InteractiveWidget):
    """Month grid with keyboard-selectable day (arrows, pageup/pagedown, home/end, enter)."""

    def __init__(
        self,
        x: int = 0,
        y: int = 0,
        *,
        year: int | None = None,
        month: int | None = None,
        first_weekday: int = 0,
        today: dt.date | None = None,
        selected: dt.date | None = None,
        on_select: Callable[[dt.date], object] | None = None,
        name: WidgetId | None = None,
    ) -> None:
        super().__init__(x, y, 20, 8, name=name)
        if not 0 <= first_weekday <= 6:
            raise ValueError("first_weekday must be 0 (Monday) .. 6 (Sunday)")
        self.today = today or dt.date.today()
        self.first_weekday = first_weekday
        if selected is not None:
            base = selected
        elif year is None and month is None:
            base = self.today
        else:
            base = make_date(
                self.today.year if year is None else year,
                self.today.month if month is None else month,
                1,
            )
        self.selected = base
        self.on_select = on_select

    focusable = True

    @property
    def year(self) -> int:
        return self.selected.year

    @property
    def month(self) -> int:
        return self.selected.month

    def _move_days(self, days: int) -> None:
        with contextlib.suppress(OverflowError):
            self.selected += dt.timedelta(days=days)

    def _move_months(self, months: int) -> None:
        idx = self.selected.year * 12 + self.selected.month - 1 + months
        year, month = divmod(idx, 12)
        if not 1 <= year <= 9999:
            return
        last = _calendar.monthrange(year, month + 1)[1]
        self.selected = dt.date(year, month + 1, min(self.selected.day, last))

    def handle_key(self, event: KeyEvent) -> bool:
        if not self.effective_enabled:
            return False
        actions = {
            "left": lambda: self._move_days(-1),
            "right": lambda: self._move_days(1),
            "up": lambda: self._move_days(-7),
            "down": lambda: self._move_days(7),
            "pageup": lambda: self._move_months(-1),
            "pagedown": lambda: self._move_months(1),
            "home": lambda: setattr(self, "selected", self.selected.replace(day=1)),
            "end": lambda: setattr(
                self,
                "selected",
                self.selected.replace(day=_calendar.monthrange(self.year, self.month)[1]),
            ),
        }
        if event.key in actions:
            actions[event.key]()
            return True
        if event.key == "enter":
            self.invoke_callback(self.on_select, self.selected)
            return True
        return False

    def weeks(self) -> list[list[int]]:
        return _calendar.Calendar(self.first_weekday).monthdayscalendar(self.year, self.month)

    def render(self, canvas: Canvas) -> None:
        title = f"{_calendar.month_name[self.month]} {self.year}"
        canvas.write_text(0, max(0, (20 - len(title)) // 2), title, Style(bold=True))
        order = [(self.first_weekday + i) % 7 for i in range(7)]
        for i, d in enumerate(order):
            canvas.write_text(1, i * 3, _DAYS[d], Style(dim=True))
        for r, week in enumerate(self.weeks()):
            for c, day in enumerate(week):
                if not day:
                    continue
                date = dt.date(self.year, self.month, day)
                st = DEFAULT_STYLE
                if date == self.today:
                    st = st.replace(bold=True, underline=True)
                if date == self.selected:
                    st = st.replace(reverse=True)
                canvas.write_text(2 + r, c * 3, f"{day:>2}", st)

    def describe(self) -> str:
        return f"CalendarWidget({self.selected.isoformat()})"


class ClockWidget(Widget):
    """Wall-clock display in an IANA time zone; ``now_fn`` is injectable for tests."""

    def __init__(
        self,
        x: int = 0,
        y: int = 0,
        *,
        tz: str = "UTC",
        seconds: bool = True,
        font: str | None = None,
        now_fn: Callable[[], dt.datetime] | None = None,
        name: WidgetId | None = None,
    ) -> None:
        self.font = font
        rows = 1
        if font is not None:
            import widgets.assets.fonts as _fonts

            rows = _fonts.get_font(font).height  # unknown names raise KeyError here
        super().__init__(x, y, 8 if font is None else 40, rows, name=name)
        self.zone: dt.tzinfo
        if tz.upper() in ("UTC", "Z"):
            self.zone = dt.UTC  # needs no time zone database (absent on Windows)
        else:
            try:
                self.zone = ZoneInfo(tz)
            except ZoneInfoNotFoundError as exc:
                hint = " On Windows run: pip install tzdata" if sys.platform == "win32" else ""
                raise ZoneInfoNotFoundError(f"No time zone found with key {tz!r}.{hint}") from exc
        self.tz, self.seconds = tz, seconds
        self._now_fn = now_fn or (lambda: dt.datetime.now(dt.UTC))

    def now(self) -> dt.datetime:
        return self._now_fn().astimezone(self.zone)

    def text(self) -> str:
        n = self.now()
        return clock_text(n.hour, n.minute, n.second if self.seconds else None)

    def render(self, canvas: Canvas) -> None:
        if self.font is None:
            canvas.write_text(0, 0, self.text(), DEFAULT_STYLE)
            return
        import widgets.assets.fonts as _fonts

        for r, row in enumerate(_fonts.render_text(self.text(), self.font)):
            canvas.write_text(r, 0, row, DEFAULT_STYLE)

    def describe(self) -> str:
        return f"Clock({self.tz} {self.text()})"


class Countdown(Widget):
    """Counts down ``seconds`` using an injectable :class:`Clock`; completion fires once."""

    def __init__(
        self,
        seconds: float,
        x: int = 0,
        y: int = 0,
        *,
        clock: Clock | None = None,
        on_complete: Callable[[], object] | None = None,
        name: WidgetId | None = None,
    ) -> None:
        super().__init__(x, y, 8, 1, name=name)
        if seconds < 0:
            raise ValueError("seconds must be >= 0")
        self._clock = clock or MonotonicClock()
        self._end = self._clock.now() + seconds
        self.on_complete = on_complete
        self._fired = False

    @property
    def remaining(self) -> float:
        return max(0.0, self._end - self._clock.now())

    def update(self, dt_: float) -> None:
        if self.remaining <= 0 and not self._fired:
            self._fired = True
            self.invoke_callback(self.on_complete)

    def render(self, canvas: Canvas) -> None:
        canvas.write_text(0, 0, countdown_text(self.remaining), DEFAULT_STYLE)

    def describe(self) -> str:
        return f"Countdown({countdown_text(self.remaining)})"
