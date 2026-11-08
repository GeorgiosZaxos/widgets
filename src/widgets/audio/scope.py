"""Oscilloscope / waveform view. Layer L4."""

from __future__ import annotations

import math
from collections.abc import Callable

from widgets.base_elements.widget_types import RGB, Style, WidgetId
from widgets.display._common import Animated
from widgets.render.buffer import Canvas

GREEN = RGB(90, 230, 140)
Source = Callable[[int], list[float] | None]


class Oscilloscope(Animated):
    """Plots samples (-1..1) as a braille trace; ``source(n)`` returns n samples or ``None``.

    Without a source (or when it returns ``None``) a labelled simulated waveform is drawn, so the
    widget never pretends to show real audio.
    """

    def __init__(
        self,
        x: int = 0,
        y: int = 0,
        width: int = 60,
        height: int = 8,
        *,
        source: Source | None = None,
        color: RGB = GREEN,
        reduced_motion: bool | None = None,
        name: WidgetId | None = None,
    ) -> None:
        super().__init__(x, y, width, height, reduced_motion=reduced_motion, name=name)
        self.source, self.color = source, color
        self.mode = "simulated"

    def samples(self, n: int) -> list[float]:
        real = self.source(n) if self.source is not None else None
        if real:
            self.mode = "live"
            return real[:n] + [0.0] * (n - len(real))
        self.mode = "simulated"
        phase = 0.0 if self.reduced_motion else self.t * 6
        return [
            0.6
            * math.sin(i / n * 6 * math.pi + phase)
            * math.sin(i / n * math.pi * 1.5 + phase / 4)
            for i in range(n)
        ]

    def render(self, canvas: Canvas) -> None:
        w, h = canvas.width, canvas.height
        dots_w, dots_h = w * 2, max(1, (h - 1) * 4)
        values = self.samples(dots_w)
        grid: dict[tuple[int, int], int] = {}
        bits = ((0x01, 0x08), (0x02, 0x10), (0x04, 0x20), (0x40, 0x80))
        for dx, value in enumerate(values):
            dy = round((1 - max(-1.0, min(1.0, value))) / 2 * (dots_h - 1))
            key = (dy // 4, dx // 2)
            grid[key] = grid.get(key, 0) | bits[dy % 4][dx % 2]
        for (row, col), mask in grid.items():
            if row < h - 1 and col < w:
                canvas.write_text(row, col, chr(0x2800 + mask), Style(fg=self.color))
        canvas.write_text(h - 1, 0, f"scope ({self.mode})", Style(dim=True))


__all__ = ["Oscilloscope"]
