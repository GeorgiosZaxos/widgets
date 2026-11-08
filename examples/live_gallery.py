"""Live, animated gallery of every widget in the library.

    python examples/live_gallery.py            # interactive (run in a real terminal)
    python examples/live_gallery.py --page 3   # start on a page
    python examples/live_gallery.py --duration 10   # auto-quit after 10 s (smoke test)

Keys: 1-6 or left/right switch pages | n new notification | arrows/PgUp/PgDn/Enter move in the
calendar (page 6) | q quits.  Options: --ascii for ASCII-only glyphs; set WIDGETS_REDUCED_MOTION=1
for the static, reduced-motion rendering.
In PyCharm enable "Emulate terminal in output console" for the run configuration.
"""

from __future__ import annotations

import argparse
import math
import sys
from pathlib import Path
from zoneinfo import ZoneInfoNotFoundError

sys.path.insert(0, str(Path(__file__).resolve().parent))

from pbar_demo import VerticalBank

from widgets import (
    AnimatedText,
    Box,
    CalendarWidget,
    ClockWidget,
    Countdown,
    Gauge,
    Marquee,
    MatrixRain,
    Neon,
    NotificationCenter,
    NotificationType,
    Sign,
    Spinner,
    SpinnerGroup,
    VerticalPrint,
)
from widgets.assets.spinners import list_spinners
from widgets.base_elements.base import Widget
from widgets.base_elements.events import Event, KeyEvent
from widgets.base_elements.layout import Container, Screen
from widgets.base_elements.widget_types import RGB, Style
from widgets.progress.indicators import HorizontalBar, VerticalBar
from widgets.progress.state import ProgressState
from widgets.render.buffer import Canvas
from widgets.render.run import run_app

W, H = 100, 32
PAGES = ["Boxes", "Marquees", "Matrix+Gauges", "Progress", "Spinners", "Notify+Cal"]
BAR = Style(fg=RGB(255, 255, 255), bg=RGB(40, 60, 140), bold=True)
DIM = Style(dim=True)
HEAD = Style(bold=True, fg=RGB(255, 200, 60))


class Label(Widget):
    def __init__(
        self, x: int, y: int, text: str, style: Style = DIM, width: int | None = None
    ) -> None:
        super().__init__(x, y, width or len(text), 1)
        self.text, self.style = text, style

    def render(self, canvas: Canvas) -> None:
        canvas.write_text(0, 0, self.text, self.style)


class Header(Widget):
    def __init__(self) -> None:
        super().__init__(0, 0, W, 1, name="header")
        self.page = 0

    def render(self, canvas: Canvas) -> None:
        tabs = "  ".join(
            f"[{i + 1}] {p}" if i == self.page else f" {i + 1}  {p}" for i, p in enumerate(PAGES)
        )
        canvas.write_text(0, 0, tabs.ljust(canvas.width), BAR)


class Footer(Widget):
    def __init__(self) -> None:
        super().__init__(0, H - 1, W, 1, name="footer")
        self.flags = ""

    def render(self, canvas: Canvas) -> None:
        text = f" 1-6 or ←/→ pages | n notify | q quit {self.flags}"
        canvas.write_text(0, 0, text.ljust(canvas.width), DIM)


class Driver(Widget):
    """Feeds changing values to gauges and progress states (time based)."""

    def __init__(self) -> None:
        super().__init__(0, 0, 0, 0, name="driver")
        self.t = 0.0
        self.gauges: list[Gauge] = []
        self.states: list[ProgressState] = []
        self.vstates: list[ProgressState] = []

    def update(self, dt: float) -> None:
        self.t += dt
        for i, g in enumerate(self.gauges):
            g.set_value(
                50 + 60 * math.sin(self.t * 0.7 + i)
            )  # deliberately overshoots to show clamping
        for i, s in enumerate(self.states):
            s.set(int((self.t * (8 + 6 * i)) % 101))
        for i, s in enumerate(self.vstates):
            s.set(int(50 + 50 * math.sin(self.t * 1.3 + i)))


def page(*children: Widget) -> Container:
    c = Container(0, 1, W, H - 2)
    for child in children:
        c.add(child)
    return c


def build(ascii_only: bool) -> tuple[Screen, list[Container], Header, Footer, dict[str, Widget]]:
    driver = Driver()
    ids: dict[str, Widget] = {}
    p1 = page(
        Label(2, 1, "Box (rounded, shadow, centered)", HEAD),
        Box(
            2,
            2,
            28,
            6,
            text="Hello, widgets!\nSecond line",
            align="center",
            valign="middle",
            border="rounded",
            shadow=(1, 1, "▒", DIM),
            ascii_only=ascii_only,
        ),
        Label(34, 1, "Box (double, wrapped, gradient)", HEAD),
        Box(
            34,
            2,
            30,
            6,
            text="Long text wraps inside the box and follows a gradient.",
            border="double",
            overflow="wrap",
            padding=1,
            ascii_only=ascii_only,
            gradient=__import__("widgets").get_gradient("sunset"),
        ),
        Label(68, 1, "Borders", HEAD),
        *[
            Box(68 + (i % 2) * 15, 2 + (i // 2) * 3, 14, 3, text=n, border=n, ascii_only=ascii_only)
            for i, n in enumerate(("single", "heavy", "ascii", "double-single"))
        ],
        Label(2, 10, "Sign (typewriter) / Sign (gradient-scroll) / Neon", HEAD),
        Sign(
            2,
            11,
            46,
            9,
            text="HELLO",
            mode="typewriter",
            border="double",
            speed=3,
            ascii_only=ascii_only,
        ),
        Sign(
            50,
            11,
            46,
            9,
            text="LIVE",
            mode="gradient-scroll",
            border="rounded",
            ascii_only=ascii_only,
        ),
        Neon(2, 22, 50, 1, text="N E O N   S I G N", colors=("#ff00ff", "#00ffff"), speed=0.4),
        Neon(
            2, 24, 60, 3, text="Neon wraps and cycles colours; flicker is rate limited.", wrap=True
        ),
    )
    p2 = page(
        Label(2, 1, "Marquee: left / right / bounce", HEAD),
        Marquee(2, 2, 60, 1, text="<<< scrolling left, looping forever >>>", speed=10),
        Marquee(2, 3, 60, 1, text="scrolling right, looping forever", direction="right", speed=10),
        Marquee(2, 4, 60, 1, text="bounce between edges", mode="bounce", speed=12),
        Label(2, 6, "Marquee up (multi-line) / large font", HEAD),
        Marquee(
            2,
            7,
            30,
            4,
            text="line one\nline two\nline three\nline four\nline five",
            direction="up",
            speed=2,
            gap=1,
        ),
        Marquee(36, 7, 60, 7, text="BIG SCROLL", font="original-7", speed=8),
        Label(2, 15, "AnimatedText modes", HEAD),
        *[
            AnimatedText(
                2 + (i % 2) * 48,
                16 + (i // 2) * 3,
                46,
                3,
                text="Animated text sample",
                mode=m,
                speed=8,
                duration=3.0,
                loop=True,
                seed=i + 1,
            )
            for i, m in enumerate(
                (
                    "typewriter",
                    "wave",
                    "scroll",
                    "bounce",
                    "fade-in",
                    "explode",
                    "dual-marquee",
                    "fade-out",
                )
            )
        ],
    )
    gauges = [
        Gauge(
            2 + i * 24,
            14,
            22,
            11,
            kind=k,
            title=k,
            unit="%",
            ascii_only=ascii_only,
            thresholds=((0, RGB(80, 200, 120)), (70, RGB(240, 190, 40)), (90, RGB(230, 70, 70))),
        )
        for i, k in enumerate(("circular", "speedometer", "semicircular", "thermometer"))
    ]
    driver.gauges = gauges
    p3 = page(
        Label(2, 1, "Matrix rain with text reveal", HEAD),
        MatrixRain(
            2,
            2,
            96,
            11,
            text="THE MATRIX HAS YOU",
            mode="reveal",
            seed=7,
            density=0.6,
            reveal_after=3.0,
            speed=12,
        ),
        Label(2, 13, "Gauges (values overshoot 0-100 on purpose: clamped + flagged)", HEAD),
        *gauges,
        Label(2, 26, "Vertical print", HEAD),
        VerticalPrint(2, 27, 3, 3, text="UPS", style=HEAD),
    )
    hstates = [
        ProgressState(100, description=f"{n:<8}")
        for n in ("smooth", "block", "shade", "line", "dots", "classic")
    ]
    driver.states = hstates
    vstates = [
        ProgressState(100, description=n)
        for n in ("eighths", "block", "shade", "line", "dots", "solid")
    ]
    driver.vstates = vstates
    vbars = [
        VerticalBar(
            st,
            height=10,
            style=s,
            orientation="top-down" if s in ("dots", "solid") else "bottom-up",
            ascii_only=ascii_only,
        )
        for st, s in zip(
            vstates, ("eighths", "block", "shade", "line", "dots", "solid"), strict=True
        )
    ]
    bank = VerticalBank(vbars, ["eighths", "block", "shade", "line", "dots", "solid"])
    bank.move(2, 14)
    p4 = page(
        Label(2, 1, "Horizontal bars (styles)", HEAD),
        *[
            _placed(HorizontalBar(st, width=90, style=s, ascii_only=ascii_only), 2, 2 + i)
            for i, (st, s) in enumerate(
                zip(hstates, ("smooth", "block", "shade", "line", "dots", "classic"), strict=True)
            )
        ],
        Label(2, 10, "Vertical bars", HEAD),
        Label(2, 12, "(top-down fill for dots/solid)", DIM),
        bank,
    )
    group = SpinnerGroup(2, 2, 30)
    names = [
        "line",
        "dots",
        "dots-ascii",
        "bar",
        "balloon",
        "arrow2",
        "clock",
        "moon",
        "bounce",
        "star",
        "toggle",
        "hamburger",
    ]
    names = [n for n in names if n in list_spinners()][:12]
    spinners = [
        Spinner(0, 0, 30, spinner=n, text=n, speed=10, ascii_only=ascii_only) for n in names
    ]
    for s in spinners:
        group.add(s)
    more = [
        Spinner(
            40 + (i % 3) * 20,
            2 + (i // 3),
            20,
            spinner=n,
            speed=12,
            text=n[:12],
            ascii_only=ascii_only,
        )
        for i, n in enumerate(list_spinners()[:30])
    ]
    p5 = page(
        Label(2, 1, "SpinnerGroup (non-overlapping rows)", HEAD),
        *spinners,
        Label(40, 1, f"First 30 of {len(list_spinners())} catalog spinners", HEAD),
        *more,
    )
    notify = NotificationCenter(
        2, 20, 60, 6, placement="bottom", default_duration=6.0, ascii_only=ascii_only
    )
    ids["notify"] = notify
    cal = CalendarWidget(2, 2)
    ids["cal"] = cal
    cd = Countdown(120, 40, 4)
    zones = ("UTC", "Europe/Athens", "America/New_York", "Asia/Tokyo")
    clocks: list[Widget] = []
    for i, tz in enumerate(zones):
        try:
            clocks.append(ClockWidget(40, 7 + i, tz=tz))
        except ZoneInfoNotFoundError:
            clocks.append(Label(40, 7 + i, "(pip install tzdata)"))
    p6 = page(
        Label(2, 1, "Calendar (arrows move, PgUp/PgDn change month, Enter selects)", HEAD),
        cal,
        Label(40, 2, "Countdown (2 min)", HEAD),
        cd,
        Label(40, 5, "Clocks", HEAD),
        *clocks,
        *[
            Label(52, 7 + i, tz)
            for i, tz in enumerate(("UTC", "Europe/Athens", "America/New_York", "Asia/Tokyo"))
        ],
        notify,
        Label(2, 19, "Notification centre (press n to post):", HEAD),
    )
    pages = [p1, p2, p3, p4, p5, p6]
    header, footer = Header(), Footer()
    screen = Screen(W, H)
    for p in pages:
        screen.add(p)
    screen.add(header)
    screen.add(footer)
    screen.add(driver)
    cal.on_select = lambda d: notify.post(f"Selected {d.isoformat()}", NotificationType.SUCCESS)
    cd.on_complete = lambda: notify.post("Countdown finished!", NotificationType.WARNING)
    return screen, pages, header, footer, ids


def _placed(widget: Widget, x: int, y: int) -> Widget:
    widget.move(x, y)
    return widget


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--page", type=int, default=1)
    parser.add_argument("--duration", type=float, default=None)
    parser.add_argument("--ascii", action="store_true")
    args = parser.parse_args()
    screen, pages, header, footer, ids = build(args.ascii)
    state = {"page": max(0, min(len(pages) - 1, args.page - 1)), "n": 0}
    kinds = list(NotificationType)

    def show(index: int) -> None:
        state["page"] = index % len(pages)
        for i, p in enumerate(pages):
            p.visible = i == state["page"]
        header.page = state["page"]

    show(state["page"])
    footer.flags = "(ascii)" if args.ascii else ""

    def on_event(event: Event) -> None:
        if not isinstance(event, KeyEvent):
            return
        if event.key.isdigit() and 1 <= int(event.key) <= len(pages):
            show(int(event.key) - 1)
        elif event.key == "right" and state["page"] != 5:
            show(state["page"] + 1)
        elif event.key == "left" and state["page"] != 5:
            show(state["page"] - 1)
        elif event.key == "n":
            kind = kinds[state["n"] % len(kinds)]
            state["n"] += 1
            ids["notify"].post(f"Example {kind.name.lower()} message #{state['n']}", kind)  # type: ignore[attr-defined]
        elif state["page"] == 5:
            ids["cal"].handle_key(event)

    run_app(
        screen,
        fps=30,
        duration=args.duration,
        quit_keys=("q", "ctrl+q"),
        on_event=on_event,
        title="widgets live gallery",
    )


if __name__ == "__main__":
    main()
