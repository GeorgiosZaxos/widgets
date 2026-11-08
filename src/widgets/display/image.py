"""Pixel image and QR viewers using half-block characters. Layer L3."""

from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path

from widgets.base_elements.base import Widget
from widgets.base_elements.import_helper import require_import
from widgets.base_elements.widget_types import RGB, Style, WidgetId
from widgets.render.buffer import Canvas

Pixels = Sequence[Sequence[RGB]]


class ImageView(Widget):
    """Draws an RGB pixel grid; two pixel rows per terminal row (``▀`` fg=top, bg=bottom)."""

    def __init__(
        self, x: int = 0, y: int = 0, *, pixels: Pixels, name: WidgetId | None = None
    ) -> None:
        rows = [list(r) for r in pixels]
        width = max((len(r) for r in rows), default=0)
        super().__init__(x, y, width, (len(rows) + 1) // 2, name=name)
        self.pixels = rows

    @classmethod
    def gradient(cls, width: int = 40, height: int = 16, x: int = 0, y: int = 0) -> ImageView:
        """A built-in test image (hue across, brightness down)."""
        import colorsys

        pixels = [
            [
                RGB(
                    *(
                        round(c * 255)
                        for c in colorsys.hsv_to_rgb(
                            c / max(1, width), 1.0, 1 - 0.7 * r / max(1, height)
                        )
                    )
                )
                for c in range(width)
            ]
            for r in range(height)
        ]
        return cls(x, y, pixels=pixels)

    @classmethod
    def from_file(cls, path: str | Path, max_width: int = 60, x: int = 0, y: int = 0) -> ImageView:
        """Load an image with Pillow (``pip install pillow``) scaled to ``max_width`` columns."""
        image_mod = require_import("PIL.Image", feature="ImageView.from_file", extra="images")
        with image_mod.open(path) as img:
            rgb = img.convert("RGB")
            scale = min(1.0, max_width / rgb.width)
            rgb = rgb.resize((max(1, int(rgb.width * scale)), max(1, int(rgb.height * scale))))
            data = list(rgb.getdata())
            return cls(
                x,
                y,
                pixels=[
                    [RGB(*data[r * rgb.width + c]) for c in range(rgb.width)]
                    for r in range(rgb.height)
                ],
            )

    def render(self, canvas: Canvas) -> None:
        for r in range(min(canvas.height, (len(self.pixels) + 1) // 2)):
            top = self.pixels[2 * r]
            bottom = self.pixels[2 * r + 1] if 2 * r + 1 < len(self.pixels) else None
            for c in range(min(canvas.width, len(top))):
                bg = bottom[c] if bottom is not None and c < len(bottom) else None
                canvas.write_text(r, c, "▀", Style(fg=top[c], bg=bg))


class QrView(ImageView):
    """A QR code for ``text`` (needs ``pip install qrcode``), black on white with a quiet zone."""

    def __init__(
        self, x: int = 0, y: int = 0, *, text: str, border: int = 2, name: WidgetId | None = None
    ) -> None:
        qr = require_import("qrcode", feature="QrView", extra="images")
        code = qr.QRCode(border=0)
        code.add_data(text)
        code.make(fit=True)
        matrix = code.get_matrix()
        size = len(matrix) + 2 * border
        white, black = RGB(255, 255, 255), RGB(0, 0, 0)
        pixels = [[white] * size for _ in range(size)]
        for r, row in enumerate(matrix):
            for c, on in enumerate(row):
                if on:
                    pixels[r + border][c + border] = black
        super().__init__(x, y, pixels=pixels, name=name)
        self.text = text


__all__ = ["ImageView", "QrView"]
