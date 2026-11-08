"""Gallery of every colour, gradient, palette and the 256-colour cube.

python examples/color_gallery.py            interactive: left/right = section, up/down/pgup/pgdn
                                            = scroll, q = quit
python examples/color_gallery.py --text     one-shot print using the detected colour mode
"""

from __future__ import annotations

import sys

from widgets.base_elements.color_manager import (
    ColorMode,
    apply_style,
    detect_color_mode,
    get_gradient,
    get_palette,
    index_to_rgb,
    list_colors,
    list_gradients,
    list_palettes,
    parse_color,
)
from widgets.base_elements.events import Event, KeyEvent
from widgets.base_elements.interactive import InteractiveWidget
from widgets.base_elements.layout import Screen
from widgets.base_elements.widget_types import RGB, Style
from widgets.render.buffer import Canvas
from widgets.render.run import run_app

SECTIONS = ("colours", "gradients", "palettes", "256-colour cube", "ramps")
WIDTH, HEIGHT = 110, 34


def rows_for(section: str, width: int) -> list[list[tuple[str, Style]]]:
    """Rows of ``(text, style)`` segments for one section."""
    rows: list[list[tuple[str, Style]]] = []
    if section == "colours":
        cell = 22
        names = list_colors()
        per_row = max(1, width // cell)
        for i in range(0, len(names), per_row):
            row: list[tuple[str, Style]] = []
            for name in names[i : i + per_row]:
                row.append(("██ ", Style(fg=parse_color(name))))
                row.append((name[: cell - 4].ljust(cell - 3), Style()))
            rows.append(row)
    elif section == "gradients":
        bar = 40
        for name in list_gradients():
            grad = get_gradient(name)
            row = [(name[:30].ljust(31), Style(dim=True))]
            row += [("█", Style(fg=grad.at(i / (bar - 1)))) for i in range(bar)]
            rows.append(row)
    elif section == "palettes":
        for name in list_palettes():
            colours = get_palette(name)
            row = [(name[:16].ljust(17), Style(dim=True))]
            row += [("██ ", Style(fg=c)) for c in colours[:32]]
            row.append((f" ({len(colours)})", Style(dim=True)))
            rows.append(row)
    elif section == "256-colour cube":
        rows.append([("standard + bright (0-15)", Style(dim=True))])
        rows.append([("  ", Style(bg=index_to_rgb(i))) for i in range(16)])
        for block in range(6):
            rows.append([(f"cube green row {block}", Style(dim=True))])
            for g in range(6):
                rows.append(
                    [
                        ("  ", Style(bg=index_to_rgb(16 + 36 * r + 6 * g + b)))
                        for r in range(6)
                        for b in range(6)
                    ]
                )
        rows.append([("greyscale (232-255)", Style(dim=True))])
        rows.append([("  ", Style(bg=index_to_rgb(i))) for i in range(232, 256)])
    else:
        rows.append([("hue ramp", Style(dim=True))])
        import colorsys

        hue = [
            (" ", Style(bg=RGB(*(round(c * 255) for c in colorsys.hsv_to_rgb(i / 96, 1, 1)))))
            for i in range(96)
        ]
        rows.append(hue)
        rows.append([("grey ramp", Style(dim=True))])
        rows.append(
            [(" ", Style(bg=RGB(i * 255 // 95, i * 255 // 95, i * 255 // 95))) for i in range(96)]
        )
        rows.append([("red / green / blue ramps", Style(dim=True))])
        for ch in range(3):
            rows.append(
                [
                    (" ", Style(bg=RGB(*(i * 255 // 95 if k == ch else 0 for k in range(3)))))
                    for i in range(96)
                ]
            )
    return rows


class ColorGallery(InteractiveWidget):
    def __init__(self, width: int = WIDTH, height: int = HEIGHT) -> None:
        super().__init__(0, 0, width, height)
        self.section = 0
        self.top = 0
        self.mode = detect_color_mode()
        self._cache: dict[int, list[list[tuple[str, Style]]]] = {}

    def rows(self) -> list[list[tuple[str, Style]]]:
        if self.section not in self._cache:
            self._cache[self.section] = rows_for(SECTIONS[self.section], self.width - 2)
        return self._cache[self.section]

    def handle_key(self, event: KeyEvent) -> bool:
        page = self.height - 3
        last = max(0, len(self.rows()) - page)
        key = event.key
        if key in ("left", "right", "n", "p"):
            step = 1 if key in ("right", "n") else -1
            self.section, self.top = (self.section + step) % len(SECTIONS), 0
            return True
        deltas = {"up": -1, "down": 1, "pageup": -page, "pagedown": page}
        if key in deltas:
            self.top = max(0, min(last, self.top + deltas[key]))
            return True
        return False

    def render(self, canvas: Canvas) -> None:
        title = "  ".join(f"[{s}]" if i == self.section else s for i, s in enumerate(SECTIONS))
        canvas.write_text(0, 0, title, Style(bold=True))
        info = f"detected colour mode: {self.mode.name} (set COLORTERM=truecolor for 24-bit)"
        canvas.write_text(1, 0, info, Style(dim=True))
        for r, row in enumerate(self.rows()[self.top : self.top + canvas.height - 3]):
            col = 1
            for text, style in row:
                col += canvas.write_text(r + 2, col, text, style)
        total = len(self.rows())
        canvas.write_text(
            canvas.height - 1,
            0,
            f"rows {self.top + 1}-{min(total, self.top + canvas.height - 3)}/{total}   left/right section   up/down scroll   q quit",
            Style(dim=True),
        )


def print_text() -> None:
    mode = detect_color_mode()
    print(f"colour mode: {mode.name}")
    for section in SECTIONS:
        print(f"\n== {section}")
        for row in rows_for(section, 100):
            print(
                "".join(
                    apply_style(text, style, mode) if mode is not ColorMode.NONE else text
                    for text, style in row
                )
            )


def main() -> None:
    if "--text" in sys.argv:
        print_text()
        return
    gallery = ColorGallery()
    screen = Screen(WIDTH, HEIGHT)
    screen.add(gallery)

    def on_event(event: Event) -> bool:
        return False

    run_app(screen, on_event=on_event, quit_keys=("q",), title="colour gallery")


if __name__ == "__main__":
    main()
