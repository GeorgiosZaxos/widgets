"""M7 audio, synchronized playback, space crawl and beat-driven animation."""

from __future__ import annotations

import ast
import subprocess
import sys
import wave
from pathlib import Path

import pytest
from tests.conftest import text_rows

from widgets.audio.backend import (
    Capabilities,
    NullBackend,
    SubprocessBackend,
    WinsoundBackend,
    default_backend,
)
from widgets.audio.player import Equalizer, MusicPlayer, fmt_time, list_audio_files
from widgets.audio.sync import SynchronizedPlayer
from widgets.base_elements.effects import BeatSync
from widgets.base_elements.events import KeyEvent
from widgets.base_elements.lifecycle import LifecycleState
from widgets.display.effects_widgets import MatrixRain
from widgets.display.marquee import Marquee
from widgets.display.space import DEFAULT_TEXT, SpaceCrawlWidget
from widgets.display.spinner import Spinner
from widgets.errors import (
    AudioBackendError,
    AudioUnavailableError,
    UnsupportedFormatError,
    WidgetsError,
)
from widgets.render.buffer import Buffer


class Clock:
    def __init__(self) -> None:
        self.t = 0.0

    def __call__(self) -> float:
        return self.t


def key(name: str, char: str | None = None) -> KeyEvent:
    return KeyEvent(name, char)


def draw(widget, w: int, h: int) -> list[str]:
    buf = Buffer(w, h)
    if widget.state.name == "CREATED":
        widget.mount()
    widget.draw(buf)
    return text_rows(buf)


@pytest.fixture
def music(tmp_path: Path) -> Path:
    for n in ("b.mp3", "a.wav", "c.ogg", "notes.txt", "song.mid"):
        (tmp_path / n).write_bytes(b"x")
    (tmp_path / "dir.mp3").mkdir()
    return tmp_path


def make_player(music, clock=None, **kw):
    clock = clock or Clock()
    backend = kw.pop("backend", None) or NullBackend(
        clock=clock,
        durations={"a.wav": 10.0, "b.mp3": 20.0},
        metadata={"a.wav": {"title": "Alpha", "artist": "Ann"}},
    )
    p = MusicPlayer(0, 0, 60, 18, backend=backend, directory=music, **kw)
    p.mount()
    p.start()
    return p, backend, clock


# ----------------------------------------------------------- backend
@pytest.mark.req("FR-AUDIO-006")
def test_null_backend_protocol_and_errors(tmp_path):
    clock = Clock()
    b = NullBackend(clock=clock, default_duration=5.0)
    assert {".wav", ".mp3"} <= b.capabilities().extensions
    with pytest.raises(AudioBackendError):
        b.play()  # nothing loaded
    b.load("x.wav")
    b.play()
    clock.t = 2
    assert b.position() == 2 and b.duration() == 5.0
    b.pause()
    clock.t = 4
    assert b.position() == 2
    b.resume()
    clock.t = 5.5
    assert b.position() == 3.5
    b.seek(1)
    assert b.position() == 1
    clock.t = 100
    assert b.position() == 5.0 and b.state == "finished"
    b.set_volume(0.5)
    with pytest.raises(ValueError):
        b.set_volume(2)
    with pytest.raises(UnsupportedFormatError):
        b.load("x.xyz")
    b.close()
    with pytest.raises(AudioUnavailableError):
        b.play()
    assert issubclass(UnsupportedFormatError, AudioBackendError)
    assert issubclass(AudioUnavailableError, AudioBackendError)
    assert issubclass(AudioBackendError, WidgetsError)
    with pytest.raises(AudioBackendError):
        NullBackend(require_exists=True).load(tmp_path / "missing.wav")


@pytest.mark.req("FR-AUDIO-006", "FR-AUDIO-009")
def test_midi_only_when_declared_and_seek_optional():
    plain = NullBackend()
    with pytest.raises(UnsupportedFormatError, match="MIDI"):
        plain.load("tune.mid")
    midi = NullBackend(capabilities=Capabilities(midi=True))
    midi.load("tune.MID")
    assert ".mid" in midi.capabilities().supported_extensions()
    with pytest.raises(UnsupportedFormatError):
        midi.seek(1)  # can_seek defaults to False


@pytest.mark.req("FR-AUDIO-006", "FR-AUDIO-011")
def test_subprocess_backend_uses_argument_list_without_shell(tmp_path):
    f = tmp_path / "t.mp3"
    f.write_bytes(b"x")
    calls = []

    class Proc:
        def __init__(self):
            self.alive = True

        def poll(self):
            return None if self.alive else 0

        def terminate(self):
            self.alive = False

        def wait(self, timeout=None):
            return 0

    def popen(args, **kw):
        calls.append((args, kw))
        return Proc()

    clock = Clock()
    b = SubprocessBackend(["/usr/bin/player", "-q"], clock=clock, popen=popen)
    b.load(f)
    b.play()
    args, kw = calls[0]
    assert isinstance(args, list) and args[:2] == ["/usr/bin/player", "-q"]
    assert args[2] == str(f.resolve()) and kw["shell"] is False
    clock.t = 3
    assert b.position() == 3
    with pytest.raises(UnsupportedFormatError):
        b.pause()
    assert not b.capabilities().can_pause
    b.stop()
    assert b.position() == 0
    with pytest.raises(TypeError):
        SubprocessBackend("player -q")  # type: ignore[arg-type]
    with pytest.raises(AudioUnavailableError):
        SubprocessBackend(which=lambda n: None)
    ok = SubprocessBackend(which=lambda n: f"/bin/{n}" if n == "mpg123" else None)
    assert ok.command == ["/bin/mpg123", "-q"]
    with pytest.raises(AudioBackendError):
        b.load(tmp_path / "nope.mp3")
    # a path that merely looks like an option is made absolute
    odd = tmp_path / "-rf.mp3"
    odd.write_bytes(b"x")
    b.load(odd)
    assert Path(str(b.path)).is_absolute()
    # the module never builds a shell string
    tree = ast.parse(
        Path(sys.modules["widgets.audio.backend"].__file__).read_text(encoding="utf-8")
    )
    for node in ast.walk(tree):
        if isinstance(node, ast.keyword) and node.arg == "shell":
            assert isinstance(node.value, ast.Constant) and node.value.value is False
        if isinstance(node, ast.Import | ast.ImportFrom):
            assert "audioop" not in ast.dump(node)
        if isinstance(node, ast.Attribute):
            assert (
                node.attr not in ("system", "popen")
                or not isinstance(node.value, ast.Name)
                or node.value.id != "os"
            )


@pytest.mark.req("FR-AUDIO-006")
def test_winsound_backend_with_fake_module(tmp_path):
    wav = tmp_path / "s.wav"
    with wave.open(str(wav), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(8000)
        w.writeframes(b"\x00\x00" * 16000)

    class WS:
        SND_FILENAME, SND_ASYNC, SND_PURGE = 1, 2, 4
        played: list = []  # noqa: RUF012

        def PlaySound(self, what, flags):
            self.played.append((what, flags))

    ws, clock = WS(), Clock()
    b = WinsoundBackend(winsound=ws, clock=clock)
    b.load(wav)
    assert b.duration() == 2.0
    b.play()
    clock.t = 1
    assert b.position() == 1 and ws.played[-1] == (str(wav), 3)
    clock.t = 9
    assert b.position() == 2.0
    b.stop()
    with pytest.raises(UnsupportedFormatError):
        b.load(tmp_path / "x.mp3")
    bad = tmp_path / "bad.wav"
    bad.write_bytes(b"nope")
    with pytest.raises(AudioBackendError):
        b.load(bad)
    if sys.platform != "win32":
        with pytest.raises(AudioUnavailableError):
            WinsoundBackend()


@pytest.mark.req("FR-AUDIO-006")
def test_default_backend_reports_unavailability(monkeypatch):
    monkeypatch.setattr("shutil.which", lambda n: None)
    monkeypatch.setitem(sys.modules, "winsound", None)
    with pytest.raises(AudioUnavailableError):
        default_backend()


# ------------------------------------------------------------ player
@pytest.mark.req("FR-AUDIO-001")
def test_lists_supported_files_and_error_entry(music, tmp_path):
    caps = NullBackend().capabilities()
    names = [t.name for t in list_audio_files(music, caps)]
    assert names == ["a.wav", "b.mp3", "c.ogg"]  # filtered, sorted, no dir, no txt, no midi
    midi = Capabilities(midi=True)
    assert "song.mid" in [t.name for t in list_audio_files(music, midi)]
    bad = list_audio_files(tmp_path / "nope", caps)
    assert len(bad) == 1 and bad[0].error
    p, _, _ = make_player(tmp_path / "nope")
    assert not p.play_track() and "nothing to play" in p.message
    q, _, _ = make_player(music)
    q.handle_key(key("down"))
    q.handle_key(key("down"))
    q.handle_key(key("down"))
    assert q.index == 2
    q.handle_key(key("up"))
    assert q.index == 1


@pytest.mark.req("FR-AUDIO-002", "FR-AUDIO-003")
def test_transport_and_display(music):
    p, backend, clock = make_player(music)
    assert p.playback_state == "stopped"
    p.handle_key(key("enter"))
    assert p.playback_state == "playing" and p.current.name == "a.wav"
    clock.t = 65
    assert fmt_time(3.2) == "00:03" and fmt_time(None) == "--:--"
    clock.t = 4
    text = "\n".join(draw(p, 60, 18))
    assert "playing" in text and "00:04 / 00:10" in text and "vol 70%" in text
    p.handle_key(key("space"))
    assert p.playback_state == "paused"
    p.handle_key(key("space"))
    assert p.playback_state == "playing"
    p.handle_key(key("n"))
    assert p.current.name == "b.mp3"
    p.handle_key(key("p"))
    assert p.current.name == "a.wav"
    p.handle_key(key("p"))
    assert p.current.name == "c.ogg"  # wraps
    p.select(1)
    p.handle_key(key("enter"))
    assert p.current.name == "b.mp3"
    p.handle_key(key("s"))
    assert p.playback_state == "stopped" and backend.state == "stopped"
    assert not p.handle_key(key("z"))


@pytest.mark.req("FR-AUDIO-002")
def test_unsupported_operations_are_disabled_and_reported(music):
    backend = NullBackend(capabilities=Capabilities(can_pause=False, can_volume=False))
    p, _, _ = make_player(music, backend=backend)
    assert "volume control is not supported" in p.message
    p.play_track()
    assert not p.pause_audio() and "pause is not supported" in p.message
    assert p.playback_state == "playing"
    assert "pause is not supported" in "\n".join(draw(p, 60, 18))


@pytest.mark.req("FR-AUDIO-002", "FR-AUDIO-006")
def test_backend_errors_are_reported_not_raised(music):
    backend = NullBackend(fail={"play": AudioUnavailableError("no device")})
    p, _, _ = make_player(music, backend=backend)
    assert not p.play_track() and "no device" in p.message and p.playback_state == "stopped"
    p2, _, _ = make_player(
        music, backend=NullBackend(fail={"load": UnsupportedFormatError("bad codec")})
    )
    assert not p2.play_track() and "bad codec" in p2.message


@pytest.mark.req("FR-AUDIO-002")
def test_autoplay_next_and_state_callback(music):
    seen = []
    p, _, clock = make_player(music, on_state=seen.append)
    p.play_track(0)
    clock.t = 11  # a.wav lasts 10 s
    p.update(0.1)
    assert p.current.name == "b.mp3" and p.playback_state == "playing"
    assert seen[0] == "playing"
    q, _, c2 = make_player(music, autoplay_next=False)
    q.play_track(0)
    c2.t = 11
    q.update(0.1)
    assert q.playback_state == "stopped"


@pytest.mark.req("FR-AUDIO-004")
def test_volume_steps_of_five_percent_clamped(music):
    p, backend, _ = make_player(music, volume=98)
    assert p.volume == 100  # snapped to a multiple of 5
    p.handle_key(key("+", "+"))
    assert p.volume == 100
    for _ in range(3):
        p.handle_key(key("-", "-"))
    assert p.volume == 85 and backend.volume == 0.85
    for _ in range(40):
        p.volume_down()
    assert p.volume == 0 and backend.volume == 0.0
    p.volume_up()
    assert p.volume == 5


@pytest.mark.req("FR-AUDIO-010")
def test_metadata_displayed_when_provided(music):
    p, _, _ = make_player(music)
    p.play_track(0)
    assert p.metadata == {"title": "Alpha", "artist": "Ann"}
    assert "Ann - Alpha" in "\n".join(draw(p, 60, 18))
    p.play_track(1)
    assert p.metadata == {} and "b.mp3" in "\n".join(draw(p, 60, 18))
    plain = NullBackend(capabilities=Capabilities(has_metadata=False))
    q, _, _ = make_player(music, backend=plain)
    q.play_track(0)
    assert q.metadata == {}


@pytest.mark.req("FR-AUDIO-005")
def test_equalizer_live_simulated_disabled_and_presets():
    live = Equalizer(0, 0, 32, 6, bands=8, levels=lambda n: [1.0] * n)
    live.mount()
    live.update(0.1)
    assert live.mode == "live" and all(v == 1.0 for v in live.values)
    assert "simulated" not in draw(live, 32, 6)[0]
    sim = Equalizer(0, 0, 32, 6, bands=8)
    sim.mount()
    sim.update(0.3)
    assert sim.mode == "simulated" and "(simulated)" in draw(sim, 32, 6)[0]
    off = Equalizer(0, 0, 32, 6, bands=8, simulate=False)
    off.mount()
    off.update(0.3)
    assert off.mode == "disabled" and "no level data" in draw(off, 32, 6)[0]
    idle = Equalizer(0, 0, 32, 6, bands=4)
    idle.active = False
    idle.update(0.3)
    assert idle.mode == "disabled" and idle.values == [0.0] * 4
    flat = Equalizer(0, 0, 32, 6, bands=4, levels=lambda n: [1.0] * n, preset="bass")
    flat.update(0.1)
    assert flat.values[0] > flat.values[-1]
    assert flat.next_preset() != "bass"
    with pytest.raises(ValueError):
        flat.set_preset("nope")
    with pytest.raises(ValueError):
        Equalizer(bands=0)
    assert len(flat.values) == 4
    for mod in ("player", "backend", "sync"):
        tree = ast.parse(
            Path(sys.modules[f"widgets.audio.{mod}"].__file__).read_text(encoding="utf-8")
        )
        assert not any(
            isinstance(n, ast.Import | ast.ImportFrom) and "audioop" in ast.dump(n)
            for n in ast.walk(tree)
        )


@pytest.mark.req("FR-AUDIO-005")
def test_player_equalizer_uses_backend_levels_only_while_playing(music):
    p, _, _ = make_player(music)
    p.update(0.1)
    assert p.equalizer.mode == "disabled"
    p.play_track(0)
    p.update(0.1)
    assert p.equalizer.mode == "live"
    nolevels = NullBackend(capabilities=Capabilities(has_levels=False))
    q, _, _ = make_player(music, backend=nolevels)
    q.play_track(0)
    q.update(0.1)
    assert q.equalizer.mode == "simulated"
    p.handle_key(key("e"))
    assert p.equalizer.preset != "flat"


# --------------------------------------------------------- synchronized
class Dummy(Marquee):
    pass


@pytest.mark.req("FR-AUDIO-007", "FR-AUDIO-008")
def test_synchronized_player_starts_pauses_and_stops_together():
    clock = Clock()
    backend = NullBackend(clock=clock, default_duration=100.0)
    vis = [Marquee(0, 0, 10, 1, text="hi"), Spinner(0, 1, 5)]
    done = []
    sp = SynchronizedPlayer(backend, vis, on_finish=lambda: done.append(1))
    sp.start("a.wav")
    assert backend.state == "playing" and all(v.state is LifecycleState.RUNNING for v in vis)
    sp.pause()
    assert backend.state == "paused" and all(v.state is LifecycleState.PAUSED for v in vis)
    sp.resume()
    assert all(v.state is LifecycleState.RUNNING for v in vis)
    sp.stop()
    sp.stop()  # idempotent
    assert backend.state == "stopped" and done == [1]
    assert all(v.state is LifecycleState.STOPPED for v in vis)


@pytest.mark.req("FR-AUDIO-008")
def test_synchronized_player_ends_on_duration_audio_end_or_visual_stop():
    clock = Clock()
    backend = NullBackend(clock=clock, default_duration=5.0)
    v = Marquee(0, 0, 10, 1, text="hi")
    sp = SynchronizedPlayer(backend, [v], duration=2.0)
    sp.start("a.wav")
    sp.update(1.0)
    assert sp.running
    sp.update(1.5)
    assert (
        sp.state == "finished" and v.state is LifecycleState.STOPPED and backend.state == "stopped"
    )
    # audio finishes by itself -> visuals stop
    v2 = Marquee(0, 0, 10, 1, text="hi")
    sp2 = SynchronizedPlayer(backend, [v2])
    sp2.start("a.wav")
    clock.t = 100
    sp2.update(0.1)
    assert sp2.state == "finished" and v2.state is LifecycleState.STOPPED
    # a stopped visual stops the audio
    v3 = Marquee(0, 0, 10, 1, text="hi")
    clock.t = 0
    sp3 = SynchronizedPlayer(backend, [v3])
    sp3.start("a.wav")
    v3.stop()
    sp3.update(0.1)
    assert sp3.state == "finished" and backend.state == "stopped"
    with pytest.raises(ValueError):
        SynchronizedPlayer(backend, duration=0)


@pytest.mark.req("FR-AUDIO-008")
def test_cleanup_runs_even_if_backend_fails():
    backend = NullBackend(fail={"stop": AudioBackendError("stuck")})
    v = Marquee(0, 0, 10, 1, text="hi")
    sp = SynchronizedPlayer(backend, [v])
    sp.start("a.wav")
    with pytest.raises(AudioBackendError, match="stuck"):
        sp.stop()
    assert v.state is LifecycleState.STOPPED and sp.state == "finished"
    # failed start leaves nothing half-started
    bad = NullBackend(fail={"play": AudioUnavailableError("no device")})
    w = Marquee(0, 0, 10, 1, text="hi")
    sp2 = SynchronizedPlayer(bad, [w])
    with pytest.raises(AudioUnavailableError):
        sp2.start("a.wav")
    assert sp2.state == "idle" and w.state in (LifecycleState.CREATED, LifecycleState.MOUNTED)
    # context manager closes the backend even when stop fails
    s3 = SynchronizedPlayer(NullBackend(fail={"stop": AudioBackendError("x")}), [])
    with pytest.raises(AudioBackendError), s3:
        s3.start("a.wav")
    assert s3.backend.closed  # type: ignore[attr-defined]


@pytest.mark.req("FR-AUDIO-007")
def test_drive_visuals_option_ticks_them():
    backend = NullBackend()
    m = Marquee(0, 0, 10, 1, text="scroll me please", speed=10)
    sp = SynchronizedPlayer(backend, [m], drive_visuals=True)
    sp.start("a.wav")
    sp.update(1.0)
    assert m.t == 1.0


# -------------------------------------------------------------- beats
class Beats:
    def __init__(self):
        self.queue: list[list[float]] = []
        self.fail = False

    def poll(self):
        if self.fail:
            raise RuntimeError("source gone")
        return self.queue.pop(0) if self.queue else []


@pytest.mark.req("FR-ANIM-007")
def test_beat_source_drives_animation_steps_and_falls_back():
    src = Beats()
    sp = Spinner(0, 0, 10, speed=10.0, beat_source=src)
    sp.mount()
    sp.start()
    assert not sp.audio_sync_active
    sp.tick(0.5)  # time driven
    assert not sp.audio_sync_active and sp._phase == pytest.approx(5.0)
    src.queue.append([0.1, 0.2])
    before = sp._phase
    sp.tick(0.01)
    assert sp.audio_sync_active and sp._phase == pytest.approx(before + 2)
    sp.tick(0.5)  # silent but within timeout: no movement
    assert sp.audio_sync_active and sp._phase == pytest.approx(before + 2)
    sp.tick(0.6)  # timeout exceeded -> time driven again
    assert not sp.audio_sync_active
    sp.tick(0.1)
    assert sp._phase > before + 2
    src.fail = True
    sp.tick(0.1)
    assert not sp.audio_sync_active  # source error never propagates


@pytest.mark.req("FR-ANIM-007")
def test_beats_in_animated_base_and_unavailable_source():
    m = Marquee(0, 0, 10, 1, text="hello world", speed=8.0)
    src = Beats()
    m.set_beat_source(src)
    m.mount()
    m.start()
    src.queue.append([0.0])
    m.tick(0.001)
    assert m.audio_sync_active and m.t == pytest.approx(m.beat_step)
    m.set_beat_source(None)
    assert not m.audio_sync_active
    m.tick(0.5)
    assert m.t > m.beat_step
    bs = BeatSync(None)
    assert bs.poll(1.0) == 0 and not bs.active
    with pytest.raises(ValueError):
        BeatSync(None, timeout=0)
    rain = MatrixRain(0, 0, 10, 5, seed=1)
    rain.set_beat_source(src)
    assert not rain.audio_sync_active


# -------------------------------------------------------------- space
@pytest.mark.req("FR-SPACE-001")
def test_crawl_narrows_and_dims_toward_horizon_and_default_text_is_original():
    w = SpaceCrawlWidget(0, 0, 80, 24, seed=1, objects=(), ascii_only=True)
    w.mount()
    w.start()
    w.tick(7.0)
    buf = Buffer(80, 24)
    w.draw(buf)
    rows = text_rows(buf)
    widths = [len(r.strip()) for r in rows]
    inked = [i for i, n in enumerate(widths) if n]
    assert len(inked) > 5
    top, bottom = inked[0], inked[-1]
    assert widths[top] < widths[bottom]  # narrower near the horizon

    def brightness(r: int) -> int:
        return max(buf.get_cell(r, c).style.fg.r for c in range(80) if rows[r][c] != " ")

    assert brightness(top) < brightness(bottom)
    assert "star wars" not in DEFAULT_TEXT.lower() and "jedi" not in DEFAULT_TEXT.lower()


@pytest.mark.req("FR-SPACE-002")
def test_space_objects_configurable_and_seedable():
    a = SpaceCrawlWidget(0, 0, 60, 20, seed=5)
    b = SpaceCrawlWidget(0, 0, 60, 20, seed=5)
    c = SpaceCrawlWidget(0, 0, 60, 20, seed=6)
    assert a.star_field() == b.star_field() and a.star_field() != c.star_field()
    only = SpaceCrawlWidget(0, 0, 60, 20, seed=1, objects=[("galaxy", 0.01)])
    kinds = {k for _, _, k in only.star_field()}
    assert kinds == {"galaxy"} and len(only.star_field()) == round(0.01 * 60 * 20)
    dense = SpaceCrawlWidget(0, 0, 60, 20, seed=1, objects=[("nebula", 0.02), ("pulsar", 0.01)])
    assert {k for _, _, k in dense.star_field()} == {"nebula", "pulsar"}
    for bad in ([("comet", 0.1)], [("star", 2.0)]):
        with pytest.raises(ValueError):
            SpaceCrawlWidget(objects=bad)
    for kind in ("galaxy", "nebula", "pulsar", "star"):
        wd = SpaceCrawlWidget(0, 0, 40, 12, seed=2, objects=[(kind, 0.05)])
        draw(wd, 40, 12)


@pytest.mark.req("FR-SPACE-003")
def test_start_stop_pause_resume_speed_and_keys():
    w = SpaceCrawlWidget(0, 0, 60, 20, seed=1)
    w.mount()
    w.start()
    w.tick(1.0)
    pos = w.position
    assert pos == pytest.approx(1.2)
    w.handle_key(key("+", "+"))
    assert w.speed == pytest.approx(1.5)
    w.handle_key(key("-", "-"))
    w.handle_key(key("-", "-"))
    assert w.speed < 1.2
    for _ in range(60):
        w.handle_key(key("+", "+"))
    assert w.speed == 20.0
    for _ in range(100):
        w.handle_key(key("-", "-"))
    assert w.speed == 0.1
    w.handle_key(key("space"))
    assert w.state is LifecycleState.PAUSED
    t = w.t
    w.tick(1.0)
    assert w.t == t  # paused: no progress
    w.handle_key(key("space"))
    assert w.state is LifecycleState.RUNNING
    w.handle_key(key("r", "r"))
    assert w.t == 0
    w.stop()
    assert w.state is LifecycleState.STOPPED
    assert not w.handle_key(key("q", "q"))
    with pytest.raises(ValueError):
        w.set_speed(0)
    short = SpaceCrawlWidget(0, 0, 40, 10, text="hi", speed=5)
    short.mount()
    short.start()
    short.tick(60)
    assert short.finished
    assert not SpaceCrawlWidget(0, 0, 40, 10, text="hi", loop=True).finished
    rm = SpaceCrawlWidget(0, 0, 60, 20, reduced_motion=True, seed=1)
    assert draw(rm, 60, 20) == draw(rm, 60, 20)


@pytest.mark.req("FR-SPACE-004")
def test_soundtrack_plays_and_failure_does_not_stop_visuals(tmp_path):
    f = tmp_path / "theme.mp3"
    f.write_bytes(b"x")
    nb = NullBackend()
    w = SpaceCrawlWidget(0, 0, 60, 20, seed=1, soundtrack=f, backend=nb)
    w.mount()
    w.start()
    assert w.audio_playing and nb.state == "playing"
    w.pause()
    assert nb.state == "paused"
    w.resume()
    assert nb.state == "playing"
    w.stop()
    assert nb.state == "stopped" and not w.audio_playing
    broken = NullBackend(fail={"play": AudioUnavailableError("no sound card")})
    v = SpaceCrawlWidget(0, 0, 60, 20, seed=1, soundtrack=f, backend=broken)
    v.mount()
    v.start()
    assert v.audio_error == "no sound card" and v.state is LifecycleState.RUNNING
    v.tick(1.0)
    assert v.t == 1.0
    missing = SpaceCrawlWidget(0, 0, 60, 20, soundtrack=tmp_path / "x.xyz", backend=NullBackend())
    missing.mount()
    missing.start()
    assert missing.audio_error and missing.state is LifecycleState.RUNNING
    none = SpaceCrawlWidget(0, 0, 60, 20)
    none.mount()
    none.start()
    assert none.audio_error is None


@pytest.mark.req("FR-SPACE-001")
def test_legacy_shim_is_deprecated_alias():
    import importlib
    import warnings

    sys.modules.pop("widgets.include.star_wars_widget", None)
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        mod = importlib.import_module("widgets.include.star_wars_widget")
    assert mod.StarWarsWidget is SpaceCrawlWidget
    assert any(issubclass(c.category, DeprecationWarning) for c in caught)


def test_subprocess_unused_import_guard():
    assert subprocess.DEVNULL is not None


@pytest.mark.req("FR-ANIM-001")
def test_animation_configuration_is_accepted_and_validated():
    from widgets.base_elements.color_manager import Gradient
    from widgets.base_elements.widget_types import RGB, Style

    m = Marquee(
        2,
        3,
        20,
        2,
        text="hi",
        direction="right",
        mode="bounce",
        speed=3.0,
        gap=2,
        align="center",
        style=Style(bold=True),
        gradient=Gradient([(0.0, RGB(255, 0, 0)), (1.0, RGB(0, 0, 255))]),
    )
    assert (m.x, m.y, m.width, m.height, m.speed, m.direction, m.mode) == (
        2,
        3,
        20,
        2,
        3.0,
        "right",
        "bounce",
    )
    for bad in (
        {"speed": 0},
        {"speed": -1},
        {"direction": "up-ish"},
        {"mode": "zigzag"},
        {"align": "diagonal"},
    ):
        with pytest.raises(ValueError):
            Marquee(0, 0, 10, 1, text="x", **bad)
