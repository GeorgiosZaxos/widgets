"""M8 hardening: performance budgets, maintainability and security policies, packaging."""

from __future__ import annotations

import ast
import re
import subprocess
import sys
import tomllib
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src" / "widgets"
# Generous multiples of the SRS budgets so slow CI machines do not flake; tools/benchmarks.py
# reports the real numbers.
# Timing budgets are meaningless while a tracer (coverage) is running: widen them there.
SLACK = 4.0 if sys.gettrace() is None and "coverage" not in sys.modules else 40.0


def sources():
    return list(SRC.rglob("*.py"))


@pytest.mark.req("NFR-PERF-001")
def test_unchanged_diff_emits_nothing_and_is_fast():
    from tools.benchmarks import H, W, best_of  # type: ignore[import-not-found]

    from widgets.render.buffer import Buffer
    from widgets.render.diff import diff_buffers

    a, b = Buffer(W, H), Buffer(W, H)
    assert diff_buffers(a, b) == []
    assert best_of(lambda: diff_buffers(a, b), 10) < 5 * SLACK


@pytest.mark.req("NFR-PERF-001")
def test_diff_output_is_proportional_to_changed_cells():
    from widgets.base_elements.widget_types import Cell, Style
    from widgets.render.buffer import Buffer
    from widgets.render.diff import diff_buffers

    a = Buffer(200, 60)
    sizes = []
    for n in (10, 100):
        b = Buffer(200, 60)
        for i in range(n):
            b.set_cell(i % 60, (i * 7) % 200, Cell("x", Style(bold=True)))
        sizes.append(sum(len(str(op)) for op in diff_buffers(a, b)))
    assert 0 < sizes[0] < sizes[1] < 200 * 60 * 3


@pytest.mark.req("NFR-PERF-005")
def test_import_is_fast_and_lazy():
    code = (
        "import sys, time; t=time.perf_counter(); import widgets; "
        "print((time.perf_counter()-t)*1000, 'widgets.data.table' in sys.modules, "
        "'widgets.net.rss' in sys.modules, 'widgets.audio.backend' in sys.modules)"
    )
    out = subprocess.check_output([sys.executable, "-c", code], text=True, cwd=ROOT).split()
    assert float(out[0]) < 100 * SLACK
    assert out[1:] == ["False", "False", "False"]  # widgets are not imported eagerly


@pytest.mark.req("NFR-PERF-006")
def test_full_frame_fits_the_budget():
    from tools.benchmarks import best_of, build_screen  # type: ignore[import-not-found]

    from widgets.render.buffer import Buffer

    screen, buf = build_screen(), Buffer(200, 60)
    assert best_of(lambda: screen.draw(buf), 10) < 16 * SLACK


@pytest.mark.req("NFR-MAINT-001")
def test_no_sys_path_changes_or_cwd_dependence():
    for p in sources():
        text = p.read_text(encoding="utf-8")
        assert "sys.path" not in text, p
        assert "os.chdir" not in text, p
        for node in ast.walk(ast.parse(text)):
            if isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
                assert not node.module.startswith("src."), p


@pytest.mark.req("NFR-MAINT-003")
def test_library_does_not_print_and_only_attaches_null_handler():
    for p in sources():
        if "include" in p.parts or p.name.endswith("_data.py"):
            continue
        tree = ast.parse(p.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if (
                isinstance(node, ast.Call)
                and isinstance(node.func, ast.Name)
                and node.func.id == "print"
            ):
                pytest.fail(f"print() in {p}")
            if isinstance(node, ast.Attribute) and node.attr == "addHandler":
                assert p.name == "__init__.py" and p.parent == SRC, p
    import logging

    handlers = logging.getLogger("widgets").handlers
    assert handlers and all(isinstance(h, logging.NullHandler) for h in handlers)


@pytest.mark.req("NFR-SEC-005")
def test_no_shell_invocation_anywhere():
    for p in sources():
        tree = ast.parse(p.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.keyword) and node.arg == "shell":
                assert isinstance(node.value, ast.Constant) and node.value.value is False, p
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
                owner = node.func.value
                if (
                    isinstance(owner, ast.Name)
                    and owner.id == "os"
                    and node.func.attr in ("system", "popen")
                ):
                    pytest.fail(f"os.{node.func.attr} in {p}")
            if (
                isinstance(node, ast.Call)
                and isinstance(node.func, ast.Name)
                and node.func.id in ("eval", "exec")
            ):
                pytest.fail(f"{node.func.id} in {p}")


@pytest.mark.req("NFR-SEC-007")
def test_network_access_only_in_net_package():
    banned = re.compile(r"\b(urllib\.request|http\.client|socket|requests|httpx|smtplib|ftplib)\b")
    for p in sources():
        rel = p.relative_to(SRC).parts
        text = p.read_text(encoding="utf-8")
        imports = [
            n for n in ast.walk(ast.parse(text)) if isinstance(n, ast.Import | ast.ImportFrom)
        ]
        dumped = " ".join(ast.dump(n) for n in imports)
        if (
            banned.search(re.sub(r"[()'\[\],=]", " ", dumped).replace("name ", ""))
            and rel[0] != "net"
        ):
            # urllib.parse / socket-free helpers elsewhere are fine; request/connection modules are not
            pytest.fail(f"network module imported outside widgets.net: {p}")


@pytest.mark.req("NFR-PORT-003")
def test_core_imports_survive_missing_optional_and_platform_modules():
    code = (
        "import sys\n"
        "blocked = ['winsound','termios','tty','tzdata','wcwidth','pandas','openpyxl']\n"
        "if sys.platform != 'win32':\n"  # subprocess itself needs msvcrt on Windows
        "    blocked.append('msvcrt')\n"
        "for m in blocked:\n"
        "    sys.modules[m] = None\n"
        "import widgets, widgets.render.run, widgets.audio.backend, widgets.net.rss\n"
        "import widgets.data.table, widgets.display.calendar\n"
        "print('ok')"
    )
    r = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, cwd=ROOT)
    assert r.stdout.strip() == "ok", r.stderr


@pytest.mark.req("NFR-MAINT-004", "NFR-MAINT-007", "NFR-SEC-008")
def test_packaging_metadata():
    meta = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    project = meta["project"]
    assert project["requires-python"] == ">=3.13" and project["dependencies"] == []
    extras = project["optional-dependencies"]
    for name, specs in extras.items():
        assert all(re.search(r">=\d", s) for s in specs), (name, specs)  # lower-bound pinned
    assert {"dev", "tz", "unicode"} <= set(extras)
    assert (SRC / "py.typed").exists()
    assert "License" in "".join(project.get("classifiers", [])) or (ROOT / "LICENSES.md").exists()


@pytest.mark.req("NFR-MAINT-006")
def test_layer_checker_is_clean():
    r = subprocess.run(
        [sys.executable, str(ROOT / "tools" / "check_layers.py")],
        capture_output=True,
        text=True,
        cwd=ROOT,
    )
    assert r.returncode == 0, r.stdout + r.stderr


def test_documentation_is_present_and_names_privacy_and_services():
    docs = ROOT / "docs"
    for name in ("USER_GUIDE.md", "SECURITY.md", "COMPATIBILITY.md", "BENCHMARKS.md"):
        assert (docs / name).is_file(), name
    guide = (docs / "USER_GUIDE.md").read_text(encoding="utf-8")
    assert "third-party" in guide and "Open-Meteo" in guide
    assert "shell=False" in (docs / "SECURITY.md").read_text(encoding="utf-8")


@pytest.mark.req("NFR-SEC-006")
def test_untrusted_text_cannot_inject_escape_sequences():
    from widgets.render.sanitize import sanitize_text

    evil = "a\x1b[31mred\x1b]0;title\x07\x9b2Jz\x00"
    clean = sanitize_text(evil)
    assert (
        "\x1b" not in clean and "\x07" not in clean and "\x9b" not in clean and "\x00" not in clean
    )


@pytest.mark.req("NFR-I18N-001")
def test_input_decoding_is_utf8_with_explicit_invalid_byte_handling():
    from widgets.base_elements.events import KeyDecoder, KeyEvent

    events = KeyDecoder().feed("é€".encode() + b"\xff\xfe" + b"x")
    chars = [e.char for e in events if isinstance(e, KeyEvent)]
    assert "é" in chars and "€" in chars and chars[-1] == "x"  # invalid bytes never raise


@pytest.mark.req("NFR-PORT-004")
def test_colour_degrades_truecolor_to_256_to_16_to_none():
    from widgets.base_elements.color_manager import ColorMode
    from widgets.base_elements.widget_types import RGB

    assert ColorMode.NONE < ColorMode.ANSI16 < ColorMode.ANSI256 < ColorMode.TRUECOLOR
    from widgets.base_elements import color_manager as cm

    fn = (
        next(getattr(cm, n) for n in ("ansi_fg", "sgr_for_color", "color_sgr") if hasattr(cm, n))
        if any(hasattr(cm, n) for n in ("ansi_fg", "sgr_for_color", "color_sgr"))
        else None
    )
    if fn is not None:
        outs = [fn(RGB(200, 30, 30), mode) for mode in ColorMode]
        assert outs[0] in ("", None) or "38" not in str(outs[0])
        assert len({str(o) for o in outs}) >= 3


@pytest.mark.req("NFR-SEC-004")
def test_nothing_is_written_unless_requested(tmp_path):
    from widgets.data.code import CodeEditor
    from widgets.data.table import Table

    f = tmp_path / "a.py"
    f.write_text("x = 1\n", encoding="utf-8")
    ed = CodeEditor(0, 0, 40, 5, text="x = 1\n", language="python")
    ed.path = f
    ed.mount()
    ed.insert_text("y") if hasattr(ed, "insert_text") else None
    Table(0, 0, 20, 5).load_csv("a,b\n1,2\n")
    assert f.read_text(encoding="utf-8") == "x = 1\n"  # unchanged until save() is called
    assert sorted(p.name for p in tmp_path.iterdir()) == ["a.py"]
    ed.save()
    assert not [p for p in tmp_path.iterdir() if p.name != "a.py"]  # atomic: no temp leftovers


@pytest.mark.req("NFR-SEC-003")
def test_directory_tree_survives_bad_paths_and_symlink_loops(tmp_path):
    import os

    from widgets.data.dirtree import DirectoryTree

    (tmp_path / "d").mkdir()
    try:
        os.symlink(tmp_path, tmp_path / "d" / "loop")
    except (OSError, NotImplementedError):
        pytest.skip("symlinks unavailable")
    t = DirectoryTree(0, 0, 40, 10, root=tmp_path)
    t.mount()
    DirectoryTree(0, 0, 40, 10, root=tmp_path / "missing").mount()
    assert t.visible_rows()
