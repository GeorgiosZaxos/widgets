"""Chart widget: bar, line, pie, scatter, area (FR-CHART-001..005). Layer L3."""

from __future__ import annotations

import math
from dataclasses import dataclass, field

from widgets.base_elements.base import Widget
from widgets.base_elements.widget_types import DEFAULT_STYLE, RGB, Style, WidgetId
from widgets.render.buffer import Canvas

KINDS = ("bar", "line", "pie", "scatter", "area")
PALETTE = (
    RGB(86, 180, 233),
    RGB(230, 159, 0),
    RGB(0, 158, 115),
    RGB(204, 121, 167),
    RGB(240, 228, 66),
    RGB(213, 94, 0),
)
MARKS = ("●", "■", "▲", "◆", "○", "□")
ASCII_MARKS = ("*", "#", "+", "o", "x", "@")
MIN_WIDTH, MIN_HEIGHT = 16, 6


@dataclass(slots=True)
class Dataset:
    name: str
    values: list[float]
    labels: list[str] = field(default_factory=list)
    xs: list[float] = field(default_factory=list)
    visible: bool = True


def finite(v: object) -> bool:
    """True when ``v`` is a real, finite number (not a bool, NaN or infinity)."""
    return isinstance(v, int | float) and math.isfinite(v)


class Chart(Widget):
    """Chart of kind bar, line, pie, scatter or area drawn with text characters."""

    def __init__(
        self,
        x: int = 0,
        y: int = 0,
        width: int = 50,
        height: int = 14,
        *,
        kind: str = "bar",
        title: str = "",
        grid: bool = True,
        legend: bool = True,
        show_values: bool = False,
        ascii_only: bool = False,
        name: WidgetId | None = None,
    ) -> None:
        super().__init__(x, y, width, height, name=name)
        if kind not in KINDS:
            raise ValueError(f"kind must be one of {KINDS}")
        self.kind, self.title, self.grid, self.legend, self.show_values = (
            kind,
            title,
            grid,
            legend,
            show_values,
        )
        self.ascii_only = ascii_only
        self.datasets: list[Dataset] = []
        self.dirty = True

    def set_data(self, datasets: list[Dataset]) -> None:
        self.datasets = list(datasets)
        self.invalidate()

    def invalidate(self) -> None:
        self.dirty = True

    def toggle(self, name: str, visible: bool | None = None) -> None:
        for d in self.datasets:
            if d.name == name:
                d.visible = (not d.visible) if visible is None else visible
        self.invalidate()

    def _mark(self, i: int) -> str:
        return (ASCII_MARKS if self.ascii_only else MARKS)[i % len(MARKS)]

    def render(self, canvas: Canvas) -> None:
        self.dirty = False
        w, h = canvas.width, canvas.height
        if w < MIN_WIDTH or h < MIN_HEIGHT:
            canvas.write_text(0, 0, "too small"[:w], Style(dim=True))
            return
        shown = [(i, d) for i, d in enumerate(self.datasets) if d.visible]
        if not shown or all(not any(finite(v) for v in d.values) for _, d in shown):
            canvas.write_text(h // 2, max(0, (w - 7) // 2), "No data", Style(dim=True))
            return
        top = 0
        if self.title:
            canvas.write_text(
                0, max(0, (w - len(self.title)) // 2), self.title[:w], Style(bold=True)
            )
            top = 1
        bottom = h - (1 if self.legend else 0)
        if self.legend:
            x = 0
            for i, d in shown:
                text = f"{self._mark(i)} {d.name}  "
                canvas.write_text(h - 1, x, text[: w - x], Style(fg=PALETTE[i % len(PALETTE)]))
                x += len(text)
        if self.kind == "pie":
            self._pie(canvas, top, bottom, shown)
            return
        vals = [v for _, d in shown for v in d.values if finite(v)]
        lo, hi = min(0.0, float(min(vals))), float(max(vals))
        hi = hi if hi > lo else lo + 1
        label_w = max(len(f"{hi:g}"), len(f"{lo:g}")) + 1
        plot_h, plot_w = bottom - top - 1, w - label_w - 1
        if plot_h < 2 or plot_w < 2:
            canvas.write_text(0, 0, "too small"[:w], Style(dim=True))
            return

        def yrow(v: float) -> int:
            return top + plot_h - 1 - round((v - lo) / (hi - lo) * (plot_h - 1))

        for k in range(0, plot_h, max(1, plot_h // 4)):
            val = hi - (hi - lo) * k / max(1, plot_h - 1)
            canvas.write_text(top + k, 0, f"{val:g}".rjust(label_w - 1), Style(dim=True))
            if self.grid:
                canvas.write_text(
                    top + k, label_w, ("-" if self.ascii_only else "┈") * plot_w, Style(dim=True)
                )
        axis = "|" if self.ascii_only else "│"
        for r in range(top, top + plot_h):
            canvas.write_text(r, label_w - 1, axis, DEFAULT_STYLE)
        n = max(len(d.values) for _, d in shown)
        if self.kind == "scatter":
            xs_all = [float(x) for _, d in shown for x in (d.xs or range(len(d.values)))]
            xlo, xhi = min(xs_all), max(xs_all)
            xhi = xhi if xhi > xlo else xlo + 1
            for i, d in shown:
                for px, v in zip(d.xs or range(len(d.values)), d.values, strict=False):
                    if finite(v) and finite(px):
                        col = label_w + round((px - xlo) / (xhi - xlo) * (plot_w - 1))
                        canvas.write_text(
                            yrow(v), col, self._mark(i), Style(fg=PALETTE[i % len(PALETTE)])
                        )
            return
        group = max(1, plot_w // max(1, n))
        for j in range(n):
            base = label_w + j * group
            for si, (i, d) in enumerate(shown):
                if j >= len(d.values):
                    continue
                v = d.values[j]
                st = Style(fg=PALETTE[i % len(PALETTE)])
                if not finite(v):
                    canvas.write_text(
                        top + plot_h - 1, base + si, "?", Style(dim=True)
                    )  # placeholder for NaN/inf
                    continue
                col = base + (si if self.kind == "bar" else group // 2)
                if self.kind == "bar":
                    bar_w = max(1, group // (len(shown) + 1))
                    for r in range(yrow(v), top + plot_h):
                        canvas.write_text(r, col, ("#" if self.ascii_only else "█") * bar_w, st)
                else:
                    canvas.write_text(yrow(v), col, self._mark(i), st)
                    if self.kind == "area":
                        for r in range(yrow(v) + 1, top + plot_h):
                            canvas.write_text(r, col, "." if self.ascii_only else "░", st)
                if self.show_values:
                    canvas.write_text(max(top, yrow(v) - 1), col, f"{v:g}", Style(dim=True))
            if d.labels and j < len(d.labels):
                canvas.write_text(bottom - 1, base, d.labels[j][:group], Style(dim=True))

    def _pie(self, canvas: Canvas, top: int, bottom: int, shown: list[tuple[int, Dataset]]) -> None:
        d = shown[0][1]
        pairs = [
            (d.labels[k] if k < len(d.labels) else str(k + 1), v)
            for k, v in enumerate(d.values)
            if finite(v) and v > 0
        ]
        total = sum(v for _, v in pairs) or 1.0
        bar_w = canvas.width - 2
        col = 1
        for k, (_, v) in enumerate(pairs):
            n = max(1, round(v / total * bar_w))
            canvas.write_text(
                top + 1,
                col,
                self._mark(k) * min(n, bar_w - col + 1),
                Style(fg=PALETTE[k % len(PALETTE)]),
            )
            col += n
        for k, (label, v) in enumerate(pairs[: bottom - top - 3]):
            canvas.write_text(
                top + 3 + k,
                1,
                f"{self._mark(k)} {label}: {v:g} ({v / total:.0%})"[: canvas.width - 1],
                Style(fg=PALETTE[k % len(PALETTE)]),
            )

    def describe(self) -> str:
        return f"Chart({self.kind}, {len(self.datasets)} datasets)"
