"""Looks and layouts for the tqdm-compatible bars, horizontal (``tqdm``) and vertical (``vtqdm``).

    python examples/tqdm_mixed_demo.py            # all three scenes
    python examples/tqdm_mixed_demo.py looks      # spinners, gradients, colours, fill characters
    python examples/tqdm_mixed_demo.py h1v4       # 1 horizontal bar above 4 vertical bars
    python examples/tqdm_mixed_demo.py v1h4       # 1 vertical bar above 4 horizontal bars

Vertical bars share terminal rows (side by side); horizontal bars take one row each.
The look options (``spinner``, ``gradient``, ``colour``, ``fill``/``empty``, ``style``) are
keyword-only extras: code written for plain tqdm never passes them.
"""

from __future__ import annotations

import random
import sys
import time
from typing import Any

from widgets import tqdm, vtqdm

RAINBOW = ["#ff3b30", "#ff9500", "#ffcc00", "#34c759", "#0a84ff", "#bf5af2"]
FIRE = ["#7f0000", "#ff4500", "#ffd700"]
OCEAN = ["#001f3f", "#0074d9", "#7fdbff"]

LOOKS: list[tuple[str, dict[str, Any]]] = [
    ("plain", {}),
    ("colour", {"colour": "#ff66cc"}),
    ("gradient", {"gradient": RAINBOW}),
    ("fire", {"gradient": FIRE, "style": "block"}),
    ("spinner", {"spinner": "dots", "colour": "cyan"}),
    ("spin+grad", {"spinner": "line", "gradient": OCEAN}),
    ("fill = >", {"fill": "=", "empty": ".", "colour": "yellow"}),
    ("charset", {"ascii": " ▏▎▍▌▋▊▉█", "gradient": RAINBOW}),
    ("dots", {"style": "dots", "colour": "green"}),
]


def drive(bars: list[Any], steps: int = 100, delay: float = 0.02) -> None:
    """Advance every bar at its own pace until all are complete."""
    rng = random.Random(7)
    pace = [rng.uniform(0.3, 0.9) for _ in bars]  # chance of advancing on each tick
    done = [0] * len(bars)
    while any(d < steps for d in done):
        for i, bar in enumerate(bars):
            if done[i] < steps and rng.random() < pace[i]:
                done[i] += 1
                bar.update(1)
        time.sleep(delay)
    for bar in bars:
        bar.close()


def looks() -> None:
    print("\nHorizontal bars: spinners, gradients, colours and fill characters")
    drive([tqdm(total=100, desc=name, position=i, **kw) for i, (name, kw) in enumerate(LOOKS)])
    print("\nVertical bars, same options")
    drive(
        [
            vtqdm(total=100, desc=name, height=7, position=i, **kw)
            for i, (name, kw) in enumerate(LOOKS)
        ]
    )


def h1v4() -> None:
    print("\n1 horizontal bar above 4 vertical bars")
    bars: list[Any] = [
        tqdm(total=100, desc="overall", position=0, gradient=RAINBOW, spinner="dots", ncols=70)
    ]
    for i, (name, kw) in enumerate(LOOKS[2:6]):
        bars.append(vtqdm(total=100, desc=name, height=8, position=i + 1, **kw))
    drive(bars)


def v1h4() -> None:
    print("\n1 vertical bar above 4 horizontal bars")
    bars: list[Any] = [
        vtqdm(total=100, desc="overall", height=8, position=0, gradient=RAINBOW, spinner="dots")
    ]
    for i, (name, kw) in enumerate(LOOKS[2:6]):
        bars.append(tqdm(total=100, desc=name, position=i + 1, ncols=70, **kw))
    drive(bars)


SCENES = {"looks": looks, "h1v4": h1v4, "v1h4": v1h4}

if __name__ == "__main__":
    wanted = sys.argv[1:] or list(SCENES)
    for scene in wanted:
        SCENES[scene]()
    print("done")
