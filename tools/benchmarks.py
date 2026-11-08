"""Benchmarks for the NFR-PERF targets.  Usage: ``python tools/benchmarks.py [--json]``.

Targets (provisional, SRS section 12): unchanged 200x60 diff < 5 ms, full 200x60 frame < 16 ms,
``import widgets`` < 100 ms.
"""

from __future__ import annotations

import json
import statistics
import subprocess
import sys
import time
from collections.abc import Callable

from widgets.base_elements.layout import Screen
from widgets.base_elements.widget_types import Cell, Style
from widgets.data.chart import Chart, Dataset
from widgets.data.table import Table
from widgets.display.box import Box
from widgets.display.marquee import Marquee
from widgets.display.spinner import Spinner
from widgets.render.buffer import Buffer
from widgets.render.diff import diff_buffers

W, H = 200, 60


def best_of(fn: Callable[[], object], runs: int = 20) -> float:
    """Median wall time of ``fn`` in milliseconds."""
    times = []
    for _ in range(runs):
        t = time.perf_counter()
        fn()
        times.append((time.perf_counter() - t) * 1000)
    return statistics.median(times)


def import_ms() -> float:
    code = "import time; t=time.perf_counter(); import widgets; print((time.perf_counter()-t)*1000)"
    out = [
        float(subprocess.check_output([sys.executable, "-c", code], text=True)) for _ in range(5)
    ]
    return statistics.median(out)


def build_screen() -> Screen:
    screen = Screen(W, H)
    table = Table(0, 0, 100, 30)
    table.load_csv("a,b,c\n" + "\n".join(f"{i},{i * 2},row{i}" for i in range(200)))
    chart = Chart(100, 0, 100, 30, kind="bar")
    chart.set_data([Dataset("d", [float(i % 17) for i in range(24)])])
    screen.add(table)
    screen.add(chart)
    screen.add(Box(0, 30, 100, 30, border="double", overflow="wrap", text="lorem ipsum " * 200))
    screen.add(Marquee(100, 30, 100, 1, text="marquee " * 30))
    screen.add(Spinner(100, 32, 40, spinner="dots", text="working"))
    screen.mount()
    screen.start()
    return screen


def run() -> dict[str, float]:
    a, b = Buffer(W, H), Buffer(W, H)
    unchanged = best_of(lambda: diff_buffers(a, b))
    for i in range(0, W * H, 100):  # 1 % of the cells
        b.set_cell(i // W, i % W, Cell("x", Style(bold=True)))
    changed = best_of(lambda: diff_buffers(a, b))
    screen = build_screen()
    buf = Buffer(W, H)

    def frame() -> None:
        screen.tick(1 / 30)
        screen.draw(buf)

    return {
        "diff_unchanged_200x60_ms": round(unchanged, 3),
        "diff_1pct_changed_ms": round(changed, 3),
        "frame_200x60_ms": round(best_of(frame, 30), 3),
        "import_widgets_ms": round(import_ms(), 1),
    }


if __name__ == "__main__":
    result = run()
    if "--json" in sys.argv:
        print(json.dumps(result, indent=2))
    else:
        for k, v in result.items():
            print(f"{k:28} {v}")
