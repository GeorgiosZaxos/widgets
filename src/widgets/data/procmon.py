"""Process monitor. Layer L3. Needs ``psutil`` (extra ``system``) unless ``fetch`` is injected."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from widgets.base_elements.events import KeyEvent
from widgets.base_elements.import_helper import require_import
from widgets.base_elements.interactive import InteractiveWidget
from widgets.base_elements.widget_types import RGB, Style, WidgetId
from widgets.display._common import clip_cells
from widgets.display.stepper import Sparkline
from widgets.render.buffer import Canvas

Fetch = Callable[[], list[dict[str, Any]]]


def _psutil_fetch() -> Fetch:
    psutil = require_import("psutil", feature="ProcessMonitor", extra="system")

    def fetch() -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        for p in psutil.process_iter(["pid", "name", "cpu_percent", "memory_percent"]):
            info = p.info
            rows.append(
                {
                    "pid": info["pid"],
                    "name": info["name"] or "?",
                    "cpu": info["cpu_percent"] or 0.0,
                    "mem": info["memory_percent"] or 0.0,
                }
            )
        return rows

    return fetch


class ProcessMonitor(InteractiveWidget):
    """Top-N processes with a CPU history sparkline. Keys: up/down select, ``s`` sort cpu/mem/pid/name."""

    SORTS = ("cpu", "mem", "pid", "name")

    def __init__(
        self,
        x: int = 0,
        y: int = 0,
        width: int = 70,
        height: int = 14,
        *,
        fetch: Fetch | None = None,
        interval: float = 1.0,
        name: WidgetId | None = None,
    ) -> None:
        super().__init__(x, y, width, height, name=name)
        self._fetch = fetch or _psutil_fetch()
        self.interval = max(0.1, interval)
        self.rows: list[dict[str, Any]] = []
        self.sort = "cpu"
        self.index = 0
        self._acc = self.interval
        self.history = Sparkline(0, 0, max(10, width - 14), maximum=100.0)
        self.error = ""

    def refresh(self) -> None:
        try:
            self.rows = self._fetch()
            self.error = ""
        except Exception as exc:  # a failing source must not break the UI
            self.error = f"fetch failed: {exc}"
            return
        self._apply_sort()
        self.history.push(min(100.0, sum(float(r.get("cpu", 0)) for r in self.rows)))

    def _apply_sort(self) -> None:
        reverse = self.sort in ("cpu", "mem")
        self.rows.sort(key=lambda r: r.get(self.sort, 0), reverse=reverse)

    def update(self, dt: float) -> None:
        self._acc += dt
        if self._acc >= self.interval:
            self._acc = 0.0
            self.refresh()

    def handle_key(self, event: KeyEvent) -> bool:
        if event.key in ("up", "down"):
            self.index = max(
                0, min(max(0, len(self.rows) - 1), self.index + (1 if event.key == "down" else -1))
            )
            return True
        if event.key == "s":
            self.sort = self.SORTS[(self.SORTS.index(self.sort) + 1) % len(self.SORTS)]
            self._apply_sort()
            return True
        return False

    def render(self, canvas: Canvas) -> None:
        w = canvas.width
        canvas.write_text(0, 0, "CPU ", Style(dim=True))
        for i, ch in enumerate(self.history.text()[-(w - 4) :]):
            canvas.write_text(0, 4 + i, ch, Style(fg=RGB(90, 200, 255)))
        canvas.write_text(
            1,
            0,
            clip_cells(f"{'PID':>7} {'CPU%':>6} {'MEM%':>6}  NAME  (sort: {self.sort})", w),
            Style(bold=True),
        )
        page = max(0, canvas.height - 2)
        start = (
            max(0, min(self.index - page + 1, len(self.rows) - page)) if self.index >= page else 0
        )
        for r, row in enumerate(self.rows[start : start + page]):
            line = f"{row['pid']:>7} {float(row['cpu']):>6.1f} {float(row['mem']):>6.1f}  {row['name']}"
            style = Style(reverse=True) if start + r == self.index else Style()
            canvas.write_text(r + 2, 0, clip_cells(line, w).ljust(w), style)
        if self.error:
            canvas.write_text(
                canvas.height - 1, 0, clip_cells(self.error, w), Style(fg=RGB(240, 90, 90))
            )


__all__ = ["ProcessMonitor"]
