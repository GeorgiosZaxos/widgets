"""Run blocking work off the UI thread; results are applied on the UI thread (D-04)."""

from __future__ import annotations

import queue
import threading
from collections.abc import Callable


class Jobs:
    def __init__(self) -> None:
        self._results: queue.SimpleQueue[Callable[[], None]] = queue.SimpleQueue()
        self._threads: list[threading.Thread] = []
        self._closed = False

    def submit(
        self, work: Callable[[], object], done: Callable[[object, BaseException | None], None]
    ) -> None:
        if self._closed:
            return

        def run() -> None:
            try:
                value, error = work(), None
            except BaseException as exc:
                value, error = None, exc
            self._results.put(lambda: done(value, error))

        thread = threading.Thread(target=run, daemon=True, name="widgets-net")
        self._threads = [t for t in self._threads if t.is_alive()] + [thread]
        thread.start()

    def drain(self) -> int:
        """Apply finished jobs; call from ``update`` (UI thread)."""
        n = 0
        while True:
            try:
                apply = self._results.get_nowait()
            except queue.Empty:
                return n
            apply()
            n += 1

    @property
    def busy(self) -> bool:
        return any(t.is_alive() for t in self._threads) or not self._results.empty()

    def close(self) -> None:
        self._closed = True
        for t in self._threads:
            t.join(timeout=1.0)
