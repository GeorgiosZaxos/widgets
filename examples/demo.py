"""Interactive demo of the M0-M2 runtime: containers, focus, key events and time-based updates.

Run it in a real terminal (in PyCharm enable "Emulate terminal in output console"):

    python examples/demo.py

Keys: Tab / Shift+Tab move focus (the first Tab focuses the first checkbox), Space or Enter
toggles the focused checkbox, q quits.
"""

from __future__ import annotations

from widgets.base_elements.base import Widget
from widgets.base_elements.events import Event, KeyEvent
from widgets.base_elements.interactive import InteractiveWidget
from widgets.base_elements.layout import Container, Screen
from widgets.base_elements.widget_types import RGB, Style
from widgets.render.buffer import Canvas
from widgets.render.run import run_app

TITLE_STYLE = Style(fg=RGB(255, 255, 255), bg=RGB(40, 60, 140), bold=True)
FOCUS_STYLE = Style(reverse=True, bold=True)
MUTED_STYLE = Style(fg=RGB(150, 150, 150))


class Banner(Widget):
    """Text that scrolls from right to left and wraps around (time based, not frame based)."""

    def __init__(self, x: int, y: int, width: int, text: str, speed: float = 12.0) -> None:
        super().__init__(x, y, width, 1, name="banner")
        self._text = text + "   "
        self._speed = speed
        self._offset = 0.0

    def update(self, dt: float) -> None:
        self._offset = (self._offset + self._speed * dt) % len(self._text)

    def render(self, canvas: Canvas) -> None:
        start = int(self._offset)
        repeated = (self._text * (canvas.width // len(self._text) + 2))[
            start : start + canvas.width
        ]
        canvas.write_text(0, 0, repeated, Style(fg=RGB(255, 200, 60)))


class Checkbox(InteractiveWidget):
    """A focusable checkbox; focus is shown with reverse video (not by color alone)."""

    def __init__(self, x: int, y: int, label: str, name: str) -> None:
        super().__init__(x, y, len(label) + 4, 1, name=name)
        self.label = label
        self.checked = False

    def handle_key(self, event: KeyEvent) -> bool:
        if event.key in ("space", "enter"):
            self.checked = not self.checked
            return True
        return False

    def render(self, canvas: Canvas) -> None:
        mark = "x" if self.checked else " "
        style = FOCUS_STYLE if self.focused else Style()
        canvas.write_text(0, 0, f"[{mark}] {self.label}", style)


class StatusLine(Widget):
    def __init__(self, y: int, width: int) -> None:
        super().__init__(0, y, width, 1, name="status")
        self.message = "press a key"
        self.uptime = 0.0

    def update(self, dt: float) -> None:
        self.uptime += dt

    def render(self, canvas: Canvas) -> None:
        canvas.write_text(
            0, 0, f"{self.message}  |  up {self.uptime:5.1f}s  |  q quits", MUTED_STYLE
        )


def build_screen() -> tuple[Screen, StatusLine]:
    screen = Screen(80, 24)
    screen.add(Banner(0, 1, 80, "widgets: M0-M2 runtime demo - containers, focus, key events"))
    panel = screen.add(Container(2, 4, 40, 6, name="panel"))
    assert isinstance(panel, Container)
    for index, label in enumerate(("Enable logging", "Dark mode", "Verbose output")):
        panel.add(Checkbox(0, index, label, name=f"check-{index}"))
    status = StatusLine(22, 80)
    screen.add(status)
    return screen, status


class Title(Widget):
    def render(self, canvas: Canvas) -> None:
        canvas.write_text(0, 0, " widgets ".ljust(canvas.width), TITLE_STYLE)


def main() -> None:
    screen, status = build_screen()
    screen.add(Title(0, 0, 80, 1, name="title"))

    def on_event(event: Event) -> None:
        if isinstance(event, KeyEvent):
            status.message = f"last key: {event.combo}"

    run_app(screen, fps=30, quit_keys=("q", "ctrl+q"), on_event=on_event, title="widgets demo")


if __name__ == "__main__":
    main()
