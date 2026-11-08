"""Frame diffing (FR-RENDER-002..005, 008, 014). Layer L2.

``diff_buffers`` is a pure, deterministic function from (previous frame, current frame) to a list
of :class:`RenderOp`. Adjacent changed cells with equal style are merged into one operation.
A double-width glyph is always emitted as a unit: if either half changed, both are rewritten.
"""

from __future__ import annotations

from widgets.base_elements.widget_types import CONTINUATION, Cell, Rect, RenderOp
from widgets.render.buffer import Buffer


def diff_buffers(prev: Buffer | None, curr: Buffer, region: Rect | None = None) -> list[RenderOp]:
    """Operations that turn the screen showing ``prev`` into ``curr``.

    A full repaint (every cell) is produced when ``prev`` is ``None`` or its size differs
    (FR-RENDER-004). Identical frames yield ``[]`` (FR-RENDER-005). With ``region`` only cells
    inside it (extended to whole wide glyphs) are considered (FR-RENDER-008).
    """
    full = prev is None or (prev.width, prev.height) != (curr.width, curr.height)
    area = curr.bounds if region is None else region.intersect(curr.bounds)
    if area.is_empty:
        return []
    ops: list[RenderOp] = []
    for row in range(area.y, area.bottom):
        current_row = curr.row(row)
        previous_row = None if full or prev is None else prev.row(row)
        if previous_row is not None and previous_row == current_row:
            continue
        start, stop = area.x, area.right
        if start > 0 and current_row[start].glyph == CONTINUATION:
            start -= 1
        if stop < curr.width and current_row[stop].glyph == CONTINUATION:
            stop += 1
        _diff_row(row, current_row, previous_row, start, stop, ops)
    return ops


def _diff_row(
    row: int,
    current: tuple[Cell, ...],
    previous: tuple[Cell, ...] | None,
    start: int,
    stop: int,
    ops: list[RenderOp],
) -> None:
    count = stop - start
    if previous is None:
        changed = [True] * count
    else:
        changed = [previous[start + i] != current[start + i] for i in range(count)]
    # keep wide glyphs whole
    for i in range(count - 1):
        if (
            current[start + i].glyph != CONTINUATION
            and current[start + i + 1].glyph == CONTINUATION
            and (changed[i] or changed[i + 1])
        ):
            changed[i] = changed[i + 1] = True

    i = 0
    while i < count:
        if not changed[i]:
            i += 1
            continue
        column = start + i
        style = current[column].style
        pieces: list[str] = []
        while i < count and changed[i]:
            cell = current[start + i]
            if cell.style != style:
                break
            if cell.glyph == CONTINUATION:  # orphan continuation: keep the columns aligned
                pieces.append(" ")
                i += 1
                continue
            pieces.append(cell.glyph)
            is_wide = start + i + 1 < len(current) and current[start + i + 1].glyph == CONTINUATION
            i += 2 if is_wide else 1
        ops.append(RenderOp(row, column, "".join(pieces), style))
