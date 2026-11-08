"""Kanban board, markdown viewer. Layer L3."""

from __future__ import annotations

import textwrap
from collections.abc import Mapping, Sequence

from widgets.base_elements.events import KeyEvent
from widgets.base_elements.interactive import InteractiveWidget
from widgets.base_elements.widget_types import RGB, Style, WidgetId
from widgets.display._common import clip_cells
from widgets.render.buffer import Canvas


class KanbanBoard(InteractiveWidget):
    """Columns of cards. Keys: arrows select, ``[`` / ``]`` move the card left / right, ``d`` delete."""

    def __init__(
        self,
        x: int = 0,
        y: int = 0,
        width: int = 72,
        height: int = 14,
        *,
        columns: Mapping[str, Sequence[str]],
        name: WidgetId | None = None,
    ) -> None:
        super().__init__(x, y, width, height, name=name)
        if not columns:
            raise ValueError("columns must not be empty")
        self.columns: dict[str, list[str]] = {k: list(v) for k, v in columns.items()}
        self.col = 0
        self.row = 0

    @property
    def names(self) -> list[str]:
        return list(self.columns)

    def _cards(self) -> list[str]:
        return self.columns[self.names[self.col]]

    def add_card(self, text: str, column: str | None = None) -> None:
        self.columns[column or self.names[self.col]].append(text)

    def selected(self) -> str | None:
        cards = self._cards()
        return cards[self.row] if 0 <= self.row < len(cards) else None

    def move_card(self, delta: int) -> bool:
        target = self.col + delta
        card = self.selected()
        if card is None or not 0 <= target < len(self.names):
            return False
        self._cards().pop(self.row)
        self.col = target
        self._cards().append(card)
        self.row = len(self._cards()) - 1
        return True

    def handle_key(self, event: KeyEvent) -> bool:
        key = event.key
        if key in ("left", "right"):
            self.col = max(0, min(len(self.names) - 1, self.col + (1 if key == "right" else -1)))
            self.row = max(0, min(len(self._cards()) - 1, self.row))
            return True
        if key in ("up", "down"):
            self.row = max(
                0, min(max(0, len(self._cards()) - 1), self.row + (1 if key == "down" else -1))
            )
            return True
        if key == "]":
            return self.move_card(1)
        if key == "[":
            return self.move_card(-1)
        if key == "d" and self.selected() is not None:
            self._cards().pop(self.row)
            self.row = max(0, min(self.row, len(self._cards()) - 1))
            return True
        return False

    def render(self, canvas: Canvas) -> None:
        n = len(self.names)
        col_w = max(6, canvas.width // n)
        for c, name in enumerate(self.names):
            left = c * col_w
            head = f"{name} ({len(self.columns[name])})"
            canvas.write_text(
                0,
                left,
                clip_cells(head, col_w - 1).ljust(col_w - 1),
                Style(bold=True, underline=c == self.col),
            )
            for r, card in enumerate(self.columns[name][: canvas.height - 2]):
                chosen = c == self.col and r == self.row
                style = Style(reverse=True) if chosen else Style(fg=RGB(200, 200, 220))
                canvas.write_text(
                    r + 2,
                    left,
                    clip_cells(("▸ " if chosen else "  ") + card, col_w - 1).ljust(col_w - 1),
                    style,
                )


class MarkdownView(InteractiveWidget):
    """Renders a Markdown subset: headings, lists, quotes, code fences, rules, bold/italic markers.

    Keys: up/down/pageup/pagedown/home/end scroll.
    """

    def __init__(
        self,
        x: int = 0,
        y: int = 0,
        width: int = 70,
        height: int = 16,
        *,
        text: str = "",
        name: WidgetId | None = None,
    ) -> None:
        super().__init__(x, y, width, height, name=name)
        self.top = 0
        self._text = ""
        self._lines: list[tuple[str, Style]] = []
        self.set_text(text)

    def set_text(self, text: str) -> None:
        self._text = text
        self._lines = self._layout(max(10, self.width))
        self.top = 0

    def on_resize(self, width: int, height: int) -> None:
        super().on_resize(width, height)
        self._lines = self._layout(max(10, width))

    @staticmethod
    def _inline(text: str) -> str:
        import re

        text = re.sub(r"\*\*(.+?)\*\*|__(.+?)__", lambda m: m.group(1) or m.group(2), text)
        text = re.sub(r"(?<!\*)\*(?!\*)(.+?)\*|_(.+?)_", lambda m: m.group(1) or m.group(2), text)
        text = re.sub(r"`([^`]+)`", r"\1", text)
        return re.sub(r"\[([^\]]+)\]\(([^)]+)\)", r"\1 <\2>", text)

    def _layout(self, width: int) -> list[tuple[str, Style]]:
        out: list[tuple[str, Style]] = []
        in_code = False
        for raw in self._text.splitlines():
            line = raw.rstrip()
            if line.startswith("```"):
                in_code = not in_code
                continue
            if in_code:
                out.append(("  " + line, Style(fg=RGB(150, 220, 150))))
            elif line.startswith("#"):
                level = len(line) - len(line.lstrip("#"))
                title = self._inline(line.lstrip("#").strip())
                out.append(
                    (
                        title.upper() if level == 1 else title,
                        Style(bold=True, fg=RGB(120, 190, 255), underline=level <= 2),
                    )
                )
                out.append(("", Style()))
            elif line.strip() in ("---", "***", "___"):
                out.append(("─" * width, Style(dim=True)))
            elif line.lstrip().startswith(("- ", "* ", "+ ")):
                indent = len(line) - len(line.lstrip())
                body = self._inline(line.lstrip()[2:])
                for i, part in enumerate(textwrap.wrap(body, max(1, width - indent - 2)) or [""]):
                    out.append((" " * indent + ("• " if i == 0 else "  ") + part, Style()))
            elif line.startswith(">"):
                for part in textwrap.wrap(self._inline(line.lstrip("> ")), max(1, width - 2)) or [
                    ""
                ]:
                    out.append(("▌ " + part, Style(italic=True, dim=True)))
            elif not line.strip():
                out.append(("", Style()))
            else:
                for part in textwrap.wrap(self._inline(line), width) or [""]:
                    out.append((part, Style()))
        return out

    def handle_key(self, event: KeyEvent) -> bool:
        page = max(1, self.height - 1)
        last = max(0, len(self._lines) - self.height)
        delta = {"up": -1, "down": 1, "pageup": -page, "pagedown": page}
        if event.key in delta:
            self.top = max(0, min(last, self.top + delta[event.key]))
            return True
        if event.key == "home":
            self.top = 0
            return True
        if event.key == "end":
            self.top = last
            return True
        return False

    def render(self, canvas: Canvas) -> None:
        for r, (text, style) in enumerate(self._lines[self.top : self.top + canvas.height]):
            canvas.write_text(r, 0, clip_cells(text, canvas.width), style)


__all__ = ["KanbanBoard", "MarkdownView"]
