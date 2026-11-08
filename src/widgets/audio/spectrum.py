"""Real spectrum analysis for WAV files (FR-AUDIO-005). Layer L4. Needs the ``audio`` extra (numpy)."""

from __future__ import annotations

import itertools
import wave
from pathlib import Path
from typing import Any

from widgets.base_elements.import_helper import require_import
from widgets.errors import UnsupportedFormatError


class SpectrumAnalyzer:
    """Decodes a PCM WAV file and returns per-band levels (0..1) at a playback position."""

    WINDOW = 2048

    def __init__(self, path: str | Path) -> None:
        self._np: Any = require_import("numpy", feature="spectrum analysis", extra="audio")
        np = self._np
        try:
            with wave.open(str(path), "rb") as wav:
                channels, width, self.rate = (
                    wav.getnchannels(),
                    wav.getsampwidth(),
                    wav.getframerate(),
                )
                raw = wav.readframes(wav.getnframes())
        except (wave.Error, EOFError, OSError) as exc:
            raise UnsupportedFormatError(f"cannot decode {Path(path).name}: {exc}") from exc
        if width not in (1, 2, 4):
            raise UnsupportedFormatError(f"{width * 8}-bit PCM is not supported")
        dtype = {1: np.uint8, 2: np.int16, 4: np.int32}[width]
        data = np.frombuffer(raw, dtype=dtype).astype("float64")
        if width == 1:
            data -= 128.0
        data /= float(2 ** (8 * width - 1)) if width > 1 else 128.0
        self.samples = data.reshape(-1, channels).mean(axis=1) if channels > 1 else data
        self.duration = len(self.samples) / self.rate if self.rate else 0.0

    def levels(self, bands: int, position: float = 0.0) -> list[float]:
        """Logarithmically spaced band levels around ``position`` seconds."""
        np = self._np
        if bands < 1:
            raise ValueError("bands must be >= 1")
        start = max(0, int(position * self.rate))
        chunk = self.samples[start : start + self.WINDOW]
        if len(chunk) < 64:
            return [0.0] * bands
        mag = np.abs(np.fft.rfft(chunk * np.hanning(len(chunk)))) / len(chunk)
        freqs = np.fft.rfftfreq(len(chunk), 1.0 / self.rate)
        edges = np.geomspace(40.0, min(16000.0, self.rate / 2), bands + 1)
        out: list[float] = []
        for lo, hi in itertools.pairwise(edges):
            sel = mag[(freqs >= lo) & (freqs < hi)]
            level = float(sel.max()) if len(sel) else 0.0
            out.append(max(0.0, min(1.0, (20 * np.log10(level + 1e-9) + 70) / 70)))
        return out


__all__ = ["SpectrumAnalyzer"]
