"""Containers, z-order, clipping and the overlay layer (FR-LAYOUT-001..008). Layer L2.

Coordinates of a child are relative to its parent container (FR-LAYOUT-001). A container paints
its children in ascending ``z`` (ties: insertion order), each clipped to the container's rectangle
because it renders into a :class:`~widgets.render.buffer.BufferView` of that rectangle.
"""

from __future__ import annotations

from collections.abc import Sequence

from widgets.base_elements.base import Widget
from widgets.base_elements.lifecycle import LifecycleState
from widgets.base_elements.widget_types import WidgetId
from widgets.errors import LifecycleError
from widgets.render.buffer import Canvas


class Container(Widget):
    """A widget that owns and lays out child widgets."""

    def __init__(
        self, x: int = 0, y: int = 0, width: int = 0, height: int = 0, **kwargs: object
    ) -> None:
        super().__init__(x, y, width, height, **kwargs)  # type: ignore[arg-type]
        self._children: list[Widget] = []
        self._by_name: dict[WidgetId, Widget] = {}

    # -- children ----------------------------------------------------------------------------

    def _child_widgets(self) -> Sequence[Widget]:
        return tuple(self._children)

    @property
    def children(self) -> tuple[Widget, ...]:
        """Children in paint order: ascending ``z``, then insertion order."""
        return tuple(sorted(self._children, key=lambda child: child.z))

    def __len__(self) -> int:
        return len(self._children)

    def __contains__(self, item: object) -> bool:
        return item in self._children or (isinstance(item, str) and item in self._by_name)

    def get(self, name: WidgetId) -> Widget:
        try:
            return self._by_name[name]
        except KeyError:
            raise KeyError(f"no child named {name!r}") from None

    def add(self, child: Widget) -> Widget:
        """Add ``child`` and bring it to this container's lifecycle state."""
        if child is self or self in child.walk():
            raise ValueError("a widget cannot contain itself")
        if child.parent is not None:
            raise ValueError(f"{child.name!r} already has a parent")
        if child.state is not LifecycleState.CREATED:
            raise ValueError(f"{child.name!r} has already been used (state: {child.state.value})")
        if child.name in self._by_name:
            raise ValueError(f"a child named {child.name!r} already exists")
        if self.state in (LifecycleState.UNMOUNTED, LifecycleState.CLOSED):
            raise LifecycleError(f"cannot add children to a {self.state.value} container")
        self._children.append(child)
        self._by_name[child.name] = child
        child._parent = self
        self._sync_child(child)
        return child

    def _sync_child(self, child: Widget) -> None:
        state = self.state
        if state is LifecycleState.CREATED:
            return
        child.mount(self._context)
        if state in (LifecycleState.RUNNING, LifecycleState.PAUSED):
            child.start()
            if state is LifecycleState.PAUSED:
                child.pause()
        elif state is LifecycleState.STOPPED:
            child.stop()

    def remove(self, child: Widget | WidgetId, *, close: bool = True) -> Widget:
        """Detach a child (closing it by default so its resources are released)."""
        widget = self.get(child) if isinstance(child, str) else child
        if widget not in self._children:
            raise KeyError(f"{widget.name!r} is not a child of {self.name!r}")
        self._children.remove(widget)
        del self._by_name[widget.name]
        widget._parent = None
        if close:
            widget.close()
        return widget

    # -- behaviour ------------------------------------------------------------------------------

    def on_resize(self, width: int, height: int) -> None:
        for child in list(self._children):
            child.on_parent_resize(width, height)

    def update(self, dt: float) -> None:
        for child in self.children:
            child.tick(dt)

    def render(self, canvas: Canvas) -> None:
        for child in self.children:
            child.draw(canvas)


class Screen(Container):
    """Root container with an overlay layer painted above everything else (FR-LAYOUT-006).

    ``overlay`` is itself a container for dropdowns, notifications and dialogs; it has its own
    z-order and is resized together with the screen.
    """

    def __init__(self, width: int, height: int, *, name: WidgetId = "screen") -> None:
        super().__init__(0, 0, width, height, name=name)
        self.overlay = Container(0, 0, width, height, name="overlay")
        self.overlay._parent = self

    def _child_widgets(self) -> Sequence[Widget]:
        return (*self._children, self.overlay)

    def on_resize(self, width: int, height: int) -> None:
        self.overlay.resize(width, height)
        super().on_resize(width, height)

    def update(self, dt: float) -> None:
        super().update(dt)
        self.overlay.tick(dt)

    def render(self, canvas: Canvas) -> None:
        super().render(canvas)
        self.overlay.draw(canvas)
