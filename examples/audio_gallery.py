"""Live gallery of the M7 widgets: music player + equalizer, synchronized visuals, space crawl.

    python examples/audio_gallery.py [--page N] [--duration S] [--null] [--ascii] [--dir PATH]

F1 Music player  (up/down select, enter play, space pause, s stop, n/p next/prev, +/- volume, e preset)
F2 Synchronized  (s start/stop audio + visuals together, space pause/resume; visuals follow the beat)
F3 Space crawl   (space pause, +/- speed, r restart; soundtrack plays if a backend is available)
F10 / Ctrl+Q quits.

Sound: three short tunes are synthesised into a temp folder (original melodies, plain ``wave``
module - no audioop).  On Windows they play through ``winsound`` (.wav only: no pause/volume); with
ffplay/mpv/mpg123/afplay installed the command-line player is used.  ``--null`` (or no usable
backend) falls back to a silent simulated backend so every widget still works.
"""

from __future__ import annotations

import argparse
import math
import struct
import tempfile
import wave
from pathlib import Path

from widgets.audio.backend import AudioBackend, NullBackend, default_backend
from widgets.audio.player import MusicPlayer
from widgets.audio.sync import SynchronizedPlayer
from widgets.base_elements.base import Widget
from widgets.base_elements.events import Event, KeyEvent
from widgets.base_elements.interactive import InteractiveWidget
from widgets.base_elements.layout import Screen
from widgets.base_elements.widget_types import RGB, Style
from widgets.display.effects_widgets import MatrixRain
from widgets.display.marquee import Marquee
from widgets.display.space import SpaceCrawlWidget
from widgets.display.spinner import Spinner
from widgets.errors import AudioBackendError
from widgets.render.buffer import Canvas
from widgets.render.run import run_app

W, H = 100, 30
RATE = 22050
BAR = Style(fg=RGB(255, 255, 255), bg=RGB(40, 60, 140), bold=True)
TUNES = {
    "01 morning.wav": (
        [
            "C4",
            "E4",
            "G4",
            "C5",
            "G4",
            "E4",
            "C4",
            "G3",
            "A3",
            "C4",
            "E4",
            "A4",
            "E4",
            "C4",
            "A3",
            "F3",
        ],
        0.28,
    ),
    "02 harbour.wav": (
        [
            "D4",
            "F4",
            "A4",
            "D5",
            "C5",
            "A4",
            "F4",
            "D4",
            "E4",
            "G4",
            "B4",
            "E5",
            "D5",
            "B4",
            "G4",
            "E4",
        ],
        0.34,
    ),
    "03 lantern.wav": (
        [
            "A3",
            "C4",
            "E4",
            "A4",
            "B4",
            "A4",
            "E4",
            "C4",
            "G3",
            "B3",
            "D4",
            "G4",
            "A4",
            "G4",
            "D4",
            "B3",
        ],
        0.24,
    ),
}
NOTE = {"C": 0, "D": 2, "E": 4, "F": 5, "G": 7, "A": 9, "B": 11}


def freq(note: str) -> float:
    semis = NOTE[note[0]] + 12 * (int(note[1]) - 4) - 9
    return 440.0 * 2 ** (semis / 12)


def synth(path: Path, notes: list[str], step: float) -> None:
    frames = bytearray()
    for n in notes * 2:
        f, count = freq(n), int(RATE * step)
        for i in range(count):
            env = min(1.0, i / 400) * min(1.0, (count - i) / 1500)
            s = 0.55 * math.sin(2 * math.pi * f * i / RATE) + 0.2 * math.sin(
                4 * math.pi * f * i / RATE
            )
            frames += struct.pack("<h", int(9000 * env * s))
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(RATE)
        w.writeframes(bytes(frames))


class BeatClock:
    """BeatSource: one beat every 60/bpm seconds of audio position while the player runs."""

    def __init__(self, backend: AudioBackend, bpm: float = 120.0) -> None:
        self.backend, self.period, self.last = backend, 60.0 / bpm, 0.0

    def poll(self) -> list[float]:
        pos = self.backend.position()
        if pos < self.last:
            self.last = 0.0
        beats = []
        while self.last + self.period <= pos:
            self.last += self.period
            beats.append(self.last)
        return beats


class Pump(Widget):
    """Zero-size widget that gives a callback a per-frame hook."""

    def __init__(self, fn) -> None:  # type: ignore[no-untyped-def]
        super().__init__(0, 0, 0, 0)
        self.fn = fn

    def update(self, dt: float) -> None:
        self.fn(dt)

    def render(self, canvas: Canvas) -> None:
        return


class Bar(Widget):
    def __init__(self, y: int, kind: str) -> None:
        super().__init__(0, y, W, 1)
        self.kind, self.page, self.msg = kind, 0, ""

    def render(self, canvas: Canvas) -> None:
        if self.kind == "head":
            text = "  ".join(
                f"[F{i + 1}] {p}" if i == self.page else f" F{i + 1}  {p}"
                for i, p in enumerate(("Player", "Synchronized", "Space crawl"))
            )
            canvas.write_text(0, 0, text.ljust(canvas.width), BAR)
        else:
            canvas.write_text(
                0,
                0,
                f" {self.msg}   | F10 quit"[: canvas.width].ljust(canvas.width),
                Style(dim=True),
            )


class Label(Widget):
    def __init__(self, x: int, y: int, text: str, style: Style) -> None:
        super().__init__(x, y, len(text), 1)
        self.text, self.style = text, style

    def render(self, canvas: Canvas) -> None:
        canvas.write_text(0, 0, self.text, self.style)


class Hold(InteractiveWidget):
    """Focus target for the synchronized page; shows state."""

    def __init__(self, sp: SynchronizedPlayer) -> None:
        super().__init__(2, 4, 90, 3)
        self.sp = sp

    def render(self, canvas: Canvas) -> None:
        sp = self.sp
        canvas.write_text(
            0,
            0,
            f"state: {sp.state}   audio position: {sp.backend.position():5.1f}s   elapsed: {sp.elapsed:5.1f}s",
            Style(bold=True),
        )
        canvas.write_text(1, 0, "s start / stop    space pause / resume", Style(dim=True))
        if sp.error:
            canvas.write_text(2, 0, f"error: {sp.error}", Style(fg=RGB(230, 70, 70)))


def make_backend(null: bool) -> tuple[AudioBackend, str]:
    if not null:
        try:
            b = default_backend()
            return b, f"audio: {type(b).__name__}"
        except AudioBackendError as exc:
            return NullBackend(), f"audio: simulated (silent) - {exc}"
    return NullBackend(), "audio: simulated (silent)"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--page", type=int, default=1)
    ap.add_argument("--duration", type=float, default=None)
    ap.add_argument("--null", action="store_true")
    ap.add_argument("--ascii", action="store_true")
    ap.add_argument("--dir", type=Path, default=None)
    args = ap.parse_args()

    folder = args.dir
    if folder is None:
        folder = Path(tempfile.mkdtemp(prefix="widgets_audio_"))
        for name, (notes, step) in TUNES.items():
            synth(folder / name, notes, step)
    backend, note = make_backend(args.null)
    soundtrack = next(iter(sorted(folder.glob("*.wav"))), None)

    player = MusicPlayer(2, 2, 96, 26, backend=backend, directory=folder, ascii_only=args.ascii)

    # page 2: visuals that follow the audio
    sync_backend, _ = make_backend(args.null)
    clock = BeatClock(sync_backend, bpm=120.0)
    spin = Spinner(
        2,
        9,
        40,
        spinner="dots",
        text="beat-driven spinner",
        speed=8.0,
        beat_source=clock,
        ascii_only=args.ascii,
    )
    text = Marquee(
        2,
        11,
        90,
        1,
        text="  ~~ the marquee advances on every beat while the audio plays ~~  ",
        speed=6.0,
    )
    text.set_beat_source(clock)
    rain = MatrixRain(2, 13, 90, 12, seed=3)
    visuals: list[Widget] = [spin, text, rain]
    sp = SynchronizedPlayer(sync_backend, visuals)
    hold = Hold(sp)
    sync_label = Label(
        2,
        2,
        "Audio and visuals start, pause and stop together (stopping one stops the other)",
        Style(bold=True, fg=RGB(255, 200, 60)),
    )

    crawl = SpaceCrawlWidget(
        0,
        1,
        W,
        H - 2,
        seed=7,
        soundtrack=soundtrack,
        backend=make_backend(args.null)[0],
        ascii_only=args.ascii,
    )

    screen = Screen(W, H)
    head, foot = Bar(0, "head"), Bar(H - 1, "foot")
    pages: list[list[Widget]] = [[player], [sync_label, hold, spin, text, rain], [crawl]]
    for w in (player, sync_label, hold, spin, text, rain, crawl):
        screen.add(w)
    screen.add(head)
    screen.add(foot)
    cur = {"i": 0}

    def show(i: int) -> None:
        cur["i"] = i
        for k, ws in enumerate(pages):
            for w in ws:
                w.visible = k == i
                if isinstance(w, InteractiveWidget):
                    (w.focus if k == i else w.blur)()
        head.page = i
        if i == 1:
            for v in visuals:
                v.visible = sp.running

    def frame(dt: float) -> None:
        sp.update(dt)
        if cur["i"] == 1:
            for v in visuals:
                v.visible = sp.running
        foot.msg = {
            0: f"{note} | {player.status_text()} | {player.message}",
            1: note,
            2: f"{note} | {'soundtrack: ' + (crawl.audio_error or 'playing') if soundtrack else ''}",
        }[cur["i"]]

    screen.add(Pump(frame))
    show(max(0, min(2, args.page - 1)))

    def on_event(event: Event) -> None:
        if not isinstance(event, KeyEvent):
            return
        if event.key in ("f1", "f2", "f3"):
            show(int(event.key[1]) - 1)
            return
        i = cur["i"]
        if i == 0:
            player.handle_key(event)
        elif i == 1:
            try:
                if event.key == "s":
                    if sp.running:
                        sp.stop()
                    else:
                        sp.start(soundtrack or "demo.wav")
                elif event.key == "space":
                    sp.pause() if sp.state == "playing" else sp.resume()
            except AudioBackendError as exc:
                sp.error = exc
        else:
            crawl.handle_key(event)

    run_app(
        screen,
        fps=30,
        duration=args.duration,
        quit_keys=("ctrl+q", "f10"),
        on_event=on_event,
        title="widgets audio gallery",
    )
    sp.close()


if __name__ == "__main__":
    main()
