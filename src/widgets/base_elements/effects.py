"""Shared effects engine: clock, easing, seeded RNG, flash limiter, reduced motion (FR-FX-*). Layer L2.

Every animated widget uses this module (decision D-10) so timing, randomness and accessibility
policy behave identically across the library.
"""

from __future__ import annotations

import math
import os
import random
import time
from collections import deque
from collections.abc import Callable, Mapping
from typing import Protocol


class Clock(Protocol):
    """Injectable monotonic clock (FR-FX-003)."""

    def now(self) -> float:
        """Monotonic time in seconds."""
        ...

    def sleep(self, seconds: float) -> None: ...


class MonotonicClock:
    """The real clock."""

    def now(self) -> float:
        return time.monotonic()

    def sleep(self, seconds: float) -> None:
        if seconds > 0:
            time.sleep(seconds)


class ManualClock:
    """Deterministic clock for tests: ``sleep`` simply advances time."""

    def __init__(self, start: float = 0.0) -> None:
        self._time = start
        self.sleeps: list[float] = []

    def now(self) -> float:
        return self._time

    def advance(self, seconds: float) -> None:
        self._time += seconds

    def sleep(self, seconds: float) -> None:
        self.sleeps.append(seconds)
        self._time += max(0.0, seconds)


# ---------------------------------------------------------------------------
# Easing (FR-FX-002) - definitions follow easings.net
# ---------------------------------------------------------------------------


def _linear(t: float) -> float:
    return t


def _ease_in(t: float) -> float:
    return t * t


def _ease_out(t: float) -> float:
    return 1 - (1 - t) ** 2


def _ease_in_out(t: float) -> float:
    return 2 * t * t if t < 0.5 else 1 - (-2 * t + 2) ** 2 / 2


def _bounce(t: float) -> float:
    n1, d1 = 7.5625, 2.75
    if t < 1 / d1:
        return n1 * t * t
    if t < 2 / d1:
        t -= 1.5 / d1
        return n1 * t * t + 0.75
    if t < 2.5 / d1:
        t -= 2.25 / d1
        return n1 * t * t + 0.9375
    t -= 2.625 / d1
    return n1 * t * t + 0.984375


def _elastic(t: float) -> float:
    if t == 0:
        return 0.0
    if t == 1:
        return 1.0
    c4 = (2 * math.pi) / 3
    return 2 ** (-10 * t) * math.sin((t * 10 - 0.75) * c4) + 1


EASINGS: Mapping[str, Callable[[float], float]] = {
    "linear": _linear,
    "ease_in": _ease_in,
    "ease_out": _ease_out,
    "ease_in_out": _ease_in_out,
    "bounce": _bounce,
    "elastic": _elastic,
}


def ease(name: str, t: float) -> float:
    """Apply easing ``name`` to ``t`` (clamped to ``[0, 1]``).

    ``f(0) == 0`` and ``f(1) == 1`` for every easing; ``elastic`` (and, slightly, ``bounce``)
    may overshoot in between by design.
    """
    try:
        function = EASINGS[name]
    except KeyError:
        raise ValueError(f"unknown easing {name!r}; available: {sorted(EASINGS)}") from None
    if math.isnan(t):
        raise ValueError("t must not be NaN")
    return function(min(1.0, max(0.0, t)))


# ---------------------------------------------------------------------------
# Randomness (FR-FX-004)
# ---------------------------------------------------------------------------


def make_rng(seed: int | None = None) -> random.Random:
    """A private RNG; the same ``seed`` always produces the same sequence."""
    return random.Random(seed)


# ---------------------------------------------------------------------------
# Photosensitivity and reduced motion (FR-FX-005, FR-FX-006)
# ---------------------------------------------------------------------------


class FlashLimiter:
    """Allows at most ``max_per_second`` large-area flashes in any rolling second.

    A *flash* is a light/dark transition covering more than ``area_threshold`` of the screen
    (WCAG 2.3.1 derived: at most 3 per second, area above 25%).
    """

    def __init__(self, max_per_second: int = 3, area_threshold: float = 0.25) -> None:
        if max_per_second < 1:
            raise ValueError("max_per_second must be >= 1")
        if not 0.0 <= area_threshold <= 1.0:
            raise ValueError("area_threshold must be in [0, 1]")
        self._max = max_per_second
        self._threshold = area_threshold
        self._times: deque[float] = deque()

    def allow(self, now: float, area_fraction: float = 1.0) -> bool:
        """Whether a flash covering ``area_fraction`` of the screen may happen at ``now``."""
        if area_fraction <= self._threshold:
            return True
        while self._times and now - self._times[0] >= 1.0:
            self._times.popleft()
        if len(self._times) >= self._max:
            return False
        self._times.append(now)
        return True


def reduced_motion_enabled(
    env: Mapping[str, str] | None = None, override: bool | None = None
) -> bool:
    """``override`` if given, else ``WIDGETS_REDUCED_MOTION=1`` in the environment."""
    if override is not None:
        return override
    environment = os.environ if env is None else env
    return environment.get("WIDGETS_REDUCED_MOTION") == "1"


# ---------------------------------------------------------------------------
# Parameter validation (FR-FX-007)
# ---------------------------------------------------------------------------


def require_positive(name: str, value: float) -> float:
    """Return ``value`` if it is > 0, else raise ``ValueError`` naming ``name``."""
    if isinstance(value, bool) or not isinstance(value, int | float) or not value > 0:
        raise ValueError(f"{name} must be a number > 0, got {value!r}")
    return float(value)


def require_non_negative(name: str, value: float) -> float:
    """Return ``value`` if it is >= 0, else raise ``ValueError`` naming ``name``."""
    if isinstance(value, bool) or not isinstance(value, int | float) or not value >= 0:
        raise ValueError(f"{name} must be a number >= 0, got {value!r}")
    return float(value)


def require_fraction(name: str, value: float) -> float:
    """Return ``value`` if it is within [0, 1], else raise ``ValueError`` naming ``name``."""
    if isinstance(value, bool) or not isinstance(value, int | float) or not 0.0 <= value <= 1.0:
        raise ValueError(f"{name} must be a number in [0, 1], got {value!r}")
    return float(value)


# ---------------------------------------------------------------------------
# Audio-driven timing (FR-ANIM-007)
# ---------------------------------------------------------------------------


class BeatSource(Protocol):
    """Anything that can report beat/event timestamps since the previous call."""

    def poll(self) -> list[float]: ...


class BeatSync:
    """Turns a :class:`BeatSource` into step counts; falls back to time-driven when it is silent.

    ``active`` is True only while the source delivered events within ``timeout`` seconds of
    animation time. A source that raises is treated as unavailable (never propagates).
    """

    def __init__(self, source: BeatSource | None = None, timeout: float = 1.0) -> None:
        self.source = source
        self.timeout = require_positive("timeout", timeout)
        self.active = False
        self.last_error: Exception | None = None
        self._silent = 0.0

    def set_source(self, source: BeatSource | None) -> None:
        self.source = source
        self.active = False
        self._silent = 0.0
        self.last_error = None

    def poll(self, dt: float) -> int:
        """Number of beats since the last call; updates ``active``."""
        if self.source is None:
            self.active = False
            return 0
        try:
            beats = len(self.source.poll())
        except Exception as exc:
            self.last_error, self.active, self._silent = exc, False, 0.0
            return 0
        if beats:
            self._silent, self.active = 0.0, True
        else:
            self._silent += dt
            if self._silent >= self.timeout:
                self.active = False
        return beats
