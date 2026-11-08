"""Vertical print widget and helpers (FR-VPRINT-001..003). Layer L3."""

from __future__ import annotations

from widgets.assets.borders import get_border_style
from widgets.assets.fonts import Font, get_vertical_font, render_vertical
from widgets.base_elements.base import Widget
from widgets.base_elements.color_manager import Gradient, get_gradient
from widgets.base_elements.widget_types import DEFAULT_STYLE, Style, WidgetId
from widgets.display._common import aligned_col, char_style
from widgets.render.buffer import Canvas
from widgets.render.width import display_width


def vertical_text(text: str, direction: str = "down") -> list[str]:
    """One character per row; ``direction='up'`` reads bottom-to-top."""
    if direction not in ("down", "up"):
        raise ValueError("direction must be 'down' or 'up'")
    chars = list(text)
    return chars if direction == "down" else chars[::-1]


def countdown_text(seconds: float) -> str:
    """``MM:SS`` (or ``HH:MM:SS``) for a remaining time; negative values show zero."""
    total = max(0, int(seconds))
    h, rem = divmod(total, 3600)
    m, s = divmod(rem, 60)
    return f"{h:02d}:{m:02d}:{s:02d}" if h else f"{m:02d}:{s:02d}"


def loading_text(t: float, label: str = "Loading", dots: int = 3) -> str:
    """Return ``label`` followed by up to ``dots`` animated dots for time ``t``."""
    return label + "." * (int(t * 3) % (dots + 1))


def clock_text(hours: int, minutes: int, seconds: int | None = None) -> str:
    """Return ``HH:MM`` (or ``HH:MM:SS``) text for the given time of day."""
    base = f"{hours:02d}:{minutes:02d}"
    return base if seconds is None else f"{base}:{seconds:02d}"


def rainbow_text(text: str, shift: float = 0.0) -> list[tuple[str, Style]]:
    """``(char, style)`` pairs coloured with the rainbow gradient."""
    grad = get_gradient("rainbow")
    return [(ch, char_style(i, len(text), DEFAULT_STYLE, grad, shift)) for i, ch in enumerate(text)]


class VerticalPrint(Widget):
    """Text laid out top-to-bottom, plain or in a vertical large-character font."""

    def __init__(
        self,
        x: int = 0,
        y: int = 0,
        width: int = 5,
        height: int = 12,
        *,
        text: str = "",
        font: Font | str | None = None,
        direction: str = "down",
        spacing: int = 0,
        align: str = "left",
        style: Style = DEFAULT_STYLE,
        gradient: Gradient | None = None,
        border: str | None = None,
        padding: int = 0,
        ascii_only: bool = False,
        name: WidgetId | None = None,
    ) -> None:
        super().__init__(x, y, width, height, name=name)
        vertical_text("", direction)
        aligned_col(0, 1, align)
        if border is not None:
            get_border_style(border)
        self.text, self.direction, self.spacing, self.align = text, direction, spacing, align
        self.font = get_vertical_font(font) if isinstance(font, str) else font
        self.style, self.gradient, self.border, self.padding = style, gradient, border, padding
        self.ascii_only = ascii_only

    def rows(self) -> list[str]:
        src = self.text if self.direction == "down" else self.text[::-1]
        if self.font is not None:
            return render_vertical(src, self.font, spacing=self.spacing)
        out: list[str] = []
        for i, ch in enumerate(src):
            out.append(ch)
            if i < len(src) - 1:
                out.extend([""] * self.spacing)
        return out

    def render(self, canvas: Canvas) -> None:
        w, h = canvas.width, canvas.height
        inset = 1 if self.border else 0
        if self.border:
            tl, tr, bl, br, hc, vc = get_border_style(self.border).chars(self.ascii_only)
            for c in range(w):
                canvas.write_text(0, c, hc, self.style)
                canvas.write_text(h - 1, c, hc, self.style)
            for r in range(h):
                canvas.write_text(r, 0, vc, self.style)
                canvas.write_text(r, w - 1, vc, self.style)
            for r, c, g in ((0, 0, tl), (0, w - 1, tr), (h - 1, 0, bl), (h - 1, w - 1, br)):
                canvas.write_text(r, c, g, self.style)
        off = inset + self.padding
        rows = self.rows()
        for i, row in enumerate(rows):
            if off + i >= h - off:
                break
            st = char_style(i, len(rows), self.style, self.gradient)
            canvas.write_text(
                off + i, off + aligned_col(display_width(row), w - 2 * off, self.align), row, st
            )

    def describe(self) -> str:
        return f"VerticalPrint({self.direction}, {self.text[:30]!r})"
