"""M3: assets, progress state/stats, indicators, inline manager, tqdm subset, non-TTY mode."""

from __future__ import annotations

import io
import re
import sys
import threading
from collections.abc import Callable, Iterator

import pytest

from conftest import FakeTTY
from widgets.assets.bars import get_bar_style, list_bar_styles
from widgets.assets.spinners import get_spinner, list_spinners, spinner_frames
from widgets.base_elements.color_manager import Gradient
from widgets.base_elements.effects import ManualClock
from widgets.base_elements.widget_types import RGB
from widgets.errors import LifecycleError
from widgets.progress import tqdm as tqdm_module
from widgets.progress.indicators import (
    CircularIndicator,
    HorizontalBar,
    SpinnerIndicator,
    VerticalBar,
)
from widgets.progress.inline import ProgressManager
from widgets.progress.state import ProgressState, format_duration
from widgets.progress.tqdm import tqdm, trange
from widgets.render.buffer import Buffer
from widgets.render.width import display_width
from widgets.terminal import ansi
from widgets.terminal.session import TerminalMode, TerminalSession

# -- a tiny virtual terminal ----------------------------------------------------------------

_TOKEN = re.compile(r"\x1b\[\?\d+[hl]|\x1b\[([\d;]*)([A-Za-z])|\r|\n|[^\x1b\r\n]+")


class VScreen:
    """Applies the control sequences the inline renderer uses; exposes the visible lines."""

    def __init__(self) -> None:
        self.rows = [""]
        self.r = self.c = 0
        self.cursor_visible = True

    def feed(self, data: str) -> VScreen:
        for m in _TOKEN.finditer(data):
            tok = m.group(0)
            if tok == "\r":
                self.c = 0
            elif tok == "\n":
                self.r += 1
                self.c = 0
                if self.r == len(self.rows):
                    self.rows.append("")
            elif tok == "\x1b[?25l":
                self.cursor_visible = False
            elif tok == "\x1b[?25h":
                self.cursor_visible = True
            elif tok.startswith("\x1b[?"):
                pass
            elif tok.startswith("\x1b["):
                arg, final = m.group(1), m.group(2)
                if final == "A":
                    self.r = max(0, self.r - int(arg or 1))
                elif final == "J" and (arg in ("", "0")):
                    self.rows[self.r] = self.rows[self.r][: self.c]
                    del self.rows[self.r + 1 :]
                # SGR ('m') and everything else: no visible effect
            else:
                row = self.rows[self.r].ljust(self.c)
                self.rows[self.r] = row[: self.c] + tok + row[self.c + len(tok) :]
                self.c += len(tok)
        return self

    @property
    def lines(self) -> list[str]:
        out = [row.rstrip() for row in self.rows]
        while out and not out[-1]:
            out.pop()
        return out


def screen_of(stream: io.StringIO) -> VScreen:
    return VScreen().feed(stream.getvalue())


# -- fixtures -------------------------------------------------------------------------------------

ENV = {"TERM": "xterm-256color", "COLUMNS": "40", "LINES": "24"}


@pytest.fixture(autouse=True)
def managers() -> Iterator[list[ProgressManager]]:
    created: list[ProgressManager] = []
    yield created
    for m in created:
        m.close()
    for m in list(tqdm_module._MANAGERS.values()):
        m.close()
    tqdm_module._MANAGERS.clear()


@pytest.fixture
def make_manager(
    managers: list[ProgressManager],
) -> Callable[..., tuple[ProgressManager, io.StringIO, ManualClock]]:
    def factory(
        columns: int = 40, *, tty: bool = True, **kw: object
    ) -> tuple[ProgressManager, io.StringIO, ManualClock]:
        stream: io.StringIO = FakeTTY() if tty else io.StringIO()
        env = {**ENV, "COLUMNS": str(columns)}
        session = TerminalSession(
            TerminalMode.INLINE, stream=stream, env=env, handle_signals=False, use_atexit=False
        )
        clock = ManualClock()
        manager = ProgressManager(session=session, clock=clock, **kw)  # type: ignore[arg-type]
        managers.append(manager)
        return manager, stream, clock

    return factory


@pytest.fixture
def tty_env(monkeypatch: pytest.MonkeyPatch) -> None:
    for key, value in ENV.items():
        monkeypatch.setenv(key, value)
    monkeypatch.delenv("NO_COLOR", raising=False)


def state(
    total: float | None = 100, clock: ManualClock | None = None, **kw: object
) -> ProgressState:
    return ProgressState(total, clock=clock or ManualClock(), **kw)  # type: ignore[arg-type]


def render_line(widget: HorizontalBar, width: int) -> str:
    buf = Buffer(width, 1)
    widget.render(buf)
    return buf.to_lines()[0]


# -- assets ----------------------------------------------------------------------------------------


@pytest.mark.req("FR-ASSET-001")
def test_bar_style_catalog_sizes_and_errors() -> None:
    assert len(list_bar_styles("horizontal")) >= 8 and len(list_bar_styles("vertical")) >= 8
    with pytest.raises(KeyError) as info:
        get_bar_style("nope")
    assert "smooth" in str(info.value)  # lists the valid names
    with pytest.raises(KeyError, match="eighths"):
        get_bar_style("nope", "vertical")
    with pytest.raises(ValueError):
        list_bar_styles("diagonal")


@pytest.mark.req("FR-ASSET-009")
def test_every_bar_and_spinner_has_an_ascii_fallback() -> None:
    for orientation in ("horizontal", "vertical"):
        for name in list_bar_styles(orientation):
            fill, empty, partials, left, right = get_bar_style(name, orientation).glyphs(True)
            assert all(s.isascii() for s in (fill, empty, left, right, *partials)), name
    for name in list_spinners():
        assert all(f.isascii() for f in spinner_frames(name, ascii_only=True)), name


@pytest.mark.req("FR-ASSET-006")
def test_spinner_catalog() -> None:
    assert len(list_spinners()) >= 20
    spec = get_spinner("dots")
    assert len(spec.frames) > 1 and spec.interval > 0 and spec.ascii_safe is False
    assert get_spinner("line").ascii_safe is True
    with pytest.raises(KeyError, match="line"):
        get_spinner("nope")


# -- state and statistics ----------------------------------------------------------------------------


@pytest.mark.req("FR-PROG-001")
def test_counter_semantics() -> None:
    s = state(10)
    s.update()
    s.update(4)
    assert s.n == 5
    s.set(8)
    assert s.n == 8 and s.fraction == 0.8
    with pytest.raises(ValueError):
        s.update(-9)
    with pytest.raises(ValueError):
        s.set(-1)
    assert s.n == 8  # unchanged by the failed calls


@pytest.mark.req("FR-PROG-001")
def test_overshoot_keeps_total_and_clamps_percentage() -> None:
    s = state(10)
    s.update(15)
    assert s.total == 10 and s.n == 15 and s.fraction == 1.0


@pytest.mark.req("FR-PROG-001")
def test_finish_and_close() -> None:
    s = state(10)
    s.finish()
    assert s.n == 10 and s.finished
    unknown = state(None)
    unknown.finish()
    assert unknown.n == 0 and unknown.fraction is None


@pytest.mark.req("FR-PROG-004")
def test_speed_is_an_exponential_moving_average() -> None:
    clock = ManualClock()
    s = ProgressState(100, clock=clock, smoothing=0.3)
    assert s.speed is None and s.eta is None
    clock.advance(1.0)
    s.update(10)  # 10 items/s
    assert s.speed == pytest.approx(10.0)
    clock.advance(1.0)
    s.update(20)  # 20 items/s -> 0.3*20 + 0.7*10
    assert s.speed == pytest.approx(13.0)


@pytest.mark.req("FR-PROG-004")
def test_eta_elapsed_and_percentage() -> None:
    clock = ManualClock()
    s = ProgressState(100, clock=clock)
    clock.advance(2.0)
    s.update(50)
    assert s.elapsed == pytest.approx(2.0)
    assert s.eta == pytest.approx(50 / 25)
    assert state(None).eta is None


@pytest.mark.req("FR-PROG-004")
def test_stalled_after_timeout() -> None:
    clock = ManualClock()
    s = ProgressState(10, clock=clock, stall_timeout=5)
    clock.advance(5)
    assert not s.stalled
    clock.advance(0.1)
    assert s.stalled
    s.update()
    assert not s.stalled
    s.close()
    clock.advance(100)
    assert not s.stalled  # finished tasks are never "stalled"


@pytest.mark.req("FR-PROG-004")
def test_state_validates_configuration() -> None:
    for bad in (
        {"total": -1},
        {"smoothing": 0},
        {"smoothing": 1.5},
        {"stall_timeout": 0},
        {"n": -1},
    ):
        with pytest.raises(ValueError):
            ProgressState(clock=ManualClock(), **bad)  # type: ignore[arg-type]
    assert ProgressState(smoothing=1.0).smoothing == 1.0


@pytest.mark.req("FR-PROG-003")
def test_description_and_postfix() -> None:
    s = state(10, description="copy")
    s.set_postfix(loss=0.5, lr=1)
    assert s.description == "copy" and s.postfix == "loss=0.5, lr=1"
    s.set_postfix("warming up")
    assert s.postfix == "warming up"
    s.set_postfix("x", a=1)
    assert s.postfix == "x, a=1"


def test_format_duration() -> None:
    assert format_duration(5) == "00:05" and format_duration(3725) == "1:02:05"
    assert format_duration(None) == "?" and format_duration(float("inf")) == "?"


@pytest.mark.req("FR-PROG-017")
@pytest.mark.slow
def test_state_updates_are_thread_safe() -> None:
    s = ProgressState(None)

    def work() -> None:
        for _ in range(2000):
            s.update()

    threads = [threading.Thread(target=work) for _ in range(8)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert s.n == 16000


# -- indicators ------------------------------------------------------------------------------------


@pytest.mark.req("FR-PROG-005")
def test_horizontal_bar_content_and_fill() -> None:
    s = state(100, description="copy")
    s.update(50)
    bar = HorizontalBar(s, style="classic", unit="B")
    line = render_line(bar, 70)
    assert line.startswith("copy: [") and " 50%" in line and "50/100" in line and "B/s" in line
    inner = line[line.index("[") + 1 : line.index("]")]
    assert inner.count("=") == round(len(inner) / 2) or abs(inner.count("=") - len(inner) / 2) <= 1
    assert set(inner) <= {"=", "."}


@pytest.mark.req("FR-PROG-005")
def test_bar_options_disable_fields() -> None:
    s = state(10)
    s.update(5)
    bar = HorizontalBar(
        s, show_percentage=False, show_count=False, show_time=False, show_speed=False
    )
    assert render_line(bar, 30).rstrip().endswith("|")


@pytest.mark.req("FR-PROG-005")
def test_sub_cell_glyph_for_smooth_style() -> None:
    s = state(8)
    s.update(1)
    bar = HorizontalBar(
        s,
        style="smooth",
        show_percentage=False,
        show_count=False,
        show_time=False,
        show_speed=False,
    )
    line = render_line(bar, 10)  # 8 cells between the bars: 1/8 of 8 cells = one full cell
    s.set(1.5)
    line2 = render_line(bar, 10)
    assert line != line2 and any(ch in line2 for ch in "▏▎▍▌▋▊▉█")


@pytest.mark.req("FR-PROG-005")
def test_gradient_colors_the_fill() -> None:
    s = state(10)
    s.update(10)
    g = Gradient(((0.0, RGB(255, 0, 0)), (1.0, RGB(0, 0, 255))))
    bar = HorizontalBar(
        s, gradient=g, show_percentage=False, show_count=False, show_time=False, show_speed=False
    )
    buf = Buffer(12, 1)
    bar.render(buf)
    colors = {c.style.fg for c in buf.row(0) if c.glyph == "█"}
    assert len(colors) > 3


@pytest.mark.req("FR-PROG-018")
@pytest.mark.parametrize(
    "description", ["", "a short one", "a very very long description indeed " * 3]
)
def test_bar_never_exceeds_the_available_width(description: str) -> None:
    s = state(1234, description=description)
    s.update(600)
    s.set_postfix(loss=0.1234, epoch=3)
    bar = HorizontalBar(s, unit_scale=True)
    for width in range(1, 100):
        buf = Buffer(width, 1)
        bar.render(buf)  # must not raise
        text = buf.to_lines()[0]
        assert display_width(text) <= width


@pytest.mark.req("FR-PROG-018")
def test_fields_are_dropped_in_priority_order() -> None:
    s = state(100, description="job")
    s.update(40)
    s.set_postfix("extra")
    bar = HorizontalBar(s)
    full = render_line(bar, 100)
    assert "extra" in full and "it/s" in full
    seen = []
    for width in (100, 60, 50, 40, 32, 24, 16):
        line = render_line(bar, width)
        seen.append(("extra" in line, "it/s" in line, "<" in line, "40/100" in line, "40%" in line))
    # each field, once gone, never comes back at a smaller width
    for column in range(5):
        flags = [row[column] for row in seen]
        assert flags == sorted(flags, reverse=True)
    assert seen[0][0] and not seen[-1][0]


@pytest.mark.req("FR-PROG-018")
def test_long_description_is_truncated_with_ellipsis() -> None:
    s = state(10, description="x" * 80)
    line = render_line(HorizontalBar(s), 30)
    assert "…" in line and display_width(line) <= 30


@pytest.mark.req("FR-PROG-009")
def test_unknown_styles_raise_keyerror_listing_names() -> None:
    s = state(10)
    with pytest.raises(KeyError, match="smooth"):
        HorizontalBar(s, style="nope")
    with pytest.raises(KeyError, match="eighths"):
        VerticalBar(s, style="nope")
    with pytest.raises(KeyError, match="line"):
        SpinnerIndicator(spinner="nope")


@pytest.mark.req("FR-PROG-005")
def test_unknown_total_renders_an_indeterminate_bar() -> None:
    s = state(None)
    s.update(7)
    bar = HorizontalBar(s)
    first = render_line(bar, 40)
    bar.update(0.5)
    assert "7" in first and "%" not in first
    assert render_line(bar, 40) != first  # the moving block advanced


@pytest.mark.req("FR-PROG-009")
def test_ascii_mode_uses_only_ascii_glyphs() -> None:
    s = state(10)
    s.update(5)
    assert render_line(HorizontalBar(s, ascii_only=True), 50).isascii()


@pytest.mark.req("FR-PROG-006")
def test_vertical_bar_bottom_up_and_top_down() -> None:
    s = state(8)
    s.update(4)
    up = VerticalBar(s, 4, style="solid")
    assert up.column() == [" ", " ", "█", "█"]
    down = VerticalBar(s, 4, style="solid", orientation="top-down")
    assert down.column() == ["█", "█", " ", " "]
    with pytest.raises(ValueError):
        VerticalBar(s, 4, orientation="sideways")
    buf = Buffer(1, 4)
    up.render(buf)
    assert buf.to_lines() == [" ", " ", "█", "█"]


@pytest.mark.req("FR-PROG-006")
def test_vertical_bar_sub_cell_glyphs() -> None:
    s = state(4)
    s.set(1.5)  # 1.5/4 of 4 rows = 1.5 rows -> one full row and a half-height glyph
    col = VerticalBar(s, 4, style="eighths").column()
    assert col[-1] == "█" and col[-2] == "▄" and col[0] == " "


@pytest.mark.req("FR-PROG-007")
def test_circular_indicator_fills_clockwise() -> None:
    s = state(100)
    c = CircularIndicator(s, 5)
    ring = c.ring()
    assert len(ring) == len(set(ring)) and ring[0][0] == 0  # starts at the top row

    def lit(n: float) -> int:
        s.set(n)
        buf = Buffer(c.width, c.height)
        c.render(buf)
        return sum(cell.glyph == "●" for r in range(c.height) for cell in buf.row(r))

    assert lit(0) == 0 and lit(100) == len(ring)
    assert 0 < lit(50) < len(ring)
    with pytest.raises(ValueError):
        CircularIndicator(s, 2)


@pytest.mark.req("FR-PROG-007")
def test_circular_indicator_shows_percentage() -> None:
    s = state(100)
    s.set(42)
    c = CircularIndicator(s, 5, ascii_only=True)
    buf = Buffer(c.width, c.height)
    c.render(buf)
    assert "42%" in "".join(buf.to_lines())


@pytest.mark.req("FR-PROG-008", "FR-SPINNER-001", "FR-SPINNER-003")
def test_spinner_advances_by_time_and_is_configurable() -> None:
    sp = SpinnerIndicator(spinner="line", speed=10, text="loading")
    assert sp.frame == "-"
    sp.update(0.1)
    assert sp.frame == "\\"
    sp.update(0.05)
    sp.update(0.05)
    assert sp.frame == "|"
    sp.set_speed(100)
    sp.update(0.01)
    assert sp.frame == "/"
    sp.set_text("done soon")
    buf = Buffer(30, 1)
    sp.render(buf)
    assert buf.to_lines()[0].startswith("/ done soon")
    with pytest.raises(ValueError):
        SpinnerIndicator(speed=0)


@pytest.mark.req("FR-PROG-008", "FR-ASSET-009", "FR-FX-006")
def test_spinner_ascii_fallback_and_reduced_motion() -> None:
    sp = SpinnerIndicator(spinner="dots", ascii_only=True)
    for _ in range(12):
        sp.update(0.1)
        assert sp.frame.isascii()
    still = SpinnerIndicator(spinner="line", reduced_motion=True)
    first = still.frame
    still.update(5.0)
    assert still.frame == first


# -- inline manager -----------------------------------------------------------------------------------


@pytest.mark.req("FR-PROG-010")
def test_each_indicator_gets_its_own_row(make_manager: Callable[..., tuple]) -> None:  # type: ignore[type-arg]
    mgr, stream, _clock = make_manager()
    a, b, c = (HorizontalBar(state(10, description=d)) for d in "abc")
    mgr.add(a)
    mgr.add(b)
    assert mgr.height == 2
    mgr.add(c, position=1)  # inserted between the others; nothing overlaps
    assert mgr.height == 3
    lines = screen_of(stream).lines
    assert [line[0] for line in lines] == ["a", "c", "b"]
    mgr.remove(c, leave=False)
    assert mgr.height == 2
    assert [line[0] for line in screen_of(stream).lines] == ["a", "b"]


@pytest.mark.req("FR-PROG-010")
def test_region_height_follows_multiline_indicators(make_manager: Callable[..., tuple]) -> None:  # type: ignore[type-arg]
    mgr, stream, _ = make_manager()
    mgr.add(HorizontalBar(state(10)))
    mgr.add(CircularIndicator(state(10), 3))
    assert mgr.height == 1 + 3
    assert len(screen_of(stream).lines) == 4


@pytest.mark.req("FR-PROG-011")
def test_write_prints_above_the_region_without_garbling(make_manager: Callable[..., tuple]) -> None:  # type: ignore[type-arg]
    mgr, stream, clock = make_manager()
    bar_state = state(10, clock=clock, description="job")
    mgr.add(HorizontalBar(bar_state))
    for i in range(3):
        bar_state.update()
        clock.advance(1)
        mgr.write(f"message {i}")
        mgr.refresh()
    lines = screen_of(stream).lines
    assert lines[:3] == ["message 0", "message 1", "message 2"]
    assert lines[3].startswith("job:") and "3/10" in lines[3]
    assert len(lines) == 4  # the bar exists exactly once


@pytest.mark.req("FR-PROG-011")
def test_multiline_and_hostile_messages(make_manager: Callable[..., tuple]) -> None:  # type: ignore[type-arg]
    mgr, stream, _ = make_manager()
    mgr.add(HorizontalBar(state(10)))
    mgr.write("first\nsecond\x1b[2J\x1b]0;evil\x07")
    lines = screen_of(stream).lines
    assert lines[:2] == ["first", "second"]
    assert "\x1b[2J" not in stream.getvalue()


@pytest.mark.req("FR-PROG-012")
def test_close_leaves_completed_bars_and_restores_the_cursor(
    make_manager: Callable[..., tuple],
) -> None:  # type: ignore[type-arg]
    mgr, stream, _ = make_manager()
    s = state(10, description="done")
    mgr.add(HorizontalBar(s))
    s.finish()
    mgr.close()
    screen = screen_of(stream)
    assert screen.lines[-1].startswith("done:") and "10/10" in screen.lines[-1]
    assert screen.cursor_visible
    assert screen.r == len(screen.rows) - 1 and screen.rows[-1] == ""  # cursor below the region
    assert stream.getvalue().endswith(ansi.SHOW_CURSOR)
    mgr.close()  # idempotent
    with pytest.raises(LifecycleError):
        mgr.add(HorizontalBar(state(1)))


@pytest.mark.req("FR-PROG-012")
def test_leave_false_erases_the_bar(make_manager: Callable[..., tuple]) -> None:  # type: ignore[type-arg]
    mgr, stream, _ = make_manager()
    mgr.add(HorizontalBar(state(10, description="keep")))
    mgr.add(HorizontalBar(state(10, description="gone")), leave=False)
    mgr.close()
    lines = screen_of(stream).lines
    assert any(line.startswith("keep") for line in lines)
    assert not any(line.startswith("gone") for line in lines)


@pytest.mark.req("FR-PROG-012", "FR-CLEAN-008")
def test_session_cleanup_restores_the_cursor_after_an_interruption(  # type: ignore[type-arg]
    make_manager: Callable[..., tuple],
) -> None:
    mgr, stream, _ = make_manager()
    mgr.add(HorizontalBar(state(10)))
    assert not screen_of(stream).cursor_visible
    mgr.session.close()  # what atexit / a signal handler / an exception path runs
    assert screen_of(stream).cursor_visible and mgr.closed


@pytest.mark.req("FR-PROG-015")
def test_default_stream_is_stderr(
    monkeypatch: pytest.MonkeyPatch, managers: list[ProgressManager]
) -> None:
    fake = FakeTTY()
    monkeypatch.setattr(sys, "stderr", fake)
    for key, value in ENV.items():
        monkeypatch.setenv(key, value)
    mgr = ProgressManager()
    managers.append(mgr)
    mgr.add(HorizontalBar(state(10, description="err")))
    assert "err:" in fake.getvalue() and mgr.session.stream is fake


@pytest.mark.req("FR-PROG-017")
def test_refresh_is_rate_limited(make_manager: Callable[..., tuple]) -> None:  # type: ignore[type-arg]
    mgr, stream, clock = make_manager(mininterval=0.5)
    mgr.add(HorizontalBar(state(10)))
    size = len(stream.getvalue())
    clock.advance(0.2)
    assert mgr.refresh() is False and len(stream.getvalue()) == size
    clock.advance(0.4)
    assert mgr.refresh() is True and len(stream.getvalue()) > size
    assert mgr.refresh(force=True) is True


@pytest.mark.req("FR-PROG-017", "FR-PROG-011")
@pytest.mark.slow
def test_concurrent_updates_and_writes_keep_the_region_consistent(  # type: ignore[type-arg]
    make_manager: Callable[..., tuple],
) -> None:
    mgr, stream, _ = make_manager(mininterval=0.0)
    states = [state(None, description=f"w{i}") for i in range(3)]
    for s in states:
        mgr.add(HorizontalBar(s))

    def work(i: int) -> None:
        for k in range(150):
            states[i].update()
            mgr.refresh()
            if k % 10 == 0:
                mgr.write(f"worker {i} step {k}")

    threads = [threading.Thread(target=work, args=(i,)) for i in range(3)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    mgr.refresh(force=True)
    lines = screen_of(stream).lines
    messages = [line for line in lines if line.startswith("worker")]
    assert len(messages) == 3 * 15 and len(set(messages)) == 3 * 15  # each exactly once
    assert [line[:2] for line in lines[-3:]] == ["w0", "w1", "w2"]  # region intact at the bottom
    assert all(not line.startswith("worker") for line in lines[-3:])


@pytest.mark.req("FR-PROG-018")
def test_region_lines_never_exceed_the_terminal_width(make_manager: Callable[..., tuple]) -> None:  # type: ignore[type-arg]
    mgr, stream, _ = make_manager(columns=30)
    s = state(1000, description="a long description for narrow terminals")
    s.update(500)
    mgr.add(HorizontalBar(s))
    mgr.write("x" * 10)
    assert all(len(line) <= 29 for line in screen_of(stream).lines)


# -- non-TTY mode --------------------------------------------------------------------------------------


@pytest.mark.req("FR-PROG-016", "FR-TERM-009")
def test_non_tty_emits_plain_lines_at_the_interval(make_manager: Callable[..., tuple]) -> None:  # type: ignore[type-arg]
    mgr, stream, clock = make_manager(tty=False)
    s = state(100, clock=clock, description="job")
    mgr.add(HorizontalBar(s))  # first line right away
    clock.advance(1)
    s.update(10)
    assert mgr.refresh() is False  # inside the 10 s interval
    clock.advance(10)
    s.update(10)
    assert mgr.refresh() is True
    out = stream.getvalue()
    assert "\x1b" not in out and out.count("\n") == 2
    assert out.splitlines()[0].startswith("job:") and "20/100" in out.splitlines()[1]


@pytest.mark.req("FR-PROG-016")
def test_non_tty_prints_a_final_line_on_close(make_manager: Callable[..., tuple]) -> None:  # type: ignore[type-arg]
    mgr, stream, clock = make_manager(tty=False)
    s = state(10, clock=clock, description="job")
    bar = HorizontalBar(s)
    mgr.add(bar)
    s.finish()
    mgr.remove(bar)
    lines = stream.getvalue().splitlines()
    assert lines[-1].startswith("job:") and "10/10" in lines[-1]
    assert "\x1b" not in stream.getvalue()


@pytest.mark.req("FR-PROG-016", "FR-PROG-011")
def test_non_tty_write_is_a_plain_line(make_manager: Callable[..., tuple]) -> None:  # type: ignore[type-arg]
    mgr, stream, _ = make_manager(tty=False)
    mgr.add(HorizontalBar(state(10)))
    mgr.write("hello")
    assert "hello\n" in stream.getvalue() and "\x1b" not in stream.getvalue()


# -- tqdm subset -------------------------------------------------------------------------------------------


@pytest.mark.req("FR-PROG-002", "FR-PROG-013")
def test_iteration_yields_items_unchanged_and_finishes(tty_env: None) -> None:
    stream = FakeTTY()
    items = ["a", object(), 3]
    bar = tqdm(items, file=stream, desc="loop")
    assert bar.total == 3
    assert list(bar) == items
    assert bar.n == 3
    screen = screen_of(stream)
    assert screen.lines[-1].startswith("loop:") and "3/3" in screen.lines[-1]
    assert screen.cursor_visible and not tqdm_module._MANAGERS  # manager released


@pytest.mark.req("FR-PROG-002")
def test_total_from_len_explicit_total_and_generators(tty_env: None) -> None:
    stream = FakeTTY()
    assert tqdm(range(5), file=stream).total == 5
    assert tqdm(range(5), total=9, file=stream).total == 9
    gen = tqdm((i for i in range(4)), file=stream)
    assert gen.total is None
    assert list(gen) == [0, 1, 2, 3] and gen.n == 4


@pytest.mark.req("FR-PROG-002")
def test_break_closes_the_bar(tty_env: None) -> None:
    stream = FakeTTY()
    bar = tqdm(range(100), file=stream)
    for i in bar:
        if i == 3:
            break
    # a for-loop `break` leaves the generator suspended: closing is the generator's job
    iterator = iter(bar)
    next(iterator)
    iterator.close()
    assert bar.n >= 3 and screen_of(stream).cursor_visible and not tqdm_module._MANAGERS


@pytest.mark.req("FR-PROG-002", "FR-PROG-012")
def test_exception_in_the_iterable_closes_the_bar(tty_env: None) -> None:
    stream = FakeTTY()

    def boom() -> Iterator[int]:
        yield 1
        raise RuntimeError("source failed")

    with pytest.raises(RuntimeError, match="source failed"):
        list(tqdm(boom(), file=stream, total=5))
    assert screen_of(stream).cursor_visible and not tqdm_module._MANAGERS


@pytest.mark.req("FR-PROG-002", "FR-PROG-012")
def test_exception_in_the_loop_body_restores_the_cursor_with_a_context_manager(
    tty_env: None,
) -> None:
    stream = FakeTTY()
    with pytest.raises(ValueError), tqdm(total=3, file=stream) as bar:
        bar.update()
        raise ValueError("body failed")
    assert bar.n == 1 and screen_of(stream).cursor_visible


@pytest.mark.req("FR-PROG-013")
def test_trange_and_manual_updates(tty_env: None) -> None:
    stream = FakeTTY()
    assert list(trange(2, 8, 2, file=stream)) == [2, 4, 6]
    with tqdm(total=10, file=stream, initial=2, unit="B", unit_scale=True) as bar:
        assert bar.n == 2
        bar.update(3)
        assert bar.n == 5
        bar.reset(total=20)
        assert bar.n == 0 and bar.total == 20


@pytest.mark.req("FR-PROG-003", "FR-PROG-013")
def test_tqdm_description_and_postfix(tty_env: None, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("COLUMNS", "120")
    stream = FakeTTY()
    with tqdm(total=10, file=stream, postfix={"acc": 0.5}) as bar:
        bar.set_description("epoch 1")
        bar.set_postfix(loss=0.25)
        bar.set_postfix_str("note")
        bar.refresh()
        last = screen_of(stream).lines[-1]
    assert "epoch 1" in last and "note" in last


@pytest.mark.req("FR-PROG-013")
def test_disable_and_unknown_arguments() -> None:
    stream = FakeTTY()
    assert list(tqdm(range(3), file=stream, disable=True)) == [0, 1, 2]
    assert stream.getvalue() == ""
    with pytest.raises(TypeError):
        tqdm(range(3), no_such_option=1)  # type: ignore[call-arg]
    with pytest.raises(TypeError):
        list(tqdm(total=3, file=stream, disable=True))  # no iterable to iterate


@pytest.mark.req("FR-PROG-013", "FR-PROG-011")
def test_tqdm_write_prints_above_the_bars(tty_env: None) -> None:
    stream = FakeTTY()
    with tqdm(total=4, file=stream, desc="work", mininterval=0) as bar:
        bar.update()
        tqdm.write("log line", file=stream)
        bar.update()
        lines = screen_of(stream).lines
        assert lines[0] == "log line" and lines[1].startswith("work:") and len(lines) == 2
    tqdm.write("after", file=stream)  # no active bar: plain write
    assert stream.getvalue().endswith("after\n")


@pytest.mark.req("FR-PROG-010", "FR-PROG-013")
def test_concurrent_bars_share_the_region_and_position(tty_env: None) -> None:
    stream = FakeTTY()
    top = tqdm(total=2, file=stream, desc="top", position=0)
    bottom = tqdm(total=2, file=stream, desc="bottom", position=1)
    middle = tqdm(total=2, file=stream, desc="middle", position=1)
    lines = screen_of(stream).lines
    assert [line.split(":")[0] for line in lines] == ["top", "middle", "bottom"]
    for bar in (top, middle, bottom):
        bar.close()
    assert not tqdm_module._MANAGERS and screen_of(stream).cursor_visible


@pytest.mark.req("FR-PROG-013")
def test_leave_false_and_clear(tty_env: None) -> None:
    stream = FakeTTY()
    with tqdm(total=2, file=stream, desc="temp", leave=False) as bar:
        bar.update(2)
    assert not any(line.startswith("temp") for line in screen_of(stream).lines)
    with tqdm(total=2, file=stream, desc="shown") as bar2:
        bar2.clear()
        assert not any(line.startswith("shown") for line in screen_of(stream).lines)
        bar2.refresh()
        assert any(line.startswith("shown") for line in screen_of(stream).lines)


@pytest.mark.req("FR-PROG-013", "FR-PROG-017")
def test_miniters_skips_intermediate_repaints(tty_env: None) -> None:
    stream = FakeTTY()
    with tqdm(total=100, file=stream, miniters=10, mininterval=0) as bar:
        size = len(stream.getvalue())
        for _ in range(9):
            bar.update()
        assert len(stream.getvalue()) == size  # fewer than miniters items since the last repaint
        bar.update()
        assert len(stream.getvalue()) > size


@pytest.mark.req("FR-PROG-015", "FR-PROG-016")
def test_default_output_goes_to_stderr_as_plain_text(capsys: pytest.CaptureFixture[str]) -> None:
    assert list(tqdm(range(3), desc="plain")) == [0, 1, 2]
    out = capsys.readouterr()
    assert out.out == ""  # stdout is never polluted
    assert "3/3" in out.err and "\x1b" not in out.err


@pytest.mark.req("FR-PROG-013")
def test_injected_manager_is_not_closed_by_the_bar(
    make_manager: Callable[..., tuple],  # type: ignore[type-arg]
) -> None:
    mgr, _stream, _ = make_manager()
    with tqdm(range(3), manager=mgr, desc="x") as bar:
        list(bar)
    assert not mgr.closed
    mgr.close()


# -- real pseudo-terminal ------------------------------------------------------------------------------------

_PROGRESS_SCRIPT = """
import sys, time
sys.path.insert(0, {src!r})
from widgets.progress.tqdm import tqdm
for i in tqdm(range(30), desc="work"):
    time.sleep(0.01)
    if i == 10:
        tqdm.write("msg-in-the-middle")
print("stdout-text")
"""


@pytest.mark.slow
@pytest.mark.skipif(sys.platform == "win32", reason="pty not available")
@pytest.mark.req("FR-PROG-011", "FR-PROG-012", "FR-PROG-015")
def test_tqdm_in_a_real_terminal() -> None:
    from pathlib import Path

    from test_terminal_api_layers import _pty_run

    src = str(Path(__file__).resolve().parent.parent / "src")
    code, out = _pty_run(_PROGRESS_SCRIPT.format(src=src))
    text = out.decode("utf-8", "replace")
    assert code == 0, text[-300:]
    screen = VScreen().feed(text)
    lines = screen.lines
    assert "msg-in-the-middle" in lines
    bar_lines = [line for line in lines if line.startswith("work:")]
    assert len(bar_lines) == 1 and "30/30" in bar_lines[0]  # exactly one bar, completed
    assert lines.index("msg-in-the-middle") < lines.index(bar_lines[0])
    assert "stdout-text" in lines
    assert screen.cursor_visible and "\x1b[?1049h" not in text  # inline: no alternate screen


@pytest.mark.req("FR-PROG-005", "FR-PROG-006")
def test_pbar_demo_runs_non_tty(capsys: pytest.CaptureFixture[str]) -> None:
    import importlib.util
    import pathlib

    path = pathlib.Path(__file__).resolve().parent.parent / "examples" / "pbar_demo.py"
    spec = importlib.util.spec_from_file_location("pbar_demo", path)
    assert spec and spec.loader
    demo = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(demo)
    demo.horizontal(True, 5)
    demo.vertical(True, 5)
    demo.mixed(True, 5)
    err = capsys.readouterr().err
    assert "smooth" in err and "100%" in err and "cpu" in err


@pytest.mark.req("FR-PROG-010")
def test_vertical_bars_share_the_same_rows(
    make_manager: Callable[..., tuple[ProgressManager, io.StringIO, ManualClock]],
) -> None:
    from widgets.progress.vertical import VerticalTqdmBar

    manager, stream, clock = make_manager(100)
    bars = [
        VerticalTqdmBar(state(10, clock, description=f"job{i}"), None, height=5) for i in range(3)
    ]
    for i, bar in enumerate(bars):
        bar.progress.set(5 + i)
        manager.add(bar)
    manager.refresh(force=True)
    assert manager.height == 5  # three bars, one band of five rows
    first = screen_of(stream).lines[0]
    assert all(f"job{i}" in first for i in range(3))


@pytest.mark.req("FR-PROG-010")
def test_finished_vertical_bars_stay_beside_later_ones(
    make_manager: Callable[..., tuple[ProgressManager, io.StringIO, ManualClock]],
) -> None:
    from widgets.progress.vertical import VerticalTqdmBar

    manager, stream, clock = make_manager(100)
    first = manager.add(VerticalTqdmBar(state(10, clock, description="one"), None, height=4))
    manager.remove(first, leave=True)
    assert manager.indicators == () and manager.retained == 1
    manager.add(VerticalTqdmBar(state(10, clock, description="two"), None, height=4))
    manager.refresh(force=True)
    assert manager.height == 4
    line = screen_of(stream).lines[0]
    assert "one" in line and "two" in line


@pytest.mark.req("FR-PROG-010")
def test_parked_region_ends_with_newline_and_rejoins_only_when_recent(
    make_manager: Callable[..., tuple[ProgressManager, io.StringIO, ManualClock]],
) -> None:
    from widgets.progress.vertical import VerticalTqdmBar

    manager, stream, clock = make_manager(100)
    one = manager.add(VerticalTqdmBar(state(10, clock, description="one"), None, height=3))
    manager.remove(one, leave=True)
    manager.park()
    assert manager.parked
    stream.write("plain output\n")  # safe: the cursor is below the region
    clock.advance(5.0)  # too late to rejoin: the finished bar stays as ordinary output
    manager.add(VerticalTqdmBar(state(10, clock, description="two"), None, height=3))
    assert not manager.parked and manager.retained == 0


@pytest.mark.req("FR-PROG-010")
def test_look_options_render(
    make_manager: Callable[..., tuple[ProgressManager, io.StringIO, ManualClock]],
) -> None:
    from widgets.progress.indicators import custom_bar_style

    style = custom_bar_style(" -=", None, None)
    assert (style.fill, style.empty, style.partials) == ("=", " ", ("-",))
    manager, stream, _clock = make_manager(80)
    bar = tqdm(
        total=4,
        file=stream,
        manager=manager,
        spinner="line",
        gradient=["red", "blue"],
        colour="green",
        fill="#",
        empty=".",
    )
    bar.update(2)
    manager.refresh(force=True)
    line = screen_of(stream).lines[-1]
    assert "#" in line and "." in line and line[0] in "-\\|/"
    bar.close()


@pytest.mark.req("FR-PROG-010")
def test_bar_format_fixed_width_bar_field(
    make_manager: Callable[..., tuple[ProgressManager, io.StringIO, ManualClock]],
) -> None:
    manager, stream, _clock = make_manager(100)
    bar = tqdm(
        total=30,
        file=stream,
        manager=manager,
        bar_format="{desc}: |{bar:20}| {n_fmt}/{total_fmt}",
        desc="x",
    )
    bar.update(15)
    manager.refresh(force=True)
    line = screen_of(stream).lines[-1]
    assert line.startswith("x: |") and line.count("█") == 10 and line.endswith("| 15/30")
    bar.close()
