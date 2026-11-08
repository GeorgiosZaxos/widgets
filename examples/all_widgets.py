"""Live tour of the display, progress and audio widgets, including every newer mode.

python examples/all_widgets.py        n / p = next / previous page, q = quit
(The data and network widgets have their own tours: data_gallery.py and net_gallery.py.)
"""

from __future__ import annotations

from collections.abc import Callable

from widgets import (
    AnimatedText,
    Box,
    CalendarWidget,
    Gauge,
    Marquee,
    MatrixRain,
    Neon,
    NotificationCenter,
    NotificationType,
    Spinner,
    VerticalPrint,
)
from widgets.audio.player import Equalizer
from widgets.base_elements.events import Event, KeyEvent
from widgets.base_elements.layout import Container, Screen
from widgets.base_elements.widget_types import Style
from widgets.display.calendar import ClockWidget
from widgets.display.effects_widgets import create_banner
from widgets.display.space import SpaceCrawlWidget
from widgets.progress.indicators import CircularIndicator, HorizontalBar, VerticalBar
from widgets.progress.state import ProgressState
from widgets.render.run import run_app

Label = Callable[[], object]


def label(text: str, y: int) -> Marquee:
    return Marquee(2, y, 100, 1, text=text, speed=1, style=Style(dim=True), reduced_motion=True)


def text_effects() -> list[object]:
    return [
        label("Neon: palette + big font + outline", 0),
        Neon(2, 1, 60, 5, text="NEON", palette="rainbow", font="original-5", outline=True),
        label("Sign banner", 7),
        _at(create_banner("HELLO", width=44, mode="neon"), 2, 8),
        label("Marquee: snake / diagonal", 18),
        Marquee(2, 19, 30, 4, text="snake!", direction="snake", speed=14),
        Marquee(36, 19, 30, 4, text="diagonal", direction="diagonal", speed=6),
    ]


def matrix() -> list[object]:
    return [
        label("Matrix: rain+reveal | vt typing | encrypted", 0),
        MatrixRain(2, 1, 34, 12, text="WAKE UP", mode="reveal", reveal_after=1.0, seed=1),
        MatrixRain(
            38, 1, 34, 12, text="login: neo\npassword: ****\naccess granted", mode="vt", speed=10
        ),
        MatrixRain(74, 1, 30, 12, text="SECRET MESSAGE", mode="encrypted", reveal_after=2, seed=3),
        AnimatedText(2, 15, 40, 3, text="wavy text", mode="wave"),
        Spinner(2, 19, 24, spinner="dots", text="working"),
    ]


def progress() -> list[object]:
    def state(n: float) -> ProgressState:
        s = ProgressState(100, description="demo")
        s.update(n)
        return s

    bars: list[object] = [
        label("Horizontal bar_format | circular | vertical fills + animation", 0),
        HorizontalBar(
            state(60), 60, bar_format="{desc} {percentage:3.0f}%|{bar}| {n_fmt}/{total_fmt}"
        ),
        CircularIndicator(state(75), 7),
    ]
    for i, (fill, anim) in enumerate(
        [("bottom-up", "none"), ("top-down", "pulse"), ("center-out", "scan"), ("edges-in", "none")]
    ):
        bars.append(VerticalBar(state(70), 10, orientation=fill, animate=anim))
        bars[-1].move(4 + i * 4, 6)  # type: ignore[attr-defined]
        bars.append(label(fill, 17))
    return bars


def misc() -> list[object]:
    center = NotificationCenter(2, 12, 40, 3)
    center.post("File saved", NotificationType.SUCCESS)
    center.post("Disk almost full", NotificationType.WARNING)
    return [
        label("Box | Gauge | Vertical print | Clock | Notifications", 0),
        Box(2, 1, 26, 5, text="Hello, widgets", align="center", valign="middle", border="rounded"),
        Gauge(30, 1, 21, 10, kind="speedometer", value=72, title="CPU", unit="%"),
        VerticalPrint(54, 1, 5, 8, text="VERT", border="single"),
        ClockWidget(2, 7, font="original-5"),
        center,
        CalendarWidget(62, 1),
    ]


def space_audio() -> list[object]:
    return [
        SpaceCrawlWidget(
            0,
            0,
            90,
            20,
            intro="Long ago, in a quiet corner\nof the network...",
            intro_time=3,
            loop=True,
            seed=2,
        ),
        label("Equalizer (simulated levels; see spectrum_demo.py for real FFT)", 21),
        Equalizer(2, 22, 60, 6, bands=24),
    ]


def _at(widget: object, x: int, y: int) -> object:
    widget.move(x, y)  # type: ignore[attr-defined]
    return widget


PAGES = [text_effects, matrix, progress, misc, space_audio]


def main() -> None:
    screen = Screen(110, 32)
    state = {"page": 0}
    current: list[Container] = []

    def show(index: int, live: bool = True) -> None:
        for old in current:
            screen.remove(old)
        current.clear()
        page = Container(0, 0, 110, 32, name=f"page{index}")
        for widget in PAGES[index]():
            page.add(widget)  # type: ignore[arg-type]
        page.add(label(f"page {index + 1}/{len(PAGES)}  n=next p=prev q=quit", 31))
        screen.add(page)
        current.append(page)
        if live:
            page.mount()
            page.start()

    def on_event(event: Event) -> bool:
        if isinstance(event, KeyEvent) and event.key in ("n", "p"):
            state["page"] = (state["page"] + (1 if event.key == "n" else -1)) % len(PAGES)
            show(state["page"])
            return True
        return False

    show(0, live=False)
    run_app(screen, on_event=on_event, quit_keys=("q",), title="widgets tour")


if __name__ == "__main__":
    main()
