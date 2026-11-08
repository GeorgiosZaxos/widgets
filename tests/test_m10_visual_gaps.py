"""Visual-parity gaps closed from the legacy comparison (matrix, neon, sign, marquee, bars)."""

from __future__ import annotations

import pytest

from widgets.display.effects_widgets import MatrixRain, Neon, create_banner, create_sign
from widgets.display.marquee import Marquee
from widgets.progress.indicators import VerticalBar
from widgets.progress.state import ProgressState
from widgets.render.buffer import Buffer


def _text(buf: Buffer) -> str:
    return "\n".join("".join(c.glyph for c in buf.row(r)) for r in range(buf.height))


def _draw(widget, w: int, h: int) -> Buffer:  # type: ignore[no-untyped-def]
    buf = Buffer(w, h)
    widget.render(buf)
    return buf


def test_matrix_vt_types_text_with_cursor() -> None:
    m = MatrixRain(0, 0, 20, 3, text="HELLO", mode="vt", speed=2.0, reduced_motion=False)
    assert "HE" not in _text(_draw(m, 20, 3))
    m.update(1.0)
    assert _text(_draw(m, 20, 3)).startswith("HE")
    m.update(5.0)
    assert "HELLO" in _text(_draw(m, 20, 3))


def test_matrix_encrypted_resolves_text() -> None:
    m = MatrixRain(0, 0, 20, 5, text="SECRET", mode="encrypted", seed=1, reveal_after=0.0)
    m.update(0.0)
    assert "SECRET" not in _text(_draw(m, 20, 5))
    m.update(5.0)
    assert "SECRET" in _text(_draw(m, 20, 5))


def test_matrix_rejects_unknown_mode() -> None:
    with pytest.raises(ValueError):
        MatrixRain(mode="nope")


def test_neon_palette_font_outline() -> None:
    n = Neon(0, 0, 40, 7, text="HI", palette="rainbow", font="original-5", outline=True)
    out = _text(_draw(n, 40, 7))
    assert out.strip()
    assert "░" in out


def test_sign_helpers() -> None:
    sign = create_sign("HI", border="single")
    assert sign.height >= 7
    banner = create_banner("HI", width=30)
    assert banner.width == 30
    assert _text(_draw(banner, 30, banner.height)).strip()


@pytest.mark.parametrize("direction", ["diagonal", "snake"])
def test_marquee_path_directions(direction: str) -> None:
    m = Marquee(0, 0, 10, 4, text="abc", direction=direction, speed=1.0)
    m.update(5.0)
    assert "a" in _text(_draw(m, 10, 4))


def test_vertical_bar_fill_modes_and_animation() -> None:
    state = ProgressState(total=10)
    state.update(5)
    centre = VerticalBar(state, 8, orientation="center-out", style="block")
    col = centre.column()
    assert col[3] != col[0] and col[4] != col[7]
    assert col[0] == col[7]
    edges = VerticalBar(state, 8, orientation="edges-in", style="block")
    assert edges.column()[0] != edges.column()[3]
    with pytest.raises(ValueError):
        VerticalBar(state, 8, orientation="sideways")
    anim = VerticalBar(state, 8, animate="scan")
    anim.update(0.3)
    assert _text(_draw(anim, 1, 8))
