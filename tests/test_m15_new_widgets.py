"""New widgets: tabs, split pane, stepper, sparkline, heatmap, log viewer, palette, timer,
image/QR, kanban, markdown, process monitor, scope, game."""

from __future__ import annotations

import pytest

from widgets.audio.scope import Oscilloscope
from widgets.base_elements.events import KeyEvent
from widgets.data.kanban import KanbanBoard, MarkdownView
from widgets.data.logview import LogViewer
from widgets.data.procmon import ProcessMonitor
from widgets.display.box import Box
from widgets.display.game import GridGame
from widgets.display.image import ImageView, QrView
from widgets.display.palette import CommandPalette, TimerWidget, fuzzy_score
from widgets.display.stepper import Heatmap, Sparkline, Stepper
from widgets.display.tabs import SplitPane, Tabs
from widgets.errors import MissingDependencyError
from widgets.render.buffer import Buffer


def key(k: str, **kw: object) -> KeyEvent:
    return KeyEvent(k, char=k if len(k) == 1 else None, **kw)  # type: ignore[arg-type]


def draw(widget, w: int | None = None, h: int | None = None) -> str:  # type: ignore[no-untyped-def]
    if widget.state.value == "created":
        widget.mount()
        widget.start()
    buf = Buffer(w or max(1, widget.width), h or max(1, widget.height))
    widget.render(buf)
    return "\n".join("".join(c.glyph for c in buf.row(r)) for r in range(buf.height))


def test_tabs_switch_and_visibility() -> None:
    tabs = Tabs(0, 0, 40, 6)
    a = tabs.add_page("One", Box(text="A"))
    b = tabs.add_page("Two", Box(text="B"))
    assert a.visible and not b.visible
    assert tabs.handle_key(key("pagedown", ctrl=True)) and tabs.index == 1
    assert b.visible and not a.visible
    assert tabs.handle_key(key("1", alt=True)) and tabs.index == 0
    assert "One" in draw(tabs)


def test_split_pane_ratio() -> None:
    sp = SplitPane(0, 0, 41, 6, first=Box(text="L"), second=Box(text="R"), ratio=0.5)
    assert sp.first.width + sp.second.width == 40
    before = sp.first.width
    sp.handle_key(key("right", alt=True))
    assert sp.first.width > before
    with pytest.raises(ValueError):
        SplitPane(first=Box(), second=Box(), orientation="diag")


def test_stepper_states_and_symbols() -> None:
    st = Stepper(0, 0, 60, steps=["Fetch", "Build", "Test"])
    st.advance()
    st.fail()
    assert [st.step_state(i) for i in range(3)] == ["done", "failed", "pending"]
    text = draw(st)
    assert "●" in text and "✖" in text and "○" in text
    assert not st.finished


def test_sparkline_scales_and_bounds() -> None:
    sp = Sparkline(0, 0, 5, values=[0, 1, 2, 3, 4, 5, 6])
    assert len(sp.values) == 5
    assert sp.text()[-1] == "█"
    sp.push(0)
    assert len(sp.values) == 5


def test_heatmap_levels() -> None:
    hm = Heatmap(0, 0, data=[[0, 5], [10, 5]], row_labels=["a", "b"])
    assert hm.level(0) == 0 and hm.level(10) == 1
    assert "██" in draw(hm)


def test_logview_filter_follow_bounds() -> None:
    lv = LogViewer(0, 0, 60, 5, max_entries=10, show_time=False)
    for i in range(30):
        lv.log(f"line {i}", "ERROR" if i % 10 == 0 else "INFO")
    assert len(lv.entries) == 10
    lv.set_filter(min_level="ERROR")
    assert all(e.level == "ERROR" for e in lv.visible_entries())
    lv.set_filter("", "DEBUG")
    lv.handle_key(key("up"))
    assert not lv.follow
    lv.handle_key(key("end"))
    assert lv.follow
    assert "ERR" in draw(lv) or "INF" in draw(lv)
    with pytest.raises(ValueError):
        lv.log("x", "LOUD")


def test_command_palette_fuzzy_and_run() -> None:
    hits: list[str] = []
    pal = CommandPalette(
        commands={"Open file": lambda: hits.append("open"), "Quit app": lambda: hits.append("quit")}
    )
    for ch in "qa":
        pal.handle_key(key(ch))
    assert pal.matches()[0] == "Quit app"
    pal.handle_key(key("enter"))
    assert hits == ["quit"]
    assert fuzzy_score("zzz", "abc") is None and fuzzy_score("", "x") == 0
    pal.handle_key(key("backspace"))
    assert pal.query == "q"


def test_timer_countdown_and_finish() -> None:
    done: list[int] = []
    t = TimerWidget(
        mode="countdown", duration=3, on_finish=lambda: done.append(1), reduced_motion=True
    )
    t.mount()
    t.start()
    t.update(1.0)
    assert t.clock_text() == "00:02"
    t.update(5.0)
    assert t.finished and done == [1] and t.clock_text() == "00:00"
    t.reset()
    assert not t.finished
    pomo = TimerWidget(mode="pomodoro", phases=[("focus", 2), ("break", 1)], reduced_motion=True)
    pomo.mount()
    pomo.start()
    pomo.update(2.5)
    assert pomo.phase()[0] == "break"


def test_image_view_and_qr() -> None:
    img = ImageView.gradient(8, 4)
    assert img.width == 8 and img.height == 2
    assert "▀" in draw(img)
    try:
        import qrcode  # noqa: F401
    except ImportError:
        with pytest.raises(MissingDependencyError):
            QrView(text="hello")
    else:
        assert "▀" in draw(QrView(text="hello"))


def test_kanban_move_and_delete() -> None:
    kb = KanbanBoard(columns={"todo": ["a", "b"], "doing": [], "done": []})
    kb.handle_key(key("]"))
    assert kb.columns["todo"] == ["b"] and kb.columns["doing"] == ["a"] and kb.col == 1
    assert kb.handle_key(key("d")) and kb.columns["doing"] == []
    assert not kb.handle_key(key("["))
    assert "todo" in draw(kb)


def test_markdown_renders_subset() -> None:
    md = MarkdownView(
        0, 0, 40, 10, text="# Title\n\n- item **bold**\n\n```\ncode\n```\n[link](http://x)"
    )
    out = draw(md)
    assert "TITLE" in out and "• item bold" in out and "link <http://x>" in out
    assert md.handle_key(key("end"))


def test_process_monitor_with_injected_fetch() -> None:
    rows = [
        {"pid": 1, "name": "init", "cpu": 1.0, "mem": 0.5},
        {"pid": 2, "name": "busy", "cpu": 90.0, "mem": 2.0},
    ]
    pm = ProcessMonitor(0, 0, 60, 8, fetch=lambda: [dict(r) for r in rows])
    pm.update(1.0)
    assert pm.rows[0]["name"] == "busy"
    pm.handle_key(key("s"))
    assert pm.sort == "mem"
    assert "busy" in draw(pm)
    bad = ProcessMonitor(fetch=lambda: 1 / 0)  # type: ignore[arg-type,return-value]
    bad.update(2.0)
    assert "fetch failed" in bad.error


def test_oscilloscope_modes() -> None:
    scope = Oscilloscope(0, 0, 30, 6, reduced_motion=True)
    assert "simulated" in draw(scope)
    live = Oscilloscope(0, 0, 30, 6, source=lambda n: [0.5] * n)
    assert "live" in draw(live)


def test_grid_game_collect_and_walls() -> None:
    wins: list[int] = []
    g = GridGame(0, 0, 30, 8, level=["####", "#@*#", "####"], on_win=wins.append)
    assert not g.step(0, -1)
    assert g.step(1, 0) and g.won and wins == [1]
    assert not g.step(-1, 0)
    g.handle_key(key("r"))
    assert not g.won
    assert "gems" in draw(g)


# -- RssTicker ---------------------------------------------------------------------------
def _ticker_transport():
    from widgets.net.http import HttpResponse

    class T:
        def get(self, url, *, headers=None, timeout=10.0, max_bytes=1 << 20):
            name = url.rsplit("/", 1)[-1]
            items = "".join(f"<item><title>{name} story {i}</title></item>" for i in range(5))
            return HttpResponse(
                200, f"<rss version='2.0'><channel>{items}</channel></rss>".encode(), {}
            )

    return T()


def test_rss_ticker_lanes_scroll_with_own_direction_speed_colour() -> None:
    import time

    from widgets.base_elements.widget_types import RGB
    from widgets.net.rss import FeedSource
    from widgets.net.rss_ticker import RssTicker, TickerLane
    from widgets.render.buffer import Buffer

    lanes = [
        TickerLane(FeedSource("A", "https://x.test/a"), "left", 10, color="#ff0000"),
        TickerLane(FeedSource("B", "https://x.test/b"), "right", 20, color="#00ff00"),
    ]
    t = RssTicker(0, 0, 30, lanes=lanes, transport=_ticker_transport(), spacing=1)
    assert t.height == 3
    for _ in range(100):
        t.update(0.05)
        if "story" in t.lane_text(0) and "story" in t.lane_text(1):
            break
        time.sleep(0.02)
    assert "A ▸ a story 0" in t.lane_text(0)
    buf = Buffer(30, 3)
    t.render(buf)
    lines = buf.to_lines()
    assert lines[1].strip() == ""  # spacing row stays empty
    assert lines[0].strip() and lines[2].strip()
    assert buf.get_cell(0, 0).style.fg == RGB(255, 0, 0)
    assert buf.get_cell(2, 0).style.fg == RGB(0, 255, 0)
    before = lines[0]
    t.update(1.0)
    t.render(buf)
    assert buf.to_lines()[0] != before  # lane 0 moved
    t.update(1.0)
    assert t._marquees[0].direction == "left" and t._marquees[1].direction == "right"
    assert t._marquees[1].speed == 20
    assert t._marquees[0].style.fg == RGB(255, 0, 0)
    t.set_speed_scale(2.0)
    assert t._marquees[1].speed == 40
    t.reverse()
    assert t._marquees[0].direction == "right"
    t.on_close()


def test_rss_ticker_validation() -> None:
    import pytest

    from widgets.net.rss import FeedSource
    from widgets.net.rss_ticker import RssTicker, TickerLane

    src = FeedSource("A", "https://x.test/a")
    with pytest.raises(ValueError):
        RssTicker(lanes=[])
    with pytest.raises(ValueError):
        RssTicker(lanes=[TickerLane(src, "up")])
    with pytest.raises(ValueError):
        RssTicker(lanes=[TickerLane(src, "left", 0)])


def test_rss_ticker_per_lane_speed_keys() -> None:
    from widgets.net.rss import FeedSource
    from widgets.net.rss_ticker import RssTicker, TickerLane
    from widgets.render.buffer import Buffer

    lanes = [TickerLane(FeedSource(n, f"https://x.test/{n}"), "left", 10) for n in "ab"]
    t = RssTicker(0, 0, 40, lanes=lanes, transport=_ticker_transport(), show_speed=True)
    t.handle_key(key("down"))
    t.handle_key(key("+"))
    assert t.lane_speed(0) == 10 and t.lane_speed(1) == 12.5
    t.handle_key(key("]"))
    assert t.lane_speed(0) == 12.5 and t.lane_speed(1) == 15.625
    buf = Buffer(40, 2)
    t.render(buf)
    assert "/s" in buf.to_lines()[1]
    t.on_close()
