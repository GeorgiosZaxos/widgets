"""Progress state and statistics (FR-PROG-001, 003, 004). Layer L2.

``ProgressState`` is a thread-safe counter with timing statistics. It knows nothing about
rendering; indicators and the manager read it.
"""

from __future__ import annotations

import threading
from collections.abc import Mapping

from widgets.base_elements.effects import Clock, MonotonicClock


def format_duration(seconds: float | None) -> str:
    """``M:SS`` / ``H:MM:SS``; ``"?"`` when unknown."""
    if seconds is None or seconds != seconds or seconds < 0 or seconds == float("inf"):
        return "?"
    whole = int(seconds + 0.5)
    hours, rest = divmod(whole, 3600)
    minutes, secs = divmod(rest, 60)
    return f"{hours}:{minutes:02d}:{secs:02d}" if hours else f"{minutes:02d}:{secs:02d}"


class ProgressState:
    """Counter + statistics for one task.

    ``update`` / ``set`` never let ``n`` go negative (``ValueError``). ``n`` may exceed ``total``;
    ``total`` is left as given and ``fraction`` is clamped to 1.0. Speed is an exponential
    moving average (``smoothing`` weights the newest sample, default 0.3).
    """

    def __init__(
        self,
        total: float | None = None,
        *,
        n: float = 0,
        description: str = "",
        smoothing: float = 0.3,
        stall_timeout: float = 10.0,
        clock: Clock | None = None,
    ) -> None:
        if total is not None and (isinstance(total, bool) or total < 0):
            raise ValueError(f"total must be >= 0 or None, got {total!r}")
        if n < 0:
            raise ValueError(f"n must be >= 0, got {n!r}")
        if not 0 < smoothing <= 1:
            raise ValueError(f"smoothing must be in (0, 1], got {smoothing!r}")
        if stall_timeout <= 0:
            raise ValueError(f"stall_timeout must be > 0, got {stall_timeout!r}")
        self._lock = threading.RLock()
        self._clock: Clock = MonotonicClock() if clock is None else clock
        self.total = total
        self.description = description
        self.smoothing = smoothing
        self.stall_timeout = stall_timeout
        self._n = n
        self._initial = n
        self._postfix: dict[str, object] = {}
        self._postfix_text = ""
        self._finished = False
        self._start = self._clock.now()
        self._last_update = self._start
        self._speed: float | None = None

    # -- counting -----------------------------------------------------------------------

    @property
    def n(self) -> float:
        return self._n

    @property
    def finished(self) -> bool:
        return self._finished

    def update(self, n: float = 1) -> None:
        """Advance by ``n`` (default 1)."""
        with self._lock:
            new = self._n + n
            if new < 0:
                raise ValueError(f"progress cannot become negative ({self._n!r} {n:+})")
            now = self._clock.now()
            if n > 0:
                dt = now - self._last_update
                if dt > 0:
                    sample = n / dt
                    self._speed = (
                        sample
                        if self._speed is None
                        else self.smoothing * sample + (1 - self.smoothing) * self._speed
                    )
                self._last_update = now
            self._n = new

    def set(self, n: float) -> None:
        """Set the absolute position."""
        with self._lock:
            if n < 0:
                raise ValueError(f"n must be >= 0, got {n!r}")
            self.update(n - self._n)

    def reset(self, total: float | None = None) -> None:
        """Start over (keeps the description); optionally with a new ``total``."""
        with self._lock:
            if total is not None:
                self.total = total
            self._n = self._initial = 0
            self._finished = False
            self._speed = None
            self._start = self._last_update = self._clock.now()

    def finish(self) -> None:
        """Mark complete: sets ``n`` to ``total`` when known."""
        with self._lock:
            if self.total is not None and self._n < self.total:
                self.update(self.total - self._n)
            self._finished = True

    def close(self) -> None:
        with self._lock:
            self._finished = True

    # -- text -----------------------------------------------------------------------------

    def set_postfix(self, text: str | None = None, **kwargs: object) -> None:
        """Extra info shown after the bar: free text and/or ``key=value`` pairs."""
        with self._lock:
            self._postfix_text = "" if text is None else str(text)
            self._postfix = dict(kwargs)

    @property
    def postfix(self) -> str:
        with self._lock:
            parts = [self._postfix_text] if self._postfix_text else []
            parts.extend(f"{key}={value}" for key, value in self._postfix.items())
            return ", ".join(parts)

    # -- statistics -------------------------------------------------------------------------

    @property
    def elapsed(self) -> float:
        return max(0.0, self._clock.now() - self._start)

    @property
    def speed(self) -> float | None:
        """Smoothed items per second, or ``None`` before two updates were seen."""
        return self._speed

    @property
    def fraction(self) -> float | None:
        """``n / total`` clamped to ``[0, 1]``; ``None`` for an unknown/zero total."""
        total = self.total
        if total is None or total <= 0:
            return None
        return min(1.0, self._n / total)

    @property
    def eta(self) -> float | None:
        total = self.total
        speed = self._speed
        if total is None or speed is None or speed <= 0:
            return None
        return max(0.0, total - self._n) / speed

    @property
    def stalled(self) -> bool:
        """True when no update arrived for longer than ``stall_timeout`` (and not finished)."""
        return not self._finished and self._clock.now() - self._last_update > self.stall_timeout

    def snapshot(self) -> Mapping[str, object]:
        with self._lock:
            return {
                "n": self._n,
                "total": self.total,
                "fraction": self.fraction,
                "elapsed": self.elapsed,
                "speed": self._speed,
                "eta": self.eta,
                "stalled": self.stalled,
            }
