"""Gap closure against the legacy implementation: assets, tree, editor, form, grid, clock, tqdm."""

from __future__ import annotations

import asyncio
import datetime as dt
import io
from datetime import date

import pytest
from tests.conftest import text_rows

from widgets.assets import borders, symbols
from widgets.base_elements.events import KeyEvent
from widgets.data.code import CodeEditor, detect_language, highlight
from widgets.data.dashboard import DashboardGrid
from widgets.data.form import Field, Form
from widgets.data.tree import Tree, TreeNode
from widgets.display.box import Box
from widgets.display.calendar import ClockWidget
from widgets.progress import tqdm as tq
from widgets.render.buffer import Buffer


def key(name, char=None, **kw):
    return KeyEvent(name, char, **kw)


@pytest.mark.req("FR-ASSET-002")
def test_legacy_border_styles_added_and_legacy_spellings_resolve():
    names = borders.list_border_styles()
    for n in (
        "music",
        "arrow",
        "brackets",
        "parentheses",
        "triple-dash",
        "retro-slash",
        "modern-slim",
    ):
        assert n in names
        assert all(len(c) == 1 for c in borders.get_border_style(n).chars())
    assert (
        borders.get_border_style("triple_dash").name == "triple-dash"
    )  # underscore spelling accepted
    assert "bold-rounded" not in names  # corrupt legacy glyphs are not imported
    assert borders.get_border_style("single").chars()[0] == "┌"


@pytest.mark.req("FR-ASSET-006")
def test_unicode_helpers_categories_block_chars_codepoint_info():
    assert "LATIN_AND_DERIVATIVES" in symbols.list_categories()
    info = symbols.codepoint_info("é")
    assert (
        info["hex"] == "U+00E9"
        and info["block"] == "LATIN_1_SUPPLEMENT"
        and "LATIN" in str(info["name"])
    )
    chars = symbols.get_block_chars("BASIC_LATIN")
    assert "A" in chars and "\x00" not in chars
    assert symbols.lookup("sun").char == "☉"
    with pytest.raises(KeyError):
        symbols.get_block("nope")


@pytest.mark.req("FR-TREE-002")
def test_tree_expand_collapse_all_and_navigation_helpers():
    root = TreeNode("r")
    a = root.add(TreeNode("a"))
    a.add(TreeNode("a1")).add(TreeNode("a11"))
    root.add(TreeNode("b"))
    t = Tree(0, 0, 30, 10, root=root)
    assert len(t.visible_rows()) == 3
    t.handle_key(key("*", "*"))
    assert len(t.visible_rows()) == 5
    t.move_to_bottom()
    assert t.selected.label == "b"
    t.handle_key(key("-", "-"))
    assert len(t.visible_rows()) == 3 and t.index == 0
    t.expand_all()
    t.index = 3
    assert t.info() == {"label": "a11", "depth": 3, "children": 0, "descendants": 0}
    t.move_to_parent()
    assert t.selected.label == "a1"
    t.move_to_root()
    t.move_to_first_child()
    assert t.selected.label == "a"


@pytest.mark.req("FR-CODE-009")
def test_editor_selection_clipboard_and_undo():
    ed = CodeEditor(0, 0, 40, 6, text="hello world\nsecond line")
    ed.mount()
    for _ in range(5):
        ed.handle_key(key("right", shift=True))
    assert ed.selected_text() == "hello"
    ed.handle_key(key("c", "c", ctrl=True))
    assert ed.clipboard == "hello"
    ed.handle_key(key("x", "x", ctrl=True))
    assert ed.lines[0] == " world" and ed.selection() is None
    ed.handle_key(key("end"))
    ed.handle_key(key("v", "v", ctrl=True))
    assert ed.lines[0] == " worldhello"
    ed.handle_key(key("a", "a", ctrl=True))
    assert ed.selected_text() == ed.text
    ed.handle_key(key("q", "q"))  # typing replaces the selection
    assert ed.text == "q"
    assert ed.undo() and ed.text == " worldhello\nsecond line"
    ed.row = ed.col = 0
    ed.anchor = None
    ed.delete_forward()
    assert ed.lines[0] == "worldhello"
    ed.anchor = (0, 3)
    ed.row, ed.col = 1, 3  # multi-line selection
    assert ed.selected_text() == "ldhello\nsec"
    ed.delete_selection()
    assert ed.lines == ["worond line"]
    assert ed.undo() and ed.text == "worldhello\nsecond line"


@pytest.mark.req("FR-CODE-009")
def test_editor_search_wraps_and_selects_and_reverse():
    ed = CodeEditor(0, 0, 40, 6, text="one two\ntwo three\nfour two")
    assert ed.find("two") and ed.selected_text() == "two" and (ed.row, ed.col) == (0, 7)
    assert ed.find_next() and ed.row == 1
    assert ed.find_next() and ed.row == 2
    assert ed.find_next() and ed.row == 0  # wraps
    assert ed.find_previous() and ed.row == 2  # wraps backwards
    assert not ed.find("zzz") and "not found" in ed.message
    assert not ed.find("") or ed.search_query == ""
    ed.handle_key(key("f3"))  # repeats the last successful query? (empty after failure -> no crash)
    ed.mount()
    buf = Buffer(40, 6)
    ed.find("four")
    ed.draw(buf)


@pytest.mark.req("FR-CODE-004")
def test_language_detected_from_extension_on_load(tmp_path):
    f = tmp_path / "m.rs"
    f.write_text("fn main() {}\n", encoding="utf-8")
    ed = CodeEditor(0, 0, 40, 4)
    ed.load(f)
    assert (
        ed.language == "rust"
        and detect_language("x.PY") == "python"
        and detect_language("x.unknown") is None
    )
    explicit = CodeEditor(0, 0, 40, 4, language="python")
    explicit.load(f)
    assert explicit.language == "python"  # an explicit choice wins
    assert {k for _, _, k in highlight("fn main() {}", "rust")} >= {"keyword"}


@pytest.mark.req("FR-FORM-001")
def test_form_date_and_textarea_fields():
    d = Field("when", "date", value="2024-02-29")
    assert d.validate() is None and d.current() == date(2024, 2, 29)
    assert "date" in Field("when", "date", value="2024-02-30").validate()
    lo = Field("when", "date", value="2020-01-01", minimum=date(2021, 1, 1).toordinal())
    assert "on or after" in lo.validate()
    form = Form(
        0, 0, 50, fields=[Field("when", "date"), Field("note", "textarea"), Field("n", "text")]
    )
    form.mount()
    form.focus()
    for ch in "2024x-05-01":
        form.handle_key(key(ch, ch))
    assert form.fields[0].text == "2024-05-01"  # letters are ignored in date fields
    form.handle_key(key("tab"))
    for ch in "ab":
        form.handle_key(key(ch, ch))
    form.handle_key(key("enter"))  # newline, not submit
    form.handle_key(key("c", "c"))
    assert form.fields[1].text == "ab\nc"
    submitted = []
    form.on_submit = submitted.append
    form.handle_key(key("s", "s", ctrl=True))
    assert (
        submitted and submitted[0]["when"] == date(2024, 5, 1) and submitted[0]["note"] == "ab\nc"
    )


@pytest.mark.req("FR-DASH-001")
def test_dashboard_grid_places_resizes_and_describes():
    g = DashboardGrid(0, 0, 41, 21, rows=2, cols=2, gap=1)
    a, b, c = Box(0, 0, 1, 1, name="a"), Box(0, 0, 1, 1, name="b"), Box(0, 0, 1, 1, name="c")
    g.add_widget(a, 0, 0)
    g.add_widget(b, 0, 1, rowspan=2)
    g.add_widget(c, 1, 0)
    assert (a.x, a.y, a.width, a.height) == (0, 0, 20, 10)
    assert (b.x, b.width, b.height) == (21, 20, 21)
    with pytest.raises(ValueError):
        g.add_widget(Box(0, 0, 1, 1), 1, 1)  # occupied by b's span
    with pytest.raises(ValueError):
        g.add_widget(Box(0, 0, 1, 1), 2, 0)  # outside the grid
    g.resize(81, 41)
    assert a.width == 40 and c.y == 21
    spec = g.layout_spec()
    assert spec["rows"] == 2 and {x["widget"] for x in spec["cells"]} == {"a", "b", "c"}
    g.remove_widget(b)
    g.add_widget(Box(0, 0, 1, 1, name="d"), 1, 1)
    with pytest.raises(ValueError):
        DashboardGrid(rows=0)


@pytest.mark.req("FR-CAL-003")
def test_clock_big_font():
    now = dt.datetime(2024, 1, 1, 12, 34, 56, tzinfo=dt.UTC)
    c = ClockWidget(0, 0, font="ascii-5", now_fn=lambda: now)
    assert c.height == 5
    buf = Buffer(60, 5)
    c.mount()
    c.draw(buf)
    assert len("".join(text_rows(buf)).strip()) > 20
    small = ClockWidget(0, 0, now_fn=lambda: now)
    assert small.height == 1
    with pytest.raises(KeyError):
        ClockWidget(0, 0, font="no-such-font")


@pytest.mark.req("FR-API-001")
def test_tqdm_contrib_helpers_wrapattr_and_asyncio():
    out = io.StringIO()
    assert [i for i, _ in tq.tenumerate("abc", file=out)] == [0, 1, 2]
    assert list(tq.tzip([1, 2, 3], "ab", file=out)) == [(1, "a"), (2, "b")]
    assert list(tq.tmap(lambda a, b: a + b, [1, 2], [10, 20], file=out)) == [11, 22]
    src = io.BytesIO(b"x" * 1000)
    with tq.wrapattr(src, "read", total=1000, file=out) as f:
        assert len(f.read(400)) == 400 and len(f.read()) == 600
    sink = io.BytesIO()
    with tq.wrapattr(sink, "write", total=3, file=out) as f:
        f.write(b"abc")
    assert sink.getvalue() == b"abc"
    with pytest.raises(ValueError):
        tq.wrapattr(src, "seek")

    async def work(n):
        await asyncio.sleep(0.01 * (3 - n))
        return n * 2

    async def main():
        res = await tq.asyncio_tools.gather(*(work(i) for i in range(3)), file=out)
        done = []
        for fut in tq.asyncio_tools.as_completed([work(i) for i in range(3)], file=out):
            done.append(await fut)
        return res, done

    res, done = asyncio.run(main())
    assert res == [0, 2, 4] and sorted(done) == [0, 2, 4]
