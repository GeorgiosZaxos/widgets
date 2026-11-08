"""Character-cell screen buffer, clipped views and the ``Canvas`` protocol (FR-BUF-*, FR-LAYOUT-005).

Layer L1.

Wide glyph representation (FR-BUF-009): the first cell holds the glyph, the second cell holds the
:data:`~widgets.base_elements.widget_types.CONTINUATION` marker (an empty glyph). Combining marks
are appended to the glyph of the preceding base cell. Overwriting either half of a wide glyph
blanks the other half, so a buffer never contains an orphaned half.
"""

from __future__ import annotations

from typing import Protocol

from widgets.base_elements.widget_types import (
    BLANK_CELL,
    CONTINUATION,
    DEFAULT_STYLE,
    Cell,
    Rect,
    Style,
)
from widgets.render.sanitize import sanitize_text
from widgets.render.width import DEFAULT_WIDTH_POLICY, WidthPolicy


def _check_dimension(name: str, value: object) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise TypeError(f"{name} must be int, got {type(value).__name__}")
    if value < 0:
        raise ValueError(f"{name} must be >= 0, got {value}")
    return value


class Buffer:
    """Two-dimensional grid of :class:`Cell` values."""

    __slots__ = ("_height", "_policy", "_rows", "_width")

    def __init__(
        self,
        width: int,
        height: int,
        *,
        policy: WidthPolicy = DEFAULT_WIDTH_POLICY,
        fill: Cell = BLANK_CELL,
    ) -> None:
        self._width = _check_dimension("width", width)
        self._height = _check_dimension("height", height)
        self._policy = policy
        self._rows: list[list[Cell]] = [[fill] * self._width for _ in range(self._height)]

    # -- basic properties ---------------------------------------------------

    @property
    def width(self) -> int:
        return self._width

    @property
    def height(self) -> int:
        return self._height

    @property
    def policy(self) -> WidthPolicy:
        return self._policy

    @property
    def bounds(self) -> Rect:
        return Rect(0, 0, self._width, self._height)

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, Buffer):
            return NotImplemented
        return (self._width, self._height) == (other._width, other._height) and (
            self._rows == other._rows
        )

    __hash__ = None  # type: ignore[assignment]

    def __repr__(self) -> str:
        return f"Buffer({self._width}x{self._height})"

    # -- wide glyph integrity ----------------------------------------------

    def _break_pair(self, row: int, col: int) -> None:
        """Blank the other half of a wide glyph that cell (row, col) belongs to."""
        cells = self._rows[row]
        cell = cells[col]
        if cell.glyph == CONTINUATION:
            if col > 0 and cells[col - 1].glyph != CONTINUATION:
                cells[col - 1] = Cell(" ", cells[col - 1].style)
        elif col + 1 < self._width and cells[col + 1].glyph == CONTINUATION:
            cells[col + 1] = Cell(" ", cell.style)

    # -- cell access ----------------------------------------------------------

    def set_cell(self, row: int, col: int, cell: Cell) -> None:
        """Set one cell; out-of-range coordinates are ignored (FR-BUF-003/005)."""
        if 0 <= row < self._height and 0 <= col < self._width:
            self._break_pair(row, col)
            self._rows[row][col] = cell

    def get_cell(self, row: int, col: int) -> Cell:
        if not (0 <= row < self._height and 0 <= col < self._width):
            raise IndexError(
                f"cell ({row}, {col}) is outside the {self._width}x{self._height} buffer"
            )
        return self._rows[row][col]

    def row(self, row: int) -> tuple[Cell, ...]:
        """Immutable copy of one row (FR-BUF-008)."""
        if not 0 <= row < self._height:
            raise IndexError(f"row {row} is outside the buffer height {self._height}")
        return tuple(self._rows[row])

    # -- text -------------------------------------------------------------------

    def write_text(
        self,
        row: int,
        col: int,
        text: str,
        style: Style = DEFAULT_STYLE,
        *,
        clip: Rect | None = None,
    ) -> int:
        """Write ``text`` left to right starting at (row, col).

        The text is sanitised first (controls and escape sequences can never reach the terminal).
        Returns the display width of the text, i.e. how far the pen advanced, regardless of how
        much was clipped. Parts outside the buffer (and the optional ``clip``) are dropped; a wide
        glyph that is cut by the clip edge is replaced by a space.
        """
        text = sanitize_text(text)
        area = self.bounds if clip is None else self.bounds.intersect(clip)
        in_row = area.y <= row < area.bottom
        left, right = area.x, area.right
        policy = self._policy
        x = col
        last_base: int | None = None

        for ch in text:
            width = policy.char_width(ch)
            if width == 0:
                if in_row and last_base is not None:
                    base = self._rows[row][last_base]
                    self._rows[row][last_base] = Cell(base.glyph + ch, base.style)
                continue
            last_base = None
            if in_row:
                if width == 1:
                    if left <= x < right:
                        self._place(row, x, ch, style)
                        last_base = x
                elif left <= x and x + 1 < right:
                    self._place_wide(row, x, ch, style)
                    last_base = x
                else:  # wide glyph cut by the clip edge: show a space for the visible half
                    for visible in (x, x + 1):
                        if left <= visible < right:
                            self._place(row, visible, " ", style)
            x += width
        return x - col

    def _place(self, row: int, col: int, glyph: str, style: Style) -> None:
        self._break_pair(row, col)
        self._rows[row][col] = Cell(glyph, style)

    def _place_wide(self, row: int, col: int, glyph: str, style: Style) -> None:
        self._break_pair(row, col)
        self._break_pair(row, col + 1)
        self._rows[row][col] = Cell(glyph, style)
        self._rows[row][col + 1] = Cell(CONTINUATION, style)

    # -- bulk operations ----------------------------------------------------------

    def fill(self, rect: Rect, cell: Cell | None = None) -> None:
        """Fill the part of ``rect`` inside the buffer with ``cell`` (default: blank)."""
        value = BLANK_CELL if cell is None or cell.glyph == CONTINUATION else cell
        area = rect.intersect(self.bounds)
        for r in range(area.y, area.bottom):
            for c in range(area.x, area.right):
                self._break_pair(r, c)
                self._rows[r][c] = value

    def clear(self, cell: Cell | None = None) -> None:
        """Fill every cell with ``cell`` or a blank cell (FR-BUF-006)."""
        value = BLANK_CELL if cell is None or cell.glyph == CONTINUATION else cell
        self._rows = [[value] * self._width for _ in range(self._height)]

    def resize(self, width: int, height: int, *, fill: Cell = BLANK_CELL) -> None:
        """Resize, keeping the overlapping top-left region; new cells are ``fill`` (FR-BUF-007)."""
        new_width = _check_dimension("width", width)
        new_height = _check_dimension("height", height)
        old_rows, old_width = self._rows, self._width
        rows: list[list[Cell]] = []
        for r in range(new_height):
            if r < len(old_rows):
                kept = old_rows[r][:new_width]
                kept.extend([fill] * (new_width - len(kept)))
                if 0 < new_width < old_width and old_rows[r][new_width].glyph == CONTINUATION:
                    kept[new_width - 1] = Cell(" ", kept[new_width - 1].style)  # cut a wide glyph
                rows.append(kept)
            else:
                rows.append([fill] * new_width)
        self._rows, self._width, self._height = rows, new_width, new_height

    def copy_region_from(self, source: Buffer, rect: Rect) -> None:
        """Raw copy of ``rect`` (widened to whole wide glyphs) from a buffer of the same size.

        Used by the renderer to update its previous-frame cache for a partially rendered region.
        """
        if (source.width, source.height) != (self._width, self._height):
            raise ValueError("copy_region_from requires buffers of the same size")
        area = rect.intersect(self.bounds)
        for r in range(area.y, area.bottom):
            cells = source._rows[r]
            start, stop = area.x, area.right
            if start > 0 and cells[start].glyph == CONTINUATION:
                start -= 1
            if stop < self._width and cells[stop].glyph == CONTINUATION:
                stop += 1
            self._rows[r][start:stop] = cells[start:stop]

    def copy(self) -> Buffer:
        duplicate = Buffer(0, 0, policy=self._policy)
        duplicate._width, duplicate._height = self._width, self._height
        duplicate._rows = [list(row) for row in self._rows]
        return duplicate

    # -- inspection ---------------------------------------------------------------------

    def to_lines(self) -> list[str]:
        """Rows as text (continuation cells omitted, so a wide glyph counts once)."""
        return ["".join(c.glyph for c in row) for row in self._rows]

    def view(self, rect: Rect) -> BufferView:
        """A clipped, coordinate-translated window onto this buffer (FR-LAYOUT-005)."""
        return BufferView(self, rect)


class BufferView:
    """A window onto a :class:`Buffer` with local coordinates ``(0, 0)`` at ``rect``'s corner.

    All writes are clipped to ``rect`` (and to the parent view's clip). The single exception to
    "never touch cells outside the rectangle" is repairing a wide glyph that straddles the view
    boundary: when one half inside the view is overwritten, the other half outside is blanked
    so no half glyph is left behind.
    """

    __slots__ = ("_buffer", "_clip", "_rect")

    def __init__(self, buffer: Buffer, rect: Rect, *, clip: Rect | None = None) -> None:
        self._buffer = buffer
        self._rect = rect
        visible = rect.intersect(buffer.bounds)
        self._clip = visible if clip is None else visible.intersect(clip)

    @property
    def width(self) -> int:
        return self._rect.width

    @property
    def height(self) -> int:
        return self._rect.height

    @property
    def rect(self) -> Rect:
        """The view's rectangle in buffer coordinates (may extend beyond the buffer)."""
        return self._rect

    def set_cell(self, row: int, col: int, cell: Cell) -> None:
        r, c = self._rect.y + row, self._rect.x + col
        if self._clip.contains(c, r):
            self._buffer.set_cell(r, c, cell)

    def get_cell(self, row: int, col: int) -> Cell:
        r, c = self._rect.y + row, self._rect.x + col
        if not self._clip.contains(c, r):
            raise IndexError(f"cell ({row}, {col}) is outside the {self.width}x{self.height} view")
        return self._buffer.get_cell(r, c)

    def write_text(self, row: int, col: int, text: str, style: Style = DEFAULT_STYLE) -> int:
        return self._buffer.write_text(
            self._rect.y + row, self._rect.x + col, text, style, clip=self._clip
        )

    def fill(self, rect: Rect, cell: Cell | None = None) -> None:
        target = rect.translate(self._rect.x, self._rect.y).intersect(self._clip)
        self._buffer.fill(target, cell)

    def clear(self, cell: Cell | None = None) -> None:
        self._buffer.fill(self._clip, cell)

    def view(self, rect: Rect) -> BufferView:
        return BufferView(self._buffer, rect.translate(self._rect.x, self._rect.y), clip=self._clip)


class Canvas(Protocol):
    """What widgets render into: satisfied by both :class:`Buffer` and :class:`BufferView`."""

    @property
    def width(self) -> int: ...

    @property
    def height(self) -> int: ...

    def set_cell(self, row: int, col: int, cell: Cell) -> None: ...

    def get_cell(self, row: int, col: int) -> Cell: ...

    def write_text(self, row: int, col: int, text: str, style: Style = ...) -> int: ...

    def fill(self, rect: Rect, cell: Cell | None = None) -> None: ...

    def clear(self, cell: Cell | None = None) -> None: ...

    def view(self, rect: Rect) -> BufferView: ...
