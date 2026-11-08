"""Static gallery of the M4 widgets: renders each at a fixed time and prints it.

python examples/m4_gallery.py [seconds]
"""

from __future__ import annotations

import sys

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
    Sign,
    Spinner,
    VerticalPrint,
)
from widgets.render.buffer import Buffer


def show(title: str, widget: object, width: int, height: int, t: float) -> None:
    buf = Buffer(width, height)
    widget.mount()  # type: ignore[attr-defined]
    widget.start()  # type: ignore[attr-defined]
    widget.update(t)  # type: ignore[attr-defined]
    widget.draw(buf)  # type: ignore[attr-defined]
    print(f"== {title}")
    print("\n".join(line.rstrip() for line in buf.to_lines()))
    print()


def main() -> None:
    t = float(sys.argv[1]) if len(sys.argv) > 1 else 1.5
    show(
        "Box",
        Box(0, 0, 26, 5, text="Hello, widgets", align="center", valign="middle", border="rounded"),
        26,
        5,
        t,
    )
    show("Spinner", Spinner(0, 0, 20, spinner="dots", text="working"), 20, 1, t)
    show("Marquee", Marquee(0, 0, 24, 1, text="  breaking news  ", speed=6), 24, 1, t)
    show("AnimatedText (wave)", AnimatedText(0, 0, 24, 3, text="wavy text", mode="wave"), 24, 3, t)
    show("Sign", Sign(0, 0, 40, 9, text="Hi", border="double"), 40, 9, t)
    show("Neon", Neon(0, 0, 20, 1, text="NEON"), 20, 1, t)
    show(
        "Matrix",
        MatrixRain(
            0, 0, 30, 6, text="WAKE UP", mode="reveal", seed=1, density=0.7, reveal_after=0.5
        ),
        30,
        6,
        t + 2,
    )
    show("Vertical print", VerticalPrint(0, 0, 5, 8, text="VERT", border="single"), 5, 8, t)
    show(
        "Gauge", Gauge(0, 0, 21, 10, kind="speedometer", value=72, title="CPU", unit="%"), 21, 10, t
    )
    center = NotificationCenter(0, 0, 36, 3)
    center.post("File saved", NotificationType.SUCCESS)
    center.post("Disk almost full", NotificationType.WARNING)
    show("Notifications", center, 36, 3, t)
    show("Calendar", CalendarWidget(), 20, 8, t)


if __name__ == "__main__":
    main()
