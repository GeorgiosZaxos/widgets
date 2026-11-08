"""Music player and equalizer widgets (FR-AUDIO-001..005, 009, 010). Layer L3."""

from __future__ import annotations

import contextlib
import math
import os
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from widgets.audio.backend import AudioBackend, Capabilities
from widgets.base_elements.events import KeyEvent
from widgets.base_elements.interactive import InteractiveWidget
from widgets.base_elements.widget_types import DEFAULT_STYLE, RGB, Rect, Style, WidgetId
from widgets.display._common import Animated, clip_cells
from widgets.errors import AudioBackendError
from widgets.render.buffer import Canvas

VOLUME_STEP = 5
BLOCKS = " ▁▂▃▄▅▆▇█"
PRESETS: dict[str, Callable[[int, int], float]] = {
    "flat": lambda i, n: 1.0,
    "bass": lambda i, n: 1.0 - 0.6 * (i / max(1, n - 1)),
    "treble": lambda i, n: 0.4 + 0.6 * (i / max(1, n - 1)),
    "vocal": lambda i, n: 0.45 + 0.55 * math.sin(math.pi * (i + 0.5) / n),
}


@dataclass(frozen=True, slots=True)
class Track:
    path: Path
    name: str
    error: str | None = None  # set for entries that stand for a problem (FR-AUDIO-001)


def list_audio_files(directory: str | Path, caps: Capabilities) -> list[Track]:
    """Supported audio files of ``directory`` (sorted); an unreadable directory yields one error entry."""
    d = Path(directory)
    exts = caps.supported_extensions()
    try:
        names = sorted(os.listdir(d), key=str.casefold)
    except OSError as exc:
        return [Track(d, f"<cannot read {d}: {exc.strerror or exc}>", error=str(exc))]
    out = [Track(d / n, n) for n in names if Path(n).suffix.lower() in exts and (d / n).is_file()]
    return out


def fmt_time(seconds: float | None) -> str:
    """Format ``seconds`` as ``mm:ss`` (``--:--`` when unknown)."""
    if seconds is None:
        return "--:--"
    s = int(max(0, seconds))
    return f"{s // 60:02d}:{s % 60:02d}"


class Equalizer(Animated):
    """N-band level display. Levels come from the backend; otherwise simulated or disabled."""

    def __init__(
        self,
        x: int = 0,
        y: int = 0,
        width: int = 32,
        height: int = 6,
        *,
        bands: int = 16,
        preset: str = "flat",
        levels: Callable[[int], list[float] | None] | None = None,
        simulate: bool = True,
        ascii_only: bool = False,
        reduced_motion: bool | None = None,
        name: WidgetId | None = None,
    ) -> None:
        super().__init__(x, y, width, height, reduced_motion=reduced_motion, name=name)
        if bands < 1:
            raise ValueError("bands must be >= 1")
        if preset not in PRESETS:
            raise ValueError(f"unknown preset {preset!r}; choose from {sorted(PRESETS)}")
        self.bands, self.preset, self.source, self.simulate = bands, preset, levels, simulate
        self.ascii_only = ascii_only
        self.active = True  # False when nothing is playing
        self.values = [0.0] * bands
        self.band_gains = [1.0] * bands
        self.mode = "disabled"

    def set_band_gain(self, band: int, gain: float) -> None:
        """Set the user gain (0..2) of one band, on top of the preset."""
        if not 0 <= band < self.bands:
            raise IndexError(f"band must be within 0..{self.bands - 1}")
        self.band_gains[band] = max(0.0, min(2.0, float(gain)))

    def adjust_band(self, band: int, delta: float) -> float:
        """Raise or lower one band by ``delta``; returns the new gain."""
        self.set_band_gain(band, self.band_gains[band] + delta)
        return self.band_gains[band]

    def reset_bands(self) -> None:
        self.band_gains = [1.0] * self.bands

    def set_preset(self, preset: str) -> None:
        if preset not in PRESETS:
            raise ValueError(f"unknown preset {preset!r}; choose from {sorted(PRESETS)}")
        self.preset = preset

    def next_preset(self) -> str:
        names = list(PRESETS)
        self.preset = names[(names.index(self.preset) + 1) % len(names)]
        return self.preset

    def advance(self, dt: float) -> None:
        raw: list[float] | None = None
        if self.active and self.source is not None:
            raw = self.source(self.bands)
        if raw is not None:
            self.mode = "live"
        elif self.active and self.simulate:
            self.mode = "simulated"
            raw = [
                0.5
                + 0.5 * math.sin(self.t * (2.0 + 0.7 * i) + i) * math.sin(self.t * 0.9 + i * 0.3)
                for i in range(self.bands)
            ]
        else:
            self.mode = "disabled"
            raw = [0.0] * self.bands
        gain = PRESETS[self.preset]
        target = [
            max(0.0, min(1.0, v * gain(i, self.bands) * self.band_gains[i]))
            for i, v in enumerate(raw[: self.bands])
        ]
        target += [0.0] * (self.bands - len(target))
        fall = max(0.0, dt) * 2.5
        self.values = [
            t if t >= v else max(t, v - fall) for v, t in zip(self.values, target, strict=True)
        ]

    def render(self, canvas: Canvas) -> None:
        h, w = canvas.height, canvas.width
        label = {"live": "", "simulated": " (simulated)", "disabled": " (no level data)"}[self.mode]
        canvas.write_text(0, 0, clip_cells(f"EQ {self.preset}{label}", w), Style(dim=True))
        rows = max(0, h - 1)
        if rows == 0:
            return
        per = max(1, w // self.bands)
        for b, v in enumerate(self.values):
            eighths = round(v * rows * 8)
            col = b * per
            for r in range(rows):
                full = eighths - (rows - 1 - r) * 8
                if full <= 0:
                    continue
                ch = "#" if self.ascii_only else BLOCKS[min(8, full)]
                t = 1.0 - (r / max(1, rows - 1))
                style = Style(fg=RGB(int(60 + 195 * t), int(220 - 120 * t), 90))
                width = max(1, per - 1) if per > 1 else 1
                canvas.write_text(1 + r, col, ch * width, style)


class MusicPlayer(InteractiveWidget):
    """Directory browser + transport + volume + equalizer.

    Keys: up/down select | enter play | space pause/resume | s stop | n / p next / previous |
    + / - volume (5 % steps) | e next equalizer preset.
    """

    def __init__(
        self,
        x: int = 0,
        y: int = 0,
        width: int = 60,
        height: int = 18,
        *,
        backend: AudioBackend,
        directory: str | Path | None = None,
        volume: int = 70,
        autoplay_next: bool = True,
        bands: int = 24,
        ascii_only: bool = False,
        on_state: Callable[[str], object] | None = None,
        name: WidgetId | None = None,
    ) -> None:
        super().__init__(x, y, width, height, name=name)
        self.backend = backend
        self.autoplay_next = autoplay_next
        self.ascii_only = ascii_only
        self.on_state = on_state
        self.tracks: list[Track] = []
        self.index = 0
        self.top = 0
        self.playback_state = "stopped"  # stopped | playing | paused
        self.current: Track | None = None
        self.message = ""
        self.volume = max(0, min(100, round(volume / VOLUME_STEP) * VOLUME_STEP))
        self.equalizer = Equalizer(
            0, 0, width, 6, bands=bands, levels=self._levels, ascii_only=ascii_only
        )
        self.equalizer.active = False
        self.directory: Path | None = None
        if directory is not None:
            self.scan(directory)
        self._apply_volume()

    # -- data --------------------------------------------------------------------------------
    @property
    def caps(self) -> Capabilities:
        return self.backend.capabilities()

    def scan(self, directory: str | Path) -> None:
        self.directory = Path(directory)
        self.tracks = list_audio_files(self.directory, self.caps)
        self.index = self.top = 0
        if not self.tracks:
            self.message = "no supported audio files found"

    def browse(self, directory: str | Path | None = None) -> list[tuple[str, bool]]:
        """File tree level: ``(name, is_directory)`` for sub-directories and supported files."""
        base = Path(directory) if directory is not None else self.directory
        if base is None:
            return []
        try:
            entries = sorted(base.iterdir(), key=lambda e: (not e.is_dir(), e.name.lower()))
        except OSError as exc:
            self.message = f"cannot read {base.name}: {exc.strerror or exc}"
            return []
        supported = {ext.lower() for ext in self.caps.extensions}
        return [
            (e.name, e.is_dir())
            for e in entries
            if not e.name.startswith(".") and (e.is_dir() or e.suffix.lower() in supported)
        ]

    def enter_directory(self, name: str) -> bool:
        """Descend into (or, with ``".."``, leave) a directory and rescan it."""
        if self.directory is None:
            return False
        target = self.directory.parent if name == ".." else self.directory / name
        if not target.is_dir():
            return False
        self.scan(target)
        return True

    def _levels(self, bands: int) -> list[float] | None:
        fn = getattr(self.backend, "levels", None)
        if not self.caps.has_levels or fn is None or self.playback_state != "playing":
            return None
        result: list[float] | None = fn(bands)
        return result

    @property
    def metadata(self) -> dict[str, str]:
        fn = getattr(self.backend, "metadata", None)
        if not self.caps.has_metadata or fn is None or self.current is None:
            return {}
        data: dict[str, str] = fn()
        return data

    @property
    def elapsed(self) -> float:
        if self.playback_state == "stopped":
            return 0.0
        return self._safe(self.backend.position, 0.0) or 0.0

    @property
    def duration(self) -> float | None:
        return None if self.current is None else self._safe(self.backend.duration, None)

    def _safe(self, fn: Callable[[], object], default: object) -> float | None:
        try:
            value = fn()
        except AudioBackendError:
            return default  # type: ignore[return-value]
        return value  # type: ignore[return-value]

    def _set_state(self, state: str) -> None:
        if state != self.playback_state:
            self.playback_state = state
            self.equalizer.active = state == "playing"
            self.invoke_callback(self.on_state, state)

    def _fail(self, exc: Exception) -> bool:
        self.message = str(exc)
        return False

    # -- transport (FR-AUDIO-002) --------------------------------------------------------------
    def select(self, index: int) -> None:
        if self.tracks:
            self.index = max(0, min(len(self.tracks) - 1, index))

    def play_track(self, index: int | None = None) -> bool:
        if index is not None:
            self.select(index)
        if not self.tracks or self.tracks[self.index].error:
            self.message = "nothing to play"
            return False
        track = self.tracks[self.index]
        try:
            self.backend.load(track.path)
            self.backend.play()
        except AudioBackendError as exc:
            self._set_state("stopped")
            return self._fail(exc)
        except OSError as exc:
            self._set_state("stopped")
            return self._fail(AudioBackendError(str(exc)))
        self.current, self.message = track, ""
        self._set_state("playing")
        return True

    def pause_audio(self) -> bool:
        if not self.caps.can_pause:
            self.message = "pause is not supported by this backend"
            return False
        if self.playback_state != "playing":
            return False
        try:
            self.backend.pause()
        except AudioBackendError as exc:
            return self._fail(exc)
        self._set_state("paused")
        return True

    def resume_audio(self) -> bool:
        if self.playback_state != "paused":
            return False
        try:
            self.backend.resume()
        except AudioBackendError as exc:
            return self._fail(exc)
        self._set_state("playing")
        return True

    def toggle(self) -> bool:
        if self.playback_state == "playing":
            return self.pause_audio()
        if self.playback_state == "paused":
            return self.resume_audio()
        return self.play_track()

    def stop_audio(self) -> None:
        try:
            self.backend.stop()
        except AudioBackendError as exc:
            self._fail(exc)
        self._set_state("stopped")

    def next_track(self) -> bool:
        if not self.tracks:
            return False
        return self.play_track((self.index + 1) % len(self.tracks))

    def prev_track(self) -> bool:
        if not self.tracks:
            return False
        return self.play_track((self.index - 1) % len(self.tracks))

    # -- volume (FR-AUDIO-004) -----------------------------------------------------------------
    def set_volume(self, percent: int) -> bool:
        self.volume = max(0, min(100, percent))
        return self._apply_volume()

    def volume_up(self) -> bool:
        return self.set_volume(self.volume + VOLUME_STEP)

    def volume_down(self) -> bool:
        return self.set_volume(self.volume - VOLUME_STEP)

    def _apply_volume(self) -> bool:
        if not self.caps.can_volume:
            self.message = "volume control is not supported by this backend"
            return False
        try:
            self.backend.set_volume(self.volume / 100)
        except AudioBackendError as exc:
            return self._fail(exc)
        return True

    # -- widget plumbing -----------------------------------------------------------------------
    def update(self, dt: float) -> None:
        self.equalizer.update(dt)
        if self.playback_state == "playing":
            dur = self.duration
            if dur is not None and self.elapsed >= dur:
                self._set_state("stopped")
                if self.autoplay_next and len(self.tracks) > 1:
                    self.next_track()

    def on_close(self) -> None:
        with contextlib.suppress(AudioBackendError):
            self.backend.close()

    def handle_key(self, event: KeyEvent) -> bool:
        if not self.effective_enabled:
            return False
        key = event.key
        if key == "up":
            self.select(self.index - 1)
        elif key == "down":
            self.select(self.index + 1)
        elif key == "enter":
            self.play_track()
        elif key in ("space", " "):
            self.toggle()
        elif key == "s":
            self.stop_audio()
        elif key == "n":
            self.next_track()
        elif key == "p":
            self.prev_track()
        elif key in ("+", "="):
            self.volume_up()
        elif key in ("-", "_"):
            self.volume_down()
        elif key == "e":
            self.equalizer.next_preset()
        else:
            return False
        return True

    def status_text(self) -> str:
        icons = (
            {"playing": "|>", "paused": "||", "stopped": "[]"}
            if self.ascii_only
            else {"playing": "▶", "paused": "⏸", "stopped": "■"}
        )
        return (
            f"{icons[self.playback_state]} {self.playback_state}  {fmt_time(self.elapsed)} / "
            f"{fmt_time(self.duration)}  vol {self.volume}%"
        )

    def render(self, canvas: Canvas) -> None:
        w, h = canvas.width, canvas.height
        eq_h = min(6, max(0, h - 6))
        info = 3
        list_h = max(0, h - eq_h - info)
        title = self.directory.name if self.directory else "music"
        canvas.write_text(
            0,
            0,
            clip_cells(f"♪ {title}" if not self.ascii_only else f"* {title}", w),
            Style(bold=True),
        )
        if self.index < self.top:
            self.top = self.index
        if list_h and self.index >= self.top + list_h - 1:
            self.top = self.index - list_h + 2
        for r in range(max(0, list_h - 1)):
            i = self.top + r
            if i >= len(self.tracks):
                break
            t = self.tracks[i]
            marker = ">" if i == self.index else " "
            playing = (
                "*"
                if self.current and t.path == self.current.path and self.playback_state != "stopped"
                else " "
            )
            style = Style(bold=i == self.index, fg=RGB(230, 70, 70) if t.error else None)
            canvas.write_text(1 + r, 0, clip_cells(f"{marker}{playing}{t.name}", w), style)
        base = max(0, h - eq_h - info)
        meta = self.metadata
        who = " - ".join(p for p in (meta.get("artist"), meta.get("title")) if p) or (
            self.current.name if self.current else ""
        )
        canvas.write_text(base, 0, clip_cells(who, w), DEFAULT_STYLE)
        canvas.write_text(base + 1, 0, clip_cells(self.status_text(), w), Style(dim=True))
        canvas.write_text(base + 2, 0, clip_cells(self.message, w), Style(fg=RGB(230, 150, 60)))
        if eq_h:
            self.equalizer.resize(w, eq_h)
            self.equalizer.render(canvas.view(Rect(0, base + info, w, eq_h)))

    def describe(self) -> str:
        return f"MusicPlayer({len(self.tracks)} tracks, {self.playback_state})"
