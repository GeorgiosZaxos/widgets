"""Directory tree widget (FR-DIR-001..007). Layer L3.

Children load on demand when a directory is first expanded. Loading is synchronous here; pass
``lister`` to substitute a slower/async source in tests. Errors become inline error entries.
"""

from __future__ import annotations

import os
import stat as stat_mod
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path

from widgets.base_elements.events import KeyEvent
from widgets.base_elements.interactive import InteractiveWidget
from widgets.base_elements.widget_types import DEFAULT_STYLE, RGB, Style, WidgetId
from widgets.display._common import clip_cells
from widgets.render.buffer import Canvas


@dataclass(slots=True)
class Entry:
    path: Path
    name: str
    is_dir: bool = False
    is_symlink: bool = False
    size: int = 0
    mode: int = 0
    mtime: float = 0.0
    error: str | None = None
    expanded: bool = False
    loaded: bool = False
    children: list[Entry] = field(default_factory=list)
    loop: bool = False


def stat_entry(path: Path) -> Entry:
    """Describe ``path`` as an ``Entry``; unreadable paths yield an entry carrying the error."""
    try:
        st = path.lstat()
    except OSError as exc:
        return Entry(path, path.name or str(path), error=f"{exc.strerror or exc}")
    link = stat_mod.S_ISLNK(st.st_mode)
    is_dir = stat_mod.S_ISDIR(st.st_mode)
    return Entry(
        path,
        path.name or str(path),
        is_dir=is_dir,
        is_symlink=link,
        size=st.st_size,
        mode=st.st_mode,
        mtime=st.st_mtime,
    )


class DirectoryTree(InteractiveWidget):
    """Lazily loaded, navigable directory tree."""

    def __init__(
        self,
        x: int = 0,
        y: int = 0,
        width: int = 60,
        height: int = 16,
        *,
        root: str | os.PathLike[str] = ".",
        show_hidden: bool = False,
        follow_symlinks: bool = False,
        sort: str = "name",
        descending: bool = False,
        show_size: bool = True,
        show_perms: bool = False,
        show_date: bool = False,
        lister: Callable[[Path], list[Path]] | None = None,
        ascii_only: bool = False,
        name: WidgetId | None = None,
    ) -> None:
        super().__init__(x, y, width, height, name=name)
        if sort not in ("name", "size", "mtime"):
            raise ValueError("sort must be name, size or mtime")
        self.root = stat_entry(Path(root))
        self.root.is_dir = True
        self.show_hidden, self.follow_symlinks, self.sort_by, self.descending = (
            show_hidden,
            follow_symlinks,
            sort,
            descending,
        )
        self.show_size, self.show_perms, self.show_date = show_size, show_perms, show_date
        self._lister = lister or (lambda p: sorted(p.iterdir()))
        self.ascii_only = ascii_only
        self.filter_text = ""
        self.filtering = False
        self.index = 0
        self.top = 0
        self._ancestors: dict[Path, set[Path]] = {}
        self.expand(self.root)

    # -- loading ---------------------------------------------------------------------------
    def _load(self, entry: Entry, chain: set[Path]) -> None:
        entry.loaded = True
        entry.children = []
        try:
            paths = self._lister(entry.path)
        except OSError as exc:
            entry.children = [
                Entry(entry.path / "?", f"<{exc.strerror or exc}>", error=str(exc.strerror or exc))
            ]
            return
        for p in paths:
            child = stat_entry(p)
            if child.is_symlink and self.follow_symlinks:
                try:
                    target = p.resolve(strict=True)
                    child.is_dir = target.is_dir()
                    if child.is_dir and (target in chain or target == entry.path.resolve()):
                        child.loop = True
                except OSError:
                    child.error = "broken link"
            elif child.is_symlink:
                child.is_dir = False  # not followed by default
            entry.children.append(child)
        self._ancestors[entry.path] = (
            chain | {entry.path.resolve()} if entry.path.exists() else chain
        )

    def expand(self, entry: Entry) -> None:
        if not entry.is_dir or entry.loop or entry.error:
            return
        if not entry.loaded:
            self._load(entry, self._ancestors.get(entry.path.parent, set()))
        entry.expanded = True

    def collapse(self, entry: Entry) -> None:
        entry.expanded = False

    def refresh(self, entry: Entry | None = None) -> None:
        target = entry or self.root
        was = target.expanded
        target.loaded = False
        if was:
            self.expand(target)

    def _sorted(self, children: list[Entry]) -> list[Entry]:
        """Directories first; ``descending`` reverses the order within each group."""
        keyf = {
            "name": lambda e: e.name.casefold(),
            "size": lambda e: e.size,
            "mtime": lambda e: e.mtime,
        }[self.sort_by]
        dirs = sorted((c for c in children if c.is_dir), key=keyf, reverse=self.descending)
        files = sorted((c for c in children if not c.is_dir), key=keyf, reverse=self.descending)
        return dirs + files

    def visible_rows(self) -> list[tuple[int, Entry]]:
        out: list[tuple[int, Entry]] = []

        def walk(e: Entry, depth: int) -> None:
            out.append((depth, e))
            if e.expanded:
                for c in self._sorted(e.children):
                    if not self.show_hidden and c.name.startswith(".") and c.error is None:
                        continue
                    if (
                        self.filter_text
                        and not c.is_dir
                        and self.filter_text.lower() not in c.name.lower()
                    ):
                        continue
                    walk(c, depth + 1)

        walk(self.root, 0)
        return out

    @property
    def selected(self) -> Entry | None:
        rows = self.visible_rows()
        return rows[self.index][1] if rows else None

    def _clamp(self) -> None:
        n = len(self.visible_rows())
        self.index = max(0, min(n - 1, self.index))
        if self.index < self.top:
            self.top = self.index
        elif self.index >= self.top + max(1, self.height):
            self.top = self.index - self.height + 1

    def set_sort(self, key: str, descending: bool = False) -> None:
        if key not in ("name", "size", "mtime"):
            raise ValueError("sort must be name, size or mtime")
        self.sort_by, self.descending = key, descending
        self._clamp()

    def handle_key(self, event: KeyEvent) -> bool:
        if not self.effective_enabled:
            return False
        key = event.key
        if self.filtering:
            if key == "escape":
                self.filtering, self.filter_text = False, ""
            elif key == "enter":
                self.filtering = False
            elif key == "backspace":
                self.filter_text = self.filter_text[:-1]
            elif event.char and event.char.isprintable():
                self.filter_text += event.char
            else:
                return False
            self._clamp()
            return True
        e = self.selected
        if key == "/":
            self.filtering = True
            self.filter_text = ""
        elif key == "up":
            self.index -= 1
        elif key == "down":
            self.index += 1
        elif key == "home":
            self.index = 0
        elif key == "end":
            self.index = len(self.visible_rows()) - 1
        elif key in ("right", "enter", "space") and e is not None and e.is_dir:
            (self.collapse if (e.expanded and key != "right") else self.expand)(e)
        elif key == "left" and e is not None:
            if e.expanded:
                self.collapse(e)
            else:
                rows = self.visible_rows()
                depth = rows[self.index][0]
                for i in range(self.index - 1, -1, -1):
                    if rows[i][0] < depth:
                        self.index = i
                        break
        elif key == "r":
            self.refresh(e if e is not None and e.is_dir else None)
        elif key == ".":
            self.show_hidden = not self.show_hidden
        else:
            return False
        self._clamp()
        return True

    def render(self, canvas: Canvas) -> None:
        self._clamp()
        rows = self.visible_rows()
        o, c, f = ("v", ">", " ") if self.ascii_only else ("▾", "▸", " ")
        for r, (depth, e) in enumerate(rows[self.top : self.top + canvas.height]):
            mark = (o if e.expanded else c) if e.is_dir else f
            suffix = (
                ("/" if e.is_dir else "")
                + (" @" if e.is_symlink else "")
                + (" (loop)" if e.loop else "")
            )
            extra = ""
            if self.show_size and not e.is_dir and e.error is None:
                extra += f"  {e.size:>9,}"
            if self.show_perms and e.error is None:
                extra += "  " + stat_mod.filemode(e.mode)
            if self.show_date and e.error is None:
                extra += "  " + time.strftime("%Y-%m-%d %H:%M", time.localtime(e.mtime))
            text = clip_cells("  " * depth + f"{mark} {e.name}{suffix}{extra}", canvas.width)
            sel = self.top + r == self.index
            style = Style(fg=RGB(230, 70, 70)) if e.error else DEFAULT_STYLE
            if sel:
                style = style.replace(reverse=self.focused, bold=True)
            canvas.write_text(r, 0, text.ljust(canvas.width) if sel else text, style)
        if self.filtering or self.filter_text:
            canvas.write_text(
                canvas.height - 1,
                0,
                f"/{self.filter_text}".ljust(canvas.width),
                Style(reverse=True),
            )

    def describe(self) -> str:
        e = self.selected
        return f"DirectoryTree({self.root.path}, selected={e.path if e else None})"
