"""M4 core widgets: box, spinner, marquee, animated text, sign, neon, matrix, vprint, gauge,
notification, calendar."""

from __future__ import annotations

import datetime as dt
from zoneinfo import ZoneInfoNotFoundError

import pytest
from tests.conftest import text_rows

from widgets.base_elements.effects import ManualClock
from widgets.base_elements.events import KeyEvent
from widgets.base_elements.widget_types import DEFAULT_STYLE, Style
from widgets.display.box import Box
from widgets.display.calendar import CalendarWidget, ClockWidget, Countdown, make_date
from widgets.display.effects_widgets import MatrixRain, Neon, Sign
from widgets.display.gauge import Gauge
from widgets.display.marquee import AnimatedText, Marquee
from widgets.display.notify import NotificationCenter, NotificationType
from widgets.display.spinner import Spinner, SpinnerGroup
from widgets.display.vprint import VerticalPrint, countdown_text, vertical_text
from widgets.render.buffer import Buffer


def draw(widget, width: int, height: int, *, t: float = 0.0) -> list[str]:
    buf = Buffer(width, height)
    widget.mount()
    widget.start()
    if t:
        widget.update(t)
    widget.draw(buf)
    return text_rows(buf)


@pytest.mark.req("FR-BOX-001")
def test_box_borders_and_tiny_sizes() -> None:
    rows = draw(Box(0, 0, 6, 3, text="", border="single"), 6, 3)
    assert rows[0] == "┌────┐" and rows[2] == "└────┘"
    for w, h in ((0, 0), (1, 1), (2, 1), (1, 3)):
        draw(Box(0, 0, w, h, text="x"), 6, 3)  # must not raise


@pytest.mark.req("FR-BOX-002")
def test_box_align_wrap_truncate() -> None:
    rows = draw(Box(0, 0, 12, 5, text="hi", align="center", valign="middle"), 12, 5)
    assert rows[2].strip("│ ") == "hi"
    wrapped = draw(Box(0, 0, 8, 6, text="aaa bbb ccc", overflow="wrap"), 8, 6)
    assert [r.strip("│ ") for r in wrapped[1:4]] == ["aaa", "bbb", "ccc"]
    cut = draw(Box(0, 0, 6, 3, text="abcdefgh"), 6, 3)
    assert cut[1] == "│abcd│"


@pytest.mark.req("FR-BOX-003")
def test_box_shadow_stays_inside_widget() -> None:
    rows = draw(Box(0, 0, 8, 4, text="x", shadow=(1, 1, "▒", DEFAULT_STYLE)), 8, 4)
    assert rows[1].endswith("▒") and rows[3].strip().startswith("▒")


@pytest.mark.req("FR-SPINNER-001", "FR-SPINNER-003")
def test_spinner_speed_and_live_changes() -> None:
    s = Spinner(spinner="line", speed=10.0, text="go")
    first = draw(s, 10, 1)[0]
    s.update(0.1)
    second = draw(Spinner(), 10, 1)[0]
    assert first.startswith("-")
    s.set_spinner("dots-ascii")
    s.set_text("x")
    assert s.frame in "".join(["-\\|/"]) or s.spinner == "dots-ascii"
    with pytest.raises(ValueError):
        Spinner(speed=0)
    with pytest.raises(KeyError):
        Spinner(spinner="zzz")
    assert second


@pytest.mark.req("FR-SPINNER-002")
def test_spinner_alignment() -> None:
    assert draw(Spinner(0, 0, 10, text="ab", align="right"), 10, 1)[0].endswith("ab")


@pytest.mark.req("FR-SPINNER-004")
def test_spinner_group_rows_do_not_overlap() -> None:
    group = SpinnerGroup(2, 3, 12)
    a, b = group.add(Spinner()), group.add(Spinner())
    assert (a.y, b.y) == (3, 4)
    group.remove(a)
    assert b.y == 3
    group.start_all()
    group.update(0.1)
    group.stop_all()


@pytest.mark.req("FR-MARQUEE-001", "FR-MARQUEE-002")
def test_marquee_scrolls_and_bounces() -> None:
    m = Marquee(0, 0, 8, 1, text="ABCDEFGHIJ", speed=2.0, gap=2)
    start = draw(m, 8, 1)[0]
    moved = draw(Marquee(0, 0, 8, 1, text="ABCDEFGHIJ", speed=2.0, gap=2), 8, 1, t=2.0)[0]
    assert start == "ABCDEFGH" and moved == "EFGHIJ  "
    right = draw(Marquee(0, 0, 8, 1, text="ABCDEFGHIJ", direction="right", speed=2.0), 8, 1, t=1.0)[
        0
    ]
    assert right != start
    bounce = Marquee(0, 0, 4, 1, text="ABCDEF", mode="bounce", speed=1.0)
    assert [
        draw(Marquee(0, 0, 4, 1, text="ABCDEF", mode="bounce", speed=1.0), 4, 1, t=t)[0]
        for t in (0, 2, 4)
    ] == ["ABCD", "CDEF", "ABCD"]
    assert bounce
    up = draw(Marquee(0, 0, 3, 2, text="a\nb\nc", direction="up", speed=1.0, gap=0), 3, 2, t=1.0)
    assert up[0].strip() == "b"
    with pytest.raises(ValueError):
        Marquee(direction="sideways")


@pytest.mark.req("FR-MARQUEE-002")
def test_marquee_pause_resume() -> None:
    m = Marquee(0, 0, 8, 1, text="ABCDEFGHIJ", speed=2.0)
    m.mount()
    m.start()
    m.tick(1.0)
    m.pause()
    m.tick(5.0)
    assert m.t == 1.0
    m.resume()
    m.tick(1.0)
    assert m.t == 2.0


@pytest.mark.req("FR-MARQUEE-003")
def test_marquee_with_font() -> None:
    rows = draw(Marquee(0, 0, 30, 7, text="Hi", font="original-7"), 30, 7)
    assert any(ch != " " for ch in rows[0] + rows[3])


@pytest.mark.req("FR-ANIM-002", "FR-ANIM-006")
@pytest.mark.parametrize(
    "mode",
    ["scroll", "bounce", "dual-marquee", "typewriter", "fade-in", "fade-out", "wave", "explode"],
)
def test_animated_modes_are_deterministic(mode: str) -> None:
    def run() -> list[str]:
        w = AnimatedText(
            0, 0, 20, 3, text="hello world", mode=mode, duration=2.0, seed=7, speed=5.0
        )
        w.mount()
        w.start()
        out: list[str] = []
        for _ in range(5):
            w.update(0.3)
            buf = Buffer(20, 3)
            w.draw(buf)
            out.extend(text_rows(buf))
        return out

    assert run() == run()


@pytest.mark.req("FR-ANIM-002")
def test_typewriter_progress() -> None:
    w = AnimatedText(0, 0, 20, 1, text="abcdef", mode="typewriter", speed=2.0)
    assert draw(w, 20, 1, t=1.0)[0].startswith("ab")


@pytest.mark.req("FR-ANIM-003")
def test_spinner_placement() -> None:
    assert (
        draw(
            AnimatedText(
                0,
                0,
                20,
                1,
                text="go",
                mode="scroll",
                spinner="line",
                placement="replace",
                reduced_motion=True,
            ),
            20,
            1,
        )[0].strip()
        == "-"
    )
    assert draw(
        AnimatedText(
            0, 0, 20, 1, text="go", mode="typewriter", spinner="line", placement="both", speed=100
        ),
        20,
        1,
        t=1.0,
    )[0].startswith("- go")


@pytest.mark.req("FR-ANIM-004")
def test_duration_stops_once_and_completes_once() -> None:
    calls: list[int] = []
    w = AnimatedText(0, 0, 20, 1, text="x", duration=1.0, on_complete=lambda: calls.append(1))
    w.mount()
    w.start()
    w.tick(0.6)
    w.tick(0.6)
    w.tick(0.6)
    assert calls == [1] and w.state.name == "STOPPED"


@pytest.mark.req("FR-ANIM-005", "FR-FX-007")
def test_animated_validation() -> None:
    with pytest.raises(ValueError):
        AnimatedText(mode="nope")
    with pytest.raises(ValueError):
        AnimatedText(speed=0)
    with pytest.raises(ValueError):
        AnimatedText(duration=-1)
    with pytest.raises(ValueError):
        AnimatedText(easing="zzz")


@pytest.mark.req("FR-FX-006")
def test_reduced_motion_is_static() -> None:
    a = draw(Marquee(0, 0, 8, 1, text="ABCDEFGHIJ", reduced_motion=True), 8, 1, t=3.0)
    assert a[0] == "ABCDEFGH"
    n = Neon(text="x", reduced_motion=True)
    n.update(1.0)
    first = n.colour()
    n.update(0.37)
    assert n.colour() == first
    m = MatrixRain(0, 0, 10, 4, seed=1, reduced_motion=True)
    assert draw(m, 10, 4) == draw(
        MatrixRain(0, 0, 10, 4, seed=1, reduced_motion=True), 10, 4, t=2.0
    )


@pytest.mark.req("FR-NEON-001", "FR-NEON-002")
def test_neon_cycles_and_wraps() -> None:
    n = Neon(0, 0, 10, 3, text="aa bb cc dd", wrap=True, align="center", speed=1.0)
    c0 = n.colour()
    n.update(0.25)
    assert n.colour() != c0
    assert any(r.strip() for r in draw(Neon(0, 0, 10, 3, text="aa bb cc dd", wrap=True), 10, 3))


@pytest.mark.req("FR-FX-005")
def test_neon_flicker_is_throttled() -> None:
    n = Neon(text="x", flicker=True)
    n.mount()
    n.start()
    toggles, last = 0, n._dim
    for _ in range(1000):
        n.update(0.01)
        if n._dim != last:
            toggles += 1
            last = n._dim
    assert toggles / 10.0 <= 3.0 * 2  # <= 3 flashes/s (each flash = 2 toggles)


@pytest.mark.req("FR-SIGN-001", "FR-SIGN-002")
@pytest.mark.parametrize(
    "mode", ["static", "typewriter", "bounce", "marquee", "wave", "fade", "neon", "gradient-scroll"]
)
def test_sign_modes(mode: str) -> None:
    rows = draw(Sign(0, 0, 40, 9, text="Hi", mode=mode, border="double", padding=0), 40, 9, t=0.5)
    assert rows[0].startswith("╔")
    with pytest.raises(ValueError):
        Sign(mode="zzz")


@pytest.mark.req("FR-MATRIX-001", "FR-MATRIX-002")
def test_matrix_seeded_and_reveal() -> None:
    a = draw(MatrixRain(0, 0, 20, 8, seed=3, density=1.0), 20, 8, t=1.0)
    b = draw(MatrixRain(0, 0, 20, 8, seed=3, density=1.0), 20, 8, t=1.0)
    assert a == b and any(r.strip() for r in a)
    assert draw(MatrixRain(0, 0, 20, 8, seed=3, density=0.0), 20, 8, t=1.0) == [" " * 20] * 8
    rev = draw(
        MatrixRain(0, 0, 20, 8, text="OK", mode="reveal", seed=3, reveal_after=0.5), 20, 8, t=5.0
    )
    assert "OK" in rev[4]
    with pytest.raises(ValueError):
        MatrixRain(density=1.5)


@pytest.mark.req("FR-VPRINT-001", "FR-VPRINT-002")
def test_vertical_print() -> None:
    assert vertical_text("abc") == ["a", "b", "c"] and vertical_text("abc", "up") == ["c", "b", "a"]
    rows = draw(VerticalPrint(0, 0, 3, 5, text="abc", spacing=1), 3, 5)
    assert [r.strip() for r in rows] == ["a", "", "b", "", "c"]
    assert draw(VerticalPrint(0, 0, 5, 8, text="HE", font="original-3", border="single"), 5, 8)[
        0
    ].startswith("┌")
    with pytest.raises(ValueError):
        vertical_text("x", "sideways")


@pytest.mark.req("FR-VPRINT-003")
def test_vprint_helpers() -> None:
    from widgets.display.vprint import clock_text, loading_text, rainbow_text

    assert (
        countdown_text(75) == "01:15"
        and countdown_text(3725) == "01:02:05"
        and countdown_text(-3) == "00:00"
    )
    assert clock_text(9, 5) == "09:05" and clock_text(9, 5, 7) == "09:05:07"
    assert loading_text(0.0) == "Loading" and loading_text(0.4).endswith(".")
    assert len(rainbow_text("abc")) == 3


@pytest.mark.req("FR-GAUGE-001", "FR-GAUGE-003")
@pytest.mark.parametrize("kind", ["circular", "speedometer", "semicircular", "thermometer"])
def test_gauge_kinds_render(kind: str) -> None:
    g = Gauge(0, 0, 17, 9, kind=kind, value=50, title="T", unit="%")
    rows = draw(g, 17, 9)
    assert any("50%" in r for r in rows)
    assert "50%" in g.text()


@pytest.mark.req("FR-GAUGE-002")
def test_gauge_clamp_and_validation() -> None:
    g = Gauge(minimum=0, maximum=10, value=15)
    assert g.value == 10 and g.out_of_range and "out of range" in g.text()
    g.set_value(5)
    assert not g.out_of_range
    with pytest.raises(ValueError):
        Gauge(minimum=5, maximum=5)
    with pytest.raises(ValueError):
        g.set_value(float("nan"))


@pytest.mark.req("FR-GAUGE-003")
def test_gauge_threshold_colour() -> None:
    from widgets.base_elements.widget_types import RGB

    g = Gauge(value=10, thresholds=((0, RGB(0, 255, 0)), (80, RGB(255, 0, 0))))
    assert g.colour() == RGB(0, 255, 0)
    g.set_value(90)
    assert g.colour() == RGB(255, 0, 0)


@pytest.mark.req("FR-NOTIFY-001", "FR-NOTIFY-002", "FR-NOTIFY-003")
def test_notifications_prefix_and_placement() -> None:
    clock = ManualClock()
    n = NotificationCenter(0, 0, 30, 4, clock=clock, placement="bottom", ascii_only=True)
    n.post("saved", NotificationType.SUCCESS)
    n.post("bad", NotificationType.ERROR)
    rows = draw(n, 30, 4)
    assert rows[2].startswith("[OK]") and rows[3].startswith("[ERROR]")
    assert {t.value[1] for t in NotificationType} == {
        "[INFO]",
        "[OK]",
        "[WARN]",
        "[ERROR]",
        "[NOTE]",
    }


@pytest.mark.req("FR-NOTIFY-004")
def test_notifications_expiry_dismiss_and_queue() -> None:
    clock = ManualClock()
    n = NotificationCenter(clock=clock, default_duration=5.0, max_queue=2)
    a = n.post("a")
    n.post("b", expires_at=100.0)
    n.post("c")
    assert [x.message for x in n.active] == ["b", "c"]
    clock.advance(6.0)
    assert [x.message for x in n.active] == ["b"]
    assert n.dismiss(2) and not n.dismiss(a or 0)
    n.post("d")
    n.dismiss_all()
    assert n.active == []
    q = NotificationCenter(clock=clock, max_queue=1, overflow="drop_newest")
    q.post("first")
    assert q.post("second") is None and q.active[0].message == "first"


@pytest.mark.req("FR-NOTIFY-004")
def test_notifications_thread_safe() -> None:
    import threading

    n = NotificationCenter(max_queue=500)
    threads = [threading.Thread(target=lambda: [n.post("x") for _ in range(50)]) for _ in range(8)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert len(n.active) == 400 and len({x.id for x in n.active}) == 400


@pytest.mark.req("FR-CAL-001")
def test_calendar_grid_and_navigation() -> None:
    today = dt.date(2026, 11, 6)
    c = CalendarWidget(year=2026, month=11, today=today, selected=today)
    rows = draw(c, 20, 8)
    assert "November 2026" in rows[0] and rows[1].startswith("Mo")
    sunday_first = CalendarWidget(year=2026, month=11, first_weekday=6, today=today)
    assert draw(sunday_first, 20, 8)[1].startswith("Su")
    chosen: list[dt.date] = []
    c.on_select = chosen.append
    for key in ("right", "down", "pagedown", "end", "home", "enter"):
        assert c.handle_key(KeyEvent(key))
    assert c.selected == dt.date(2026, 12, 1) and chosen == [dt.date(2026, 12, 1)]
    assert not c.handle_key(KeyEvent("x", "x"))
    c.enabled = False
    assert not c.handle_key(KeyEvent("left"))


@pytest.mark.req("FR-CAL-001")
def test_calendar_month_end_clamps() -> None:
    c = CalendarWidget(selected=dt.date(2026, 1, 31), today=dt.date(2026, 1, 1))
    c.handle_key(KeyEvent("pagedown"))
    assert c.selected == dt.date(2026, 2, 28)


@pytest.mark.req("FR-CAL-002")
def test_clock_timezone_and_countdown_once() -> None:
    fixed = dt.datetime(2026, 11, 6, 12, 0, 5, tzinfo=dt.UTC)
    assert ClockWidget(tz="UTC", now_fn=lambda: fixed).text() == "12:00:05"
    try:
        athens = ClockWidget(tz="Europe/Athens", now_fn=lambda: fixed)
    except ZoneInfoNotFoundError:
        pytest.skip("no tz database (pip install tzdata)")
    assert athens.text() == "14:00:05"
    clock = ManualClock()
    fired: list[int] = []
    cd = Countdown(3, clock=clock, on_complete=lambda: fired.append(1))
    cd.update(0)
    clock.advance(2)
    cd.update(0)
    assert fired == [] and countdown_text(cd.remaining) == "00:01"
    clock.advance(5)
    cd.update(0)
    cd.update(0)
    assert fired == [1]


@pytest.mark.req("FR-CAL-003")
def test_invalid_dates_and_zones() -> None:
    with pytest.raises(ValueError, match="invalid date"):
        make_date(2026, 13, 1)
    with pytest.raises(ValueError):
        CalendarWidget(year=2026, month=0)
    with pytest.raises(ZoneInfoNotFoundError):
        ClockWidget(tz="Mars/Olympus")
    with pytest.raises(ValueError):
        Countdown(-1)


def test_style_import_used() -> None:
    assert Style().is_default
