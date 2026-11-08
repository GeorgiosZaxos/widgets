"""M2: events, lifecycle, widget base, layout, focus, effects, frame loop."""

from __future__ import annotations

import pytest

from conftest import make_renderer
from widgets.base_elements.base import Widget
from widgets.base_elements.effects import (
    EASINGS,
    FlashLimiter,
    ManualClock,
    ease,
    make_rng,
)
from widgets.base_elements.events import (
    CustomEvent,
    EventQueue,
    KeyDecoder,
    KeyEvent,
    KeyReader,
    PasteEvent,
    ResizeEvent,
    ScriptedInput,
)
from widgets.base_elements.interactive import FocusManager, InteractiveWidget
from widgets.base_elements.layout import Container, Screen
from widgets.base_elements.lifecycle import LifecycleState
from widgets.base_elements.widget_types import Rect
from widgets.errors import LifecycleError
from widgets.render.buffer import Buffer, Canvas
from widgets.render.run import FrameLoop

# -- key decoding ---------------------------------------------------------------------------


def keys(data: bytes) -> list[KeyEvent]:
    d = KeyDecoder()
    events = d.feed(data) + d.flush()
    return [e for e in events if isinstance(e, KeyEvent)]


@pytest.mark.req("FR-INPUT-006", "FR-INPUT-007")
def test_decode_printable_and_named_keys() -> None:
    assert [k.key for k in keys(b"ab")] == ["a", "b"]
    assert keys(b"\r")[0].key == "enter"
    assert keys(b"\x1b[A")[0].key == "up"
    assert keys(b"\x1b[B")[0].key == "down"
    assert keys(b"\t")[0].key == "tab"
    assert keys(b"\x03")[0].combo == "ctrl+c"
    assert keys("é".encode())[0].char == "é"


@pytest.mark.req("FR-INPUT-007")
def test_decode_modifiers() -> None:
    assert keys(b"\x1b[1;5A")[0].combo == "ctrl+up"
    assert keys(b"\x1bf")[0].combo == "alt+f"


@pytest.mark.req("FR-INPUT-007")
def test_decoder_never_raises_on_garbage() -> None:
    d = KeyDecoder()
    for blob in (b"\xff\xfe", b"\x1b[999;999;999~", b"\x1b\x1b\x1b", b"\x1b[", b"\x00"):
        d.feed(blob)
        d.flush()
    assert not d.pending
    assert d.feed(b"x")[0].key == "x"  # still usable


@pytest.mark.req("FR-INPUT-007")
def test_split_utf8_sequence_across_feeds() -> None:
    d = KeyDecoder()
    data = "日".encode()
    assert d.feed(data[:1]) == []
    out = d.feed(data[1:])
    assert out and isinstance(out[0], KeyEvent) and out[0].char == "日"


@pytest.mark.req("FR-INPUT-007", "FR-INPUT-009")
def test_bracketed_paste() -> None:
    d = KeyDecoder()
    events = d.feed(b"\x1b[200~hello\nworld\x1b[201~")
    pastes = [e for e in events if isinstance(e, PasteEvent)]
    assert pastes and pastes[0].text == "hello\nworld"


@pytest.mark.req("FR-INPUT-004", "FR-INPUT-007")
def test_lone_escape_resolved_by_timeout_without_blocking() -> None:
    clock = ManualClock()
    source = ScriptedInput([b"\x1b"])
    reader = KeyReader(source, esc_timeout=0.05, clock=clock)
    assert reader.poll(0) == []
    clock.advance(0.06)
    events = reader.poll(0)
    assert [e.key for e in events if isinstance(e, KeyEvent)] == ["escape"]
    reader.close()
    assert source.closed


@pytest.mark.req("FR-INPUT-009", "NFR-REL-005", "D-04")
def test_event_queue_bounded_and_ordered() -> None:
    q = EventQueue(maxsize=2)
    assert q.put(CustomEvent("a")) and q.put(CustomEvent("b"))
    assert q.put(CustomEvent("c")) is False
    assert [e.name for e in q.drain() if isinstance(e, CustomEvent)] == ["a", "b"]
    assert q.empty()


# -- lifecycle ------------------------------------------------------------------------------


class Probe(Widget):
    def __init__(self, log: list[str], name: str = "probe", **kw: object) -> None:
        super().__init__(0, 0, 4, 1, name=name, **kw)  # type: ignore[arg-type]
        self.log = log

    def on_mount(self, context: object | None) -> None:
        self.log.append(f"{self.name}:mount")

    def on_start(self) -> None:
        self.log.append(f"{self.name}:start")

    def on_pause(self) -> None:
        self.log.append(f"{self.name}:pause")

    def on_resume(self) -> None:
        self.log.append(f"{self.name}:resume")

    def on_stop(self) -> None:
        self.log.append(f"{self.name}:stop")

    def on_unmount(self) -> None:
        self.log.append(f"{self.name}:unmount")

    def on_close(self) -> None:
        self.log.append(f"{self.name}:close")


@pytest.mark.req("FR-LIFE-001", "FR-LIFE-002")
def test_full_lifecycle_in_order() -> None:
    log: list[str] = []
    w = Probe(log)
    assert w.state is LifecycleState.CREATED
    w.mount()
    w.start()
    w.pause()
    w.resume()
    w.stop()
    w.unmount()
    w.close()
    assert [e.split(":")[1] for e in log] == [
        "mount",
        "start",
        "pause",
        "resume",
        "stop",
        "unmount",
        "close",
    ]
    assert w.state is LifecycleState.CLOSED


@pytest.mark.req("FR-LIFE-003")
def test_repeating_an_operation_is_a_noop() -> None:
    log: list[str] = []
    w = Probe(log)
    w.mount()
    w.mount()
    w.start()
    w.start()
    assert log == ["probe:mount", "probe:start"]


@pytest.mark.req("FR-LIFE-003")
def test_illegal_transitions_raise() -> None:
    w = Probe([])
    with pytest.raises(LifecycleError):
        w.start()  # not mounted
    w.mount()
    with pytest.raises(LifecycleError):
        w.pause()  # not running
    w.start()
    with pytest.raises(LifecycleError):
        w.unmount()  # must stop first


@pytest.mark.req("FR-LIFE-002")
def test_restart_after_stop_allowed() -> None:
    log: list[str] = []
    w = Probe(log)
    w.mount()
    w.start()
    w.stop()
    w.start()
    assert w.state is LifecycleState.RUNNING


@pytest.mark.req("FR-CORE-005", "NFR-REL-004")
@pytest.mark.parametrize("steps", [[], ["mount"], ["mount", "start"], ["mount", "start", "pause"]])
def test_close_from_any_state_is_idempotent(steps: list[str]) -> None:
    log: list[str] = []
    w = Probe(log)
    for s in steps:
        getattr(w, s)()
    w.close()
    w.close()
    assert w.state is LifecycleState.CLOSED
    assert log.count("probe:close") == 1


@pytest.mark.req("NFR-REL-001")
def test_close_continues_after_hook_failure() -> None:
    class Bad(Probe):
        def on_stop(self) -> None:
            raise RuntimeError("boom")

    log: list[str] = []
    w = Bad(log)
    w.mount()
    w.start()
    with pytest.raises(RuntimeError, match="boom"):
        w.close()  # every step is attempted, then the first error is re-raised
    assert w.state is LifecycleState.CLOSED
    assert "probe:close" in log
    w.close()  # idempotent afterwards


@pytest.mark.req("NFR-REL-002")
def test_cleanup_registered_on_widget_runs_on_close() -> None:
    log: list[str] = []
    w = Probe([])
    w.cleanup.register(lambda: log.append("cleaned"))
    w.close()
    assert log == ["cleaned"]


# -- container --------------------------------------------------------------------------------


@pytest.mark.req("FR-LAYOUT-002", "FR-LAYOUT-003")
def test_container_add_get_remove_and_z_order() -> None:
    log: list[str] = []
    c = Container(0, 0, 10, 5, name="c")
    a, b = Probe(log, "a"), Probe(log, "b", z=-1)
    c.add(a)
    c.add(b)
    assert [w.name for w in c.children] == ["b", "a"]
    assert c.get("a") is a and "a" in c and len(c) == 2
    assert a.parent is c
    c.remove("a")
    assert a.state is LifecycleState.CLOSED and "a" not in c


@pytest.mark.req("FR-CORE-001", "FR-LAYOUT-002")
def test_container_rejects_bad_children() -> None:
    c = Container(0, 0, 10, 5, name="c")
    p = Probe([], "p")
    c.add(p)
    with pytest.raises(ValueError):
        c.add(p)  # already has a parent
    with pytest.raises(ValueError):
        c.add(Probe([], "p"))  # duplicate name
    with pytest.raises(ValueError):
        c.add(c)
    outer = Container(0, 0, 5, 5, name="outer")
    outer.add(c)
    with pytest.raises(ValueError):
        c.add(outer)  # cycle
    with pytest.raises(KeyError):
        c.get("zzz")


@pytest.mark.req("FR-LIFE-005", "FR-LAYOUT-002")
def test_child_follows_container_lifecycle() -> None:
    log: list[str] = []
    c = Container(0, 0, 10, 5, name="c")
    c.add(Probe(log, "early"))
    c.mount()
    c.start()
    assert log == ["early:mount", "early:start"]
    c.add(Probe(log, "late"))  # added to a running container: caught up
    assert log[-2:] == ["late:mount", "late:start"]
    c.close()
    assert c.state is LifecycleState.CLOSED
    assert log.count("late:close") == 1


@pytest.mark.req("FR-LAYOUT-001", "FR-LAYOUT-004")
def test_children_clipped_to_container_and_offset() -> None:
    buf = Buffer(12, 4)

    class Fill(Widget):
        def render(self, canvas: Canvas) -> None:
            for r in range(canvas.height):
                canvas.write_text(r, 0, "#" * canvas.width)

    c = Container(2, 1, 4, 2, name="c")
    c.add(Fill(1, 0, 10, 5, name="f"))
    c.draw(buf)
    lines = buf.to_lines()
    assert lines[1] == "   ###      "
    assert lines[2] == "   ###      "
    assert lines[0].strip() == "" and lines[3].strip() == ""


@pytest.mark.req("FR-LAYOUT-006")
def test_screen_overlay_paints_last() -> None:
    class Ch(Widget):
        def __init__(self, ch: str, name: str) -> None:
            super().__init__(0, 0, 3, 1, name=name)
            self.ch = ch

        def render(self, canvas: Canvas) -> None:
            canvas.write_text(0, 0, self.ch * 3)

    s = Screen(5, 1)
    s.overlay.add(Ch("o", "over"))
    s.add(Ch("b", "base"))
    buf = Buffer(5, 1)
    s.draw(buf)
    assert buf.to_lines()[0].startswith("ooo")


@pytest.mark.req("FR-CORE-002")
def test_invisible_widgets_are_not_drawn_or_updated_rules() -> None:
    log: list[str] = []
    c = Container(0, 0, 4, 1, name="c")
    p = Probe(log, "p")
    c.add(p)
    c.visible = False
    assert not p.effective_visible
    c.enabled = False
    assert not p.effective_enabled


# -- focus ------------------------------------------------------------------------------------


class Btn(InteractiveWidget):
    focusable = True

    def __init__(self, name: str, tab_index: int = 0) -> None:
        super().__init__(0, 0, 3, 1, name=name)
        self.pressed: list[str] = []
        self.focus_events: list[str] = []

    def on_focus(self) -> None:
        self.focus_events.append("focus")

    def on_blur(self) -> None:
        self.focus_events.append("blur")

    def handle_key(self, event: KeyEvent) -> bool:
        if event.key == "enter":
            self.pressed.append(self.name)
            return True
        return False


def tree() -> tuple[Screen, FocusManager, list[Btn]]:
    s = Screen(20, 5)
    btns = [Btn(f"b{i}") for i in range(3)]
    for b in btns:
        s.add(b)
    s.mount()
    s.start()
    return s, FocusManager(s), btns


@pytest.mark.req("FR-INPUT-008")
def test_tab_cycles_focus_and_wraps() -> None:
    _, fm, (b0, _b1, b2) = tree()
    tab, back = KeyEvent("tab"), KeyEvent("backtab", shift=True)
    fm.dispatch(tab)
    assert fm.focused is b0
    fm.dispatch(tab)
    fm.dispatch(tab)
    assert fm.focused is b2
    fm.dispatch(tab)
    assert fm.focused is b0
    fm.dispatch(back)
    assert fm.focused is b2


@pytest.mark.req("FR-INPUT-002")
def test_focus_blur_called_once_per_transition() -> None:
    _, fm, (b0, b1, _b2) = tree()
    fm.focus(b0)
    fm.focus(b0)
    fm.focus(b1)
    assert b0.focus_events == ["focus", "blur"]
    assert b1.focus_events == ["focus"]


@pytest.mark.req("FR-INPUT-001", "FR-INPUT-008")
def test_keys_go_to_focused_widget_only() -> None:
    _, fm, (b0, b1, _b2) = tree()
    fm.focus(b1)
    assert fm.dispatch(KeyEvent("enter")) is True
    assert b1.pressed == ["b1"] and b0.pressed == []


@pytest.mark.req("FR-INPUT-008")
def test_disabled_or_hidden_widgets_are_skipped() -> None:
    _, fm, (b0, b1, b2) = tree()
    b1.enabled = False
    b2.visible = False
    assert fm.focus_order() == [b0]
    assert fm.focus(b1) is False


@pytest.mark.req("FR-INPUT-008")
def test_focus_dropped_when_widget_removed() -> None:
    s, fm, (b0, _b1, _b2) = tree()
    fm.focus(b0)
    s.remove(b0)
    fm.dispatch(KeyEvent("x"))
    assert fm.focused is None


# -- effects ------------------------------------------------------------------------------------


@pytest.mark.req("FR-FX-002")
@pytest.mark.parametrize("name", sorted(EASINGS))
def test_easing_endpoints_and_clamping(name: str) -> None:
    assert ease(name, 0.0) == pytest.approx(0.0)
    assert ease(name, 1.0) == pytest.approx(1.0)
    assert ease(name, -3) == pytest.approx(0.0)
    assert ease(name, 9) == pytest.approx(1.0)


@pytest.mark.req("FR-FX-001")
def test_unknown_easing_and_nan() -> None:
    with pytest.raises(ValueError):
        ease("nope", 0.5)
    with pytest.raises(ValueError):
        ease("linear", float("nan"))


@pytest.mark.req("FR-FX-003")
def test_manual_clock() -> None:
    c = ManualClock(10.0)
    c.advance(1.5)
    c.sleep(0.5)
    assert c.now() == 12.0 and c.sleeps == [0.5]


@pytest.mark.req("FR-FX-004")
def test_seeded_rng_is_reproducible() -> None:
    assert [make_rng(7).random() for _ in range(3)] == [make_rng(7).random() for _ in range(3)]


@pytest.mark.req("FR-FX-005")
def test_flash_limiter() -> None:
    f = FlashLimiter(max_per_second=3)
    assert [f.allow(0.1 * i) for i in range(5)] == [True, True, True, False, False]
    assert f.allow(1.2) is True
    assert f.allow(2.0, area_fraction=0.1) is True  # small areas are never limited


# -- frame loop ---------------------------------------------------------------------------------


class Counter(Widget):
    def __init__(self) -> None:
        super().__init__(0, 0, 10, 1, name="counter")
        self.dts: list[float] = []

    def update(self, dt: float) -> None:
        self.dts.append(dt)

    def render(self, canvas: Canvas) -> None:
        canvas.write_text(0, 0, f"n={len(self.dts)}")


def make_loop(root: Widget, **kw: object) -> tuple[FrameLoop, ManualClock]:
    renderer, _out = make_renderer()
    clock = ManualClock()
    loop = FrameLoop(root, renderer=renderer, clock=clock, size=(10, 2), **kw)  # type: ignore[arg-type]
    return loop, clock


@pytest.mark.req("FR-RENDER-009")
def test_loop_runs_for_duration_at_fps() -> None:
    w = Counter()
    loop, clock = make_loop(w, fps=10, duration=1.0)
    loop.run()
    assert 9 <= loop.frames <= 11
    assert all(abs(s - 0.1) < 1e-6 for s in clock.sleeps)  # fixed-rate pacing
    assert w.state is LifecycleState.CLOSED


@pytest.mark.req("FR-RENDER-009")
def test_loop_validates_arguments() -> None:
    for bad in (0, 241, True):
        with pytest.raises(ValueError):
            make_loop(Counter(), fps=bad)
    with pytest.raises(ValueError):
        make_loop(Counter(), duration=-1)
    with pytest.raises(ValueError):
        FrameLoop(Counter())


@pytest.mark.req("FR-RENDER-009")
def test_dt_is_clamped_after_a_stall() -> None:
    w = Counter()
    loop, clock = make_loop(w, fps=10, duration=0.5, max_dt=0.2)

    original = w.update

    def stall(dt: float) -> None:
        original(dt)
        if len(w.dts) == 2:
            clock.advance(5.0)

    w.update = stall  # type: ignore[method-assign]
    loop.run()
    assert max(w.dts) <= 0.2


@pytest.mark.req("FR-RENDER-010", "NFR-REL-003")
def test_exception_closes_tree_and_propagates() -> None:
    class Boom(Counter):
        def update(self, dt: float) -> None:
            raise RuntimeError("kaboom")

    w = Boom()
    loop, _ = make_loop(w, fps=10, duration=1)
    with pytest.raises(RuntimeError, match="kaboom"):
        loop.run()
    assert w.state is LifecycleState.CLOSED


@pytest.mark.req("FR-RENDER-010")
def test_keyboard_interrupt_still_cleans_up() -> None:
    class Interrupt(Counter):
        def update(self, dt: float) -> None:
            raise KeyboardInterrupt

    w = Interrupt()
    loop, _ = make_loop(w, fps=10, duration=1)
    with pytest.raises(KeyboardInterrupt):
        loop.run()
    assert w.state is LifecycleState.CLOSED


@pytest.mark.req("FR-INPUT-010", "FR-INPUT-001")
def test_quit_key_stops_loop_and_unmatched_keys_reach_focus() -> None:
    s = Screen(10, 2)
    b = Btn("b")
    s.add(b)
    source = ScriptedInput([b"\t", b"\r", b"q"])
    reader = KeyReader(source)
    loop, _ = make_loop(s, fps=10, duration=5, key_reader=reader, quit_keys=("q",))
    loop.run()
    assert b.pressed == ["b"]
    assert loop.stopped and loop.frames < 10
    assert source.closed


@pytest.mark.req("FR-INPUT-009", "FR-INPUT-005", "D-04")
def test_events_from_queue_reach_on_event() -> None:
    seen: list[str] = []
    q = EventQueue()
    q.put(CustomEvent("hello"))
    loop, _ = make_loop(
        Counter(),
        fps=10,
        duration=0.3,
        events=q,
        on_event=lambda e: seen.append(getattr(e, "name", "?")) or None,
    )
    loop.run()
    assert seen == ["hello"]


@pytest.mark.req("FR-LAYOUT-007", "FR-RENDER-011")
def test_resize_event_rebuilds_buffer_and_screen() -> None:
    s = Screen(10, 2)
    q = EventQueue()
    q.put(ResizeEvent(20, 4))
    loop, _ = make_loop(s, fps=10, duration=0.3, events=q)
    loop.run()
    assert (s.width, s.height) == (20, 4)
    assert (loop.buffer.width, loop.buffer.height) == (20, 4)


@pytest.mark.req("FR-INPUT-005")
def test_callback_errors_are_logged_not_fatal(caplog: pytest.LogCaptureFixture) -> None:
    q = EventQueue()
    q.put(CustomEvent("x"))

    def bad(_e: object) -> bool:
        raise ValueError("cb")

    loop, _ = make_loop(Counter(), fps=10, duration=0.3, events=q, on_event=bad)
    loop.run()
    assert any("on_event" in r.getMessage() for r in caplog.records)


def test_rect_import_used() -> None:
    assert Rect(0, 0, 1, 1).right == 1
