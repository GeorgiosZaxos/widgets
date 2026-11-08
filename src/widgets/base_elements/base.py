"""The widget base class (FR-CORE-001..011, FR-LIFE-*, FR-INPUT-005). Layer L2.

Subclasses override the ``on_*`` hooks, :meth:`Widget.update` (time based state) and
:meth:`Widget.render` (paint into the supplied canvas using *local* coordinates). The runtime
calls :meth:`Widget.draw`, which enforces visibility and clips the widget to its rectangle.
"""

from __future__ import annotations

import itertools
import logging
import threading
from collections.abc import Callable, Iterator, Sequence
from typing import ClassVar

from widgets.base_elements.cleanup import CleanupManager
from widgets.base_elements.events import KeyEvent
from widgets.base_elements.lifecycle import LifecycleMachine, LifecycleState
from widgets.base_elements.widget_types import Rect, WidgetId
from widgets.render.buffer import Canvas

logger = logging.getLogger(__name__)


def _check_int(name: str, value: object) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise TypeError(f"{name} must be int, got {type(value).__name__}")
    return value


def _check_extent(name: str, value: object) -> int:
    number = _check_int(name, value)
    if number < 0:
        raise ValueError(f"{name} must be >= 0, got {number}")
    return number


class Widget:
    """Base class of all widgets."""

    focusable: ClassVar[bool] = False
    _name_counter: ClassVar[itertools.count[int]] = itertools.count(1)

    def __init__(
        self,
        x: int = 0,
        y: int = 0,
        width: int = 0,
        height: int = 0,
        *,
        name: WidgetId | None = None,
        visible: bool = True,
        enabled: bool = True,
        z: int = 0,
        raise_callback_errors: bool = False,
    ) -> None:
        self._x = _check_int("x", x)
        self._y = _check_int("y", y)
        self._width = _check_extent("width", width)
        self._height = _check_extent("height", height)
        if name is None:
            name = f"{type(self).__name__.lower()}-{next(Widget._name_counter)}"
        elif not isinstance(name, str) or not name:
            raise ValueError("name must be a non-empty string")
        self._name: WidgetId = name
        self._visible = bool(visible)
        self._enabled = bool(enabled)
        self._z = _check_int("z", z)
        self._parent: Widget | None = None
        self._context: object | None = None
        self._lifecycle = LifecycleMachine(name)
        self._close_lock = threading.RLock()
        self.tab_index: int | None = None
        self.raise_callback_errors = raise_callback_errors
        self.cleanup = CleanupManager(name)
        """Resources owned by the widget; released by :meth:`close` (FR-CORE-005/006)."""

    # -- identity and geometry ----------------------------------------------------------

    @property
    def name(self) -> WidgetId:
        return self._name

    @property
    def x(self) -> int:
        return self._x

    @x.setter
    def x(self, value: int) -> None:
        self.move(value, self._y)

    @property
    def y(self) -> int:
        return self._y

    @y.setter
    def y(self, value: int) -> None:
        self.move(self._x, value)

    @property
    def width(self) -> int:
        return self._width

    @width.setter
    def width(self, value: int) -> None:
        self.resize(value, self._height)

    @property
    def height(self) -> int:
        return self._height

    @height.setter
    def height(self, value: int) -> None:
        self.resize(self._width, value)

    @property
    def z(self) -> int:
        """Stacking order inside the parent container (higher paints later)."""
        return self._z

    @z.setter
    def z(self, value: int) -> None:
        self._z = _check_int("z", value)

    @property
    def rect(self) -> Rect:
        return Rect(self._x, self._y, self._width, self._height)

    def move(self, x: int, y: int) -> None:
        self._x = _check_int("x", x)
        self._y = _check_int("y", y)

    def resize(self, width: int, height: int) -> None:
        new_width = _check_extent("width", width)
        new_height = _check_extent("height", height)
        changed = (new_width, new_height) != (self._width, self._height)
        self._width, self._height = new_width, new_height
        if changed:
            self.on_resize(new_width, new_height)

    # -- state -----------------------------------------------------------------------------

    @property
    def visible(self) -> bool:
        return self._visible

    @visible.setter
    def visible(self, value: bool) -> None:
        self._visible = bool(value)

    @property
    def enabled(self) -> bool:
        return self._enabled

    @enabled.setter
    def enabled(self, value: bool) -> None:
        self._enabled = bool(value)

    @property
    def state(self) -> LifecycleState:
        return self._lifecycle.state

    @property
    def parent(self) -> Widget | None:
        return self._parent

    def ancestors(self) -> Iterator[Widget]:
        node = self._parent
        while node is not None:
            yield node
            node = node._parent

    @property
    def effective_visible(self) -> bool:
        return self._visible and all(a._visible for a in self.ancestors())

    @property
    def effective_enabled(self) -> bool:
        return self._enabled and all(a._enabled for a in self.ancestors())

    # -- tree ----------------------------------------------------------------------------------

    def _child_widgets(self) -> Sequence[Widget]:
        """All direct children (overridden by containers)."""
        return ()

    def _lifecycle_children(self) -> list[Widget]:
        return [c for c in self._child_widgets() if c.state is not LifecycleState.CLOSED]

    def walk(self) -> Iterator[Widget]:
        """Pre-order traversal of this widget and its open descendants."""
        yield self
        for child in self._lifecycle_children():
            yield from child.walk()

    # -- lifecycle (FR-LIFE-002..005) ------------------------------------------------------------

    def mount(self, context: object | None = None) -> None:
        if self._lifecycle.begin("mount"):
            self._context = context
            self.on_mount(context)
            for child in self._lifecycle_children():
                child.mount(context)

    def start(self) -> None:
        if self._lifecycle.begin("start"):
            self.on_start()
            for child in self._lifecycle_children():
                child.start()

    def pause(self) -> None:
        if self._lifecycle.begin("pause"):
            self.on_pause()
            for child in self._lifecycle_children():
                child.pause()

    def resume(self) -> None:
        if self._lifecycle.begin("resume"):
            self.on_resume()
            for child in self._lifecycle_children():
                child.resume()

    def stop(self) -> None:
        if self._lifecycle.begin("stop"):
            for child in reversed(self._lifecycle_children()):
                child.stop()
            self.on_stop()

    def unmount(self) -> None:
        if self._lifecycle.begin("unmount"):
            for child in reversed(self._lifecycle_children()):
                child.unmount()
            self.on_unmount()

    def close(self) -> None:
        """Stop, unmount and release everything. Idempotent; accepts any state (FR-CORE-005).

        All steps are attempted even if one fails; the first error is re-raised afterwards.
        """
        errors: list[Exception] = []

        def attempt(step: Callable[[], object]) -> None:
            try:
                step()
            except Exception as exc:
                logger.exception("error while closing widget %s", self._name)
                errors.append(exc)

        with self._close_lock:
            if self.state is LifecycleState.CLOSED:
                return
            if self.state in (
                LifecycleState.RUNNING,
                LifecycleState.PAUSED,
                LifecycleState.MOUNTED,
            ):
                attempt(self.stop)
            if self.state in (LifecycleState.STOPPED, LifecycleState.MOUNTED):
                attempt(self.unmount)
            self._lifecycle.mark_closed()
            for child in self._lifecycle_children():
                attempt(child.close)
            attempt(self.on_close)
            attempt(self.cleanup.cleanup)
        if errors:
            raise errors[0]

    def __enter__(self) -> Widget:
        if self.state is LifecycleState.CREATED:
            self.mount()
        if self.state in (LifecycleState.MOUNTED, LifecycleState.STOPPED):
            self.start()
        return self

    def __exit__(self, *exc_info: object) -> None:
        self.close()

    # -- hooks for subclasses ----------------------------------------------------------------------

    def on_mount(self, context: object | None) -> None:
        """Called once when the widget is mounted (parents before children)."""

    def on_start(self) -> None:
        """Called when the widget starts running."""

    def on_pause(self) -> None:
        """Called when the widget is paused."""

    def on_resume(self) -> None:
        """Called when a paused widget resumes."""

    def on_stop(self) -> None:
        """Called when the widget stops (children are stopped first). Join worker threads here."""

    def on_unmount(self) -> None:
        """Called when the widget is unmounted (children first)."""

    def on_close(self) -> None:
        """Called once from :meth:`close`, before :attr:`cleanup` runs."""

    def on_resize(self, width: int, height: int) -> None:
        """Called after this widget's own size changed."""

    def on_parent_resize(self, width: int, height: int) -> None:
        """Called when the parent container was resized, e.g. to re-anchor this widget."""

    # -- time, painting, input ---------------------------------------------------------------------------

    def update(self, dt: float) -> None:
        """Advance time-dependent state by ``dt`` seconds (called only while RUNNING)."""

    def tick(self, dt: float) -> None:
        """Runtime entry point for time updates; ignores widgets that are not running."""
        if self.state is LifecycleState.RUNNING:
            self.update(dt)

    def render(self, canvas: Canvas) -> None:
        """Paint into ``canvas`` using local coordinates; ``(0, 0)`` is the widget's top-left."""

    def draw(self, canvas: Canvas) -> None:
        """Paint this widget into its parent's ``canvas``.

        Invisible, empty, unmounted and closed widgets paint nothing (FR-CORE-007); output is
        clipped to the widget's rectangle (FR-LAYOUT-004).
        """
        if not self._visible or self._width == 0 or self._height == 0:
            return
        if self.state in (LifecycleState.UNMOUNTED, LifecycleState.CLOSED):
            return
        self.render(canvas.view(self.rect))

    def handle_key(self, event: KeyEvent) -> bool:
        """Process a key event; return True if it was consumed."""
        return False

    def dispatch_key(self, event: KeyEvent) -> bool:
        """Offer ``event`` to the widget; disabled or invisible widgets never consume it."""
        if not (self._enabled and self._visible):
            return False
        return bool(self.handle_key(event))

    def handle_paste(self, text: str) -> bool:
        """Process bracketed-paste text; return True if consumed."""
        return False

    def dispatch_paste(self, text: str) -> bool:
        if not (self._enabled and self._visible):
            return False
        return bool(self.handle_paste(text))

    # -- callbacks (FR-INPUT-005) ---------------------------------------------------------------------------

    def invoke_callback(self, callback: Callable[..., object] | None, *args: object) -> object:
        """Call a user callback on the UI thread; errors are logged unless configured to raise."""
        if callback is None:
            return None
        try:
            return callback(*args)
        except Exception:
            if self.raise_callback_errors:
                raise
            logger.exception("callback %r of widget %s raised", callback, self._name)
            return None

    # -- introspection ---------------------------------------------------------------------------------------

    def describe(self) -> str:
        """Plain-text summary of the widget's state (FR-CORE-011)."""
        flags = []
        if not self._visible:
            flags.append("hidden")
        if not self._enabled:
            flags.append("disabled")
        suffix = f" [{', '.join(flags)}]" if flags else ""
        return (
            f"{type(self).__name__} '{self._name}' at ({self._x}, {self._y}) "
            f"{self._width}x{self._height}, {self.state.value}{suffix}"
        )

    def __repr__(self) -> str:
        return f"<{self.describe()}>"
