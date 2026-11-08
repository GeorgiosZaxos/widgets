"""Step progress, sparkline and heatmap. Layer L3."""

from __future__ import annotations

from collections import deque
from collections.abc import Iterable, Sequence

from widgets.base_elements.base import Widget
from widgets.base_elements.color_manager import Gradient, get_gradient
from widgets.base_elements.widget_types import RGB, Style, WidgetId
from widgets.render.buffer import Canvas
from widgets.render.width import display_width

DONE = Style(fg=RGB(80, 220, 120))
ACTIVE = Style(fg=RGB(90, 170, 255), bold=True)
FAILED = Style(fg=RGB(240, 80, 80), bold=True)
PENDING = Style(dim=True)
BLOCKS = " ▁▂▃▄▅▆▇█"
ASCII_BLOCKS = " ._-=+*#@"


class Stepper(Widget):
    """``● Fetch ─ ◉ Build ─ ○ Test`` with done, active, failed and pending states.

    Symbols differ as well as colours, so status never depends on colour alone.
    """

    def __init__(
        self,
        x: int = 0,
        y: int = 0,
        width: int = 60,
        *,
        steps: Sequence[str],
        current: int = 0,
        ascii_only: bool = False,
        name: WidgetId | None = None,
    ) -> None:
        super().__init__(x, y, width, 2, name=name)
        if not steps:
            raise ValueError("steps must not be empty")
        self.steps = list(steps)
        self.current = max(0, min(len(steps), current))
        self.failed: set[int] = set()
        self.ascii_only = ascii_only

    def advance(self) -> None:
        self.current = min(len(self.steps), self.current + 1)

    def fail(self) -> None:
        if self.current < len(self.steps):
            self.failed.add(self.current)

    def reset(self) -> None:
        self.current = 0
        self.failed.clear()

    @property
    def finished(self) -> bool:
        return self.current >= len(self.steps) and not self.failed

    def step_state(self, i: int) -> str:
        if i in self.failed:
            return "failed"
        if i < self.current:
            return "done"
        return "active" if i == self.current else "pending"

    def render(self, canvas: Canvas) -> None:
        marks = {
            "done": ("v" if self.ascii_only else "●", DONE),
            "active": (">" if self.ascii_only else "◉", ACTIVE),
            "failed": ("x" if self.ascii_only else "✖", FAILED),
            "pending": ("o" if self.ascii_only else "○", PENDING),
        }
        col = 0
        for i, title in enumerate(self.steps):
            mark, style = marks[self.step_state(i)]
            col += canvas.write_text(0, col, mark + " " + title, style)
            if i < len(self.steps) - 1:
                col += canvas.write_text(0, col, " ── " if not self.ascii_only else " -- ", PENDING)
        label = f"step {min(self.current + 1, len(self.steps))}/{len(self.steps)}"
        canvas.write_text(1, 0, label + (" (failed)" if self.failed else ""), PENDING)


class Sparkline(Widget):
    """A one-row history chart using block characters."""

    def __init__(
        self,
        x: int = 0,
        y: int = 0,
        width: int = 30,
        *,
        values: Iterable[float] = (),
        maximum: float | None = None,
        gradient: Gradient | str | None = None,
        ascii_only: bool = False,
        name: WidgetId | None = None,
    ) -> None:
        super().__init__(x, y, width, 1, name=name)
        self.values: deque[float] = deque(values, maxlen=max(1, width))
        self.maximum = maximum
        self.gradient = get_gradient(gradient) if isinstance(gradient, str) else gradient
        self.ascii_only = ascii_only

    def push(self, value: float) -> None:
        self.values.append(float(value))

    def on_resize(self, width: int, height: int) -> None:
        self.values = deque(self.values, maxlen=max(1, width))
        super().on_resize(width, height)

    def text(self) -> str:
        glyphs = ASCII_BLOCKS if self.ascii_only else BLOCKS
        if not self.values:
            return ""
        top = self.maximum if self.maximum is not None else max(self.values)
        top = top if top > 0 else 1.0
        return "".join(
            glyphs[max(0, min(len(glyphs) - 1, round(v / top * (len(glyphs) - 1))))]
            for v in self.values
        )

    def render(self, canvas: Canvas) -> None:
        text = self.text()
        top = self.maximum if self.maximum is not None else max(self.values, default=1.0)
        for i, ch in enumerate(text[: canvas.width]):
            style = Style()
            if self.gradient is not None:
                style = Style(fg=self.gradient.at(min(1.0, self.values[i] / (top or 1.0))))
            canvas.write_text(0, i, ch, style)


class Heatmap(Widget):
    """A grid of coloured cells; each value maps through a gradient (two columns per cell)."""

    def __init__(
        self,
        x: int = 0,
        y: int = 0,
        *,
        data: Sequence[Sequence[float]],
        row_labels: Sequence[str] = (),
        gradient: Gradient | str = "heat",
        ascii_only: bool = False,
        name: WidgetId | None = None,
    ) -> None:
        rows = [list(r) for r in data]
        label_w = max((display_width(s) for s in row_labels), default=0)
        width = label_w + (1 if label_w else 0) + 2 * max((len(r) for r in rows), default=0)
        super().__init__(x, y, width, len(rows), name=name)
        self.data, self.row_labels, self.label_w = rows, list(row_labels), label_w
        self.gradient = get_gradient(gradient) if isinstance(gradient, str) else gradient
        self.ascii_only = ascii_only
        flat = [v for r in rows for v in r]
        self.lo, self.hi = (min(flat), max(flat)) if flat else (0.0, 1.0)

    def level(self, value: float) -> float:
        return 0.0 if self.hi == self.lo else (value - self.lo) / (self.hi - self.lo)

    def render(self, canvas: Canvas) -> None:
        for r, row in enumerate(self.data):
            col = 0
            if self.label_w:
                label = self.row_labels[r] if r < len(self.row_labels) else ""
                col += canvas.write_text(r, 0, label.ljust(self.label_w) + " ", Style(dim=True))
            for v in row:
                lvl = self.level(v)
                if self.ascii_only:
                    glyph = ASCII_BLOCKS[round(lvl * (len(ASCII_BLOCKS) - 1))] * 2
                    col += canvas.write_text(r, col, glyph, Style())
                else:
                    col += canvas.write_text(r, col, "██", Style(fg=self.gradient.at(lvl)))


__all__ = ["Heatmap", "Sparkline", "Stepper"]
