"""Code editor widget (FR-CODE-001..008). Layer L3.

Selection, clipboard and search/replace (FR-CODE-009, P3) are not implemented yet.
"""

from __future__ import annotations

import os
import re
import tempfile
from dataclasses import dataclass
from pathlib import Path

import widgets.data._syntax_data as _extra
from widgets.base_elements.events import KeyEvent
from widgets.base_elements.interactive import InteractiveWidget
from widgets.base_elements.widget_types import DEFAULT_STYLE, RGB, Style, WidgetId
from widgets.errors import WidgetsError
from widgets.render.buffer import Canvas

DEFAULT_MAX_BYTES = 10 * 1024 * 1024
HISTORY_LIMIT = 1000


class CodeFileError(WidgetsError):
    """A file could not be opened/decoded/saved as requested."""


_PY_KW = [
    "False",
    "None",
    "True",
    "and",
    "as",
    "assert",
    "async",
    "await",
    "break",
    "class",
    "continue",
    "def",
    "del",
    "elif",
    "else",
    "except",
    "finally",
    "for",
    "from",
    "global",
    "if",
    "import",
    "in",
    "is",
    "lambda",
    "nonlocal",
    "not",
    "or",
    "pass",
    "raise",
    "return",
    "try",
    "while",
    "with",
    "yield",
    "match",
    "case",
]
_JS_KW = [
    "async",
    "await",
    "break",
    "case",
    "catch",
    "class",
    "const",
    "continue",
    "debugger",
    "default",
    "delete",
    "do",
    "else",
    "export",
    "extends",
    "finally",
    "for",
    "function",
    "if",
    "import",
    "in",
    "instanceof",
    "let",
    "new",
    "of",
    "return",
    "static",
    "super",
    "switch",
    "this",
    "throw",
    "try",
    "typeof",
    "var",
    "void",
    "while",
    "with",
    "yield",
    "null",
    "true",
    "false",
    "undefined",
]


LANGUAGES = frozenset({"python", "javascript", *_extra.KEYWORDS})


EXTENSIONS = {
    ".py": "python",
    ".pyw": "python",
    ".js": "javascript",
    ".mjs": "javascript",
    ".ts": "typescript",
    ".java": "java",
    ".c": "c",
    ".h": "c",
    ".cpp": "c++",
    ".cc": "c++",
    ".hpp": "c++",
    ".go": "go",
    ".rs": "rust",
    ".php": "php",
    ".swift": "swift",
}


def detect_language(path: str | os.PathLike[str]) -> str | None:
    """Highlight language for a file name (by extension), or ``None``."""
    return EXTENSIONS.get(Path(path).suffix.lower())


def _rules(language: str) -> list[tuple[str, re.Pattern[str]]]:
    if language == "python":
        kw = _PY_KW
    elif language == "javascript":
        kw = _JS_KW
    else:
        kw = list(_extra.KEYWORDS[language])
    comment = r"#.*" if language in ("python", "php") else r"//.*"
    if language == "php":
        comment = r"(?:#|//).*"
    return [
        ("comment", re.compile(comment)),
        (
            "string",
            re.compile(
                r"""(""" + r""""(?:\\.|[^"\\])*"|'(?:\\.|[^'\\])*'|`(?:\\.|[^`\\])*`""" + r""")"""
            ),
        ),
        ("number", re.compile(r"\b\d+(?:\.\d+)?\b")),
        ("keyword", re.compile(r"\b(?:" + "|".join(kw) + r")\b")),
    ]


TOKEN_STYLES = {
    "keyword": Style(fg=RGB(200, 120, 255), bold=True),
    "string": Style(fg=RGB(120, 200, 120)),
    "comment": Style(fg=RGB(130, 130, 130), italic=True),
    "number": Style(fg=RGB(240, 170, 80)),
}


def highlight(line: str, language: str | None) -> list[tuple[int, int, str]]:
    """Token spans ``(start, end, kind)``; any failure degrades to no highlighting."""
    if language not in LANGUAGES:
        return []
    try:
        spans: list[tuple[int, int, str]] = []
        taken = [False] * len(line)
        for kind, pattern in _rules(language):
            for m in pattern.finditer(line):
                if m.end() == m.start() or any(taken[m.start() : m.end()]):
                    continue
                for i in range(m.start(), m.end()):
                    taken[i] = True
                spans.append((m.start(), m.end(), kind))
        return sorted(spans)
    except Exception:
        return []


@dataclass(slots=True)
class _Op:
    kind: str  # "ins" | "del"
    row: int
    col: int
    text: str


class CodeEditor(InteractiveWidget):
    """Editable multi-line text widget with syntax highlighting and explicit save."""

    def __init__(
        self,
        x: int = 0,
        y: int = 0,
        width: int = 60,
        height: int = 16,
        *,
        text: str = "",
        language: str | None = None,
        line_numbers: bool = True,
        read_only: bool = False,
        tab_width: int = 4,
        name: WidgetId | None = None,
    ) -> None:
        super().__init__(x, y, width, height, name=name)
        self.language, self.line_numbers, self.read_only, self.tab_width = (
            language,
            line_numbers,
            read_only,
            tab_width,
        )
        self.lines: list[str] = text.split("\n") if text else [""]
        self.row = self.col = self.top = self.left = 0
        self.path: Path | None = None
        self.encoding = "utf-8"
        self.newline = "\n"
        self.dirty = False
        self.message = ""
        self.anchor: tuple[int, int] | None = None  # selection start (row, col); cursor is the end
        self.clipboard = ""
        self.search_query = ""
        self._undo: list[list[_Op]] = []
        self._redo: list[list[_Op]] = []

    # -- model ---------------------------------------------------------------------------
    @property
    def text(self) -> str:
        return "\n".join(self.lines)

    def set_text(self, text: str) -> None:
        self.lines = text.split("\n") if text else [""]
        self.row = self.col = self.top = self.left = 0
        self._undo.clear()
        self._redo.clear()
        self.dirty = False

    def _fix(self) -> None:
        self.row = max(0, min(len(self.lines) - 1, self.row))
        self.col = max(0, min(len(self.lines[self.row]), self.col))
        body = max(1, self.height)
        if self.row < self.top:
            self.top = self.row
        elif self.row >= self.top + body:
            self.top = self.row - body + 1
        width = max(1, self.width - self._gutter())
        if self.col < self.left:
            self.left = self.col
        elif self.col >= self.left + width:
            self.left = self.col - width + 1

    # -- selection, clipboard, search (FR-CODE-009) ----------------------------------------
    def selection(self) -> tuple[tuple[int, int], tuple[int, int]] | None:
        """Ordered ``((row, col), (row, col))`` of the selection, or ``None``."""
        if self.anchor is None or self.anchor == (self.row, self.col):
            return None
        a, b = self.anchor, (self.row, self.col)
        return (a, b) if a <= b else (b, a)

    def selected_text(self) -> str:
        sel = self.selection()
        if sel is None:
            return ""
        (r1, c1), (r2, c2) = sel
        if r1 == r2:
            return self.lines[r1][c1:c2]
        parts = [self.lines[r1][c1:], *self.lines[r1 + 1 : r2], self.lines[r2][:c2]]
        return "\n".join(parts)

    def select_all(self) -> None:
        self.anchor = (0, 0)
        self.row = len(self.lines) - 1
        self.col = len(self.lines[self.row])
        self._fix()

    def clear_selection(self) -> None:
        self.anchor = None

    def delete_selection(self) -> bool:
        """Remove the selected text as one undoable step; ``False`` if nothing is selected."""
        group = self._remove_selection()
        if group is None:
            return False
        self._push(group)
        self._fix()
        return True

    def _remove_selection(self) -> list[_Op] | None:
        sel = self.selection()
        if sel is None or self.read_only:
            return None
        (_, _), (r2, c2) = sel
        count = len(self.selected_text())
        self.row, self.col = r2, c2
        group: list[_Op] = []
        for _ in range(count):
            if self.col > 0:
                line = self.lines[self.row]
                self._record(group, _Op("del", self.row, self.col - 1, line[self.col - 1]))
                self.lines[self.row] = line[: self.col - 1] + line[self.col :]
                self.col -= 1
            else:
                prev = self.lines[self.row - 1]
                self._record(group, _Op("del", self.row - 1, len(prev), "\n"))
                self.lines[self.row - 1] = prev + self.lines[self.row]
                del self.lines[self.row]
                self.row, self.col = self.row - 1, len(prev)
        self.anchor = None
        return group

    def copy(self) -> str:
        self.clipboard = self.selected_text() or self.clipboard
        return self.clipboard

    def cut(self) -> str:
        text = self.copy() if self.selection() else ""
        self.delete_selection()
        return text

    def paste(self) -> None:
        if self.clipboard:
            self.delete_selection()
            self.insert_text(self.clipboard)

    def _offset(self, row: int, col: int) -> int:
        return sum(len(line) + 1 for line in self.lines[:row]) + col

    def _position(self, offset: int) -> tuple[int, int]:
        for r, line in enumerate(self.lines):
            if offset <= len(line):
                return r, offset
            offset -= len(line) + 1
        return len(self.lines) - 1, len(self.lines[-1])

    def find(self, query: str | None = None, *, backwards: bool = False) -> bool:
        """Select the next (or previous) occurrence of ``query``; wraps around the document."""
        if query is not None:
            self.search_query = query
        q = self.search_query
        if not q:
            return False
        text = self.text
        sel = self.selection()
        if backwards:
            off = self._offset(*(sel[0] if sel else (self.row, self.col)))
            idx = text.rfind(q, 0, off)
            if idx == -1:
                idx = text.rfind(q)
        else:
            off = self._offset(*(sel[1] if sel else (self.row, self.col)))
            idx = text.find(q, off)
            if idx == -1:
                idx = text.find(q)
        if idx == -1:
            self.message = f"{q!r} not found"
            return False
        r, c = self._position(idx)
        er, ec = self._position(idx + len(q))
        self.anchor, self.row, self.col = (r, c), er, ec
        self._fix()
        self.message = f"found {q!r} at {r + 1}:{c + 1}"
        return True

    def find_next(self) -> bool:
        return self.find()

    def find_previous(self) -> bool:
        return self.find(backwards=True)

    def goto_line(self, line: int) -> None:
        """1-based line number, clamped to the document."""
        self.row, self.col = line - 1, 0
        self._fix()

    def _record(self, group: list[_Op], op: _Op) -> None:
        group.append(op)

    def _push(self, group: list[_Op]) -> None:
        if group:
            self._undo.append(group)
            del self._undo[: max(0, len(self._undo) - HISTORY_LIMIT)]
            self._redo.clear()
            self.dirty = True

    def insert_text(self, text: str) -> None:
        if self.read_only or not text:
            return
        group: list[_Op] = self._remove_selection() or []  # replace-selection is one undo step
        for chunk_i, chunk in enumerate(text.split("\n")):
            if chunk_i:
                self._newline(group)
            if chunk:
                line = self.lines[self.row]
                self.lines[self.row] = line[: self.col] + chunk + line[self.col :]
                self._record(group, _Op("ins", self.row, self.col, chunk))
                self.col += len(chunk)
        self._push(group)
        self._fix()

    def _newline(self, group: list[_Op]) -> None:
        line = self.lines[self.row]
        self.lines[self.row] = line[: self.col]
        self.lines.insert(self.row + 1, line[self.col :])
        self._record(group, _Op("ins", self.row, self.col, "\n"))
        self.row, self.col = self.row + 1, 0

    def delete_back(self) -> None:
        if self.read_only or self.delete_selection():
            return
        group: list[_Op] = []
        if self.col > 0:
            line = self.lines[self.row]
            self._record(group, _Op("del", self.row, self.col - 1, line[self.col - 1]))
            self.lines[self.row] = line[: self.col - 1] + line[self.col :]
            self.col -= 1
        elif self.row > 0:
            prev = self.lines[self.row - 1]
            self._record(group, _Op("del", self.row - 1, len(prev), "\n"))
            self.lines[self.row - 1] = prev + self.lines[self.row]
            del self.lines[self.row]
            self.row, self.col = self.row - 1, len(prev)
        self._push(group)
        self._fix()

    def delete_forward(self) -> None:
        if self.read_only or self.delete_selection():
            return
        group: list[_Op] = []
        line = self.lines[self.row]
        if self.col < len(line):
            self._record(group, _Op("del", self.row, self.col, line[self.col]))
            self.lines[self.row] = line[: self.col] + line[self.col + 1 :]
        elif self.row < len(self.lines) - 1:
            self._record(group, _Op("del", self.row, len(line), "\n"))
            self.lines[self.row] = line + self.lines[self.row + 1]
            del self.lines[self.row + 1]
        self._push(group)
        self._fix()

    def _apply(self, op: _Op, inverse: bool) -> None:
        inserting = (op.kind == "ins") != inverse
        if inserting:
            if op.text == "\n":
                line = self.lines[op.row]
                self.lines[op.row] = line[: op.col]
                self.lines.insert(op.row + 1, line[op.col :])
                self.row, self.col = op.row + 1, 0
            else:
                line = self.lines[op.row]
                self.lines[op.row] = line[: op.col] + op.text + line[op.col :]
                self.row, self.col = op.row, op.col + len(op.text)
        elif op.text == "\n":
            self.lines[op.row] += self.lines[op.row + 1]
            del self.lines[op.row + 1]
            self.row, self.col = op.row, op.col
        else:
            line = self.lines[op.row]
            self.lines[op.row] = line[: op.col] + line[op.col + len(op.text) :]
            self.row, self.col = op.row, op.col

    def undo(self) -> bool:
        if not self._undo:
            return False
        group = self._undo.pop()
        for op in reversed(group):
            self._apply(op, inverse=True)
        self._redo.append(group)
        self.dirty = True
        self._fix()
        return True

    def redo(self) -> bool:
        if not self._redo:
            return False
        group = self._redo.pop()
        for op in group:
            self._apply(op, inverse=False)
        self._undo.append(group)
        self.dirty = True
        self._fix()
        return True

    # -- files ---------------------------------------------------------------------------
    def load(
        self,
        path: str | os.PathLike[str],
        *,
        encoding: str = "utf-8",
        max_bytes: int = DEFAULT_MAX_BYTES,
        errors: str = "strict",
        oversize: str = "refuse",
    ) -> None:
        p = Path(path)
        try:
            size = p.stat().st_size
            raw = p.read_bytes() if size <= max_bytes else b""
        except OSError as exc:
            raise CodeFileError(f"cannot read {p}: {exc.strerror or exc}") from exc
        read_only = False
        if size > max_bytes:
            if oversize == "refuse":
                raise CodeFileError(f"{p} is {size} bytes, above the {max_bytes} byte limit")
            raw, read_only = p.read_bytes()[:max_bytes], True
        try:
            text = raw.decode(encoding, errors=errors)
        except UnicodeDecodeError as exc:
            raise CodeFileError(
                f"{p} is not valid {encoding}: {exc.reason} at byte {exc.start}"
            ) from exc
        if errors != "strict":
            read_only = True
        self.newline = (
            "\r\n" if "\r\n" in text else "\r" if "\r" in text and "\n" not in text else "\n"
        )
        self.set_text(text.replace("\r\n", "\n").replace("\r", "\n"))
        self.path, self.encoding, self.read_only = p, encoding, read_only or self.read_only
        if self.language is None:
            self.language = detect_language(p)

    def save(self, path: str | os.PathLike[str] | None = None) -> None:
        """Explicit, atomic save (temp file in the same directory, then replace); keeps file mode."""
        target = Path(path) if path is not None else self.path
        if target is None:
            raise CodeFileError("no path to save to")
        if self.read_only:
            raise CodeFileError("editor is read-only")
        data = self.text.replace("\n", self.newline).encode(self.encoding)
        fd, tmp = tempfile.mkstemp(dir=target.parent, prefix=f".{target.name}.", suffix=".tmp")
        try:
            with os.fdopen(fd, "wb") as handle:
                handle.write(data)
                handle.flush()
                os.fsync(handle.fileno())
            if target.exists():
                os.chmod(tmp, target.stat().st_mode & 0o7777)
            os.replace(tmp, target)
        except OSError as exc:
            Path(tmp).unlink(missing_ok=True)
            raise CodeFileError(f"cannot save {target}: {exc.strerror or exc}") from exc
        self.path, self.dirty = target, False

    # -- input / rendering ---------------------------------------------------------------------------
    def handle_key(self, event: KeyEvent) -> bool:
        if not self.effective_enabled:
            return False
        key = event.key
        page = max(1, self.height - 1)
        if event.ctrl:
            if key == "c":
                self.copy()
                return True
            if key == "x":
                self.cut()
                return True
            if key == "v":
                self.paste()
                return True
            if key == "a":
                self.select_all()
                return True
            if key == "f":
                self.find_next()
                return True
            if key == "z":
                return self.undo() or True
            if key == "y":
                return self.redo() or True
            if key == "s":
                try:
                    self.save()
                    self.message = f"saved {self.path}"
                except CodeFileError as exc:
                    self.message = str(exc)
                return True
            return False
        moving = key in ("up", "down", "left", "right", "home", "end", "pageup", "pagedown")
        if moving:
            if event.shift:
                if self.anchor is None:
                    self.anchor = (self.row, self.col)
            else:
                self.anchor = None
        if key == "f3":
            self.find(backwards=event.shift)
            return True
        if key == "escape" and self.anchor is not None:
            self.anchor = None
            return True
        if key == "up":
            self.row -= 1
        elif key == "down":
            self.row += 1
        elif key == "left":
            if self.col == 0 and self.row > 0:
                self.row -= 1
                self.col = len(self.lines[self.row])
            else:
                self.col -= 1
        elif key == "right":
            if self.col >= len(self.lines[self.row]) and self.row < len(self.lines) - 1:
                self.row, self.col = self.row + 1, 0
            else:
                self.col += 1
        elif key == "home":
            self.col = 0
        elif key == "end":
            self.col = len(self.lines[self.row])
        elif key == "pageup":
            self.row -= page
        elif key == "pagedown":
            self.row += page
        elif key == "enter":
            self.insert_text("\n")
        elif key == "backspace":
            self.delete_back()
        elif key == "delete":
            self.delete_forward()
        elif key == "tab":
            self.insert_text(" " * self.tab_width)
        elif event.char and event.char.isprintable() and not event.alt:
            self.insert_text(event.char)
        else:
            return False
        self._fix()
        return True

    def _gutter(self) -> int:
        return len(str(len(self.lines))) + 1 if self.line_numbers else 0

    def render(self, canvas: Canvas) -> None:
        self._fix()
        gutter = self._gutter()
        width = max(0, canvas.width - gutter)
        for r in range(canvas.height):
            i = self.top + r
            if i >= len(self.lines):
                break
            if gutter:
                canvas.write_text(r, 0, str(i + 1).rjust(gutter - 1) + " ", Style(dim=True))
            line = self.lines[i]
            spans = highlight(line, self.language)
            by_char = [DEFAULT_STYLE] * len(line)
            for s, e, kind in spans:
                for k in range(s, e):
                    by_char[k] = TOKEN_STYLES[kind]
            sel = self.selection()
            for k in range(self.left, min(len(line), self.left + width)):
                style = by_char[k]
                if sel and sel[0] <= (i, k) < sel[1]:
                    style = Style(reverse=True)
                canvas.write_text(r, gutter + k - self.left, line[k], style)
        if self.focused:
            cr, cc = self.row - self.top, gutter + self.col - self.left
            if 0 <= cr < canvas.height and 0 <= cc < canvas.width:
                cell = self.lines[self.row][self.col : self.col + 1] or " "
                canvas.write_text(cr, cc, cell, Style(reverse=True))

    def describe(self) -> str:
        return f"CodeEditor({self.path or 'untitled'}, line {self.row + 1}, col {self.col + 1}{', modified' if self.dirty else ''})"
