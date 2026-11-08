"""Deterministic, thread-safe resource cleanup (FR-CLEAN-001..007). Layer L0."""

from __future__ import annotations

import itertools
import logging
import threading
from collections.abc import Callable
from dataclasses import dataclass
from typing import Protocol, runtime_checkable

logger = logging.getLogger(__name__)


@runtime_checkable
class SupportsClose(Protocol):
    """Protocol for objects with a ``close()`` method."""

    def close(self) -> object: ...


CleanupAction = Callable[[], object] | SupportsClose


@dataclass(frozen=True, slots=True)
class CleanupToken:
    """Handle returned by :meth:`CleanupManager.register`."""

    id: int


class CleanupManager:
    """Runs registered actions once, in reverse registration order.

    * Failures are logged and never prevent the remaining actions (FR-CLEAN-004).
    * ``cleanup()`` is idempotent and safe from any thread (FR-CLEAN-003/007).
    * Registering after ``cleanup()`` started runs the action immediately (FR-CLEAN-005).
    * Two racing ``cleanup()`` calls: the second returns at once while the first finishes the work.
    """

    def __init__(self, name: str = "cleanup") -> None:
        self._name = name
        self._lock = threading.Lock()
        self._ids = itertools.count(1)
        self._actions: dict[int, CleanupAction] = {}
        self._closed = False

    @property
    def closed(self) -> bool:
        return self._closed

    def __len__(self) -> int:
        with self._lock:
            return len(self._actions)

    def register(self, action: CleanupAction) -> CleanupToken:
        """Register a callable or an object with ``close()``; returns a cancellation token."""
        if not (callable(action) or callable(getattr(action, "close", None))):
            raise TypeError("cleanup action must be callable or have a close() method")
        with self._lock:
            token = CleanupToken(next(self._ids))
            if not self._closed:
                self._actions[token.id] = action
                return token
        self._run(action)
        return token

    def cancel(self, token: CleanupToken) -> bool:
        """Remove a pending action. ``False`` if it already ran, was cancelled or is unknown."""
        with self._lock:
            return self._actions.pop(token.id, None) is not None

    def cleanup(self) -> None:
        """Run all pending actions in reverse registration order (idempotent)."""
        with self._lock:
            if self._closed:
                return
            self._closed = True
        while True:
            with self._lock:
                if not self._actions:
                    return
                _, action = self._actions.popitem()  # LIFO == reverse registration order
            self._run(action)

    def _run(self, action: CleanupAction) -> None:
        try:
            if callable(action):
                action()
            else:
                action.close()
        except Exception:
            logger.exception("cleanup action %r failed in %s", action, self._name)

    def __enter__(self) -> CleanupManager:
        return self

    def __exit__(self, *exc_info: object) -> None:
        self.cleanup()
