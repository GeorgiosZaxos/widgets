"""Widget lifecycle state machine (FR-LIFE-001..003). Layer L2.

``CREATED -> MOUNTED -> RUNNING <-> PAUSED -> STOPPED -> UNMOUNTED -> CLOSED``

* Repeating the operation that produced the current state is a no-op (returns ``False``).
* An operation that is illegal in the current state raises :class:`LifecycleError`.
* ``STOPPED -> RUNNING`` (restart) is allowed; ``close`` is allowed from any state.
"""

from __future__ import annotations

import enum
import threading

from widgets.errors import LifecycleError


class LifecycleState(enum.Enum):
    """States of the widget lifecycle (created, mounted, running, paused, stopped, closed)."""

    CREATED = "created"
    MOUNTED = "mounted"
    RUNNING = "running"
    PAUSED = "paused"
    STOPPED = "stopped"
    UNMOUNTED = "unmounted"
    CLOSED = "closed"


_S = LifecycleState

_RULES: dict[str, tuple[frozenset[LifecycleState], LifecycleState]] = {
    "mount": (frozenset({_S.CREATED}), _S.MOUNTED),
    "start": (frozenset({_S.MOUNTED, _S.STOPPED}), _S.RUNNING),
    "pause": (frozenset({_S.RUNNING}), _S.PAUSED),
    "resume": (frozenset({_S.PAUSED}), _S.RUNNING),
    "stop": (frozenset({_S.MOUNTED, _S.RUNNING, _S.PAUSED}), _S.STOPPED),
    "unmount": (frozenset({_S.MOUNTED, _S.STOPPED}), _S.UNMOUNTED),
}


class LifecycleMachine:
    """Holds one widget's state and validates transitions."""

    def __init__(self, label: str) -> None:
        self._label = label
        self._state = LifecycleState.CREATED
        self._lock = threading.RLock()

    @property
    def state(self) -> LifecycleState:
        return self._state

    def begin(self, operation: str) -> bool:
        """Commit ``operation``. True if the state changed, False if it was already in effect."""
        allowed, target = _RULES[operation]
        with self._lock:
            if self._state is target:
                return False
            if self._state not in allowed:
                raise LifecycleError(
                    f"{self._label}: cannot {operation}() while {self._state.value}"
                )
            self._state = target
            return True

    def mark_closed(self) -> bool:
        """Move to CLOSED from any state. False if it was already closed."""
        with self._lock:
            if self._state is LifecycleState.CLOSED:
                return False
            self._state = LifecycleState.CLOSED
            return True
