"""Audio backend Protocol and implementations (FR-AUDIO-006, 009, 011). Layer L3.

``NullBackend`` simulates playback with an injectable clock (tests, demos without a sound card).
``SubprocessBackend`` drives an external player with an *argument list* (``shell=False``,
NFR-SEC-005).  ``WinsoundBackend`` plays ``.wav`` through the Windows standard library.
No backend decodes PCM with ``audioop`` (removed in Python 3.13, D-13).
"""

from __future__ import annotations

import shutil
import subprocess
import sys
import time
import wave
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol

from widgets.errors import AudioBackendError, AudioUnavailableError, UnsupportedFormatError

MIDI_EXTENSIONS = frozenset({".mid", ".midi"})
COMMON_EXTENSIONS = frozenset({".wav", ".mp3", ".ogg", ".flac", ".m4a", ".aac", ".opus"})


@dataclass(frozen=True, slots=True)
class Capabilities:
    """What a backend can do; unsupported operations are disabled and reported by widgets."""

    extensions: frozenset[str] = COMMON_EXTENSIONS
    can_pause: bool = True
    can_seek: bool = False
    can_volume: bool = True
    has_levels: bool = False
    has_metadata: bool = False
    midi: bool = False

    def supported_extensions(self) -> frozenset[str]:
        return self.extensions | (MIDI_EXTENSIONS if self.midi else frozenset())


class AudioBackend(Protocol):
    """Protocol for audio playback backends (play, pause, resume, stop, volume, position)."""

    def capabilities(self) -> Capabilities: ...
    def load(self, path: str | Path) -> None: ...
    def play(self) -> None: ...
    def pause(self) -> None: ...
    def resume(self) -> None: ...
    def stop(self) -> None: ...
    def seek(self, seconds: float) -> None: ...
    def position(self) -> float: ...
    def duration(self) -> float | None: ...
    def set_volume(self, volume: float) -> None: ...
    def close(self) -> None: ...


def check_format(caps: Capabilities, path: str | Path) -> Path:
    """Reject files the backend cannot play (MIDI only when declared, FR-AUDIO-009)."""
    p = Path(path)
    ext = p.suffix.lower()
    if ext in MIDI_EXTENSIONS and not caps.midi:
        raise UnsupportedFormatError(f"MIDI playback is not supported by this backend: {p.name}")
    if ext not in caps.supported_extensions():
        raise UnsupportedFormatError(f"unsupported audio format {ext or '(none)'!r}: {p.name}")
    return p


class NullBackend:
    """Simulated playback. Time comes from ``clock``; nothing is audible.

    ``fail`` maps a method name to an exception raised by it (to test error paths).
    """

    def __init__(
        self,
        *,
        clock: Callable[[], float] = time.monotonic,
        default_duration: float | None = 30.0,
        durations: Mapping[str, float] | None = None,
        capabilities: Capabilities | None = None,
        metadata: Mapping[str, Mapping[str, str]] | None = None,
        fail: Mapping[str, Exception] | None = None,
        require_exists: bool = False,
    ) -> None:
        self._caps = capabilities or Capabilities(has_levels=True, has_metadata=True, can_seek=True)
        self._clock = clock
        self._default = default_duration
        self._durations = dict(durations or {})
        self._meta = {k: dict(v) for k, v in (metadata or {}).items()}
        self._fail = dict(fail or {})
        self._require_exists = require_exists
        self.path: Path | None = None
        self.state = "stopped"  # stopped | playing | paused | finished
        self.volume = 1.0
        self.closed = False
        self.calls: list[str] = []
        self._base = 0.0
        self._started = 0.0

    # -- helpers ---------------------------------------------------------------------------
    def _enter(self, name: str) -> None:
        self.calls.append(name)
        if self.closed and name != "close":
            raise AudioUnavailableError("backend is closed")
        exc = self._fail.get(name)
        if exc is not None:
            raise exc

    def capabilities(self) -> Capabilities:
        return self._caps

    def load(self, path: str | Path) -> None:
        self._enter("load")
        p = check_format(self._caps, path)
        if self._require_exists and not p.is_file():
            raise AudioBackendError(f"cannot read {p}")
        self.path, self.state, self._base = p, "stopped", 0.0

    def play(self) -> None:
        self._enter("play")
        if self.path is None:
            raise AudioBackendError("no file loaded")
        self._base, self._started, self.state = 0.0, self._clock(), "playing"

    def pause(self) -> None:
        self._enter("pause")
        if not self._caps.can_pause:
            raise UnsupportedFormatError("pause is not supported by this backend")
        if self.state == "playing":
            self._base = self.position()
            self.state = "paused"

    def resume(self) -> None:
        self._enter("resume")
        if self.state == "paused":
            self._started, self.state = self._clock(), "playing"

    def stop(self) -> None:
        self._enter("stop")
        self.state, self._base = "stopped", 0.0

    def seek(self, seconds: float) -> None:
        self._enter("seek")
        if not self._caps.can_seek:
            raise UnsupportedFormatError("seek is not supported by this backend")
        total = self.duration()
        self._base = max(0.0, seconds if total is None else min(seconds, total))
        self._started = self._clock()

    def position(self) -> float:
        if self.state == "playing":
            pos = self._base + (self._clock() - self._started)
            total = self.duration()
            if total is not None and pos >= total:
                self.state = "finished"
                self._base = total
                return total
            return pos
        return self._base

    def duration(self) -> float | None:
        if self.path is None:
            return None
        return self._durations.get(self.path.name, self._default)

    def set_volume(self, volume: float) -> None:
        self._enter("set_volume")
        if not 0.0 <= volume <= 1.0:
            raise ValueError("volume must be within 0..1")
        self.volume = volume

    def close(self) -> None:
        self._enter("close")
        self.closed, self.state = True, "stopped"

    # -- optional extras -------------------------------------------------------------------
    def levels(self, bands: int) -> list[float] | None:
        """Deterministic pseudo-spectrum in 0..1 while playing (simulated backend data)."""
        if not self._caps.has_levels or self.state != "playing":
            return None
        pos = self.position()
        out = []
        for i in range(bands):
            wave_ = abs(((pos * (1.3 + 0.37 * i) + i * 0.61) % 2.0) - 1.0)
            out.append(round(0.15 + 0.85 * wave_ * (1.0 - i / (2.0 * bands)), 4))
        return out

    def metadata(self) -> dict[str, str]:
        if self.path is None or not self._caps.has_metadata:
            return {}
        return dict(self._meta.get(self.path.name, {}))


class SubprocessBackend:
    """External command-line player started with an argument list (never a shell string)."""

    PLAYERS: tuple[tuple[str, tuple[str, ...]], ...] = (
        ("ffplay", ("-nodisp", "-autoexit", "-loglevel", "quiet")),
        ("mpv", ("--no-video", "--really-quiet")),
        ("mpg123", ("-q",)),
        ("afplay", ()),
        ("aplay", ("-q",)),
        ("paplay", ()),
    )

    def __init__(
        self,
        command: Sequence[str] | None = None,
        *,
        clock: Callable[[], float] = time.monotonic,
        popen: Callable[..., Any] = subprocess.Popen,
        which: Callable[[str], str | None] | None = None,
    ) -> None:
        if command is None:
            find = which or shutil.which
            for name, args in self.PLAYERS:
                exe = find(name)
                if exe:
                    command = [exe, *args]
                    break
            else:
                raise AudioUnavailableError("no supported command-line audio player found")
        if isinstance(command, str):
            raise TypeError("command must be a list of arguments, not a shell string")
        self.command = list(command)
        self._clock, self._popen = clock, popen
        self._caps = Capabilities(can_pause=False, can_volume=False)
        self.path: Path | None = None
        self._proc: Any = None
        self._started = 0.0
        self.closed = False

    def capabilities(self) -> Capabilities:
        return self._caps

    def load(self, path: str | Path) -> None:
        p = check_format(self._caps, path)
        full = p.expanduser().resolve()  # absolute, so it can never look like an option
        if not full.is_file():
            raise AudioBackendError(f"cannot read {full}")
        self.stop()
        self.path = full

    def play(self) -> None:
        if self.closed:
            raise AudioUnavailableError("backend is closed")
        if self.path is None:
            raise AudioBackendError("no file loaded")
        self.stop()
        try:
            self._proc = self._popen(
                [*self.command, str(self.path)],
                shell=False,
                stdin=subprocess.DEVNULL,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
        except OSError as exc:
            raise AudioUnavailableError(f"cannot start player: {exc}") from exc
        self._started = self._clock()

    def pause(self) -> None:
        raise UnsupportedFormatError("pause is not supported by this backend")

    def resume(self) -> None:
        raise UnsupportedFormatError("resume is not supported by this backend")

    def stop(self) -> None:
        proc, self._proc = self._proc, None
        if proc is not None and proc.poll() is None:
            proc.terminate()
            try:
                proc.wait(timeout=2)
            except Exception:
                proc.kill()

    def seek(self, seconds: float) -> None:
        raise UnsupportedFormatError("seek is not supported by this backend")

    def position(self) -> float:
        if self._proc is None or self._proc.poll() is not None:
            return 0.0
        return self._clock() - self._started

    def duration(self) -> float | None:
        return None

    def set_volume(self, volume: float) -> None:
        raise UnsupportedFormatError("volume control is not supported by this backend")

    def close(self) -> None:
        self.closed = True
        self.stop()


class WinsoundBackend:
    """``.wav`` playback through ``winsound`` (Windows standard library; no pause/volume)."""

    def __init__(
        self, *, clock: Callable[[], float] = time.monotonic, winsound: Any = None
    ) -> None:
        if winsound is None:
            try:
                import winsound as _ws
            except ImportError as exc:
                raise AudioUnavailableError("winsound is only available on Windows") from exc
            winsound = _ws
        self._ws, self._clock = winsound, clock
        self._caps = Capabilities(frozenset({".wav"}), can_pause=False, can_volume=False)
        self.path: Path | None = None
        self._duration: float | None = None
        self._started: float | None = None
        self.closed = False

    def capabilities(self) -> Capabilities:
        return self._caps

    def load(self, path: str | Path) -> None:
        p = check_format(self._caps, path)
        try:
            with wave.open(str(p), "rb") as w:
                self._duration = w.getnframes() / float(w.getframerate())
        except (OSError, wave.Error, EOFError) as exc:
            raise AudioBackendError(f"cannot read {p}: {exc}") from exc
        self.stop()
        self.path = p

    def play(self) -> None:
        if self.closed:
            raise AudioUnavailableError("backend is closed")
        if self.path is None:
            raise AudioBackendError("no file loaded")
        try:
            self._ws.PlaySound(str(self.path), self._ws.SND_FILENAME | self._ws.SND_ASYNC)
        except RuntimeError as exc:
            raise AudioUnavailableError(str(exc)) from exc
        self._started = self._clock()

    def pause(self) -> None:
        raise UnsupportedFormatError("pause is not supported by this backend")

    def resume(self) -> None:
        raise UnsupportedFormatError("resume is not supported by this backend")

    def stop(self) -> None:
        if self._started is not None:
            self._ws.PlaySound(None, self._ws.SND_PURGE)
        self._started = None

    def seek(self, seconds: float) -> None:
        raise UnsupportedFormatError("seek is not supported by this backend")

    def position(self) -> float:
        if self._started is None:
            return 0.0
        pos = self._clock() - self._started
        if self._duration is not None and pos >= self._duration:
            self._started = None
            return self._duration
        return pos

    def duration(self) -> float | None:
        return self._duration

    def set_volume(self, volume: float) -> None:
        raise UnsupportedFormatError("volume control is not supported by this backend")

    def close(self) -> None:
        self.closed = True
        self.stop()


def default_backend() -> AudioBackend:
    """The first real backend available on this machine, else ``AudioUnavailableError``."""
    errors: list[str] = []
    for factory in (SubprocessBackend, WinsoundBackend):
        try:
            return factory()
        except AudioUnavailableError as exc:
            errors.append(str(exc))
    raise AudioUnavailableError("; ".join(errors))


__all__ = [
    "AudioBackend",
    "Capabilities",
    "NullBackend",
    "SubprocessBackend",
    "WinsoundBackend",
    "check_format",
    "default_backend",
]
_ = sys
