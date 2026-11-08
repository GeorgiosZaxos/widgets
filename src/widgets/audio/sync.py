"""Run visual widgets alongside audio (FR-AUDIO-007, 008). Layer L3."""

from __future__ import annotations

import contextlib
import logging
from collections.abc import Callable, Sequence
from pathlib import Path
from types import TracebackType

from widgets.audio.backend import AudioBackend
from widgets.base_elements.base import Widget
from widgets.base_elements.lifecycle import LifecycleState
from widgets.errors import AudioBackendError

logger = logging.getLogger(__name__)


class SynchronizedPlayer:
    """Starts, pauses and stops an audio backend and a set of visual widgets together.

    * ``start`` loads and plays the file, then starts the visuals; if the audio fails, the visuals
      are not left half-started.
    * ``update(dt)`` must be called regularly (e.g. from the app loop): it ends the session when
      ``duration`` elapsed, the audio finished, or any visual was stopped/closed - so stopping
      either side stops the other.
    * ``stop`` always attempts every cleanup step and re-raises the first error afterwards.
    """

    def __init__(
        self,
        backend: AudioBackend,
        visuals: Sequence[Widget] = (),
        *,
        duration: float | None = None,
        drive_visuals: bool = False,
        on_finish: Callable[[], object] | None = None,
    ) -> None:
        if duration is not None and duration <= 0:
            raise ValueError("duration must be > 0")
        self.backend = backend
        self.visuals = list(visuals)
        self.duration = duration
        self.drive_visuals = drive_visuals
        self.on_finish = on_finish
        self.state = "idle"  # idle | playing | paused | finished
        self.elapsed = 0.0
        self.error: Exception | None = None

    @property
    def running(self) -> bool:
        return self.state in ("playing", "paused")

    def start(self, path: str | Path) -> None:
        if self.running:
            raise RuntimeError("already started; call stop() first")
        self.elapsed, self.error = 0.0, None
        try:
            self.backend.load(path)
            self.backend.play()
        except Exception:
            self.state = "idle"
            self._stop_visuals()
            raise
        self.state = "playing"
        for v in self.visuals:
            if v.state is LifecycleState.CREATED:
                v.mount()
            if v.state in (LifecycleState.MOUNTED, LifecycleState.STOPPED):
                v.start()
            elif v.state is LifecycleState.PAUSED:
                v.resume()

    def pause(self) -> None:
        if self.state != "playing":
            return
        self.backend.pause()  # may raise if unsupported: visuals keep running then
        self.state = "paused"
        for v in self.visuals:
            if v.state is LifecycleState.RUNNING:
                v.pause()

    def resume(self) -> None:
        if self.state != "paused":
            return
        self.backend.resume()
        self.state = "playing"
        for v in self.visuals:
            if v.state is LifecycleState.PAUSED:
                v.resume()

    def _stop_visuals(self) -> list[Exception]:
        errors: list[Exception] = []
        for v in self.visuals:
            try:
                if v.state in (LifecycleState.RUNNING, LifecycleState.PAUSED):
                    v.stop()
            except Exception as exc:
                logger.exception("visual %s failed to stop", v)
                errors.append(exc)
        return errors

    def stop(self) -> None:
        if self.state in ("idle", "finished"):
            return
        self.state = "finished"
        errors = self._stop_visuals()
        try:
            self.backend.stop()
        except Exception as exc:
            logger.exception("audio backend failed to stop")
            errors.append(exc)
        if self.on_finish is not None:
            try:
                self.on_finish()
            except Exception:
                logger.exception("on_finish callback raised")
        if errors:
            self.error = errors[0]
            raise errors[0]

    def update(self, dt: float) -> None:
        if not self.running:
            return
        if self.state == "playing":
            self.elapsed += dt
            if self.drive_visuals:
                for v in self.visuals:
                    v.tick(dt)
        if self.duration is not None and self.elapsed >= self.duration:
            return self._end()
        if any(v.state in (LifecycleState.STOPPED, LifecycleState.CLOSED) for v in self.visuals):
            return self._end()
        try:
            total = self.backend.duration()
            if total is not None and self.backend.position() >= total:
                return self._end()
        except AudioBackendError as exc:
            self.error = exc
            return self._end()

    def _end(self) -> None:
        with contextlib.suppress(Exception):  # recorded in ``error``
            self.stop()

    def close(self) -> None:
        """Stop everything and release the backend, even if stopping fails."""
        errors: list[Exception] = []
        try:
            self.stop()
        except Exception as exc:
            errors.append(exc)
        try:
            self.backend.close()
        except Exception as exc:
            errors.append(exc)
        if errors:
            raise errors[0]

    def __enter__(self) -> SynchronizedPlayer:
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        self.close()
