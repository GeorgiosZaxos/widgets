"""WidgetRunner, equalizer band gains, player file tree, space intro."""

from __future__ import annotations

import io
from pathlib import Path

import pytest

from widgets.audio.backend import NullBackend
from widgets.audio.player import Equalizer, MusicPlayer
from widgets.display.marquee import Marquee
from widgets.display.space import SpaceCrawlWidget
from widgets.render.buffer import Buffer
from widgets.render.run import WidgetRunner


def test_band_gains() -> None:
    eq = Equalizer(0, 0, 20, 5, bands=4)
    assert eq.adjust_band(1, 0.5) == 1.5
    eq.set_band_gain(2, 9)
    assert eq.band_gains[2] == 2.0
    eq.reset_bands()
    assert eq.band_gains == [1.0] * 4
    with pytest.raises(IndexError):
        eq.set_band_gain(9, 1)


def test_player_file_tree(tmp_path: Path) -> None:
    (tmp_path / "album").mkdir()
    (tmp_path / "album" / "a.wav").write_bytes(b"RIFF")
    (tmp_path / "notes.txt").write_text("x")
    player = MusicPlayer(backend=NullBackend(), directory=tmp_path)
    names = player.browse()
    assert ("album", True) in names and all(n != "notes.txt" for n, _ in names)
    assert player.enter_directory("album") and player.directory == tmp_path / "album"
    assert player.enter_directory("..") and player.directory == tmp_path
    assert not player.enter_directory("missing")


def test_space_intro_then_crawl() -> None:
    w = SpaceCrawlWidget(
        0,
        0,
        60,
        20,
        intro="Long ago,\nin a quiet network",
        intro_time=2.0,
        reduced_motion=False,
        seed=1,
    )
    w.update(1.0)
    buf = Buffer(60, 20)
    w.render(buf)
    text = "\n".join("".join(c.glyph for c in buf.row(r)) for r in range(20))
    assert "Long ago," in text
    assert w.position == 0.0
    w.update(3.0)
    assert w.position > 0


def test_widget_runner_runs_and_restores() -> None:
    out = io.StringIO()
    runner = WidgetRunner(duration=0.1, fps=20)
    runner.add(Marquee(0, 0, 20, 1, text="hello"))
    runner.run(stream=out, interactive=False)
    assert out.getvalue()
