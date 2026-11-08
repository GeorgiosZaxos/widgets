"""Gauge widget: circular, speedometer, semicircular, thermometer (FR-GAUGE-001..003). Layer L3."""

from __future__ import annotations

import math

from widgets.base_elements.base import Widget
from widgets.base_elements.color_manager import Gradient
from widgets.base_elements.widget_types import DEFAULT_STYLE, RGB, Style, WidgetId
from widgets.render.buffer import Canvas

GAUGE_STYLES = ("circular", "speedometer", "semicircular", "thermometer")


class Gauge(Widget):
    """Gauge showing a value inside a range, with optional gradient and label."""

    def __init__(
        self,
        x: int = 0,
        y: int = 0,
        width: int = 15,
        height: int = 8,
        *,
        kind: str = "semicircular",
        value: float = 0.0,
        minimum: float = 0.0,
        maximum: float = 100.0,
        title: str = "",
        unit: str = "",
        thresholds: tuple[tuple[float, RGB], ...] = (),
        gradient: Gradient | None = None,
        ticks: int = 0,
        ascii_only: bool = False,
        name: WidgetId | None = None,
    ) -> None:
        super().__init__(x, y, width, height, name=name)
        if kind not in GAUGE_STYLES:
            raise ValueError(f"kind must be one of {GAUGE_STYLES}")
        if not minimum < maximum:
            raise ValueError(f"minimum ({minimum}) must be less than maximum ({maximum})")
        self.kind, self.minimum, self.maximum, self.title, self.unit = (
            kind,
            minimum,
            maximum,
            title,
            unit,
        )
        self.thresholds, self.gradient, self.ticks, self.ascii_only = (
            tuple(sorted(thresholds, key=lambda t: t[0])),
            gradient,
            ticks,
            ascii_only,
        )
        self._value = minimum
        self.out_of_range = False
        self.set_value(value)

    @property
    def value(self) -> float:
        return self._value

    def set_value(self, value: float) -> None:
        if math.isnan(value):
            raise ValueError("value must not be NaN")
        self.out_of_range = not self.minimum <= value <= self.maximum
        self._value = min(self.maximum, max(self.minimum, value))

    @property
    def fraction(self) -> float:
        return (self._value - self.minimum) / (self.maximum - self.minimum)

    def text(self) -> str:
        """Text form of the value (FR-ACC-001)."""
        flag = " (out of range)" if self.out_of_range else ""
        label = f"{self.title}: " if self.title else ""
        return f"{label}{self._value:g}{self.unit} of {self.minimum:g}-{self.maximum:g}{self.unit}{flag}"

    def colour(self) -> RGB | None:
        if self.gradient is not None:
            return self.gradient.at(self.fraction)
        chosen = None
        for limit, rgb in self.thresholds:
            if self._value >= limit:
                chosen = rgb
        return chosen

    def _cells(self) -> list[tuple[float, float]]:
        """Arc positions ``(dx, dy)`` in a unit circle, ordered along the gauge direction."""
        n = max(8, self.width * 2)
        if self.kind == "circular":
            return [
                (math.sin(2 * math.pi * i / n), -math.cos(2 * math.pi * i / n)) for i in range(n)
            ]
        return [
            (-math.cos(math.pi * i / (n - 1)), -math.sin(math.pi * i / (n - 1))) for i in range(n)
        ]

    def render(self, canvas: Canvas) -> None:
        w, h = canvas.width, canvas.height
        fill_g, empty_g = ("#", ".") if self.ascii_only else ("█", "░")
        rgb = self.colour()
        fs = Style(fg=rgb) if rgb else DEFAULT_STYLE
        top = 0
        if self.title:
            canvas.write_text(
                0, max(0, (w - len(self.title)) // 2), self.title[:w], Style(bold=True)
            )
            top = 1
        label = f"{self._value:g}{self.unit}"
        if self.kind == "thermometer":
            bar_h = max(1, h - top - 1)
            filled = round(self.fraction * bar_h)
            cx = w // 2
            for r in range(bar_h):
                on = (bar_h - 1 - r) < filled
                canvas.write_text(
                    top + r, cx, fill_g if on else empty_g, fs if on else DEFAULT_STYLE
                )
            canvas.write_text(top + bar_h, max(0, cx - len(label) // 2), label[:w], DEFAULT_STYLE)
            return
        avail_h = h - top - 1
        radius_y = max(1, avail_h - 1) if self.kind != "circular" else max(1, (avail_h - 1) // 2)
        radius_x = max(1, min((w - 1) // 2, radius_y * 2))
        cx = w // 2
        cy = top + radius_y
        cells = self._cells()
        filled = round(self.fraction * len(cells))
        seen: dict[tuple[int, int], int] = {}
        for i, (dx, dy) in enumerate(cells):
            col, row = (
                round(cx + dx * radius_x),
                round(cy + dy * radius_y),
            )
            seen.setdefault((row, col), i)
        for (row, col), i in seen.items():
            on = i < filled
            canvas.write_text(row, col, fill_g if on else empty_g, fs if on else DEFAULT_STYLE)
        if self.kind == "speedometer":
            ang = math.pi * (1 - self.fraction)
            nx, ny = math.cos(ang), -math.sin(ang)
            for step in range(1, radius_y):
                canvas.write_text(
                    round(cy + ny * step),
                    round(cx + nx * step * 2),
                    "*" if self.ascii_only else "•",
                    fs,
                )
        canvas.write_text(
            min(h - 1, cy + (1 if self.kind != "circular" else 0)),
            max(0, cx - len(label) // 2),
            label[:w],
            Style(bold=True),
        )
        if self.kind != "circular":
            lo, hi = f"{self.minimum:g}", f"{self.maximum:g}"
            canvas.write_text(min(h - 1, cy + 1), 0, lo[:w], DEFAULT_STYLE)
            canvas.write_text(min(h - 1, cy + 1), max(0, w - len(hi)), hi, DEFAULT_STYLE)

    def describe(self) -> str:
        return f"Gauge({self.kind}, {self.text()})"
