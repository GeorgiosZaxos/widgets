"""Box with border, text, padding, gradient and shadow (FR-BOX-001..003). Layer L3."""

from __future__ import annotations

import textwrap

from widgets.assets.borders import get_border_style
from widgets.base_elements.base import Widget
from widgets.base_elements.color_manager import Gradient
from widgets.base_elements.widget_types import DEFAULT_STYLE, Cell, Rect, Style, WidgetId
from widgets.display._common import aligned_col, char_style, clip_cells
from widgets.render.buffer import Canvas


class Box(Widget):
    """Bordered text box with alignment, padding and wrapping."""

    def __init__(
        self,
        x: int = 0,
        y: int = 0,
        width: int = 20,
        height: int = 5,
        *,
        text: str = "",
        border: str | None = "single",
        align: str = "left",
        valign: str = "top",
        padding: int | tuple[int, int, int, int] = 0,
        overflow: str = "truncate",
        style: Style = DEFAULT_STYLE,
        border_style: Style = DEFAULT_STYLE,
        gradient: Gradient | None = None,
        shadow: tuple[int, int, str, Style] | None = None,
        ascii_only: bool = False,
        name: WidgetId | None = None,
    ) -> None:
        super().__init__(x, y, width, height, name=name)
        if overflow not in ("truncate", "wrap"):
            raise ValueError("overflow must be 'truncate' or 'wrap'")
        if valign not in ("top", "middle", "bottom"):
            raise ValueError("valign must be top, middle or bottom")
        aligned_col(0, 1, align)
        if border is not None:
            get_border_style(border)
        self.text, self.border, self.align, self.valign = text, border, align, valign
        self.padding = (padding,) * 4 if isinstance(padding, int) else tuple(padding)
        self.overflow, self.style, self.border_style = overflow, style, border_style
        self.gradient, self.shadow, self.ascii_only = gradient, shadow, ascii_only

    def set_text(self, text: str) -> None:
        self.text = text

    def lines_for(self, width: int) -> list[str]:
        out: list[str] = []
        for line in self.text.split("\n"):
            if self.overflow == "wrap" and width > 0:
                out.extend(textwrap.wrap(line, width) or [""])
            else:
                out.append(clip_cells(line, width))
        return out

    def render(self, canvas: Canvas) -> None:
        w, h = canvas.width, canvas.height
        sdx = sdy = 0
        if self.shadow is not None:
            sdx, sdy = max(0, self.shadow[0]), max(0, self.shadow[1])
            glyph, sstyle = self.shadow[2], self.shadow[3]
            for row in range(h):
                for col in range(w):
                    if (col >= w - sdx or row >= h - sdy) and (row >= sdy and col >= sdx):
                        canvas.set_cell(row, col, Cell(glyph, sstyle))
            w, h = max(0, w - sdx), max(0, h - sdy)
        if w <= 0 or h <= 0:
            return
        canvas.fill(Rect(0, 0, w, h), Cell(" ", self.style))
        inset = 0
        if self.border is not None:
            tl, tr, bl, br, hch, vch = get_border_style(self.border).chars(self.ascii_only)
            bs = self.border_style
            for col in range(w):
                canvas.write_text(0, col, hch, bs)
                canvas.write_text(h - 1, col, hch, bs)
            for row in range(h):
                canvas.write_text(row, 0, vch, bs)
                canvas.write_text(row, w - 1, vch, bs)
            canvas.write_text(0, 0, tl, bs)
            canvas.write_text(0, w - 1, tr, bs)
            canvas.write_text(h - 1, 0, bl, bs)
            canvas.write_text(h - 1, w - 1, br, bs)
            inset = 1
        pt, pr, pb, pl = self.padding
        left, top = inset + pl, inset + pt
        iw, ih = w - 2 * inset - pl - pr, h - 2 * inset - pt - pb
        if iw <= 0 or ih <= 0 or not self.text:
            return
        lines = self.lines_for(iw)[:ih]
        first = (
            top
            + {"top": 0, "middle": (ih - len(lines)) // 2, "bottom": ih - len(lines)}[self.valign]
        )
        for i, line in enumerate(lines):
            col = left + aligned_col(len(line), iw, self.align)
            for k, ch in enumerate(line):
                canvas.write_text(
                    first + i, col + k, ch, char_style(k, len(line), self.style, self.gradient)
                )

    def describe(self) -> str:
        return f"Box({self.name!r}, {self.width}x{self.height}, border={self.border}, text={self.text[:30]!r})"
