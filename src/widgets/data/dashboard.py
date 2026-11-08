"""Dashboard widgets: fetching off the UI thread, history, callbacks (FR-DASH-001..006). Layer L3."""

from __future__ import annotations

import queue
import threading
from collections import deque
from collections.abc import Callable

from widgets.base_elements.base import Widget
from widgets.base_elements.layout import Container
from widgets.base_elements.widget_types import DEFAULT_STYLE, RGB, Style, WidgetId
from widgets.render.buffer import Canvas

MIN_INTERVAL = 0.1
SPARK = "▁▂▃▄▅▆▇█"
ASCII_SPARK = "_.,-~^*#"


class DashboardWidget(Widget):
    """Base class. ``fetch`` runs on a worker thread; results are applied on the UI thread in ``update``."""

    def __init__(
        self,
        x: int = 0,
        y: int = 0,
        width: int = 40,
        height: int = 4,
        *,
        fetch: Callable[[], object] | None = None,
        interval: float = 1.0,
        history_size: int = 100,
        on_update: Callable[[object], object] | None = None,
        name: WidgetId | None = None,
    ) -> None:
        super().__init__(x, y, width, height, name=name)
        if interval < MIN_INTERVAL:
            raise ValueError(f"interval must be >= {MIN_INTERVAL}")
        if history_size < 1:
            raise ValueError("history_size must be >= 1")
        self.fetch, self.interval, self.on_update = fetch, interval, on_update
        self.history: deque[object] = deque(maxlen=history_size)
        self.error = False
        self.last_error: BaseException | None = None
        self._results: queue.SimpleQueue[tuple[str, object]] = queue.SimpleQueue()
        self._stop_evt = threading.Event()
        self._run_evt = threading.Event()
        self._wake = threading.Event()
        self._thread: threading.Thread | None = None

    # -- worker ---------------------------------------------------------------------------
    def _worker(self) -> None:
        while not self._stop_evt.is_set():
            if self._run_evt.is_set() and self.fetch is not None:
                try:
                    self._results.put(("ok", self.fetch()))
                except Exception as exc:
                    self._results.put(("err", exc))
            self._wake.wait(self.interval)
            self._wake.clear()

    def on_start(self) -> None:
        self._stop_evt.clear()
        self._run_evt.set()
        if self.fetch is not None and (self._thread is None or not self._thread.is_alive()):
            self._thread = threading.Thread(
                target=self._worker, name=f"dash-{self.name}", daemon=True
            )
            self._thread.start()

    def on_pause(self) -> None:
        self._run_evt.clear()

    def on_resume(self) -> None:
        self._run_evt.set()
        self._wake.set()

    def on_stop(self) -> None:
        self._stop_evt.set()
        self._run_evt.clear()
        self._wake.set()
        if self._thread is not None:
            self._thread.join(timeout=2.0)
            self._thread = None

    def on_close(self) -> None:
        self.on_stop()

    # -- UI thread ---------------------------------------------------------------------------
    def push(self, data: object) -> None:
        """Event-driven update (thread-safe); applied on the next ``update``."""
        self._results.put(("ok", data))

    def update(self, dt: float) -> None:
        self.apply_pending()

    def apply_pending(self) -> int:
        applied = 0
        while True:
            try:
                kind, payload = self._results.get_nowait()
            except queue.Empty:
                return applied
            if kind == "err":
                self.error, self.last_error = True, payload  # type: ignore[assignment]
                continue
            self.error = False
            self.history.append(payload)
            self.invoke_callback(self.on_update, payload)
            applied += 1

    @property
    def latest(self) -> object | None:
        return self.history[-1] if self.history else None


class TextDashboard(DashboardWidget):
    """Dashboard that shows the latest fetched value as text, refreshed on an interval."""

    def __init__(
        self, *args: object, formatter: Callable[[object], str] = str, **kwargs: object
    ) -> None:
        super().__init__(*args, **kwargs)  # type: ignore[arg-type]
        self.formatter = formatter

    def render(self, canvas: Canvas) -> None:
        text = self.formatter(self.latest) if self.history else "waiting for data…"
        for r, line in enumerate(text.split("\n")[: canvas.height - (1 if self.error else 0)]):
            canvas.write_text(r, 0, line[: canvas.width], DEFAULT_STYLE)
        if self.error:
            canvas.write_text(
                canvas.height - 1,
                0,
                f"! {self.last_error}"[: canvas.width],
                Style(fg=RGB(230, 70, 70)),
            )


class MetricDashboard(DashboardWidget):
    """Latest numeric value with unit plus a sparkline of the history."""

    def __init__(
        self,
        *args: object,
        label: str = "",
        unit: str = "",
        ascii_only: bool = False,
        **kwargs: object,
    ) -> None:
        super().__init__(*args, **kwargs)  # type: ignore[arg-type]
        self.label, self.unit, self.ascii_only = label, unit, ascii_only

    def sparkline(self, width: int) -> str:
        glyphs = ASCII_SPARK if self.ascii_only else SPARK
        nums = [float(v) for v in list(self.history)[-width:] if isinstance(v, int | float)]
        if not nums:
            return ""
        lo, hi = min(nums), max(nums)
        span = hi - lo or 1.0
        return "".join(
            glyphs[min(len(glyphs) - 1, int((v - lo) / span * (len(glyphs) - 1) + 0.5))]
            for v in nums
        )

    def render(self, canvas: Canvas) -> None:
        latest = self.latest
        value = f"{latest:g}{self.unit}" if isinstance(latest, int | float) else "n/a"
        canvas.write_text(0, 0, f"{self.label}: {value}"[: canvas.width], Style(bold=True))
        if canvas.height > 1:
            canvas.write_text(1, 0, self.sparkline(canvas.width), DEFAULT_STYLE)
        if self.error:
            canvas.write_text(
                canvas.height - 1,
                0,
                f"! {self.last_error}"[: canvas.width],
                Style(fg=RGB(230, 70, 70)),
            )


class DashboardGrid(Container):
    """Places arbitrary widgets on a ``rows`` x ``cols`` grid that adapts to the grid's size.

    ``add_widget(widget, row, col, rowspan, colspan)`` positions and sizes the widget to its cells;
    resizing the grid re-lays everything out. ``layout_spec()`` returns a JSON-friendly description
    of the placement (widget names and cells) for saving.
    """

    def __init__(
        self,
        x: int = 0,
        y: int = 0,
        width: int = 80,
        height: int = 24,
        *,
        rows: int = 2,
        cols: int = 2,
        gap: int = 1,
        name: WidgetId | None = None,
    ) -> None:
        super().__init__(x, y, width, height, name=name)
        if rows < 1 or cols < 1:
            raise ValueError("rows and cols must be >= 1")
        if gap < 0:
            raise ValueError("gap must be >= 0")
        self.rows, self.cols, self.gap = rows, cols, gap
        self._cells: dict[int, tuple[int, int, int, int]] = {}

    def add_widget(
        self, widget: Widget, row: int, col: int, rowspan: int = 1, colspan: int = 1
    ) -> Widget:
        if rowspan < 1 or colspan < 1:
            raise ValueError("rowspan and colspan must be >= 1")
        if not (
            row >= 0 and row + rowspan <= self.rows and col >= 0 and col + colspan <= self.cols
        ):
            raise ValueError("widget does not fit inside the grid")
        for r, c, rs, cs in self._cells.values():
            if row < r + rs and r < row + rowspan and col < c + cs and c < col + colspan:
                raise ValueError("cells are already occupied")
        self.add(widget)
        self._cells[id(widget)] = (row, col, rowspan, colspan)
        self._place(widget)
        return widget

    def remove_widget(self, widget: Widget) -> None:
        self.remove(widget)
        self._cells.pop(id(widget), None)

    def _place(self, widget: Widget) -> None:
        row, col, rowspan, colspan = self._cells[id(widget)]
        cw = max(1, (self.width - self.gap * (self.cols - 1)) // self.cols)
        ch = max(1, (self.height - self.gap * (self.rows - 1)) // self.rows)
        widget.move(col * (cw + self.gap), row * (ch + self.gap))
        widget.resize(
            cw * colspan + self.gap * (colspan - 1), ch * rowspan + self.gap * (rowspan - 1)
        )

    def resize(self, width: int, height: int) -> None:
        super().resize(width, height)
        for child in self.children:
            if id(child) in self._cells:
                self._place(child)

    def layout_spec(self) -> dict[str, object]:
        return {
            "rows": self.rows,
            "cols": self.cols,
            "gap": self.gap,
            "cells": [
                {"widget": str(w.name), "row": r, "col": c, "rowspan": rs, "colspan": cs}
                for w in self.children
                if (cell := self._cells.get(id(w))) is not None
                for r, c, rs, cs in [cell]
            ],
        }
