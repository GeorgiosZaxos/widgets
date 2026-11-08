"""Release-hardening tests that close the traceability gaps found by tools/req_coverage.py."""

from __future__ import annotations

import threading
import time
from collections.abc import Callable
from typing import Any

import pytest

import widgets
from widgets.base_elements.events import KeyEvent
from widgets.base_elements.layout import Screen
from widgets.base_elements.widget_types import Style
from widgets.data.dashboard import DashboardWidget
from widgets.data.kanban import KanbanBoard
from widgets.data.logview import LogViewer
from widgets.data.table import Table
from widgets.data.tree import Tree
from widgets.display.box import Box
from widgets.display.calendar import ClockWidget
from widgets.display.marquee import Marquee
from widgets.display.notify import NotificationCenter
from widgets.display.palette import CommandPalette
from widgets.display.spinner import Spinner
from widgets.net.http import HttpResponse
from widgets.net.rss import FeedSource, RssReader
from widgets.net.rss_ticker import RssTicker, TickerLane
from widgets.render.buffer import Buffer


def key(k: str, **kw: object) -> KeyEvent:
    return KeyEvent(k, char=k if len(k) == 1 else None, **kw)  # type: ignore[arg-type]


def draw(w: Any, width: int = 40, height: int = 6) -> list[str]:
    buf = Buffer(width, height)
    w.render(buf)
    return buf.to_lines()


class SlowTransport:
    def __init__(self, delay: float = 0.4) -> None:
        self.delay = delay

    def get(
        self, url: str, *, headers: Any = None, timeout: float = 10.0, max_bytes: int = 1 << 20
    ) -> HttpResponse:
        time.sleep(self.delay)
        return HttpResponse(
            200, b"<rss version='2.0'><channel><item><title>t</title></item></channel></rss>", {}
        )


# -- FR-API-002 / FR-API-005 -------------------------------------------------------------------
@pytest.mark.req("FR-API-002")
def test_every_public_name_is_importable_from_its_documented_path() -> None:
    names = [n for n in widgets.__all__ if n != "__version__"]
    assert len(names) > 100
    for name in names:
        obj = getattr(widgets, name)
        assert obj is not None, name
        qual = getattr(obj, "__name__", None)
        if qual is None or not hasattr(obj, "__module__"):
            continue  # constants and typing aliases have no home module
        module = __import__(obj.__module__, fromlist=["x"])
        assert getattr(module, qual, obj) is obj, name  # alias is target


@pytest.mark.req("FR-API-005")
def test_many_widgets_in_one_session_create_position_update_render_dispose() -> None:
    screen = Screen(60, 12)
    box = Box(0, 0, 20, 3, text="hi")
    spin = Spinner(0, 4, 20)
    mq = Marquee(0, 6, 20, 1, text="scroll", reduced_motion=False)
    for w in (box, spin, mq):
        screen.add(w)
    mq.x, mq.y = 5, 8
    for w in (box, spin, mq):
        w.update(0.1)
    buf = Buffer(60, 12)
    screen.render(buf)
    assert any(line.strip() for line in buf.to_lines())
    for w in (box, spin, mq):
        w.close()


# -- FR-CORE-010 --------------------------------------------------------------------------------
@pytest.mark.req("FR-CORE-010")
def test_instances_never_share_mutable_state() -> None:
    factories: list[Callable[[], Any]] = [
        lambda: Table(columns=["a"], rows=[[1]]),
        lambda: Tree(),
        lambda: LogViewer(),
        lambda: KanbanBoard(columns={"a": ["x"]}),
        lambda: CommandPalette(commands={"x": lambda: None}),
        lambda: NotificationCenter(),
        lambda: Box(),
        lambda: Marquee(),
    ]
    for make in factories:
        a, b = make(), make()
        for attr, va in vars(a).items():
            vb = vars(b).get(attr)
            if isinstance(va, list | dict | set) and va is vb:
                pytest.fail(f"{type(a).__name__}.{attr} is shared between instances")


# -- FR-INPUT-003 / NFR-USE-003 ---------------------------------------------------------------
@pytest.mark.req("FR-INPUT-003")
def test_selection_stays_in_bounds_for_empty_and_small_content() -> None:
    rss = RssReader(0, 0, 40, 8)
    pal = CommandPalette(commands={})
    lv = LogViewer(0, 0, 40, 5)
    for w in (rss, pal, lv):
        for k in ("up", "down", "pageup", "pagedown", "home", "end", "enter"):
            w.handle_key(key(k))
        draw(w)
    assert rss.item_index == 0
    lv.log("one")
    for _ in range(5):
        lv.handle_key(key("down"))
        lv.handle_key(key("up"))
    draw(lv)


@pytest.mark.req("NFR-USE-003", "NFR-ACC-004")
def test_selection_is_marked_with_a_glyph_not_colour_alone() -> None:
    from widgets.net.rss import FeedItem

    rss = RssReader(0, 0, 40, 8, sources=[FeedSource("S", "https://x.test/f")])
    rss.feeds[0].items = [FeedItem("first"), FeedItem("second")]
    lines = draw(rss, 40, 8)
    assert any(line.lstrip().startswith(">") and "first" in line for line in lines)
    pal = CommandPalette(commands={"Alpha": lambda: None, "Beta": lambda: None})
    assert any(">" in line or "▶" in line for line in draw(pal, 40, 8))


# -- FR-LIFE-004 / FR-LIFE-006 / NFR-PERF-004 -------------------------------------------------
@pytest.mark.req("FR-LIFE-004", "NFR-PERF-004")
def test_network_refresh_never_blocks_ui_and_close_joins_workers() -> None:
    rss = RssReader(
        0, 0, 40, 8, sources=[FeedSource("S", "https://x.test/f")], transport=SlowTransport(0.4)
    )
    t0 = time.perf_counter()
    assert rss.refresh(force=True) == 1
    assert time.perf_counter() - t0 < 0.15  # UI thread returns immediately
    rss.update(0.0)
    workers = [t for t in threading.enumerate() if t.name == "widgets-net"]
    assert workers
    rss.on_close()  # joins with a timeout
    assert not [t for t in threading.enumerate() if t.name == "widgets-net" and t.is_alive()]


@pytest.mark.req("FR-LIFE-006")
def test_dashboard_widget_uses_the_standard_lifecycle() -> None:
    d = DashboardWidget(0, 0, 30, 4, fetch=lambda: 1, interval=0.5)
    d.mount()
    d.start()
    d.update(1.0)
    d.pause()
    d.resume()
    d.stop()
    d.close()


# -- NFR-ACC-001 / NFR-ACC-003 / NFR-ACC-005 -----------------------------------------------
@pytest.mark.req("NFR-ACC-001")
def test_widgets_describe_themselves_as_text() -> None:
    samples = [
        Box(text="x"),
        Spinner(),
        Marquee(text="m"),
        Table(columns=["a"], rows=[[1]]),
        LogViewer(),
        KanbanBoard(columns={"a": []}),
        RssTicker(
            lanes=[TickerLane(FeedSource("S", "https://x.test/f"))], transport=SlowTransport(0)
        ),
    ]
    for w in samples:
        text = w.describe()
        assert isinstance(text, str) and text.strip(), type(w).__name__
        w.close()


@pytest.mark.req("NFR-ACC-003")
def test_wide_and_combining_characters_never_overflow_the_row() -> None:
    box = Box(0, 0, 10, 3, text="日本語日本語日本語 éé")
    for line in draw(box, 10, 3):
        from widgets.render.width import display_width

        assert display_width(line) <= 10


@pytest.mark.req("NFR-ACC-005")
def test_reduced_motion_freezes_animation_everywhere() -> None:
    from widgets.display.effects_widgets import MatrixRain, Neon
    from widgets.display.marquee import AnimatedText

    makers: list[Callable[[], Any]] = [
        lambda: Marquee(0, 0, 20, 1, text="scrolling text", reduced_motion=True),
        lambda: AnimatedText(0, 0, 20, 1, text="wave", mode="wave", reduced_motion=True),
        lambda: Neon(0, 0, 30, 6, text="N", reduced_motion=True),
        lambda: MatrixRain(0, 0, 20, 6, reduced_motion=True),
        lambda: Spinner(reduced_motion=True),
    ]
    for make in makers:
        w = make()
        before = draw(w, 30, 6)
        w.update(2.0)
        assert draw(w, 30, 6) == before, type(w).__name__


# -- NFR-I18N-002 ----------------------------------------------------------------------------
@pytest.mark.req("NFR-I18N-002")
def test_time_zones_use_zoneinfo_and_utc_always_works() -> None:
    import datetime as dt

    fixed = dt.datetime(2026, 1, 1, 12, 0, tzinfo=dt.UTC)
    utc = ClockWidget(tz="UTC", now_fn=lambda: fixed)
    assert "12:00" in "".join(draw(utc, 20, 1))
    try:
        import zoneinfo

        zoneinfo.ZoneInfo("Europe/Athens")
    except Exception:
        pytest.skip("tz database unavailable")
    athens = ClockWidget(tz="Europe/Athens", now_fn=lambda: fixed)
    assert "14:00" in "".join(draw(athens, 20, 1))


# -- NFR-PERF-002 / NFR-PERF-003 ---------------------------------------------------------------
@pytest.mark.req("NFR-PERF-002")
def test_frame_loop_sleeps_instead_of_busy_waiting() -> None:
    from conftest import make_renderer
    from widgets.base_elements.effects import ManualClock
    from widgets.render.run import FrameLoop

    renderer, _out = make_renderer()
    clock = ManualClock()
    loop = FrameLoop(
        Screen(10, 2), renderer=renderer, clock=clock, size=(10, 2), fps=30, duration=1.0
    )
    loop.run()
    assert clock.sleeps  # the loop waits for the next deadline between frames
    assert sum(clock.sleeps) > 0.5  # and spends most of the second asleep


@pytest.mark.req("NFR-PERF-003")
def test_collections_are_bounded() -> None:
    lv = LogViewer(max_entries=5)
    for i in range(50):
        lv.log(str(i))
    assert len(lv.entries) == 5
    nc = NotificationCenter(max_queue=3)
    for i in range(10):
        nc.post(f"n{i}")
    assert len(nc.active) <= 3
    rss = RssReader(max_items_per_feed=2)
    assert rss.max_items_per_feed == 2


# -- NFR-USE-002 / NFR-USE-004 -----------------------------------------------------------------
@pytest.mark.req("NFR-USE-002")
@pytest.mark.parametrize(
    ("factory", "param"),
    [
        (lambda: Marquee(speed=0), "speed"),
        (lambda: Marquee(direction="sideways"), "direction"),
        (lambda: LogViewer(max_entries=0), "max_entries"),
        (lambda: NotificationCenter(max_queue=0), "max_queue"),
        (lambda: RssReader(max_items_per_feed=0), "limits"),
        (lambda: RssTicker(lanes=[]), "lane"),
    ],
)
def test_invalid_configuration_names_the_parameter(factory: Callable[[], Any], param: str) -> None:
    with pytest.raises((ValueError, TypeError)) as info:
        factory()
    assert param in str(info.value)


@pytest.mark.req("NFR-USE-004")
def test_tiny_canvases_are_clipped_not_crashed() -> None:
    widgets_under_test: list[Any] = [
        Box(0, 0, 30, 5, text="hello world, this is long"),
        Table(0, 0, 30, 5, columns=["a", "b"], rows=[[1, 2]]),
        LogViewer(0, 0, 30, 5),
        KanbanBoard(columns={"a": ["x"], "b": []}),
        Marquee(0, 0, 30, 1, text="abc"),
    ]
    for w in widgets_under_test:
        for size in ((1, 1), (3, 1), (5, 2), (7, 3)):
            buf = Buffer(*size)
            w.render(buf)
            assert all(len(line) <= size[0] * 2 for line in buf.to_lines())


def test_style_is_importable() -> None:  # keeps the Style import honest for type checkers
    assert Style().bold is False


# -- NFR-USE-001 / NFR-MAINT-002 / FR-PROG-014 ------------------------------------------------
def _public_objects() -> list[tuple[str, Any]]:
    import importlib
    import inspect
    import pkgutil
    import warnings

    found: list[tuple[str, Any]] = []
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        for info in pkgutil.walk_packages(widgets.__path__, "widgets."):
            if info.name.startswith("widgets.include") or "._" in info.name:
                continue
            mod = importlib.import_module(info.name)
            found.append((info.name, mod))
            for name, obj in vars(mod).items():
                if name.startswith("_") or getattr(obj, "__module__", None) != info.name:
                    continue
                if inspect.isclass(obj) or inspect.isfunction(obj):
                    found.append((f"{info.name}.{name}", obj))
    return found


@pytest.mark.req("NFR-USE-001")
def test_every_public_module_class_and_function_has_a_docstring() -> None:
    missing = [n for n, o in _public_objects() if not (o.__doc__ or "").strip()]
    assert not missing, missing


@pytest.mark.req("NFR-MAINT-002")
def test_widget_protocol_signatures_are_consistent() -> None:
    import inspect

    from widgets.base_elements.base import Widget
    from widgets.base_elements.interactive import InteractiveWidget

    def params(cls: type, method: str) -> list[str]:
        return list(inspect.signature(getattr(cls, method)).parameters)[1:]

    for _name, obj in _public_objects():
        if not (inspect.isclass(obj) and issubclass(obj, Widget)):
            continue
        assert params(obj, "update") == ["dt"] or params(obj, "update")[0].startswith("dt"), obj
        if issubclass(obj, InteractiveWidget):
            assert params(obj, "handle_key") == ["event"], obj


@pytest.mark.req("FR-PROG-014", "FR-API-008")
def test_tqdm_compatible_import_paths_resolve_to_current_objects() -> None:
    import widgets.progress.tqdm as legacy

    assert widgets.tqdm is legacy.tqdm
    assert widgets.trange is legacy.trange
