"""Tabs and split pane containers. Layer L3."""

from __future__ import annotations

from widgets.base_elements.base import Widget
from widgets.base_elements.events import KeyEvent
from widgets.base_elements.layout import Container
from widgets.base_elements.widget_types import Style, WidgetId
from widgets.render.buffer import Canvas
from widgets.render.width import display_width

ACTIVE = Style(bold=True, reverse=True)
INACTIVE = Style(dim=True)


class Tabs(Container):
    """A tab bar over a set of pages; only the active page is visible.

    Keys (work while any child has focus): ctrl+pagedown / ctrl+pageup, alt+1..9.
    """

    def __init__(
        self,
        x: int = 0,
        y: int = 0,
        width: int = 60,
        height: int = 12,
        *,
        name: WidgetId | None = None,
    ) -> None:
        super().__init__(x, y, width, height, name=name)
        self._titles: list[str] = []
        self._pages: list[Widget] = []
        self.index = 0

    def add_page(self, title: str, page: Widget) -> Widget:
        page.move(0, 1)
        page.resize(self.width, max(0, self.height - 1))
        self.add(page)
        self._titles.append(title)
        self._pages.append(page)
        self._sync()
        return page

    @property
    def titles(self) -> list[str]:
        return list(self._titles)

    @property
    def active(self) -> Widget | None:
        return self._pages[self.index] if self._pages else None

    def select(self, index: int) -> None:
        if self._pages:
            self.index = max(0, min(len(self._pages) - 1, index))
            self._sync()

    def next(self) -> None:
        self.select((self.index + 1) % max(1, len(self._pages)))

    def prev(self) -> None:
        self.select((self.index - 1) % max(1, len(self._pages)))

    def _sync(self) -> None:
        for i, page in enumerate(self._pages):
            page.visible = i == self.index

    def on_resize(self, width: int, height: int) -> None:
        for page in self._pages:
            page.resize(width, max(0, height - 1))
        super().on_resize(width, height)

    def handle_key(self, event: KeyEvent) -> bool:
        if event.ctrl and event.key == "pagedown":
            self.next()
            return True
        if event.ctrl and event.key == "pageup":
            self.prev()
            return True
        if event.alt and event.key.isdigit() and event.key != "0":
            self.select(int(event.key) - 1)
            return True
        return False

    def render(self, canvas: Canvas) -> None:
        col = 0
        for i, title in enumerate(self._titles):
            label = f" {title} "
            if col + display_width(label) > canvas.width:
                break
            col += canvas.write_text(0, col, label, ACTIVE if i == self.index else INACTIVE)
            col += canvas.write_text(0, col, "│", INACTIVE)
        super().render(canvas)


class SplitPane(Container):
    """Two children side by side (``horizontal``) or stacked (``vertical``) with a divider.

    Keys: alt+left / alt+right (or alt+up / alt+down) move the divider.
    """

    def __init__(
        self,
        x: int = 0,
        y: int = 0,
        width: int = 60,
        height: int = 12,
        *,
        first: Widget,
        second: Widget,
        orientation: str = "horizontal",
        ratio: float = 0.5,
        name: WidgetId | None = None,
    ) -> None:
        if orientation not in ("horizontal", "vertical"):
            raise ValueError("orientation must be 'horizontal' or 'vertical'")
        super().__init__(x, y, width, height, name=name)
        self.orientation = orientation
        self.ratio = min(0.9, max(0.1, ratio))
        self.first, self.second = first, second
        self.add(first)
        self.add(second)
        self._layout()

    def set_ratio(self, ratio: float) -> None:
        self.ratio = min(0.9, max(0.1, ratio))
        self._layout()

    def _layout(self) -> None:
        w, h = self.width, self.height
        if self.orientation == "horizontal":
            left = max(0, int((w - 1) * self.ratio))
            self.first.move(0, 0)
            self.first.resize(left, h)
            self.second.move(left + 1, 0)
            self.second.resize(max(0, w - left - 1), h)
        else:
            top = max(0, int((h - 1) * self.ratio))
            self.first.move(0, 0)
            self.first.resize(w, top)
            self.second.move(0, top + 1)
            self.second.resize(w, max(0, h - top - 1))

    def on_resize(self, width: int, height: int) -> None:
        super().on_resize(width, height)
        self._layout()

    def handle_key(self, event: KeyEvent) -> bool:
        if not event.alt:
            return False
        step = {"left": -0.05, "up": -0.05, "right": 0.05, "down": 0.05}.get(event.key)
        if step is None:
            return False
        self.set_ratio(self.ratio + step)
        return True

    def render(self, canvas: Canvas) -> None:
        w, h = canvas.width, canvas.height
        divider = Style(dim=True)
        if self.orientation == "horizontal":
            col = self.second.x - 1
            for r in range(h):
                canvas.write_text(r, col, "│", divider)
        else:
            row = self.second.y - 1
            canvas.write_text(row, 0, "─" * w, divider)
        super().render(canvas)


__all__ = ["SplitPane", "Tabs"]
