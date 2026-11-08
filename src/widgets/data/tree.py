"""Tree widget with JSON/XML/dict loaders (FR-TREE-001..004). Layer L3."""

from __future__ import annotations

import json
import xml.etree.ElementTree as ET
from collections.abc import Iterator
from dataclasses import dataclass, field

from widgets.base_elements.events import KeyEvent
from widgets.base_elements.interactive import InteractiveWidget
from widgets.base_elements.widget_types import DEFAULT_STYLE, Style, WidgetId
from widgets.display._common import clip_cells
from widgets.errors import WidgetsError
from widgets.render.buffer import Canvas

DEFAULT_MAX_BYTES = 1 << 20


class TreeDataError(WidgetsError, ValueError):
    """Invalid, unsafe or oversized tree input."""


@dataclass(slots=True)
class TreeNode:
    label: str
    data: object = None
    children: list[TreeNode] = field(default_factory=list)
    expanded: bool = False

    def add(self, child: TreeNode) -> TreeNode:
        self.children.append(child)
        return child


def from_python(value: object, label: str = "root") -> TreeNode:
    """Build nodes from nested dicts/lists/scalars."""
    node = TreeNode(label)
    if isinstance(value, dict):
        for k, v in value.items():
            node.children.append(from_python(v, str(k)))
    elif isinstance(value, list | tuple):
        for i, v in enumerate(value):
            node.children.append(from_python(v, f"[{i}]"))
    else:
        node.label, node.data = f"{label}: {value}", value
    return node


def from_json(text: str, *, max_bytes: int = DEFAULT_MAX_BYTES) -> TreeNode:
    """Parse JSON ``text`` (at most ``max_bytes``) into a ``TreeNode`` hierarchy."""
    if len(text.encode("utf-8")) > max_bytes:
        raise TreeDataError(f"input exceeds {max_bytes} bytes")
    try:
        return from_python(json.loads(text))
    except json.JSONDecodeError as exc:
        raise TreeDataError(f"invalid JSON: {exc}") from exc


def from_xml(text: str, *, max_bytes: int = DEFAULT_MAX_BYTES) -> TreeNode:
    """DOCTYPE and entity declarations are rejected *before* parsing (FR-SEC-002)."""
    if len(text.encode("utf-8")) > max_bytes:
        raise TreeDataError(f"input exceeds {max_bytes} bytes")
    lowered = text.lower()
    if "<!doctype" in lowered or "<!entity" in lowered:
        raise TreeDataError("XML with DOCTYPE or ENTITY declarations is not accepted")
    try:
        root = ET.fromstring(text)
    except ET.ParseError as exc:
        raise TreeDataError(f"invalid XML: {exc}") from exc

    def convert(el: ET.Element) -> TreeNode:
        attrs = " ".join(f'{k}="{v}"' for k, v in el.attrib.items())
        node = TreeNode(f"<{el.tag}{' ' + attrs if attrs else ''}>", data=el.attrib)
        if el.text and el.text.strip():
            node.children.append(TreeNode(el.text.strip()))
        node.children.extend(convert(c) for c in el)
        return node

    return convert(root)


class Tree(InteractiveWidget):
    """Expandable and collapsible tree of nodes with keyboard navigation."""

    def __init__(
        self,
        x: int = 0,
        y: int = 0,
        width: int = 40,
        height: int = 12,
        *,
        root: TreeNode | None = None,
        ascii_only: bool = False,
        on_select: object = None,
        name: WidgetId | None = None,
    ) -> None:
        super().__init__(x, y, width, height, name=name)
        self.root = root or TreeNode("root")
        self.root.expanded = True
        self.ascii_only = ascii_only
        self.on_select = on_select
        self.index = 0
        self.top = 0

    def visible_rows(self) -> list[tuple[int, TreeNode]]:
        out: list[tuple[int, TreeNode]] = []

        def walk(node: TreeNode, depth: int) -> Iterator[None]:
            out.append((depth, node))
            if node.expanded:
                for child in node.children:
                    yield from walk(child, depth + 1)
            yield None

        for _ in walk(self.root, 0):
            pass
        return out

    @property
    def selected(self) -> TreeNode | None:
        rows = self.visible_rows()
        return rows[self.index][1] if rows else None

    def expand_all(self) -> None:
        def walk(node: TreeNode) -> None:
            node.expanded = bool(node.children)
            for child in node.children:
                walk(child)

        walk(self.root)
        self._clamp()

    def collapse_all(self) -> None:
        def walk(node: TreeNode) -> None:
            node.expanded = False
            for child in node.children:
                walk(child)

        walk(self.root)
        self.root.expanded = True  # the root stays open so the tree is never empty
        self.index = 0
        self._clamp()

    def move_to_root(self) -> None:
        self.index = 0

    def move_to_parent(self) -> None:
        parent = self._parent_index()
        if parent is not None:
            self.index = parent

    def move_to_first_child(self) -> None:
        node = self.selected
        if node is not None and node.children:
            node.expanded = True
            self.index += 1
            self._clamp()

    def move_to_bottom(self) -> None:
        self.index = len(self.visible_rows()) - 1
        self._clamp()

    def info(self) -> dict[str, object]:
        """Summary of the selected node: path, depth, number of children and descendants."""
        rows = self.visible_rows()
        if not rows:
            return {}
        depth, node = rows[min(self.index, len(rows) - 1)]

        def count(n: TreeNode) -> int:
            return sum(1 + count(c) for c in n.children)

        return {
            "label": node.label,
            "depth": depth,
            "children": len(node.children),
            "descendants": count(node),
        }

    def _clamp(self) -> None:
        n = len(self.visible_rows())
        self.index = max(0, min(n - 1, self.index))
        body = max(1, self.height)
        if self.index < self.top:
            self.top = self.index
        elif self.index >= self.top + body:
            self.top = self.index - body + 1

    def _parent_index(self) -> int | None:
        rows = self.visible_rows()
        depth = rows[self.index][0]
        for i in range(self.index - 1, -1, -1):
            if rows[i][0] < depth:
                return i
        return None

    def handle_key(self, event: KeyEvent) -> bool:
        if not self.effective_enabled:
            return False
        node = self.selected
        key = event.key
        if key == "up":
            self.index -= 1
        elif key == "down":
            self.index += 1
        elif key == "home":
            self.index = 0
        elif key == "end":
            self.index = len(self.visible_rows()) - 1
        elif key == "pageup":
            self.index -= max(1, self.height - 1)
        elif key == "pagedown":
            self.index += max(1, self.height - 1)
        elif key == "right" and node is not None:
            if node.children and not node.expanded:
                node.expanded = True
            elif node.children:
                self.index += 1
        elif key == "left" and node is not None:
            if node.expanded and node.children:
                node.expanded = False
            else:
                parent = self._parent_index()
                if parent is not None:
                    self.index = parent
        elif key == "*":
            self.expand_all()
        elif key == "-":
            self.collapse_all()
        elif key in ("space", "enter") and node is not None:
            if node.children:
                node.expanded = not node.expanded
            if key == "enter":
                self.invoke_callback(self.on_select, node)  # type: ignore[arg-type]
        else:
            return False
        self._clamp()
        return True

    def render(self, canvas: Canvas) -> None:
        self._clamp()
        opened, closed, leaf = ("v", ">", "-") if self.ascii_only else ("▾", "▸", "•")
        rows = self.visible_rows()
        for r, (depth, node) in enumerate(rows[self.top : self.top + canvas.height]):
            mark = (opened if node.expanded else closed) if node.children else leaf
            text = clip_cells("  " * depth + f"{mark} {node.label}", canvas.width)
            sel = (self.top + r) == self.index
            canvas.write_text(
                r,
                0,
                text.ljust(canvas.width) if sel else text,
                Style(reverse=True)
                if sel and self.focused
                else Style(bold=True)
                if sel
                else DEFAULT_STYLE,
            )

    def describe(self) -> str:
        node = self.selected
        return (
            f"Tree(selected={node.label if node else None!r}, visible={len(self.visible_rows())})"
        )
