"""Live spectrum demo: python examples/spectrum_demo.py [file.wav]   (q quits)

Needs ``pip install -e ".[audio]"`` (numpy). Without a file a 12-second test chord is generated.
"""

from __future__ import annotations

import math
import struct
import sys
import tempfile
import time
import wave
from pathlib import Path

from widgets.audio.backend import default_backend
from widgets.audio.player import Equalizer
from widgets.audio.spectrum import SpectrumAnalyzer
from widgets.render.run import WidgetRunner


def make_test_wav(path: Path, seconds: int = 12, rate: int = 22050) -> None:
    frames = bytearray()
    for i in range(seconds * rate):
        t = i / rate
        sweep = 200 + 1800 * (t % 4) / 4
        v = 0.4 * math.sin(2 * math.pi * 220 * t) + 0.3 * math.sin(2 * math.pi * sweep * t)
        v += 0.2 * math.sin(2 * math.pi * 3000 * t) * (1 if (t * 4) % 1 < 0.5 else 0)
        frames += struct.pack("<h", int(v * 20000))
    with wave.open(str(path), "wb") as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(rate)
        wav.writeframes(bytes(frames))


def main() -> None:
    path = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(tempfile.gettempdir()) / "spectrum.wav"
    if len(sys.argv) <= 1:
        make_test_wav(path)
    analyzer = SpectrumAnalyzer(path)
    backend = default_backend()
    try:
        backend.load(path)
        backend.play()
    except Exception as exc:  # no audio device: the analysis still animates
        print(f"audio playback unavailable ({exc}); showing the spectrum only", file=sys.stderr)
    started = time.monotonic()
    eq = Equalizer(
        2, 1, 60, 14, bands=30, levels=lambda b: analyzer.levels(b, time.monotonic() - started)
    )
    runner = WidgetRunner(duration=analyzer.duration, title="spectrum")
    runner.add(eq)
    runner.run()
    backend.stop()


if __name__ == "__main__":
    main()
