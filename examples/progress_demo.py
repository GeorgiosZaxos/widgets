"""Progress demo: several bars, log lines printed above them, and a spinner.

    python examples/progress_demo.py

Output goes to stderr, so ``python examples/progress_demo.py 2>/dev/null`` shows no bars.
"""

from __future__ import annotations

import time

from widgets.progress.indicators import HorizontalBar, SpinnerIndicator
from widgets.progress.inline import ProgressManager
from widgets.progress.state import ProgressState
from widgets.progress.tqdm import tqdm, trange


def tqdm_demo() -> None:
    for i in trange(40, desc="tqdm-style"):
        time.sleep(0.03)
        if i == 20:
            tqdm.write("halfway there")


def manager_demo() -> None:
    with ProgressManager() as manager:
        download, unpack = (
            ProgressState(100, description="download"),
            ProgressState(60, description="unpack"),
        )
        manager.add(HorizontalBar(download, style="smooth", unit="MB"))
        manager.add(HorizontalBar(unpack, style="shade"))
        manager.add(SpinnerIndicator(spinner="dots", text="waiting for the server"), leave=False)
        for step in range(100):
            download.update()
            if step % 5 == 0:
                unpack.update()
            if step == 50:
                manager.write("download passed 50 %")
            manager.refresh()
            time.sleep(0.03)


if __name__ == "__main__":
    tqdm_demo()
    manager_demo()
