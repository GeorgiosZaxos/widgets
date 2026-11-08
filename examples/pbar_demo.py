"""Horizontal and vertical progress-bar demo.

    python examples/pbar_demo.py            # all parts
    python examples/pbar_demo.py --part horizontal|vertical|mixed
    python examples/pbar_demo.py --ascii    # ASCII-only glyphs (FR-ASSET-009)
    python examples/pbar_demo.py --fast     # shorter run

Bars are drawn on stderr in a region at the bottom of the output, so piping stdout is safe.
Without a terminal only plain-text progress lines are printed.
"""

from __future__ import annotations

import argparse
import math
import time

from widgets.assets.bars import list_bar_styles
from widgets.base_elements.color_manager import get_gradient
from widgets.base_elements.widget_types import Style
from widgets.progress.indicators import HorizontalBar, ProgressIndicator, VerticalBar
from widgets.progress.inline import ProgressManager
from widgets.progress.state import ProgressState
from widgets.render.buffer import Canvas


class VerticalBank(ProgressIndicator):
    """Several vertical bars side by side, each with a % row and a label row beneath it."""

    def __init__(self, bars: list[VerticalBar], labels: list[str], *, gap: int = 3) -> None:
        self._bars, self._labels, self._gap = bars, labels, gap
        self._cell = max(4, *(len(label) for label in labels))
        height = bars[0].height + 2
        width = len(bars) * self._cell + (len(bars) - 1) * gap
        super().__init__(bars[0].progress, width, height, ascii_only=bars[0].ascii_only)

    def plain_text(self) -> str:
        parts = []
        for bar, label in zip(self._bars, self._labels, strict=True):
            fraction = bar.progress.fraction or 0.0
            parts.append(f"{label} {int(fraction * 100)}%")
        return "  ".join(parts)

    def render(self, canvas: Canvas) -> None:
        gradient = get_gradient("fire")
        for index, (bar, label) in enumerate(zip(self._bars, self._labels, strict=True)):
            left = index * (self._cell + self._gap) + self._cell // 2
            fraction = bar.progress.fraction or 0.0
            style = Style(fg=gradient.at(fraction))
            for row, glyph in enumerate(bar.column()):
                canvas.write_text(row, left, glyph, style)
            pct = f"{int(fraction * 100):>3}%"
            canvas.write_text(
                bar.height, index * (self._cell + self._gap), pct.center(self._cell), Style()
            )
            canvas.write_text(
                bar.height + 1, index * (self._cell + self._gap), label.center(self._cell), Style()
            )


def horizontal(ascii_only: bool, steps: int) -> None:
    """One bar per style, each advancing at its own pace; log lines print above the bars."""
    names = [
        n
        for n in ("smooth", "block", "shade", "line", "dots", "squares", "classic", "arrow")
        if n in list_bar_styles("horizontal")
    ]
    with ProgressManager(ascii_only=ascii_only) as manager:
        states = [ProgressState(100, description=f"{n:<8}") for n in names]
        for state, name in zip(states, names, strict=True):
            manager.add(HorizontalBar(state, style=name, ascii_only=ascii_only, unit="MB"))
        indeterminate = ProgressState(None, description="unknown ")
        manager.add(HorizontalBar(indeterminate, style="smooth", ascii_only=ascii_only))
        for step in range(steps):
            for index, state in enumerate(states):
                if state.n < 100 and step % (index + 1) == 0:
                    state.update(1)
            indeterminate.update(1)
            if step == steps // 2:
                manager.write("-- half-way: the fast bars are already done --")
            manager.refresh()
            time.sleep(0.02)
        for state in states:
            state.set(100)
        indeterminate.finish()
        manager.refresh(force=True)


def vertical(ascii_only: bool, steps: int) -> None:
    """An 'equaliser' of six vertical bars in different styles and fill directions."""
    spec = [
        ("eighths", "bottom-up"),
        ("block", "bottom-up"),
        ("shade", "bottom-up"),
        ("line", "bottom-up"),
        ("dots", "top-down"),
        ("solid", "top-down"),
    ]
    spec = [(s, o) for s, o in spec if s in list_bar_styles("vertical")]
    with ProgressManager(ascii_only=ascii_only) as manager:
        states = [ProgressState(100, description=s) for s, _ in spec]
        bars = [
            VerticalBar(st, height=10, style=s, orientation=o, ascii_only=ascii_only)
            for st, (s, o) in zip(states, spec, strict=True)
        ]
        manager.add(VerticalBank(bars, [s for s, _ in spec]))
        for step in range(steps):
            for index, state in enumerate(states):
                target = (step + 1) / steps * 100
                wobble = 12 * math.sin(step / 6 + index) * (1 - step / steps)
                state.set(max(0, min(100, int(target + wobble))))
            manager.refresh()
            time.sleep(0.03)
        for state in states:
            state.set(100)
        manager.refresh(force=True)


def mixed(ascii_only: bool, steps: int) -> None:
    """A horizontal bar driving two vertical gauges (e.g. CPU and memory) at once."""
    with ProgressManager(ascii_only=ascii_only) as manager:
        job = ProgressState(steps, description="job")
        cpu, mem = ProgressState(100, description="cpu"), ProgressState(100, description="mem")
        manager.add(HorizontalBar(job, style="smooth", ascii_only=ascii_only, unit="step"))
        manager.add(
            VerticalBank(
                [
                    VerticalBar(cpu, height=6, style="eighths", ascii_only=ascii_only),
                    VerticalBar(
                        mem, height=6, style="block", orientation="top-down", ascii_only=ascii_only
                    ),
                ],
                ["cpu", "mem"],
            )
        )
        for step in range(steps):
            job.update(1)
            cpu.set(int(50 + 45 * math.sin(step / 5)))
            mem.set(int(30 + 60 * step / steps))
            manager.refresh()
            time.sleep(0.03)
        manager.refresh(force=True)


def main() -> None:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawTextHelpFormatter
    )
    parser.add_argument("--part", choices=("all", "horizontal", "vertical", "mixed"), default="all")
    parser.add_argument("--ascii", action="store_true", help="use ASCII-only glyphs")
    parser.add_argument("--fast", action="store_true", help="shorter run")
    args = parser.parse_args()
    steps = 60 if args.fast else 150
    if args.part in ("all", "horizontal"):
        horizontal(args.ascii, steps)
    if args.part in ("all", "vertical"):
        vertical(args.ascii, steps)
    if args.part in ("all", "mixed"):
        mixed(args.ascii, steps)


if __name__ == "__main__":
    main()
