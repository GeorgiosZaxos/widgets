"""``vtqdm``: a tqdm-compatible API drawn as a *vertical* bar. Layer L3.

``from widgets import vtqdm as tqdm`` is a drop-in replacement for ``from tqdm import tqdm``;
only the picture differs: a column that fills upwards with the usual statistics on its right.
Extra keyword: ``height`` (rows of the column, default 8).
"""

from __future__ import annotations

from typing import Any

from widgets.assets.bars import BarStyle
from widgets.assets.spinners import get_spinner
from widgets.base_elements.color_manager import Gradient
from widgets.base_elements.widget_types import Style
from widgets.progress import meter
from widgets.progress.indicators import (
    EMPTY_STYLE,
    FILL_STYLE,
    ProgressIndicator,
    VerticalBar,
    spinner_glyph,
)
from widgets.progress.state import ProgressState
from widgets.progress.tqdm import tqdm
from widgets.render.buffer import Canvas

_TEXT = Style()
COLUMN_WIDTH = 2
STAT_WIDTH = 16
CELL_WIDTH = COLUMN_WIDTH + 1 + STAT_WIDTH
_STATS = "{desc}{percentage:3.0f}% {n_fmt}/{total_fmt} [{elapsed}<{remaining}, {rate_fmt}{postfix}]"
_STATS_UNKNOWN = "{desc}{n_fmt}{unit} [{elapsed}, {rate_fmt}{postfix}]"


class VerticalTqdmBar(ProgressIndicator):
    """A :class:`VerticalBar` column with the tqdm statistics line beside it."""

    expand = False
    group = "vertical"
    """Consecutive vertical bars share the same terminal rows (laid out side by side)."""

    def __init__(
        self,
        state: ProgressState,
        width: int | None,
        *,
        height: int = 8,
        unit: str = "it",
        unit_scale: bool = False,
        unit_divisor: float = 1000,
        bar_format: str | None = None,
        ascii_only: bool = False,
        style: str | BarStyle = "eighths",
        fill_style: Style | None = None,
        empty_style: Style | None = None,
        gradient: Gradient | None = None,
        spinner: str | None = None,
    ) -> None:
        if height < 2:
            raise ValueError("height must be >= 2")
        self.compact = bar_format is None
        default = CELL_WIDTH if bar_format is None else 40
        super().__init__(state, default if width is None else width, height, ascii_only=ascii_only)
        self.column = VerticalBar(
            state,
            height,
            style=style,
            ascii_only=ascii_only,
            gradient=gradient,
            fill_style=fill_style or FILL_STYLE,
            empty_style=empty_style or EMPTY_STYLE,
        )
        if spinner is not None:
            get_spinner(spinner)
        self.spinner = spinner
        self._spin = 0.0
        self.column.resize(COLUMN_WIDTH, height)
        self.unit, self.unit_scale, self.unit_divisor = unit, unit_scale, unit_divisor
        self.bar_format = bar_format

    def resize(self, width: int, height: int) -> None:
        super().resize(width, height)
        self.column.resize(COLUMN_WIDTH, height)

    def update(self, dt: float) -> None:
        self.column.update(dt)
        self._spin = (self._spin + 10.0 * dt) % 1_000_000.0

    def stats(self) -> str:
        """The text shown beside the column."""
        st = self.progress
        desc = f"{st.description}: " if st.description else ""
        post = st.postfix
        text = meter.format_meter(
            st.n,
            st.total,
            st.elapsed,
            prefix="",
            unit=self.unit,
            unit_scale=self.unit_scale,
            unit_divisor=self.unit_divisor,
            rate=st.speed,
            postfix=post or None,
            bar_format=self.bar_format or (_STATS if st.total else _STATS_UNKNOWN),
        )
        return text.replace("{desc}", desc) if "{desc}" in text else (desc + text)

    def plain_text(self) -> str:
        return self.stats()

    def stat_lines(self) -> list[str]:
        """The statistics as short lines (one per row) shown to the right of the column."""
        st = self.progress
        known = bool(st.total)
        templates = (
            ["{percentage:3.0f}%", "{n_fmt}/{total_fmt}", "{elapsed}<{remaining}", "{rate_fmt}"]
            if known
            else ["{n_fmt}{unit}", "{elapsed}", "{rate_fmt}"]
        )
        lines = [st.description] if st.description else []
        if self.spinner is not None:
            done = st.fraction is not None and st.fraction >= 1
            glyph = spinner_glyph(self.spinner, self._spin, self.ascii_only, done)
            lines = [f"{glyph} {lines[0]}" if lines else glyph]
        for template in templates:
            lines.append(
                meter.format_meter(
                    st.n,
                    st.total,
                    st.elapsed,
                    prefix="",
                    unit=self.unit,
                    unit_scale=self.unit_scale,
                    unit_divisor=self.unit_divisor,
                    rate=st.speed,
                    bar_format=template,
                )
            )
        if st.postfix:
            lines.append(str(st.postfix).lstrip(", "))
        return lines

    def render(self, canvas: Canvas) -> None:
        self.column.render(canvas)
        if not self.compact:
            text = self.stats()[: max(0, canvas.width - COLUMN_WIDTH)]
            canvas.write_text(self.height - 1, COLUMN_WIDTH, text, _TEXT)
            return
        x = COLUMN_WIDTH + 1
        for row, line in enumerate(self.stat_lines()[: self.height]):
            canvas.write_text(row, x, line[:STAT_WIDTH], _TEXT)


class vtqdm(tqdm):
    """tqdm-compatible progress iterator drawn as a vertical bar (``height`` rows)."""

    def __init__(self, *args: Any, height: int = 8, **kwargs: Any) -> None:
        self._height = height
        super().__init__(*args, **kwargs)

    def _make_bar(self, ncols: int | None, **options: Any) -> ProgressIndicator:
        return VerticalTqdmBar(self.state, ncols, height=self._height, **options)


def vtrange(*args: int, **kwargs: Any) -> vtqdm:
    """``vtqdm(range(*args), **kwargs)`` - the vertical twin of :func:`trange`."""
    return vtqdm(range(*args), **kwargs)
