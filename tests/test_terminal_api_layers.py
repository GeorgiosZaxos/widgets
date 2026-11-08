"""Terminal session, capabilities, public API, architecture and end-to-end (pty) tests."""

from __future__ import annotations

import contextlib
import importlib.util
import json
import os
import re
import subprocess
import sys
import textwrap
import tomllib
from collections.abc import Callable
from pathlib import Path

import pytest

import widgets
from conftest import FakeTTY
from widgets.errors import LifecycleError, TerminalBusyError
from widgets.terminal import ansi
from widgets.terminal.capabilities import detect_capabilities
from widgets.terminal.session import TerminalMode, TerminalSession

ROOT = Path(__file__).resolve().parent.parent
SessionFactory = Callable[..., TerminalSession]

# -- capabilities -------------------------------------------------------------------------


@pytest.mark.req("FR-TERM-009", "FR-TERM-012")
def test_non_tty_has_no_ansi_and_no_color() -> None:
    import io

    caps = detect_capabilities(io.StringIO(), env={"TERM": "xterm-256color"})
    assert not caps.is_tty and not caps.ansi and caps.color_mode == 0


@pytest.mark.req("FR-TERM-012")
def test_tty_capabilities_and_dumb_terminal() -> None:
    caps = detect_capabilities(FakeTTY(), env={"TERM": "xterm-256color", "COLORTERM": "truecolor"})
    assert caps.is_tty and caps.ansi and caps.unicode
    assert not detect_capabilities(FakeTTY(), env={"TERM": "dumb"}).ansi


@pytest.mark.req("FR-TERM-012", "FR-ASSET-009")
def test_ascii_only_disables_unicode() -> None:
    caps = detect_capabilities(FakeTTY(), env={"TERM": "xterm"}, ascii_only=True)
    assert not caps.unicode


# -- session ownership and restoration ------------------------------------------------------


@pytest.mark.req("FR-TERM-003", "FR-TERM-006", "FR-TERM-008", "D-01")
def test_fullscreen_session_enters_and_restores(make_session: SessionFactory) -> None:
    s = make_session(TerminalMode.FULLSCREEN)
    s.start()
    out = s.stream.getvalue()  # type: ignore[attr-defined]
    assert ansi.ENTER_ALT_SCREEN in out and ansi.HIDE_CURSOR in out
    s.close()
    out = s.stream.getvalue()  # type: ignore[attr-defined]
    assert out.rfind(ansi.EXIT_ALT_SCREEN) > out.rfind(ansi.ENTER_ALT_SCREEN)
    assert out.rfind(ansi.SHOW_CURSOR) > out.rfind(ansi.HIDE_CURSOR)


@pytest.mark.req("FR-TERM-008")
def test_inline_session_does_not_use_alt_screen(make_session: SessionFactory) -> None:
    s = make_session(TerminalMode.INLINE)
    s.start()
    s.close()
    assert ansi.ENTER_ALT_SCREEN not in s.stream.getvalue()  # type: ignore[attr-defined]


@pytest.mark.req("FR-TERM-006")
def test_close_is_idempotent_and_session_not_restartable(make_session: SessionFactory) -> None:
    s = make_session()
    s.start()
    s.close()
    first = s.stream.getvalue()  # type: ignore[attr-defined]
    s.close()
    assert s.stream.getvalue() == first  # type: ignore[attr-defined]
    with pytest.raises(LifecycleError):
        s.start()


@pytest.mark.req("FR-TERM-007", "D-01")
def test_one_owner_per_stream(make_session: SessionFactory) -> None:
    stream = FakeTTY()
    a = make_session(stream=stream)
    a.start()
    b = make_session(stream=stream)
    with pytest.raises(TerminalBusyError):
        b.start()
    a.close()
    c = make_session(stream=stream)  # released after close
    c.start()
    c.close()


@pytest.mark.req("FR-TERM-006")
def test_context_manager_restores_on_exception(make_session: SessionFactory) -> None:
    stream = FakeTTY()
    with pytest.raises(RuntimeError), make_session(stream=stream):
        raise RuntimeError("x")
    assert ansi.EXIT_ALT_SCREEN in stream.getvalue()


@pytest.mark.req("FR-TERM-009")
def test_non_tty_session_writes_no_escape_sequences() -> None:
    import io

    out = io.StringIO()
    with TerminalSession(stream=out, env={"TERM": "xterm"}, handle_signals=False, use_atexit=False):
        pass
    assert "\x1b" not in out.getvalue()


@pytest.mark.req("FR-SAN-003")
def test_title_is_sanitised(make_session: SessionFactory) -> None:
    s = make_session(title="hi\x07\x1b[31mthere")
    s.start()
    s.close()
    out = s.stream.getvalue()  # type: ignore[attr-defined]
    assert "\x07\x1b[31m" not in out


@pytest.mark.req("FR-TERM-004")
def test_size_uses_env_fallback(make_session: SessionFactory) -> None:
    s = make_session(env={"TERM": "xterm", "COLUMNS": "100", "LINES": "30"})
    cols, rows = s.get_size()
    assert cols > 0 and rows > 0


# -- public API -----------------------------------------------------------------------------


@pytest.mark.req("FR-API-001", "FR-API-004")
def test_all_names_resolve() -> None:
    for name in widgets.__all__:
        assert getattr(widgets, name) is not None, name
    assert set(dir(widgets)) >= set(widgets.__all__)
    with pytest.raises(AttributeError):
        widgets.DoesNotExist  # noqa: B018


@pytest.mark.req("FR-API-006", "NFR-PORT-001", "NFR-MAINT-007", "D-12", "D-13")
def test_version_matches_pyproject() -> None:
    data = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    assert widgets.__version__ == data["project"]["version"]
    assert data["project"]["dependencies"] == []  # D-12
    assert data["project"]["requires-python"] == ">=3.13"  # D-13


def _run(code: str, **kw: object) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-I", "-c", textwrap.dedent(code)],
        capture_output=True,
        text=True,
        timeout=60,
        **kw,  # type: ignore[arg-type]
    )


@pytest.mark.req("FR-API-003", "D-12")
def test_bare_import_is_lazy_and_pulls_no_third_party_modules() -> None:
    r = _run("""
        import sys, json
        import widgets
        loaded = sorted(m for m in sys.modules if m.startswith("widgets"))
        print(json.dumps(loaded))
    """)
    assert r.returncode == 0, r.stderr
    assert json.loads(r.stdout) == ["widgets"]


@pytest.mark.req("NFR-PORT-003", "FR-IMPORT-003", "D-12")
def test_full_import_needs_no_optional_packages() -> None:
    r = _run("""
        import sys
        import widgets
        for name in widgets.__all__:
            getattr(widgets, name)
        banned = {"wcwidth", "pandas", "openpyxl", "numpy", "curses", "audioop"}
        bad = banned & set(sys.modules)
        print(sorted(bad))
    """)
    assert r.returncode == 0, r.stderr
    assert r.stdout.strip() == "[]"


@pytest.mark.req("NFR-MAINT-003")
def test_import_has_no_side_effects_on_stdout_or_root_logger() -> None:
    r = _run("""
        import logging
        import widgets
        for n in widgets.__all__:
            getattr(widgets, n)
        print(len(logging.getLogger().handlers))
    """)
    assert r.returncode == 0, r.stderr
    assert r.stdout.strip() == "0"


@pytest.mark.req("NFR-MAINT-003")
def test_no_print_or_stdout_writes_in_library() -> None:
    offenders = []
    for path in (ROOT / "src" / "widgets").rglob("*.py"):
        if path.name == "__main__.py":  # command-line entry points may print
            continue
        text = path.read_text(encoding="utf-8")
        if re.search(r"^\s*print\(", text, re.M) or "sys.stdout.write" in text:
            offenders.append(path.name)
    assert offenders == []


@pytest.mark.req("NFR-PORT-001", "D-13")
def test_no_removed_stdlib_modules_imported() -> None:
    removed = ("audioop", "cgi", "telnetlib", "imp", "pipes", "crypt", "aifc")
    for path in (ROOT / "src" / "widgets").rglob("*.py"):
        text = path.read_text(encoding="utf-8")
        for mod in removed:
            assert not re.search(rf"^\s*(import|from)\s+{mod}\b", text, re.M), (path, mod)


# -- architecture ---------------------------------------------------------------------------


def _load_checker():  # type: ignore[no-untyped-def]
    spec = importlib.util.spec_from_file_location(
        "check_layers", ROOT / "tools" / "check_layers.py"
    )
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    sys.modules["check_layers"] = mod
    spec.loader.exec_module(mod)
    return mod


@pytest.mark.req("NFR-MAINT-006", "D-08")
def test_layer_checker_is_clean_on_the_real_tree() -> None:
    problems, _ = _load_checker().analyse(ROOT / "src")
    assert problems == []


@pytest.mark.req("NFR-MAINT-006", "D-08")
def test_layer_checker_detects_violations(tmp_path: Path) -> None:
    pkg = tmp_path / "widgets"
    (pkg / "base_elements").mkdir(parents=True)
    (pkg / "__init__.py").write_text("", encoding="utf-8")
    (pkg / "base_elements" / "__init__.py").write_text("", encoding="utf-8")
    (pkg / "base_elements" / "widget_types.py").write_text(
        "from widgets.render import buffer\n", encoding="utf-8"
    )
    (pkg / "render").mkdir()
    (pkg / "render" / "__init__.py").write_text("", encoding="utf-8")
    (pkg / "render" / "buffer.py").write_text("import numpy\n", encoding="utf-8")
    problems, _ = _load_checker().analyse(tmp_path)
    joined = "\n".join(problems)
    assert "widget_types" in joined  # L0 importing a higher layer
    assert "numpy" in joined  # module-level third-party import


# -- end to end in a real pseudo-terminal --------------------------------------------------------

pty = pytest.importorskip("pty") if sys.platform != "win32" else None


def _pty_run(script: str, keys: bytes = b"", timeout: float = 20.0) -> tuple[int, bytes]:
    import select
    import time

    pid, fd = pty.fork()  # type: ignore[union-attr]
    if pid == 0:  # pragma: no cover - child
        env = {**os.environ, "TERM": "xterm-256color", "COLUMNS": "80", "LINES": "24"}
        os.execvpe(sys.executable, [sys.executable, "-I", "-c", script], env)
    out = b""
    deadline = time.monotonic() + timeout
    sent = False
    status = 0
    while time.monotonic() < deadline:
        ready, _, _ = select.select([fd], [], [], 0.1)
        if ready:
            try:
                chunk = os.read(fd, 65536)
            except OSError:
                break
            if not chunk:
                break
            out += chunk
            if keys and not sent and b"\x1b[?1049h" in out:
                time.sleep(0.3)
                os.write(fd, keys)
                sent = True
        done, status = os.waitpid(pid, os.WNOHANG)
        if done:
            break
    else:  # pragma: no cover
        os.kill(pid, 9)
        os.waitpid(pid, 0)
        raise AssertionError(f"pty child timed out; output so far: {out[-300:]!r}")
    try:
        while True:
            chunk = os.read(fd, 65536)
            if not chunk:
                break
            out += chunk
    except OSError:
        pass
    with contextlib.suppress(ChildProcessError):
        _, status = os.waitpid(pid, 0)
    return os.waitstatus_to_exitcode(status), out


APP = f"""
import sys
sys.path.insert(0, {str(ROOT / "src")!r})
sys.path.insert(0, {str(ROOT / "examples")!r})
import demo
demo.main()
"""


@pytest.mark.req(
    "FR-TERM-006", "FR-TERM-008", "FR-RENDER-009", "FR-INPUT-008", "FR-CLEAN-008", "D-15"
)
@pytest.mark.slow
@pytest.mark.skipif(sys.platform == "win32", reason="pty not available")
def test_demo_runs_and_quits_on_q_restoring_terminal() -> None:
    code, out = _pty_run(APP, keys=b"\t \tq")
    text = out.decode("utf-8", "replace")
    assert code == 0, text[-400:]
    assert "Enable logging" in text and "Dark mode" in text
    assert "last key: q" in text  # keys reached the app through the real input path
    assert "\x1b[0;1;7m[ ] Dark mode" in text  # second Tab moved focus (reverse video)
    # Space toggled the first checkbox: the changed cell is drawn after a cursor move. Style codes
    # may sit in between when the input arrives in one burst (macOS ptys) and focus moved in the same frame.
    assert re.search(r"\x1b\[\d+;\d+H(?:\x1b\[[0-9;]*m)*x", text)
    assert text.rfind("\x1b[?1049l") > text.rfind("\x1b[?1049h")
    assert text.rfind("\x1b[?25h") > text.rfind("\x1b[?25l")


@pytest.mark.req("FR-RENDER-010", "FR-TERM-006", "NFR-REL-003", "FR-CLEAN-008")
@pytest.mark.slow
@pytest.mark.skipif(sys.platform == "win32", reason="pty not available")
def test_terminal_restored_after_unhandled_exception() -> None:
    script = f"""
import sys
sys.path.insert(0, {str(ROOT / "src")!r})
from widgets.base_elements.base import Widget
from widgets.render.run import run_app
class Boom(Widget):
    def update(self, dt):
        raise RuntimeError("kaboom")
run_app(Boom(0, 0, 10, 1, name="boom"), fps=30)
"""
    code, out = _pty_run(script)
    text = out.decode("utf-8", "replace")
    assert code != 0 and "kaboom" in text
    assert text.rfind("\x1b[?1049l") > text.rfind("\x1b[?1049h")
    assert text.rfind("\x1b[?25h") > text.rfind("\x1b[?25l")


@pytest.mark.req("FR-TERM-006", "FR-CLEAN-008", "D-01")
@pytest.mark.slow
@pytest.mark.skipif(sys.platform == "win32", reason="pty not available")
def test_terminal_restored_on_sigterm() -> None:
    import signal
    import time

    script = f"""
import sys, os, threading, signal
sys.path.insert(0, {str(ROOT / "src")!r})
from widgets.base_elements.base import Widget
from widgets.render.run import run_app
threading.Timer(0.6, lambda: os.kill(os.getpid(), signal.SIGTERM)).start()
run_app(Widget(0, 0, 10, 1, name="idle"), fps=30)
"""
    code, out = _pty_run(script, timeout=20)
    text = out.decode("utf-8", "replace")
    assert code == -signal.SIGTERM or code != 0, text[-300:]
    assert text.rfind("\x1b[?1049l") > text.rfind("\x1b[?1049h")
    assert text.rfind("\x1b[?25h") > text.rfind("\x1b[?25l")
    _ = time


@pytest.mark.req("FR-TERM-010", "FR-TERM-009")
def test_windows_vt_enabling_trusts_streams_without_a_descriptor(
    monkeypatch: pytest.MonkeyPatch, make_session: SessionFactory
) -> None:
    """Regression: on Windows an in-memory TTY stream must still get ANSI (not the process stdout)."""
    from widgets.terminal import compat

    monkeypatch.setattr(compat.sys, "platform", "win32")
    assert compat.enable_vt_processing(FakeTTY()) == (True, None)
    stream = FakeTTY()
    monkeypatch.setattr("widgets.terminal.session.sys.platform", "win32")
    s = make_session(TerminalMode.FULLSCREEN, stream=stream)
    s.start()
    assert ansi.ENTER_ALT_SCREEN in stream.getvalue()
    s.close()
    assert ansi.EXIT_ALT_SCREEN in stream.getvalue()
