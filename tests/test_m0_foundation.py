"""M0: shared types, import helpers, cleanup manager."""

from __future__ import annotations

import logging
import threading
from collections import Counter

import pytest

from widgets.base_elements.cleanup import CleanupManager
from widgets.base_elements.import_helper import optional_import, require_import
from widgets.base_elements.widget_types import (
    BLANK_CELL,
    DEFAULT_STYLE,
    RGB,
    Cell,
    Point,
    Rect,
    RenderOp,
    Size,
    Style,
)
from widgets.errors import MissingDependencyError, WidgetsError

# ---------------------------------------------------------------------------
# Types
# ---------------------------------------------------------------------------


@pytest.mark.req("FR-TYPE-001")
def test_rect_geometry() -> None:
    a = Rect(0, 0, 10, 5)
    b = Rect(5, 2, 10, 10)
    assert a.right == 10 and a.bottom == 5
    assert a.intersect(b) == Rect(5, 2, 5, 3)
    assert a.clip(b) == a.intersect(b)
    assert a.contains(0, 0) and a.contains(9, 4)
    assert not a.contains(10, 0) and not a.contains(0, 5) and not a.contains(-1, 0)
    assert a.translate(2, 3) == Rect(2, 3, 10, 5)


@pytest.mark.req("FR-TYPE-001")
def test_rect_disjoint_intersection_is_empty() -> None:
    result = Rect(0, 0, 2, 2).intersect(Rect(5, 5, 2, 2))
    assert result.is_empty and result.width == 0 and result.height == 0


@pytest.mark.req("FR-TYPE-001", "FR-CORE-009")
def test_geometry_validation() -> None:
    with pytest.raises(ValueError):
        Rect(0, 0, -1, 1)
    with pytest.raises(TypeError):
        Rect(0.5, 0, 1, 1)  # type: ignore[arg-type]
    with pytest.raises(TypeError):
        Size(True, 1)  # bool is not accepted as an int
    with pytest.raises(ValueError):
        Size(1, -2)
    assert Point(1, 2).offset(3, 4) == Point(4, 6)


@pytest.mark.req("FR-TYPE-001")
def test_rgb_validation_and_iteration() -> None:
    assert tuple(RGB(1, 2, 3)) == (1, 2, 3)
    assert RGB(255, 0, 16).to_hex() == "#ff0010"
    with pytest.raises(ValueError):
        RGB(256, 0, 0)
    with pytest.raises(TypeError):
        RGB(1.5, 0, 0)  # type: ignore[arg-type]


@pytest.mark.req("FR-TYPE-002", "FR-TYPE-004")
def test_style_is_immutable_hashable_value_type() -> None:
    a = Style(fg=RGB(1, 2, 3), bold=True)
    b = Style(fg=RGB(1, 2, 3), bold=True)
    assert a == b and hash(a) == hash(b)
    assert len({a, b, Style()}) == 2
    with pytest.raises(AttributeError):
        a.bold = False  # type: ignore[misc]
    assert Style().is_default and DEFAULT_STYLE.is_default and not a.is_default
    assert a.replace(bold=False) == Style(fg=RGB(1, 2, 3))


@pytest.mark.req("FR-TYPE-002")
def test_style_validates_colors() -> None:
    with pytest.raises(ValueError):
        Style(fg=256)
    with pytest.raises(TypeError):
        Style(bg="red")  # type: ignore[arg-type]
    assert Style(fg=0, bg=255).fg == 0


@pytest.mark.req("FR-TYPE-002", "FR-TYPE-003")
def test_cell_and_render_op() -> None:
    assert Cell(" ", DEFAULT_STYLE) == BLANK_CELL
    with pytest.raises(AttributeError):
        BLANK_CELL.glyph = "x"  # type: ignore[misc]
    op = RenderOp(row=1, col=2, text="hi", style=Style(bold=True))
    assert (op.row, op.col, op.text, op.style.bold) == (1, 2, "hi", True)


# ---------------------------------------------------------------------------
# Import helpers
# ---------------------------------------------------------------------------


@pytest.mark.req("FR-IMPORT-001")
def test_optional_import(caplog: pytest.LogCaptureFixture) -> None:
    with caplog.at_level(logging.DEBUG):
        assert optional_import("json") is not None
        assert optional_import("definitely_not_installed_pkg", feature="demo") is None
    assert not [r for r in caplog.records if r.levelno >= logging.WARNING]


@pytest.mark.req("FR-IMPORT-002")
def test_require_import_error_is_actionable() -> None:
    assert require_import("json").__name__ == "json"
    with pytest.raises(MissingDependencyError) as info:
        require_import("definitely_not_installed_pkg", feature="audio playback", extra="audio")
    message = str(info.value)
    assert "definitely_not_installed_pkg" in message
    assert "audio playback" in message
    assert "widgets[audio]" in message
    assert isinstance(info.value, ImportError) and isinstance(info.value, WidgetsError)


# ---------------------------------------------------------------------------
# Cleanup manager
# ---------------------------------------------------------------------------


class Closeable:
    def __init__(self, log: list[str], name: str) -> None:
        self.log, self.name = log, name

    def close(self) -> None:
        self.log.append(self.name)


@pytest.mark.req("FR-CLEAN-001", "FR-CLEAN-002")
def test_cleanup_runs_in_reverse_order_and_accepts_closeables() -> None:
    log: list[str] = []
    manager = CleanupManager()
    first = manager.register(lambda: log.append("a"))
    second = manager.register(Closeable(log, "b"))
    manager.register(lambda: log.append("c"))
    assert first != second
    manager.cleanup()
    assert log == ["c", "b", "a"]


@pytest.mark.req("FR-CLEAN-003")
def test_cleanup_is_idempotent() -> None:
    calls: list[int] = []
    manager = CleanupManager()
    manager.register(lambda: calls.append(1))
    manager.cleanup()
    manager.cleanup()
    assert calls == [1] and manager.closed


@pytest.mark.req("FR-CLEAN-004")
def test_cleanup_failure_is_logged_and_does_not_block(caplog: pytest.LogCaptureFixture) -> None:
    log: list[str] = []

    def boom() -> None:
        raise RuntimeError("boom")

    manager = CleanupManager()
    manager.register(lambda: log.append("first"))
    manager.register(boom)
    manager.register(lambda: log.append("last"))
    with caplog.at_level(logging.ERROR, logger="widgets.base_elements.cleanup"):
        manager.cleanup()
    assert log == ["last", "first"]
    assert any("boom" in (r.exc_text or "") for r in caplog.records)


@pytest.mark.req("FR-CLEAN-005")
def test_registration_after_cleanup_runs_immediately() -> None:
    log: list[str] = []
    manager = CleanupManager()
    manager.cleanup()
    token = manager.register(lambda: log.append("late"))
    assert log == ["late"]
    assert manager.cancel(token) is False  # already executed


@pytest.mark.req("FR-CLEAN-006")
def test_cancel_token() -> None:
    log: list[str] = []
    manager = CleanupManager()
    keep = manager.register(lambda: log.append("keep"))
    drop = manager.register(lambda: log.append("drop"))
    assert manager.cancel(drop) is True
    assert manager.cancel(drop) is False
    manager.cleanup()
    assert log == ["keep"]
    assert manager.cancel(keep) is False


@pytest.mark.req("FR-CLEAN-001")
def test_register_rejects_non_actions() -> None:
    with pytest.raises(TypeError):
        CleanupManager().register(42)  # type: ignore[arg-type]


@pytest.mark.req("FR-CLEAN-007")
@pytest.mark.slow
def test_cleanup_is_thread_safe_each_action_runs_exactly_once() -> None:
    manager = CleanupManager()
    runs: Counter[tuple[int, int]] = Counter()
    guard = threading.Lock()
    barrier = threading.Barrier(9)

    def action(key: tuple[int, int]) -> None:
        with guard:
            runs[key] += 1

    def registrar(worker: int) -> None:
        barrier.wait()
        for i in range(300):
            key = (worker, i)
            manager.register(lambda key=key: action(key))  # type: ignore[misc]

    def cleaner() -> None:
        barrier.wait()
        for _ in range(50):
            manager.cleanup()

    threads = [threading.Thread(target=registrar, args=(w,)) for w in range(8)]
    threads.append(threading.Thread(target=cleaner))
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    manager.cleanup()
    assert len(runs) == 8 * 300
    assert set(runs.values()) == {1}


def test_cleanup_manager_context_manager() -> None:
    log: list[str] = []
    with CleanupManager() as manager:
        manager.register(lambda: log.append("x"))
    assert log == ["x"]
