"""Focusable widgets and the focus manager (FR-INPUT-001..003, 008). Layer L2."""

from __future__ import annotations

from widgets.base_elements.base import Widget
from widgets.base_elements.events import KeyEvent
from widgets.base_elements.lifecycle import LifecycleState


def _eligible(widget: Widget) -> bool:
    """Can ``widget`` currently receive focus?"""
    return (
        widget.focusable
        and widget.effective_visible
        and widget.effective_enabled
        and widget.state is not LifecycleState.CLOSED
    )


class InteractiveWidget(Widget):
    """A widget that can take keyboard focus.

    ``on_focus`` / ``on_blur`` fire exactly once per focus transition (FR-INPUT-002).
    """

    focusable = True

    def __init__(self, *args: object, tab_index: int | None = None, **kwargs: object) -> None:
        super().__init__(*args, **kwargs)  # type: ignore[arg-type]
        self.tab_index = tab_index
        self._focused = False

    @property
    def focused(self) -> bool:
        return self._focused

    def focus(self) -> bool:
        """Take focus. Returns False if the widget cannot be focused right now."""
        if not _eligible(self):
            return False
        if not self._focused:
            self._focused = True
            self.on_focus()
        return True

    def blur(self) -> bool:
        """Give up focus. Returns True if the widget had focus."""
        if not self._focused:
            return False
        self._focused = False
        self.on_blur()
        return True

    def on_focus(self) -> None:
        """Called when the widget gains focus."""

    def on_blur(self) -> None:
        """Called when the widget loses focus."""

    def on_close(self) -> None:
        self.blur()
        super().on_close()


class FocusManager:
    """Tracks the focused widget under a root and routes key events (FR-INPUT-008).

    Tab order is tree order (insertion order) unless ``tab_index`` overrides it: widgets are
    stably sorted by ``tab_index`` with ``None`` counting as 0. Invisible or disabled widgets
    (including those under an invisible/disabled ancestor) are skipped.
    """

    def __init__(self, root: Widget) -> None:
        self.root = root
        self._focused: InteractiveWidget | None = None

    # -- focus ----------------------------------------------------------------------------

    @property
    def focused(self) -> InteractiveWidget | None:
        self._validate()
        return self._focused

    def focus_order(self) -> list[InteractiveWidget]:
        candidates = [
            w for w in self.root.walk() if isinstance(w, InteractiveWidget) and _eligible(w)
        ]
        return sorted(candidates, key=lambda w: w.tab_index or 0)

    def focus(self, widget: InteractiveWidget) -> bool:
        """Move focus to ``widget`` (it must be part of the tree and eligible)."""
        if widget not in self.focus_order():
            return False
        if self._focused is not None and self._focused is not widget:
            self._focused.blur()
        self._focused = widget
        return widget.focus()

    def focus_next(self) -> InteractiveWidget | None:
        return self._step(+1)

    def focus_previous(self) -> InteractiveWidget | None:
        return self._step(-1)

    def clear(self) -> None:
        if self._focused is not None:
            self._focused.blur()
            self._focused = None

    def _step(self, direction: int) -> InteractiveWidget | None:
        self._validate()
        order = self.focus_order()
        if not order:
            self.clear()
            return None
        current = self._focused
        if current is None or current not in order:
            target = order[0] if direction > 0 else order[-1]
        else:
            target = order[(order.index(current) + direction) % len(order)]
        return target if self.focus(target) else None

    def _validate(self) -> None:
        """Drop focus from a widget that left the tree or became ineligible."""
        current = self._focused
        if current is not None and current not in self.focus_order():
            current.blur()
            self._focused = None

    # -- event routing ----------------------------------------------------------------------

    def dispatch(self, event: KeyEvent) -> bool:
        """Offer the key to the focused widget, then its ancestors; Tab / Shift+Tab move focus.

        With nothing focused the root gets the event (global shortcuts).
        """
        self._validate()
        node: Widget | None = self._focused
        if node is None:
            node = None
            if self.root.dispatch_key(event):
                return True
        while node is not None:
            if node.dispatch_key(event):
                return True
            node = node.parent
        if event.key == "tab" and not (event.ctrl or event.alt):
            return self.focus_next() is not None
        if event.key == "backtab":
            return self.focus_previous() is not None
        return False

    def dispatch_paste(self, text: str) -> bool:
        self._validate()
        node: Widget | None = self._focused
        while node is not None:
            if node.dispatch_paste(text):
                return True
            node = node.parent
        return False
