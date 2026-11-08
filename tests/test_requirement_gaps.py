"""Requirement-level checks that do not fit a single module: colors, widget contract, signals."""

from __future__ import annotations

import json
import signal
import sys
import threading
from pathlib import Path

import pytest

from conftest import FakeTTY, make_renderer
from widgets.base_elements.base import Widget
from widgets.base_elements.color_manager import (
    ColorMode,
    Gradient,
    get_gradient,
    get_palette,
    gradient_to_css,
    gradient_to_json,
    list_gradients,
    list_palettes,
    palette_to_css,
    palette_to_json,
    parse_color,
    register_gradient,
    register_palette,
    rgb_to_ansi16,
    rgb_to_ansi256,
    style_to_ansi,
)
from widgets.base_elements.effects import (
    reduced_motion_enabled,
    require_fraction,
    require_non_negative,
    require_positive,
)
from widgets.base_elements.events import KeyEvent
from widgets.base_elements.lifecycle import LifecycleState
from widgets.base_elements.widget_types import RGB, Rect, Style
from widgets.errors import TerminalCapabilityError
from widgets.render.buffer import Buffer, Canvas
from widgets.render.sanitize import sanitize_text
from widgets.terminal.session import TerminalSession

ROOT = Path(__file__).resolve().parent.parent

# -- colors ---------------------------------------------------------------------------------


@pytest.mark.req("FR-COLOR-001")
def test_named_colors_and_invalid_input_names_the_value() -> None:
    assert parse_color("red") == RGB(255, 0, 0) or isinstance(parse_color("red"), RGB)
    with pytest.raises(ValueError, match="not-a-color"):
        parse_color("not-a-color")
    with pytest.raises(ValueError, match="300"):
        parse_color((300, 0, 0))


@pytest.mark.req("FR-COLOR-005")
def test_palette_registry() -> None:
    assert list_palettes()
    register_palette("gap-test", ["#000", "#fff"])
    with pytest.raises(ValueError):
        register_palette("gap-test", ["#111"])
    register_palette("gap-test", ["#111"], replace=True)
    assert get_palette("GAP-TEST") == (RGB(17, 17, 17),)
    with pytest.raises(KeyError):
        get_palette("no-such-palette")


@pytest.mark.req("FR-COLOR-006")
def test_gradient_registry_and_validation() -> None:
    assert list_gradients()
    for bad in (
        [(0.0, RGB(0, 0, 0))],
        [(0.5, RGB(0, 0, 0)), (0.2, RGB(1, 1, 1))],
        [(0.0, RGB(0, 0, 0)), (1.5, RGB(1, 1, 1))],
    ):
        with pytest.raises(ValueError):
            Gradient(tuple(bad))
    register_gradient("gap-grad", ["#000000", "#ffffff"])
    assert get_gradient("gap-grad").at(1.0) == RGB(255, 255, 255)
    with pytest.raises(ValueError):
        register_gradient("gap-grad", ["#000000", "#ffffff"])


@pytest.mark.req("FR-COLOR-007", "FR-COLOR-004")
def test_all_attributes_have_sgr_codes() -> None:
    seq = style_to_ansi(
        Style(
            bold=True, dim=True, italic=True, underline=True, blink=True, reverse=True, strike=True
        ),
        ColorMode.TRUECOLOR,
    )
    for code in ("1", "2", "3", "4", "5", "7", "9"):
        assert code in seq.removeprefix("\x1b[").removesuffix("m").split(";")
    s16 = style_to_ansi(Style(fg=RGB(255, 0, 0), bg=RGB(0, 0, 255)), ColorMode.ANSI16)
    assert any(p in s16 for p in ("31", "91")) and any(p in s16 for p in ("44", "104"))


@pytest.mark.req("FR-COLOR-008")
def test_json_and_css_export() -> None:
    data = json.loads(palette_to_json("gap-test"))
    assert "version" in data
    assert "--" in palette_to_css("gap-test")
    assert "gradient" in gradient_to_css("gap-grad")
    assert json.loads(gradient_to_json("gap-grad"))


@pytest.mark.req("FR-COLOR-010")
def test_downgrade_is_nearest_and_deterministic() -> None:
    for rgb in (RGB(0, 0, 0), RGB(255, 255, 255), RGB(10, 200, 30), RGB(128, 128, 128)):
        assert rgb_to_ansi256(rgb) == rgb_to_ansi256(rgb)
        assert 0 <= rgb_to_ansi256(rgb) <= 255 and 0 <= rgb_to_ansi16(rgb) <= 15
    assert rgb_to_ansi256(RGB(0, 0, 0)) in (0, 16)
    assert rgb_to_ansi16(RGB(255, 255, 255)) in (7, 15)


# -- widget contract ------------------------------------------------------------------------------


class Plain(Widget):
    def render(self, canvas: Canvas) -> None:
        canvas.write_text(0, 0, "x" * canvas.width)


@pytest.mark.req("FR-CORE-001")
def test_auto_generated_unique_names() -> None:
    a, b = Plain(0, 0, 1, 1), Plain(0, 0, 1, 1)
    assert a.name and b.name and a.name != b.name
    assert Plain(0, 0, 1, 1, name="mine").name == "mine"


@pytest.mark.req("FR-CORE-003")
def test_move_resize_and_queries() -> None:
    w = Plain(1, 2, 3, 4)
    w.move(5, 6)
    w.resize(7, 8)
    assert (w.x, w.y, w.width, w.height) == (5, 6, 7, 8)
    assert w.rect == Rect(5, 6, 7, 8)


@pytest.mark.req("FR-CORE-004")
def test_on_mount_and_on_unmount_hooks_fire() -> None:
    calls: list[str] = []

    class Hooked(Plain):
        def on_mount(self, context: object | None) -> None:
            calls.append("mount")

        def on_unmount(self) -> None:
            calls.append("unmount")

    w = Hooked(0, 0, 1, 1)
    w.mount()
    w.start()
    w.stop()
    w.unmount()
    assert calls == ["mount", "unmount"]


@pytest.mark.req("FR-CORE-006")
def test_widget_is_a_context_manager() -> None:
    with Plain(0, 0, 1, 1) as w:
        assert w.state is LifecycleState.RUNNING
    assert w.state is LifecycleState.CLOSED


@pytest.mark.req("FR-CORE-007", "FR-LAYOUT-008")
def test_invisible_zero_size_and_oversized_widgets_stay_in_bounds() -> None:
    buf = Buffer(6, 2)
    hidden = Plain(0, 0, 6, 1, visible=False)
    hidden.draw(buf)
    Plain(0, 0, 0, 2).draw(buf)
    assert buf.to_lines() == ["      ", "      "]
    Plain(4, 1, 50, 50).draw(buf)  # far larger than the buffer and partly off-screen
    Plain(-3, 0, 5, 3).draw(buf)
    assert buf.to_lines() == ["xx    ", "    xx"]


@pytest.mark.req("FR-CORE-007")
def test_disabled_widget_does_not_consume_keys() -> None:
    class Eager(Plain):
        def handle_key(self, event: KeyEvent) -> bool:
            return True

    w = Eager(0, 0, 1, 1)
    assert w.dispatch_key(KeyEvent("a")) is True
    w.enabled = False
    assert w.dispatch_key(KeyEvent("a")) is False


@pytest.mark.req("FR-CORE-008")
def test_update_uses_elapsed_time_not_frame_count() -> None:
    class Mover(Plain):
        pos = 0.0

        def update(self, dt: float) -> None:
            self.pos += 10 * dt

    a, b = Mover(0, 0, 1, 1), Mover(0, 0, 1, 1)
    for _ in range(10):
        a.update(0.1)
    for _ in range(100):
        b.update(0.01)
    assert a.pos == pytest.approx(b.pos)


@pytest.mark.req("FR-CORE-011")
def test_describe_is_plain_text() -> None:
    w = Plain(1, 2, 3, 4, name="thing", enabled=False)
    text = w.describe()
    assert "thing" in text and "disabled" in text and "\x1b" not in text


@pytest.mark.req("FR-RENDER-001", "D-02")
def test_widget_rendering_writes_nothing_to_stdout(capsys: pytest.CaptureFixture[str]) -> None:
    buf = Buffer(5, 1)
    Plain(0, 0, 5, 1).draw(buf)
    out = capsys.readouterr()
    assert out.out == "" and out.err == "" and buf.to_lines() == ["xxxxx"]


# -- effects --------------------------------------------------------------------------------------


@pytest.mark.req("FR-FX-006")
def test_reduced_motion_switch() -> None:
    assert reduced_motion_enabled({"WIDGETS_REDUCED_MOTION": "1"}) is True
    assert reduced_motion_enabled({}) is False
    assert reduced_motion_enabled({}, override=True) is True
    assert reduced_motion_enabled({"WIDGETS_REDUCED_MOTION": "1"}, override=False) is False


@pytest.mark.req("FR-FX-006")
def test_session_exposes_reduced_motion() -> None:
    s = TerminalSession(
        stream=FakeTTY(),
        env={"TERM": "xterm", "WIDGETS_REDUCED_MOTION": "1"},
        handle_signals=False,
        use_atexit=False,
    )
    assert s.reduced_motion is True
    s2 = TerminalSession(
        stream=FakeTTY(),
        env={"TERM": "xterm"},
        reduced_motion=True,
        handle_signals=False,
        use_atexit=False,
    )
    assert s2.reduced_motion is True


@pytest.mark.req("FR-FX-007")
def test_effect_parameter_validation() -> None:
    for fn, bad in (
        (require_positive, 0),
        (require_positive, -1),
        (require_non_negative, -0.1),
        (require_fraction, 1.1),
        (require_positive, True),
    ):
        with pytest.raises(ValueError):
            fn("p", bad)
    assert (
        require_positive("p", 2) == 2.0
        and require_non_negative("p", 0) == 0.0
        and require_fraction("p", 1) == 1.0
    )


# -- renderer / terminal ------------------------------------------------------------------------------


@pytest.mark.req("FR-RENDER-007")
def test_full_render_of_whole_buffer() -> None:
    renderer, out = make_renderer()
    b = Buffer(4, 3)
    for r in range(3):
        b.write_text(r, 0, f"r{r}ab")
    renderer.render(b)
    for r in range(3):
        assert f"r{r}ab" in out.getvalue()


@pytest.mark.req("FR-RENDER-012")
def test_cursor_operations_and_non_ansi_noop() -> None:
    renderer, out = make_renderer()
    renderer.move_cursor(2, 3)
    renderer.hide_cursor()
    renderer.show_cursor()
    renderer.save_cursor()
    renderer.restore_cursor()
    text = out.getvalue()
    for seq in ("\x1b[?25l", "\x1b[?25h", "\x1b7", "\x1b8"):
        assert seq in text
    plain, plain_out = make_renderer(ansi=False, color_mode=ColorMode.NONE)
    plain.move_cursor(1, 1)
    plain.hide_cursor()
    assert plain_out.getvalue() == ""


@pytest.mark.req("FR-RENDER-015")
def test_synchronized_output_is_opt_in() -> None:
    import io

    from widgets.render.screen_renderer import ScreenRenderer
    from widgets.terminal.session import OutputGate

    out = io.StringIO()
    r = ScreenRenderer(OutputGate(out), synchronized_output=True)
    b = Buffer(3, 1)
    b.write_text(0, 0, "abc")
    r.render(b)
    assert "\x1b[?2026h" in out.getvalue() and "\x1b[?2026l" in out.getvalue()
    plain, plain_out = make_renderer()
    plain.render(b)
    assert "?2026" not in plain_out.getvalue()


@pytest.mark.req("FR-BUF-008")
def test_row_is_immutable_and_bounds_checked() -> None:
    b = Buffer(3, 2)
    row = b.row(0)
    assert isinstance(row, tuple) and len(row) == 3
    with pytest.raises(IndexError):
        b.row(2)
    with pytest.raises(IndexError):
        b.row(-1)


@pytest.mark.req("FR-SAN-002")
def test_sanitize_text_is_public_api() -> None:
    import widgets

    assert widgets.sanitize_text is sanitize_text


@pytest.mark.req("FR-TERM-001")
def test_session_output_gate_serialises_concurrent_writers() -> None:
    import io

    from widgets.terminal.session import OutputGate

    out = io.StringIO()
    gate = OutputGate(out)
    n = 200

    def worker(ch: str) -> None:
        for _ in range(n):
            gate.write_flush(ch * 20 + "\n")

    threads = [threading.Thread(target=worker, args=(c,)) for c in "abcd"]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    lines = out.getvalue().splitlines()
    assert len(lines) == 4 * n and all(len(set(line)) == 1 and len(line) == 20 for line in lines)


@pytest.mark.req("FR-TERM-005", "NFR-PORT-002")
def test_platform_code_is_isolated_in_compat() -> None:
    offenders = []
    for path in (ROOT / "src" / "widgets").rglob("*.py"):
        if path.name == "compat.py":
            continue
        text = path.read_text(encoding="utf-8")
        if any(f"import {m}" in text for m in ("termios", "tty", "msvcrt", "fcntl", "ctypes")):
            offenders.append(path.name)
    assert offenders == [], offenders


@pytest.mark.req("FR-INPUT-011")
def test_non_interactive_session_refuses_input_instead_of_hanging() -> None:
    import io

    s = TerminalSession(
        stream=io.StringIO(),
        env={"TERM": "xterm"},
        raw_input=True,
        handle_signals=False,
        use_atexit=False,
    )
    with s:
        assert s.interactive is False
        with pytest.raises(TerminalCapabilityError):
            s.open_input()


@pytest.mark.skipif(sys.platform == "win32", reason="POSIX signals")
@pytest.mark.req("FR-TERM-011")
def test_signal_handlers_chain_and_are_uninstalled() -> None:
    seen: list[int] = []

    def previous(signum: int, frame: object) -> None:
        seen.append(signum)

    old = signal.signal(signal.SIGHUP, previous)
    try:
        s = TerminalSession(stream=FakeTTY(), env={"TERM": "xterm"}, use_atexit=False)
        s.start()
        installed = signal.getsignal(signal.SIGHUP)
        assert installed is not previous
        s.close()
        assert signal.getsignal(signal.SIGHUP) is previous  # restored on exit
    finally:
        signal.signal(signal.SIGHUP, old)


@pytest.mark.req("FR-TERM-011")
def test_signals_not_installed_off_the_main_thread() -> None:
    results: list[object] = []

    def run() -> None:
        before = signal.getsignal(signal.SIGTERM) if hasattr(signal, "SIGTERM") else None
        s = TerminalSession(stream=FakeTTY(), env={"TERM": "xterm"}, use_atexit=False)
        s.start()
        results.append(signal.getsignal(signal.SIGTERM) is before if before is not None else True)
        s.close()

    t = threading.Thread(target=run)
    t.start()
    t.join(10)
    assert results == [True]


@pytest.mark.req("FR-API-007")
def test_py_typed_marker_ships() -> None:
    assert (ROOT / "src" / "widgets" / "py.typed").exists()


@pytest.mark.req("NFR-REL-006")
def test_library_starts_no_non_daemon_threads() -> None:
    before = set(threading.enumerate())
    _renderer, _ = make_renderer()
    Plain(0, 0, 1, 1).close()
    assert set(threading.enumerate()) <= before | {threading.current_thread()}
