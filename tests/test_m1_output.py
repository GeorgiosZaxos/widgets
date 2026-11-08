"""M1: color, width, sanitize, buffer, diff, renderer."""

from __future__ import annotations

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from conftest import apply_ops, buffer_grid, make_renderer
from widgets.base_elements.color_manager import (
    ColorMode,
    Gradient,
    apply_style,
    detect_color_mode,
    hex_to_rgb,
    parse_color,
    rgb_to_ansi16,
    rgb_to_ansi256,
    style_to_ansi,
)
from widgets.base_elements.widget_types import CONTINUATION, RGB, Cell, Rect, Style
from widgets.render.buffer import Buffer
from widgets.render.diff import diff_buffers
from widgets.render.sanitize import expand_tabs, sanitize_text, sanitize_title
from widgets.render.width import display_width

# -- color --------------------------------------------------------------------------------


@pytest.mark.req("FR-COLOR-001")
def test_parse_colors() -> None:
    assert hex_to_rgb("#ff8000") == RGB(255, 128, 0)
    assert hex_to_rgb("#f80") == RGB(255, 136, 0)
    assert parse_color((1, 2, 3)) == RGB(1, 2, 3)
    assert parse_color("#000000") == RGB(0, 0, 0)
    with pytest.raises(ValueError):
        hex_to_rgb("#12345")


@pytest.mark.req("FR-COLOR-003")
def test_color_mode_detection() -> None:
    assert (
        detect_color_mode(env={"TERM": "xterm", "COLORTERM": "truecolor"}, isatty=True)
        == ColorMode.TRUECOLOR
    )
    assert detect_color_mode(env={"TERM": "xterm-256color"}, isatty=True) == ColorMode.ANSI256
    assert (
        detect_color_mode(env={"TERM": "xterm"}, isatty=True, platform="linux") == ColorMode.ANSI16
    )
    assert detect_color_mode(env={"TERM": "dumb"}, isatty=True) == ColorMode.NONE
    assert detect_color_mode(env={"TERM": "xterm-256color"}, isatty=False) == ColorMode.NONE


@pytest.mark.req("FR-COLOR-003")
def test_no_color_and_force_color() -> None:
    env = {"TERM": "xterm-256color", "COLORTERM": "truecolor", "NO_COLOR": "1"}
    assert detect_color_mode(env=env, isatty=True) == ColorMode.NONE
    assert (
        detect_color_mode(env={"FORCE_COLOR": "1", "TERM": "xterm"}, isatty=False) != ColorMode.NONE
    )


@pytest.mark.req("FR-COLOR-002", "FR-COLOR-004")
def test_downgrade_and_style_sequences() -> None:
    assert rgb_to_ansi256(RGB(255, 0, 0)) == 196
    assert rgb_to_ansi16(RGB(255, 0, 0)) in (1, 9)
    s = Style(fg=RGB(1, 2, 3), bold=True)
    assert "38;2;1;2;3" in style_to_ansi(s, ColorMode.TRUECOLOR)
    assert "38;5;" in style_to_ansi(s, ColorMode.ANSI256)
    assert "38;" not in style_to_ansi(s, ColorMode.NONE)
    assert apply_style("x", Style(fg=RGB(1, 2, 3)), ColorMode.NONE) == "x"
    assert "38;" not in apply_style("x", s, ColorMode.NONE)
    assert apply_style("x", s, ColorMode.TRUECOLOR).endswith("\x1b[0m")


@pytest.mark.req("FR-COLOR-011")
def test_gradient_endpoints_and_midpoint() -> None:
    g = Gradient([(0.0, RGB(0, 0, 0)), (1.0, RGB(255, 255, 255))])
    assert g.at(0.0) == RGB(0, 0, 0)
    assert g.at(1.0) == RGB(255, 255, 255)
    assert g.at(0.5) == RGB(128, 128, 128)
    assert g.at(-5) == RGB(0, 0, 0) and g.at(5) == RGB(255, 255, 255)


# -- width / sanitize ---------------------------------------------------------------------


@pytest.mark.req("FR-BUF-010", "D-06")
def test_display_width() -> None:
    assert display_width("abc") == 3
    assert display_width("日本") == 4
    assert display_width("é") == 1
    assert display_width("") == 0


@pytest.mark.req("FR-SAN-001", "FR-SAN-004", "D-07")
def test_sanitize_strips_escapes_and_controls() -> None:
    assert sanitize_text("a\x1b[31mred\x1b[0mb") == "aredb"
    assert sanitize_text("a\x1b]0;title\x07b") == "ab"
    assert "\x1b" not in sanitize_text("x\x1by")
    assert "\x00" not in sanitize_text("a\x00b")
    assert sanitize_text("a\nb", newlines="space") == "a b"
    assert sanitize_text("a‮b") == "ab"


@pytest.mark.req("FR-SAN-003", "FR-BUF-011")
def test_title_and_tabs() -> None:
    assert "\x07" not in sanitize_title("hi\x07there")
    assert len(sanitize_title("x" * 1000, max_length=10)) <= 10
    assert expand_tabs("a\tb", 4) == "a   b"


# -- buffer ---------------------------------------------------------------------------------


@pytest.mark.req("FR-BUF-001", "FR-BUF-002", "FR-BUF-003")
def test_buffer_basics_and_bounds() -> None:
    b = Buffer(5, 2)
    assert (b.width, b.height) == (5, 2)
    assert b.get_cell(0, 0) == Cell(" ", Style())
    with pytest.raises(IndexError):
        b.get_cell(2, 0)
    b.set_cell(9, 9, Cell("x"))  # out of range writes are ignored
    with pytest.raises(ValueError):
        Buffer(-1, 1)


@pytest.mark.req("FR-BUF-004", "FR-BUF-005")
def test_write_text_clips_and_returns_advance() -> None:
    b = Buffer(4, 1)
    assert b.write_text(0, 2, "abcdef") == 6
    assert b.to_lines() == ["  ab"]
    b.write_text(0, -2, "wxyz")
    assert b.to_lines()[0].startswith("yz")


@pytest.mark.req("FR-SAN-001", "FR-BUF-011", "D-07")
def test_write_text_sanitises() -> None:
    b = Buffer(10, 1)
    b.write_text(0, 0, "a\x1b[31mb")
    assert "\x1b" not in "".join(c.glyph for c in b.row(0))


@pytest.mark.req("FR-BUF-009")
def test_wide_glyph_cells() -> None:
    b = Buffer(6, 1)
    b.write_text(0, 1, "日")
    assert b.get_cell(0, 1).glyph == "日"
    assert b.get_cell(0, 2).glyph == CONTINUATION
    b.write_text(0, 2, "x")  # overwriting the continuation blanks the lead cell
    assert b.get_cell(0, 1).glyph == " " and b.get_cell(0, 2).glyph == "x"
    b.write_text(0, 0, "日")
    b.write_text(0, 0, "y")  # overwriting the lead blanks the continuation
    assert b.get_cell(0, 1).glyph == " "


@pytest.mark.req("FR-BUF-009")
def test_wide_glyph_cut_by_edge_becomes_space() -> None:
    b = Buffer(3, 1)
    b.write_text(0, 2, "日")
    assert b.get_cell(0, 2).glyph == " "


@pytest.mark.req("FR-BUF-009")
def test_combining_marks_join_base() -> None:
    b = Buffer(3, 1)
    b.write_text(0, 0, "éx")
    assert b.get_cell(0, 0).glyph == "é"
    assert b.get_cell(0, 1).glyph == "x"


@pytest.mark.req("FR-BUF-006", "FR-BUF-007")
def test_fill_clear_resize_copy() -> None:
    b = Buffer(4, 2)
    b.fill(Rect(1, 0, 2, 2), Cell("#"))
    assert b.to_lines() == [" ## ", " ## "]
    c = b.copy()
    assert c == b and c is not b
    b.clear()
    assert c != b
    c.resize(2, 3)
    assert (c.width, c.height) == (2, 3)


@pytest.mark.req("FR-LAYOUT-005")
def test_view_translates_and_clips() -> None:
    b = Buffer(10, 4)
    v = b.view(Rect(2, 1, 3, 2))
    assert (v.width, v.height) == (3, 2)
    v.write_text(0, 0, "abcdef")
    assert b.to_lines()[1] == "  abc     "
    v.write_text(5, 0, "zz")  # outside the view
    assert "z" not in "".join(b.to_lines())
    sub = v.view(Rect(1, 0, 1, 1))
    sub.write_text(0, 0, "Q")
    assert b.get_cell(1, 3).glyph == "Q"


_text = st.text(alphabet=st.sampled_from(list("ab日本é ")), max_size=12)


@pytest.mark.req("FR-BUF-009")
@given(_text, st.integers(-5, 12), st.integers(0, 3))
@settings(max_examples=150, deadline=None)
def test_buffer_invariants_hold_for_any_write(text: str, col: int, row: int) -> None:
    b = Buffer(8, 3)
    b.write_text(row, col, text)
    for r in range(3):
        cells = b.row(r)
        for i, c in enumerate(cells):
            if c.glyph == CONTINUATION:
                assert i > 0 and display_width(cells[i - 1].glyph) == 2
            elif display_width(c.glyph) == 2:
                assert i + 1 < len(cells) and cells[i + 1].glyph == CONTINUATION


# -- diff -----------------------------------------------------------------------------------


@pytest.mark.req("FR-RENDER-004")
def test_first_frame_is_full_repaint() -> None:
    b = Buffer(3, 2)
    ops = diff_buffers(None, b)
    assert sum(len(o.text) for o in ops) == 6
    assert diff_buffers(Buffer(2, 2), b) != []


@pytest.mark.req("FR-RENDER-005")
def test_identical_frames_have_no_ops() -> None:
    b = Buffer(5, 2)
    b.write_text(0, 0, "hi")
    assert diff_buffers(b.copy(), b) == []


@pytest.mark.req("FR-RENDER-003", "FR-RENDER-014")
def test_changes_merge_runs_of_equal_style() -> None:
    prev = Buffer(10, 1)
    cur = prev.copy()
    cur.write_text(0, 2, "abc", Style(bold=True))
    cur.write_text(0, 5, "de")
    ops = diff_buffers(prev, cur)
    assert [(o.col, o.text, o.style.bold) for o in ops] == [(2, "abc", True), (5, "de", False)]
    assert diff_buffers(prev, cur) == ops  # deterministic


@pytest.mark.req("FR-RENDER-008")
def test_region_limits_diff() -> None:
    prev = Buffer(10, 2)
    cur = prev.copy()
    cur.write_text(0, 0, "aaaaaaaaaa")
    cur.write_text(1, 0, "bbbbbbbbbb")
    ops = diff_buffers(prev, cur, Rect(0, 1, 10, 1))
    assert {o.row for o in ops} == {1}


@pytest.mark.req("FR-RENDER-002", "FR-BUF-009")
def test_wide_glyph_rewritten_as_unit() -> None:
    prev = Buffer(6, 1)
    prev.write_text(0, 0, "日")
    cur = prev.copy()
    cur.write_text(0, 0, "日", Style(bold=True))
    ops = diff_buffers(prev, cur)
    assert [(o.col, o.text) for o in ops] == [(0, "日")]
    cur2 = prev.copy()
    cur2.write_text(0, 1, "x")  # touches only the continuation half
    ops2 = diff_buffers(prev, cur2)
    grid = apply_ops(buffer_grid(prev), ops2)
    assert grid == buffer_grid(cur2)


_styles = st.sampled_from([Style(), Style(bold=True), Style(fg=RGB(1, 2, 3))])
_writes = st.lists(st.tuples(st.integers(0, 2), st.integers(-1, 9), _text, _styles), max_size=6)


def _paint(writes: list[tuple[int, int, str, Style]]) -> Buffer:
    b = Buffer(8, 3)
    for r, c, t, s in writes:
        b.write_text(r, c, t, s)
    return b


@pytest.mark.req("FR-RENDER-002")
@given(_writes, _writes)
@settings(max_examples=200, deadline=None)
def test_diff_round_trip(a: list, b: list) -> None:  # type: ignore[type-arg]
    prev, cur = _paint(a), _paint(b)
    result = apply_ops(buffer_grid(prev), diff_buffers(prev, cur))
    assert result == buffer_grid(cur)


# -- renderer -----------------------------------------------------------------------------


@pytest.mark.req("FR-RENDER-005", "FR-RENDER-006", "FR-COLOR-009", "FR-TERM-002")
def test_renderer_writes_once_and_is_silent_when_unchanged() -> None:
    renderer, out = make_renderer()
    b = Buffer(5, 2)
    b.write_text(0, 0, "hi", Style(bold=True))
    assert renderer.render(b) > 0
    first = out.getvalue()
    assert "hi" in first and "\x1b[" in first
    out.truncate(0)
    out.seek(0)
    assert renderer.render(b) == 0
    assert out.getvalue() == ""


@pytest.mark.req("FR-RENDER-002")
def test_renderer_only_emits_changed_cells() -> None:
    renderer, out = make_renderer()
    b = Buffer(10, 2)
    renderer.render(b)
    out.truncate(0)
    out.seek(0)
    b.write_text(1, 3, "X")
    renderer.render(b)
    assert "X" in out.getvalue() and len(out.getvalue()) < 40


@pytest.mark.req("FR-RENDER-004")
def test_invalidate_forces_full_repaint() -> None:
    renderer, out = make_renderer()
    b = Buffer(4, 1)
    b.write_text(0, 0, "abcd")
    renderer.render(b)
    out.truncate(0)
    out.seek(0)
    renderer.invalidate()
    renderer.render(b)
    assert "abcd" in out.getvalue()


@pytest.mark.req("FR-RENDER-008", "D-03")
def test_render_region_updates_cache_for_region_only() -> None:
    renderer, out = make_renderer()
    b = Buffer(6, 2)
    renderer.render(b)
    b.write_text(0, 0, "AA")
    b.write_text(1, 0, "BB")
    renderer.render_region(b, Rect(0, 0, 6, 1))
    out.truncate(0)
    out.seek(0)
    renderer.render(b)  # row 1 still pending, row 0 already shown
    assert "BB" in out.getvalue() and "AA" not in out.getvalue()


@pytest.mark.req("FR-RENDER-013")
def test_bottom_right_cell_trimmed_when_autowrap_on() -> None:
    renderer, out = make_renderer(autowrap_disabled=False)
    b = Buffer(3, 1)
    b.write_text(0, 0, "abc")
    renderer.render(b)
    assert "abc" not in out.getvalue() and "ab" in out.getvalue()


@pytest.mark.req("FR-TERM-009")
def test_non_ansi_finish_prints_plain_text() -> None:
    renderer, out = make_renderer(ansi=False, color_mode=ColorMode.NONE)
    b = Buffer(5, 2)
    b.write_text(0, 0, "hello", Style(bold=True))
    renderer.render(b)
    renderer.finish()
    assert "\x1b" not in out.getvalue()
    assert "hello" in out.getvalue()


@pytest.mark.req("FR-COLOR-003")
def test_renderer_color_none_emits_no_sgr_colors() -> None:
    renderer, out = make_renderer(color_mode=ColorMode.NONE)
    b = Buffer(3, 1)
    b.write_text(0, 0, "x", Style(fg=RGB(1, 2, 3)))
    renderer.render(b)
    assert "38;2" not in out.getvalue()


@pytest.mark.req("FR-COLOR-003")
def test_windows_without_term_gets_truecolor_on_modern_consoles() -> None:
    def mode(env: dict[str, str], build: int = 0) -> ColorMode:
        return detect_color_mode(env=env, isatty=True, platform="win32", windows_build=build)

    assert mode({"WT_SESSION": "abc"}) == ColorMode.TRUECOLOR  # Windows Terminal
    assert mode({}, build=22631) == ColorMode.TRUECOLOR  # Windows 11 console
    assert mode({}, build=10586) == ColorMode.ANSI16  # too old for 24-bit color
    assert mode({"WT_SESSION": "abc", "NO_COLOR": "1"}) == ColorMode.NONE  # opt-out still wins
    assert mode({"TERM": "dumb", "WT_SESSION": "abc"}) == ColorMode.NONE
    assert (
        detect_color_mode(env={}, isatty=True, platform="linux", windows_build=99999)
        == ColorMode.ANSI16
    )
