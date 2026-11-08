"""Tailing, filterable log viewer. Layer L3."""

from __future__ import annotations

import time
from collections import deque
from dataclasses import dataclass

from widgets.base_elements.events import KeyEvent
from widgets.base_elements.interactive import InteractiveWidget
from widgets.base_elements.widget_types import RGB, Style, WidgetId
from widgets.display._common import clip_cells
from widgets.render.buffer import Canvas

LEVELS = ("DEBUG", "INFO", "WARNING", "ERROR")
LEVEL_STYLE = {
    "DEBUG": Style(dim=True),
    "INFO": Style(fg=RGB(120, 200, 255)),
    "WARNING": Style(fg=RGB(240, 190, 60), bold=True),
    "ERROR": Style(fg=RGB(245, 80, 80), bold=True),
}
LEVEL_TAG = {"DEBUG": "DBG", "INFO": "INF", "WARNING": "WRN", "ERROR": "ERR"}


@dataclass(frozen=True, slots=True)
class LogEntry:
    time: float
    level: str
    message: str


class LogViewer(InteractiveWidget):
    """Bounded log with level filter, text filter and tail-follow.

    Keys: up/down/pageup/pagedown scroll, end = follow, home = oldest, ``f`` cycles the minimum
    level, ``c`` clears the text filter. Level tags (INF/WRN/ERR) never rely on colour alone.
    """

    def __init__(
        self,
        x: int = 0,
        y: int = 0,
        width: int = 80,
        height: int = 12,
        *,
        max_entries: int = 1000,
        show_time: bool = True,
        name: WidgetId | None = None,
    ) -> None:
        super().__init__(x, y, width, height, name=name)
        if max_entries < 1:
            raise ValueError("max_entries must be >= 1")
        self.entries: deque[LogEntry] = deque(maxlen=max_entries)
        self.min_level = "DEBUG"
        self.text_filter = ""
        self.follow = True
        self.top = 0
        self.show_time = show_time

    def log(self, message: str, level: str = "INFO") -> None:
        level = level.upper()
        if level not in LEVELS:
            raise ValueError(f"level must be one of {LEVELS}")
        self.entries.append(LogEntry(time.time(), level, message.replace("\n", " ")))

    def clear(self) -> None:
        self.entries.clear()
        self.top = 0

    def set_filter(self, text: str = "", min_level: str | None = None) -> None:
        self.text_filter = text.lower()
        if min_level is not None:
            if min_level not in LEVELS:
                raise ValueError(f"level must be one of {LEVELS}")
            self.min_level = min_level

    def visible_entries(self) -> list[LogEntry]:
        floor = LEVELS.index(self.min_level)
        return [
            e
            for e in self.entries
            if LEVELS.index(e.level) >= floor and self.text_filter in e.message.lower()
        ]

    def _page(self) -> int:
        return max(1, self.height - 1)

    def handle_key(self, event: KeyEvent) -> bool:
        total = len(self.visible_entries())
        last = max(0, total - self._page())
        key = event.key
        if key in ("up", "down", "pageup", "pagedown", "home"):
            self.follow = False
            delta = {"up": -1, "down": 1, "pageup": -self._page(), "pagedown": self._page()}
            self.top = 0 if key == "home" else self.top + delta[key]
            self.top = max(0, min(last, self.top))
            if self.top >= last:
                self.follow = True
            return True
        if key == "end":
            self.follow = True
            return True
        if key == "f":
            self.min_level = LEVELS[(LEVELS.index(self.min_level) + 1) % len(LEVELS)]
            return True
        if key == "c":
            self.text_filter = ""
            return True
        return False

    def render(self, canvas: Canvas) -> None:
        rows = self.visible_entries()
        page = max(1, canvas.height - 1)
        if self.follow:
            self.top = max(0, len(rows) - page)
        for r, entry in enumerate(rows[self.top : self.top + page]):
            stamp = time.strftime("%H:%M:%S ", time.localtime(entry.time)) if self.show_time else ""
            head = f"{stamp}{LEVEL_TAG[entry.level]} "
            canvas.write_text(r, 0, head, Style(dim=True))
            body = clip_cells(entry.message, max(0, canvas.width - len(head)))
            canvas.write_text(r, len(head), body, LEVEL_STYLE[entry.level])
        status = f"{len(rows)}/{len(self.entries)} >= {self.min_level}"
        if self.text_filter:
            status += f' "{self.text_filter}"'
        status += " [follow]" if self.follow else " [paused]"
        canvas.write_text(canvas.height - 1, 0, clip_cells(status, canvas.width), Style(dim=True))


__all__ = ["LEVELS", "LogEntry", "LogViewer"]
