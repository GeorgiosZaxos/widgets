"""M5 data widgets: table, chart, tree, form, directory tree, dashboard, code editor."""

from __future__ import annotations

import os
import stat
import time
from pathlib import Path

import pytest
from hypothesis import given
from hypothesis import strategies as st
from tests.conftest import text_rows

from widgets.base_elements.events import KeyEvent
from widgets.data.chart import Chart, Dataset
from widgets.data.code import CodeEditor, CodeFileError, highlight
from widgets.data.dashboard import MetricDashboard, TextDashboard
from widgets.data.dirtree import DirectoryTree
from widgets.data.form import Field, Form
from widgets.data.table import Table, sort_key
from widgets.data.tree import Tree, TreeDataError, from_json, from_python, from_xml
from widgets.errors import MissingDependencyError, TableDataError
from widgets.render.buffer import Buffer


def draw(widget, w: int, h: int) -> list[str]:
    buf = Buffer(w, h)
    if widget.state.name == "CREATED":
        widget.mount()
    widget.draw(buf)
    return text_rows(buf)


def key(name: str, char: str | None = None, **kw: bool) -> KeyEvent:
    return KeyEvent(name, char, **kw)


# ---------------------------------------------------------------- table
@pytest.mark.req("FR-TABLE-001", "FR-TABLE-002")
def test_table_render_header_numbers_alignment() -> None:
    t = Table(
        0,
        0,
        30,
        6,
        columns=["name", "qty"],
        rows=[["apple", 3], ["fig", 12]],
        row_numbers=True,
        align=["left", "right"],
    )
    rows = draw(t, 30, 6)
    assert "name" in rows[0] and "qty" in rows[0] and rows[1].startswith("─")
    assert "apple" in rows[2] and rows[3].rstrip().endswith("12")
    assert t.column_widths(30)[0] == 5


@pytest.mark.req("FR-TABLE-002")
def test_table_fixed_and_proportional_widths() -> None:
    t = Table(columns=["a", "b", "c"], rows=[[1, 2, 3]], widths=[4, "1fr", "3fr"])
    w = t.column_widths(44)
    assert w[0] == 4 and w[2] > w[1]


@pytest.mark.req("FR-TABLE-003")
def test_table_navigation_scroll_and_hide() -> None:
    t = Table(0, 0, 20, 6, columns=["n"], rows=[[i] for i in range(50)])
    t.focus()
    for _ in range(10):
        t.handle_key(key("down"))
    assert t.cursor_row == 10 and t.top > 0
    t.handle_key(key("end"))
    assert t.cursor_row == 49
    t.handle_key(key("home"))
    assert t.cursor_row == 0 and t.top == 0
    t2 = Table(columns=["a", "b"], rows=[[1, 2]])
    t2.set_column_visible(0, False)
    assert t2.visible_columns() == [1]


@pytest.mark.req("FR-TABLE-004")
def test_table_loaders() -> None:
    t = Table()
    t.load_csv("a,b\n1,2\n3,4\n")
    assert t.columns == ["a", "b"] and t.rows == [["1", "2"], ["3", "4"]]
    t.load_tsv("a\tb\n1\t2")
    assert t.rows == [["1", "2"]]
    t.load_pipe("a|b\nx|y")
    assert t.rows == [["x", "y"]]
    t.load_json('[{"a": 1, "b": 2}, {"a": 3}]')
    assert t.rows == [[1, 2], [3, None]]
    t.load_json('[["h1", "h2"], [1, 2]]')
    assert t.columns == ["h1", "h2"]

    class Frame:
        columns = ("x", "y")

        class values:
            @staticmethod
            def tolist() -> list[list[int]]:
                return [[1, 2]]

    t.load_dataframe(Frame())
    assert t.columns == ["x", "y"] and t.rows == [[1, 2]]


@pytest.mark.req("FR-TABLE-004")
def test_missing_optional_dependency() -> None:
    try:
        import openpyxl  # noqa: F401
    except ImportError:
        with pytest.raises(MissingDependencyError):
            Table().load_excel("nope.xlsx")
    with pytest.raises(MissingDependencyError):
        Table().load_dataframe(object())


@pytest.mark.req("FR-TABLE-005")
def test_table_malformed_input_is_atomic() -> None:
    t = Table(columns=["keep"], rows=[["me"]])
    with pytest.raises(TableDataError) as info:
        t.load_csv("a,b\n1,2\n3\n")
    assert info.value.row == 3 and t.rows == [["me"]]
    with pytest.raises(TableDataError):
        t.load_json("{not json")
    with pytest.raises(TableDataError):
        t.load_csv("")
    t.load_csv("a,b\n1\n", strict=False)
    assert t.columns == [] and t.rows == []


@pytest.mark.req("FR-TABLE-006")
def test_table_sort_rules() -> None:
    rows = [[None], ["b"], [2], [float("nan")], ["A"], [10], [object.__name__]]
    t = Table(columns=["v"], rows=rows)
    t.sort(0)
    got = [r[0] for r in t.rows]
    assert got[:2] == [2, 10] and got[2:5] == ["A", "b", "object"] and got[5] is None
    t.sort(0, reverse=True)
    assert t.rows[-1][0] is None or t.rows[-2][0] is None
    # stability
    s = Table(columns=["k", "i"], rows=[[1, "a"], [1, "b"], [0, "c"]])
    s.sort(0)
    assert [r[1] for r in s.rows] == ["c", "a", "b"]
    assert sort_key(True)[0] == 2


@given(
    st.lists(st.one_of(st.none(), st.integers(), st.text(max_size=3), st.floats(allow_nan=True)))
)
@pytest.mark.req("FR-TABLE-006")
def test_sort_never_raises_and_keeps_rows(values: list[object]) -> None:
    t = Table(columns=["v"], rows=[[v] for v in values])
    t.sort(0)
    assert len(t.rows) == len(values)


@pytest.mark.req("FR-TABLE-007")
def test_table_cell_limit() -> None:
    t = Table(0, 0, 30, 10)
    t.load_csv("a,b\n" + "\n".join("1,2" for _ in range(10)), max_cells=8)
    assert len(t.rows) == 4 and t.truncated
    assert "truncated" in draw(t, 30, 10)[-1]
    with pytest.raises(TableDataError):
        t.load_csv("a,b\n" + "\n".join("1,2" for _ in range(10)), max_cells=8, on_limit="reject")


# ---------------------------------------------------------------- chart
def _chart(kind: str, **kw: object) -> Chart:
    c = Chart(0, 0, 40, 12, kind=kind, title="T", **kw)  # type: ignore[arg-type]
    c.set_data([Dataset("a", [1, 3, 2, 5], labels=list("wxyz")), Dataset("b", [2, 1, 4, 3])])
    return c


@pytest.mark.req("FR-CHART-001", "FR-CHART-003")
@pytest.mark.parametrize("kind", ["bar", "line", "pie", "scatter", "area"])
def test_chart_kinds_render_with_title_and_legend(kind: str) -> None:
    rows = draw(_chart(kind), 40, 12)
    assert "T" in rows[0] and "a" in rows[-1] and any(r.strip() for r in rows[2:-2])
    assert any(r.strip() for r in draw(_chart(kind, ascii_only=True), 40, 12))


@pytest.mark.req("FR-CHART-002")
def test_chart_empty_and_nonfinite() -> None:
    empty = Chart(0, 0, 40, 12)
    assert any("No data" in r for r in draw(empty, 40, 12))
    c = Chart(0, 0, 40, 12, kind="bar")
    c.set_data([Dataset("a", [1.0, float("nan"), float("inf"), 3.0])])
    assert any("?" in r for r in draw(c, 40, 12))
    c.set_data([Dataset("a", [float("nan")])])
    assert any("No data" in r for r in draw(c, 40, 12))


@pytest.mark.req("FR-CHART-003", "FR-CHART-004")
def test_chart_toggle_and_invalidate() -> None:
    c = _chart("bar")
    draw(c, 40, 12)
    assert not c.dirty
    c.toggle("a", False)
    assert c.dirty
    c.toggle("b", False)
    assert any("No data" in r for r in draw(c, 40, 12))


@pytest.mark.req("FR-CHART-005")
def test_chart_too_small() -> None:
    small = _chart("bar")
    small.resize(10, 3)
    assert "too small" in draw(small, 10, 3)[0]
    with pytest.raises(ValueError):
        Chart(kind="radar")


# ---------------------------------------------------------------- tree
@pytest.mark.req("FR-TREE-001", "FR-TREE-002", "FR-TREE-004")
def test_tree_navigation_and_expand() -> None:
    root = from_python({"a": {"x": 1, "y": 2}, "b": [1, 2]}, "root")
    t = Tree(0, 0, 30, 10, root=root)
    t.focus()
    rows = draw(t, 30, 10)
    assert rows[0].lstrip().startswith("▾") and "a" in rows[1]
    t.handle_key(key("down"))
    t.handle_key(key("right"))  # expand a
    assert len(t.visible_rows()) > 3
    t.handle_key(key("down"))
    assert t.selected is not None and t.selected.label.startswith("x")
    t.handle_key(key("left"))  # to parent
    assert t.selected is not None and t.selected.label == "a"
    t.handle_key(key("left"))  # collapse
    assert not t.selected.expanded  # type: ignore[union-attr]
    chosen: list[str] = []
    t.on_select = lambda n: chosen.append(n.label)
    t.handle_key(key("enter"))
    assert chosen == ["a"]
    t.handle_key(key("end"))
    assert t.selected is not None and t.selected.label == "b"


@pytest.mark.req("FR-TREE-003")
def test_tree_loaders_and_xml_security() -> None:
    assert from_json('{"k": [1, {"z": 2}]}').children[0].label == "k"
    node = from_xml('<a x="1"><b>text</b><c/></a>')
    assert node.label == '<a x="1">' and len(node.children) == 2
    for bad in (
        '<!DOCTYPE a [<!ENTITY e "x">]><a>&e;</a>',
        "<!doctype a><a/>",
        '<!ENTITY e "x"><a/>',
    ):
        with pytest.raises(TreeDataError):
            from_xml(bad)
    with pytest.raises(TreeDataError):
        from_xml("<a>" + "x" * 100 + "</a>", max_bytes=50)
    with pytest.raises(TreeDataError):
        from_xml("<a><b></a>")
    with pytest.raises(TreeDataError):
        from_json("{bad")


# ---------------------------------------------------------------- form
def _form(**cb: object) -> Form:
    return Form(
        0,
        0,
        50,
        fields=[
            Field("name", "text", "Name", required=True, max_length=5),
            Field("age", "int", "Age", minimum=0, maximum=120),
            Field("ratio", "float", "Ratio"),
            Field("ok", "checkbox", "Agree"),
            Field("color", "dropdown", "Color", options=["red", "green", "blue"], value="green"),
        ],
        **cb,
    )  # type: ignore[arg-type]


def type_text(form: Form, text: str) -> None:
    for ch in text:
        form.handle_key(key(ch, ch))


@pytest.mark.req("FR-FORM-001", "FR-FORM-002", "FR-FORM-004", "FR-FORM-006")
def test_form_typing_and_values() -> None:
    changes: list[tuple[str, object]] = []
    f = _form(on_change=lambda n, v: changes.append((n, v)))
    f.focus()
    type_text(f, "abcdefgh")  # max_length 5
    assert f.get("name") == "abcde"
    f.handle_key(key("backspace"))
    f.handle_key(key("tab"))
    type_text(f, "42")
    f.handle_key(key("down"))
    type_text(f, "2.5")
    f.handle_key(key("down"))
    f.handle_key(key("space", " "))
    f.handle_key(key("down"))
    f.handle_key(key("enter"))  # open dropdown
    f.handle_key(key("down"))
    f.handle_key(key("enter"))
    vals = f.values()
    assert vals == {"name": "abcd", "age": 42, "ratio": 2.5, "ok": True, "color": "blue"}
    assert ("age", 42) in changes and f.values() is not f.values()
    f.handle_key(key("backtab"))
    assert f.index == 3


@pytest.mark.req("FR-FORM-003", "FR-FORM-005")
def test_form_validation_blocks_submit() -> None:
    submitted: list[dict[str, object]] = []
    cancelled: list[int] = []
    f = _form(on_submit=submitted.append, on_cancel=lambda: cancelled.append(1))
    f.fields[1].validators = [lambda v: "no sevens" if v == 7 else None]
    assert not f.submit() and f.fields[0].error == "required" and not submitted
    f.fields[0].text = "bob"
    f.fields[1].text = "7"
    assert not f.submit() and f.fields[1].error == "no sevens"
    f.fields[1].text = "200"
    assert not f.submit() and "<=" in (f.fields[1].error or "")
    f.fields[1].text = "x"
    assert not f.submit() and "whole" in (f.fields[1].error or "")
    f.fields[1].text = "30"
    assert f.submit() and submitted[0]["age"] == 30
    f.handle_key(key("escape"))
    assert cancelled == [1]
    f.fields[1].text = "999"
    f.submit()
    assert any("!" in r for r in draw(f, 50, 6))
    with pytest.raises(KeyError):
        f.get("zzz")
    with pytest.raises(ValueError):
        Form(fields=[Field("a"), Field("a")])
    with pytest.raises(ValueError):
        Field("d", "dropdown")


# ---------------------------------------------------------------- directory tree
@pytest.fixture
def tree_dir(tmp_path: Path) -> Path:
    (tmp_path / "sub").mkdir()
    (tmp_path / "sub" / "inner.txt").write_text("hello")
    (tmp_path / "b.txt").write_text("x" * 100)
    (tmp_path / "a.log").write_text("yy")
    (tmp_path / ".hidden").write_text("")
    return tmp_path


@pytest.mark.req("FR-DIR-001", "FR-DIR-002", "FR-DIR-003")
def test_dirtree_lazy_load_and_navigation(tree_dir: Path) -> None:
    calls: list[Path] = []

    def lister(p: Path) -> list[Path]:
        calls.append(p)
        return sorted(p.iterdir())

    t = DirectoryTree(root=tree_dir, lister=lister)
    t.focus()
    assert calls == [tree_dir]  # sub not listed until expanded
    names = [e.name for _, e in t.visible_rows()]
    assert names[1] == "sub" and ".hidden" not in names
    t.handle_key(key("down"))
    t.handle_key(key("right"))
    assert calls[-1] == tree_dir / "sub" and "inner.txt" in [e.name for _, e in t.visible_rows()]
    t.handle_key(key("left"))
    assert "inner.txt" not in [e.name for _, e in t.visible_rows()]
    e = t.selected
    assert e is not None and e.is_dir and e.mode and e.mtime


@pytest.mark.req("FR-DIR-004")
def test_dirtree_sorting_hidden_and_metadata(tree_dir: Path) -> None:
    t = DirectoryTree(root=tree_dir, show_perms=True, show_date=True)
    order = lambda: [e.name for _, e in t.visible_rows()][1:]  # noqa: E731
    assert order() == ["sub", "a.log", "b.txt"]
    t.set_sort("size", descending=True)
    assert order()[0] == "sub" and order()[1] == "b.txt"
    t.handle_key(key("."))
    assert ".hidden" in order()
    rows = draw(t, 80, 8)
    assert any("b.txt" in r and "100" in r and "-rw" in r for r in rows)
    with pytest.raises(ValueError):
        t.set_sort("color")


@pytest.mark.req("FR-DIR-005")
def test_dirtree_filter(tree_dir: Path) -> None:
    t = DirectoryTree(root=tree_dir)
    t.focus()
    t.handle_key(key("/", "/"))
    for ch in "LOG":
        t.handle_key(key(ch, ch))
    assert [e.name for _, e in t.visible_rows() if not e.is_dir] == ["a.log"]
    t.handle_key(key("escape"))
    assert len(t.visible_rows()) > 3


@pytest.mark.skipif(os.name == "nt", reason="symlinks need privileges on Windows")
@pytest.mark.req("FR-DIR-006")
def test_dirtree_symlinks(tree_dir: Path) -> None:
    (tree_dir / "link").symlink_to(tree_dir / "sub", target_is_directory=True)
    (tree_dir / "sub" / "back").symlink_to(tree_dir, target_is_directory=True)
    t = DirectoryTree(root=tree_dir)
    link = next(e for _, e in t.visible_rows() if e.name == "link")
    assert link.is_symlink and not link.is_dir
    t2 = DirectoryTree(root=tree_dir, follow_symlinks=True)
    sub = next(e for _, e in t2.visible_rows() if e.name == "sub")
    t2.expand(sub)
    back = next(c for c in sub.children if c.name == "back")
    assert back.loop
    t2.expand(back)
    assert not back.expanded
    assert any("(loop)" in r for r in draw(t2, 60, 12))


@pytest.mark.req("FR-DIR-007")
def test_dirtree_errors_do_not_crash(tree_dir: Path) -> None:
    def boom(p: Path) -> list[Path]:
        if p == tree_dir / "sub":
            raise PermissionError(13, "Permission denied")
        return sorted(p.iterdir())

    t = DirectoryTree(root=tree_dir, lister=boom)
    sub = next(e for _, e in t.visible_rows() if e.name == "sub")
    t.expand(sub)
    assert sub.children[0].error == "Permission denied"
    ghost = DirectoryTree(root=tree_dir / "does-not-exist")
    assert ghost.root.error and draw(ghost, 40, 4)[0].strip()
    gone = tree_dir / "b.txt"
    t.refresh()
    gone.unlink()
    t.refresh()
    assert "b.txt" not in [e.name for _, e in t.visible_rows()]


# ---------------------------------------------------------------- dashboard
def wait_for(cond, timeout: float = 3.0) -> bool:  # type: ignore[no-untyped-def]
    end = time.monotonic() + timeout
    while time.monotonic() < end:
        if cond():
            return True
        time.sleep(0.01)
    return False


@pytest.mark.req("FR-DASH-001", "FR-DASH-002", "FR-DASH-004")
def test_dashboard_fetches_off_ui_thread_and_callbacks_on_ui_thread() -> None:
    import threading

    fetch_threads: set[int] = set()
    callback_threads: set[int] = set()
    counter = iter(range(1000))

    def fetch() -> int:
        fetch_threads.add(threading.get_ident())
        return next(counter)

    d = TextDashboard(
        fetch=fetch, interval=0.1, on_update=lambda v: callback_threads.add(threading.get_ident())
    )
    d.mount()
    d.start()
    assert wait_for(lambda: d._results.qsize() >= 2)
    d.update(0)
    assert len(d.history) >= 2 and threading.get_ident() not in fetch_threads
    assert callback_threads == {threading.get_ident()}
    d.push("pushed")
    d.update(0)
    assert d.latest == "pushed"
    d.close()
    with pytest.raises(ValueError):
        TextDashboard(interval=0.01)


@pytest.mark.req("FR-DASH-003")
def test_dashboard_history_bounded() -> None:
    d = MetricDashboard(history_size=3, label="cpu", unit="%")
    for i in range(10):
        d.push(i)
    d.update(0)
    assert list(d.history) == [7, 8, 9]
    rows = draw(d, 20, 3)
    assert "cpu: 9%" in rows[0] and rows[1].strip()


@pytest.mark.req("FR-DASH-005")
def test_dashboard_errors_pause_resume_stop() -> None:
    state = {"fail": True, "n": 0}

    def fetch() -> int:
        state["n"] += 1
        if state["fail"]:
            raise RuntimeError("boom")
        return state["n"]

    d = TextDashboard(fetch=fetch, interval=0.1)
    d.mount()
    d.start()
    assert wait_for(lambda: d._results.qsize() >= 1)
    d.update(0)
    assert (
        d.error and isinstance(d.last_error, RuntimeError) and "boom" in "\n".join(draw(d, 40, 4))
    )
    state["fail"] = False
    assert wait_for(lambda: d._results.qsize() >= 1)
    d.update(0)
    assert not d.error and d.latest is not None
    d.pause()
    time.sleep(0.15)
    d.update(0)
    before = state["n"]
    time.sleep(0.3)
    assert state["n"] == before
    d.resume()
    assert wait_for(lambda: state["n"] > before)
    d.stop()
    assert d._thread is None
    d.close()


@pytest.mark.req("FR-DASH-006")
def test_dashboard_variants_render_waiting_text() -> None:
    assert "waiting" in draw(TextDashboard(), 30, 2)[0]
    assert "n/a" in draw(MetricDashboard(label="x"), 30, 2)[0]


# ---------------------------------------------------------------- code editor
@pytest.mark.req("FR-CODE-001", "FR-CODE-002", "FR-CODE-005")
def test_editor_cursor_and_edits() -> None:
    e = CodeEditor(0, 0, 30, 5, text="ab\ncd\nef")
    e.focus()
    e.handle_key(key("down"))
    e.handle_key(key("end"))
    assert (e.row, e.col) == (1, 2)
    e.handle_key(key("right"))
    assert (e.row, e.col) == (2, 0)
    e.handle_key(key("left"))
    assert (e.row, e.col) == (1, 2)
    e.insert_text("X\nY")
    assert e.lines == ["ab", "cdX", "Y", "ef"]
    e.delete_back()
    e.delete_back()
    e.delete_back()
    assert e.lines == ["ab", "cd", "ef"]
    e.goto_line(99)
    assert e.row == 2
    e.handle_key(key("home"))
    e.handle_key(key("delete"))
    assert e.lines[2] == "f"


@given(st.lists(st.sampled_from(["a", "b", "\n", "<", ">", "u", "r", "H", "E", "x"]), max_size=60))
@pytest.mark.req("FR-CODE-005")
def test_editor_cursor_always_valid(ops: list[str]) -> None:
    e = CodeEditor(0, 0, 10, 4)
    for op in ops:
        if op == "<":
            e.delete_back()
        elif op == ">":
            e.delete_forward()
        elif op == "u":
            e.undo()
        elif op == "r":
            e.redo()
        elif op == "H":
            e.handle_key(key("home"))
        elif op == "E":
            e.handle_key(key("up"))
        elif op == "x":
            e.handle_key(key("pagedown"))
        else:
            e.insert_text(op)
        assert 0 <= e.row < len(e.lines) and 0 <= e.col <= len(e.lines[e.row])
        assert 0 <= e.top <= e.row


@pytest.mark.req("FR-CODE-007")
def test_editor_undo_redo_roundtrip() -> None:
    e = CodeEditor(text="start")
    e.handle_key(key("end"))
    e.insert_text("\nline2")
    e.delete_back()
    snapshot = e.text
    assert e.undo() and e.undo()
    assert e.text == "start"
    assert not e.undo()
    assert e.redo() and e.redo()
    assert e.text == snapshot
    e2 = CodeEditor()
    for _ in range(1200):
        e2.insert_text("x")
    assert len(e2._undo) == 1000
    assert e2.handle_key(key("z", "z", ctrl=True))


@pytest.mark.req("FR-CODE-003")
def test_highlighting_python_js_and_fallback() -> None:
    kinds = {k for _, _, k in highlight('def f(x): return "s" + 12  # c', "python")}
    assert kinds == {"keyword", "string", "number", "comment"}
    assert {k for _, _, k in highlight("const a = `t`; // c", "javascript")} >= {
        "keyword",
        "string",
        "comment",
    }
    assert highlight("def x", "cobol") == [] and highlight("x", None) == []
    # keyword inside a string stays a string
    assert [k for _, _, k in highlight('"def"', "python")] == ["string"]
    e = CodeEditor(0, 0, 30, 3, text="def f():\n    pass", language="python")
    assert "1 def f():" in draw(e, 30, 3)[0]
    off = CodeEditor(0, 0, 30, 3, text="a\nb", line_numbers=False)
    assert draw(off, 30, 3)[0].startswith("a")


@pytest.mark.req("FR-CODE-004", "FR-CODE-006", "FR-CODE-008")
def test_editor_files(tmp_path: Path) -> None:
    p = tmp_path / "f.py"
    p.write_bytes("héllo\r\nworld\r\n".encode())
    e = CodeEditor()
    e.load(p)
    assert e.lines[0] == "héllo" and e.newline == "\r\n" and not e.dirty
    e.handle_key(key("x", "x"))
    assert e.dirty
    if os.name != "nt":
        p.chmod(0o640)
    e.save()
    assert not e.dirty and p.read_bytes().startswith("xhéllo\r\n".encode())
    if os.name != "nt":
        assert stat.S_IMODE(p.stat().st_mode) == 0o640
    assert not [f for f in tmp_path.iterdir() if f.name.endswith(".tmp")]
    # undecodable
    bad = tmp_path / "bad.bin"
    bad.write_bytes(b"\xff\xfe\x00bad")
    with pytest.raises(CodeFileError, match="not valid"):
        CodeEditor().load(bad)
    ro = CodeEditor()
    ro.load(bad, errors="replace")
    assert ro.read_only and "�" in ro.text
    with pytest.raises(CodeFileError):
        ro.save()
    # size limit
    big = tmp_path / "big.txt"
    big.write_text("x" * 100)
    with pytest.raises(CodeFileError, match="limit"):
        CodeEditor().load(big, max_bytes=10)
    part = CodeEditor()
    part.load(big, max_bytes=10, oversize="read_only")
    assert part.read_only and len(part.text) == 10
    with pytest.raises(CodeFileError):
        CodeEditor().load(tmp_path / "missing.txt")
    with pytest.raises(CodeFileError):
        CodeEditor().save()


@pytest.mark.req("FR-CODE-006")
def test_save_is_never_automatic(tmp_path: Path) -> None:
    p = tmp_path / "a.txt"
    p.write_text("one")
    e = CodeEditor()
    e.load(p)
    e.insert_text("zzz")
    assert p.read_text() == "one"


@pytest.mark.req("FR-CODE-006")
def test_ctrl_s_reports_errors_instead_of_raising(tmp_path: Path) -> None:
    e = CodeEditor(text="x")
    assert e.handle_key(key("s", "s", ctrl=True)) and "no path" in e.message
    e.path = tmp_path / "ok.txt"
    e.handle_key(key("s", "s", ctrl=True))
    assert (tmp_path / "ok.txt").read_text() == "x" and e.message.startswith("saved")


@pytest.mark.req("FR-TABLE-001")
def test_table_row_numbers_are_separated() -> None:
    t = Table(0, 0, 30, 5, columns=["n"], rows=[["a"], ["b"]], row_numbers=True)
    assert draw(t, 30, 5)[2].startswith(" 1 a") or draw(t, 30, 5)[2].startswith("1 a")
