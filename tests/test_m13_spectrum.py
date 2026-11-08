"""Real spectrum analysis."""

from __future__ import annotations

import math
import struct
import wave
from pathlib import Path

import pytest

pytest.importorskip("numpy")

from widgets.audio.spectrum import SpectrumAnalyzer
from widgets.errors import UnsupportedFormatError


def _tone(path: Path, hz: float = 1000.0) -> None:
    rate = 8000
    with wave.open(str(path), "wb") as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(rate)
        wav.writeframes(
            b"".join(
                struct.pack("<h", int(20000 * math.sin(2 * math.pi * hz * i / rate)))
                for i in range(rate)
            )
        )


def test_peak_band_follows_frequency(tmp_path: Path) -> None:
    low, high = tmp_path / "l.wav", tmp_path / "h.wav"
    _tone(low, 100)
    _tone(high, 3000)
    a, b = SpectrumAnalyzer(low).levels(16, 0.1), SpectrumAnalyzer(high).levels(16, 0.1)
    assert a.index(max(a)) < b.index(max(b))
    assert all(0 <= v <= 1 for v in a + b)
    assert SpectrumAnalyzer(low).levels(8, 99.0) == [0.0] * 8


def test_bad_file(tmp_path: Path) -> None:
    bad = tmp_path / "x.wav"
    bad.write_bytes(b"nope")
    with pytest.raises(UnsupportedFormatError):
        SpectrumAnalyzer(bad)
