"""Table widget with loaders, sorting and scrolling (FR-TABLE-001..007). Layer L3."""

from __future__ import annotations

import csv
import io
import json
import math
from collections.abc import Sequence

from widgets.base_elements.events import KeyEvent
from widgets.base_elements.interactive import InteractiveWidget
from widgets.base_elements.widget_types import DEFAULT_STYLE, Style, WidgetId
from widgets.display._common import clip_cells
from widgets.errors import MissingDependencyError, TableDataError
from widgets.render.buffer import Canvas
from widgets.render.width import display_width

DEFAULT_MAX_CELLS = 1_000_000


def sort_key(value: object) -> tuple[int, object]:
    """Stable ordering: numbers, then strings (case-insensitive), then others, then None/NaN."""
    if value is None or (isinstance(value, float) and math.isnan(value)):
        return (3, 0)
    if isinstance(value, bool):
        return (2, int(value))
    if isinstance(value, int | float):
        return (0, value)
    if isinstance(value, str):
        return (1, value.casefold())
    return (2, str(value))


class Table(InteractiveWidget):
    """Scrollable, sortable table of rows with optional borders and row numbers."""

    def __init__(
        self,
        x: int = 0,
        y: int = 0,
        width: int = 60,
        height: int = 12,
        *,
        columns: Sequence[str] = (),
        rows: Sequence[Sequence[object]] = (),
        header: bool = True,
        borders: bool = True,
        row_numbers: bool = False,
        widths: Sequence[int | str] | None = None,
        align: Sequence[str] | None = None,
        name: WidgetId | None = None,
    ) -> None:
        super().__init__(x, y, width, height, name=name)
        self.header, self.borders, self.row_numbers = header, borders, row_numbers
        self.truncated = False
        self.sorted_by: tuple[int, bool] | None = None
        self.cursor_row = 0
        self.cursor_col = 0
        self.top = 0
        self._set(list(columns), [list(r) for r in rows])
        self.widths = list(widths) if widths else None
        self.align = list(align) if align else None
        self._hidden: set[int] = set()

    # -- data ---------------------------------------------------------------------------
    def _set(self, columns: list[str], rows: list[list[object]]) -> None:
        for i, row in enumerate(rows, 1):
            if len(row) != len(columns):
                raise TableDataError(f"row has {len(row)} cells, expected {len(columns)}", row=i)
        self.columns, self.rows = columns, rows
        self.cursor_row = self.cursor_col = self.top = 0
        self._hidden = set()
        self.sorted_by = None

    def set_data(self, columns: Sequence[str], rows: Sequence[Sequence[object]]) -> None:
        self._set(list(columns), [list(r) for r in rows])

    @classmethod
    def _parse_rows(
        cls,
        records: list[list[object]],
        *,
        strict: bool,
        max_cells: int,
        on_limit: str,
        header: bool,
    ) -> tuple[list[str], list[list[object]], bool] | None:
        if not records:
            if strict:
                raise TableDataError("input is empty")
            return None
        head = (
            [str(c) for c in records[0]]
            if header
            else [f"col{i + 1}" for i in range(len(records[0]))]
        )
        body = records[1:] if header else records
        rows: list[list[object]] = []
        truncated = False
        for n, rec in enumerate(body, 2 if header else 1):
            if len(rec) != len(head):
                if strict:
                    raise TableDataError(
                        f"ragged row: {len(rec)} cells, expected {len(head)}", row=n
                    )
                return None
            if (len(rows) + 1) * len(head) > max_cells:
                if on_limit == "reject":
                    raise TableDataError(f"input exceeds {max_cells} cells", row=n)
                truncated = True
                break
            rows.append(list(rec))
        return head, rows, truncated

    def load_records(
        self,
        records: list[list[object]],
        *,
        strict: bool = True,
        header: bool = True,
        max_cells: int = DEFAULT_MAX_CELLS,
        on_limit: str = "truncate",
    ) -> None:
        """Parse fully first, then replace state (never partially replaced)."""
        parsed = self._parse_rows(
            records, strict=strict, max_cells=max_cells, on_limit=on_limit, header=header
        )
        if parsed is None:
            self._set([], [])
            self.truncated = False
            return
        head, rows, truncated = parsed
        self._set(head, rows)
        self.truncated = truncated

    def load_delimited(self, text: str, delimiter: str = ",", **opts: object) -> None:
        try:
            records = [list(r) for r in csv.reader(io.StringIO(text), delimiter=delimiter) if r]
        except csv.Error as exc:
            raise TableDataError(f"malformed delimited text: {exc}") from exc
        self.load_records(records, **opts)  # type: ignore[arg-type]

    def load_csv(self, text: str, **opts: object) -> None:
        self.load_delimited(text, ",", **opts)

    def load_tsv(self, text: str, **opts: object) -> None:
        self.load_delimited(text, "\t", **opts)

    def load_pipe(self, text: str, **opts: object) -> None:
        self.load_delimited(text, "|", **opts)

    def load_json(
        self,
        text: str,
        *,
        strict: bool = True,
        max_cells: int = DEFAULT_MAX_CELLS,
        on_limit: str = "truncate",
    ) -> None:
        try:
            data = json.loads(text)
        except json.JSONDecodeError as exc:
            raise TableDataError(f"invalid JSON: {exc}") from exc
        if not isinstance(data, list):
            raise TableDataError("JSON must be a list of objects or a list of lists")
        if data and all(isinstance(d, dict) for d in data):
            keys: list[str] = []
            for d in data:
                keys.extend(k for k in d if k not in keys)
            records: list[list[object]] = [list(keys), *[[d.get(k) for k in keys] for d in data]]
        elif all(isinstance(d, list) for d in data):
            records = [list(d) for d in data]
        elif not data:
            records = []
        else:
            raise TableDataError("JSON list mixes objects and lists")
        self.load_records(records, strict=strict, max_cells=max_cells, on_limit=on_limit)

    def load_excel(self, path: str, **opts: object) -> None:
        try:
            import openpyxl  # type: ignore[import-untyped,import-not-found,unused-ignore]
        except ImportError as exc:
            raise MissingDependencyError(
                "openpyxl", feature="Table.load_excel", extra="excel"
            ) from exc
        sheet = openpyxl.load_workbook(path, read_only=True).active
        self.load_records([list(r) for r in sheet.iter_rows(values_only=True)], **opts)  # type: ignore[arg-type]

    def load_dataframe(self, frame: object, **opts: object) -> None:
        """Duck-typed pandas ``DataFrame`` (needs ``.columns`` and ``.values.tolist()``)."""
        try:
            records: list[list[object]] = [list(map(str, frame.columns)), *frame.values.tolist()]  # type: ignore[attr-defined]
        except AttributeError as exc:
            raise MissingDependencyError(
                "pandas", feature="Table.load_dataframe", extra="data"
            ) from exc
        self.load_records(records, **opts)  # type: ignore[arg-type]

    # -- sorting, columns ---------------------------------------------------------------------------
    def sort(self, column: int, reverse: bool = False) -> None:
        if not 0 <= column < len(self.columns):
            raise ValueError(f"column {column} out of range")
        present = [r for r in self.rows if sort_key(r[column])[0] != 3]
        absent = [r for r in self.rows if sort_key(r[column])[0] == 3]
        present.sort(key=lambda r: sort_key(r[column]), reverse=reverse)  # stable
        self.rows = present + absent
        self.sorted_by = (column, reverse)

    def set_column_visible(self, column: int, visible: bool) -> None:
        (self._hidden.discard if visible else self._hidden.add)(column)

    def visible_columns(self) -> list[int]:
        return [i for i in range(len(self.columns)) if i not in self._hidden]

    # -- layout ---------------------------------------------------------------------------
    def column_widths(self, available: int) -> dict[int, int]:
        cols = self.visible_columns()
        spec = {
            c: (self.widths[c] if self.widths and c < len(self.widths) else "auto") for c in cols
        }
        out: dict[int, int] = {}
        for c in cols:
            if isinstance(spec[c], int):
                out[c] = int(spec[c])
            elif spec[c] == "auto":
                cells = [str(self.columns[c])] + [str(r[c]) for r in self.rows[:200]]
                out[c] = max(display_width(t) for t in cells) if cells else 1
        fr = {c: float(str(spec[c]).rstrip("fr") or 1) for c in cols if c not in out}
        if fr:
            rest = max(1, available - sum(out.values()) - len(cols))
            total = sum(fr.values())
            for c, f in fr.items():
                out[c] = max(1, int(rest * f / total))
        return out

    def move(self, x: int, y: int) -> None:  # keep Widget.move semantics
        super().move(x, y)

    def move_cursor(self, d_row: int = 0, d_col: int = 0) -> None:
        self.cursor_row = (
            max(0, min(len(self.rows) - 1, self.cursor_row + d_row)) if self.rows else 0
        )
        cols = self.visible_columns()
        if cols:
            idx = cols.index(self.cursor_col) if self.cursor_col in cols else 0
            self.cursor_col = cols[max(0, min(len(cols) - 1, idx + d_col))]
        body = max(
            1,
            self.height
            - (2 if self.header else 0)
            - (2 if self.borders else 0)
            + (1 if self.header else 0),
        )
        if self.cursor_row < self.top:
            self.top = self.cursor_row
        elif self.cursor_row >= self.top + body:
            self.top = self.cursor_row - body + 1

    def handle_key(self, event: KeyEvent) -> bool:
        if not self.effective_enabled:
            return False
        page = max(1, self.height - 3)
        moves = {
            "up": (-1, 0),
            "down": (1, 0),
            "left": (0, -1),
            "right": (0, 1),
            "pageup": (-page, 0),
            "pagedown": (page, 0),
            "home": (-len(self.rows), 0),
            "end": (len(self.rows), 0),
        }
        if event.key in moves:
            self.move_cursor(*moves[event.key])
            return True
        if event.key == "s" and self.columns:
            reverse = self.sorted_by == (self.cursor_col, False)
            self.sort(self.cursor_col, reverse)
            return True
        return False

    def render(self, canvas: Canvas) -> None:
        cols = self.visible_columns()
        num_w = len(str(len(self.rows))) + 2 if self.row_numbers else 0
        widths = self.column_widths(canvas.width - num_w)
        row = 0
        sep = "│" if self.borders else " "

        def line(cells: list[str], style: Style, number: str = "") -> str:
            parts = []
            for c, text in zip(cols, cells, strict=True):
                w = widths[c]
                t = clip_cells(text, w)
                a = self.align[c] if self.align and c < len(self.align) else "left"
                pad = w - display_width(t)
                parts.append(
                    " " * pad + t
                    if a == "right"
                    else t + " " * pad
                    if a == "left"
                    else " " * (pad // 2) + t + " " * (pad - pad // 2)
                )
            return (number.rjust(num_w - 1) + " " if num_w else "") + sep.join(parts)

        if self.header:
            marks = (
                {self.sorted_by[0]: ("▼" if self.sorted_by[1] else "▲")} if self.sorted_by else {}
            )
            heads = [str(self.columns[c]) + (marks.get(c, "")) for c in cols]
            canvas.write_text(row, 0, line(heads, Style(bold=True), "#"), Style(bold=True))
            row += 1
            if self.borders:
                canvas.write_text(row, 0, "─" * canvas.width, DEFAULT_STYLE)
                row += 1
        body_rows = canvas.height - row
        for i in range(self.top, min(len(self.rows), self.top + body_rows)):
            cells = ["" if self.rows[i][c] is None else str(self.rows[i][c]) for c in cols]
            style = (
                Style(reverse=True) if (i == self.cursor_row and self.focused) else DEFAULT_STYLE
            )
            canvas.write_text(row, 0, line(cells, style, str(i + 1)).ljust(canvas.width), style)
            row += 1
        if self.truncated and canvas.height:
            canvas.write_text(canvas.height - 1, 0, "… truncated"[: canvas.width], Style(dim=True))

    def describe(self) -> str:
        return f"Table({len(self.rows)} rows x {len(self.columns)} cols)"
