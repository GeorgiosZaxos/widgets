"""One demo, three interchangeable progress libraries.

    python examples/tqdm_swap_demo.py            # widgets horizontal bar (default)
    python examples/tqdm_swap_demo.py vtqdm      # widgets vertical bar
    python examples/tqdm_swap_demo.py tqdm       # the real tqdm (if installed)

Only the import block below changes between libraries; everything after it is ordinary
tqdm code, which is the whole point of the compatibility layer.
"""

from __future__ import annotations

import logging
import sys
import time

choice = sys.argv[1] if len(sys.argv) > 1 else "widgets"

# ---- the only part that differs ------------------------------------------------------------
if choice == "tqdm":
    from tqdm import tqdm, trange
    from tqdm.contrib import tenumerate
    from tqdm.contrib.concurrent import thread_map
    from tqdm.contrib.logging import (
        logging_redirect_tqdm,
    )
elif choice == "vtqdm":
    from widgets import vtqdm as tqdm
    from widgets import vtrange as trange
    from widgets.progress.contrib import tenumerate
    from widgets.progress.contrib.concurrent import thread_map
    from widgets.progress.contrib.logging import logging_redirect_tqdm
else:
    from widgets import tqdm, trange
    from widgets.progress.contrib import tenumerate
    from widgets.progress.contrib.concurrent import thread_map
    from widgets.progress.contrib.logging import logging_redirect_tqdm
# ---------------------------------------------------------------------------------------------

log = logging.getLogger("demo")
logging.basicConfig(level=logging.INFO, format="%(message)s")


def work(delay: float = 0.02) -> None:
    time.sleep(delay)


def _job(x: int) -> int:
    work(0.02)
    return x


def main() -> None:
    print(f"== using: {choice} ==")

    for _ in tqdm(range(60), desc="basic loop"):
        work()

    for _ in trange(60, desc="trange", unit="step", colour="green"):
        work()

    with tqdm(total=100, desc="download", unit="B", unit_scale=True, unit_divisor=1024) as bar:
        for _ in range(10):
            work(0.05)
            bar.update(10 * 1024 * 1024 // 10)

    for i in tqdm(range(3), desc="outer"):
        for _ in tqdm(range(30), desc=f"inner {i}", leave=False):
            work(0.01)

    bar = tqdm(range(40), desc="postfix")
    for i in bar:
        bar.set_postfix(loss=round(1 / (i + 1), 3), ok=i % 2 == 0)
        if i == 20:
            tqdm.write("halfway there (tqdm.write keeps the bar intact)")
        work()
    bar.close()

    with logging_redirect_tqdm():
        for i in tqdm(range(20), desc="with logging"):
            if i % 10 == 0:
                log.info("log line at %d", i)
            work()

    for _i, _ch in tenumerate("abcdefgh", desc="tenumerate"):
        work(0.03)

    thread_map(_job, range(30), desc="thread_map")
    print("done")


if __name__ == "__main__":
    main()
