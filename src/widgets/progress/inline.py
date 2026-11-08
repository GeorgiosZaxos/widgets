"""Inline progress manager (FR-PROG-010..012, 015..017). Layer L3.

The manager owns an INLINE :class:`TerminalSession` (no alternate screen, output stays in
scrollback) and a *region* of N lines at the bottom of the output. Indicators render into
buffers (D-02); the manager converts those buffers to terminal lines and repaints the region by
moving the cursor to its top, clearing downward and printing the new lines.

Threading (FR-PROG-017, documented): ``update`` / ``write`` / ``refresh`` may be called from any
thread. Rendering happens on the caller's thread under the manager lock and the session's output
gate, and never more often than ``mininterval`` (unless forced). No background thread exists.

Non-TTY streams (FR-PROG-016): no cursor control; plain text lines at most every
``nontty_interval`` seconds (default 10) and a final line when an indicator is removed.
"""

from __future__ import annotations

import sys
import threading
from collections.abc import Mapping
from typing import TextIO

from widgets.base_elements.color_manager import ColorMode, style_to_ansi
from widgets.base_elements.effects import Clock, MonotonicClock
from widgets.base_elements.lifecycle import LifecycleState
from widgets.base_elements.widget_types import Rect
from widgets.errors import LifecycleError
from widgets.progress.indicators import ProgressIndicator
from widgets.render.buffer import Buffer
from widgets.render.diff import diff_buffers
from widgets.render.sanitize import sanitize_text
from widgets.terminal import ansi
from widgets.terminal.session import TerminalMode, TerminalSession

_GAP = 2  # blank columns between side-by-side indicators


class ProgressManager:
    """Maintains several concurrent indicators in one inline region."""

    def __init__(
        self,
        stream: TextIO | None = None,
        *,
        session: TerminalSession | None = None,
        mininterval: float = 0.1,
        nontty_interval: float = 10.0,
        ncols: int | None = None,
        clock: Clock | None = None,
        env: Mapping[str, str] | None = None,
        ascii_only: bool = False,
    ) -> None:
        if mininterval < 0 or nontty_interval < 0:
            raise ValueError("intervals must be >= 0")
        if ncols is not None and ncols < 1:
            raise ValueError("ncols must be >= 1")
        self._lock = threading.RLock()
        self._clock: Clock = MonotonicClock() if clock is None else clock
        self._owns_session = session is None
        self._session = session or TerminalSession(
            TerminalMode.INLINE,
            stream=sys.stderr if stream is None else stream,  # FR-PROG-015: stderr by default
            env=env,
            ascii_only=ascii_only,
        )
        self.mininterval = mininterval
        self.nontty_interval = nontty_interval
        self._ncols = ncols
        self._items: list[ProgressIndicator] = []
        self._retained: list[ProgressIndicator] = []
        self._parked_at: float | None = None
        self._parked_height = 0
        self.join_window = 0.5
        """Seconds after the last active indicator finished during which a new grouped indicator
        still joins the finished ones in the same rows (afterwards they stay as plain output)."""
        self._height = 0
        self._cursor_hidden = False
        self._closed = False
        self._last_paint = float("-inf")
        self._last_plain = float("-inf")
        self._last_tick: float | None = None
        self._started = False

    # -- properties ------------------------------------------------------------------------

    @property
    def session(self) -> TerminalSession:
        return self._session

    @property
    def closed(self) -> bool:
        return self._closed

    @property
    def indicators(self) -> tuple[ProgressIndicator, ...]:
        with self._lock:
            return tuple(i for i in self._items if i not in self._retained)

    @property
    def retained(self) -> int:
        """Finished grouped indicators (e.g. vertical bars) that stay in the region."""
        return len(self._retained)

    @property
    def height(self) -> int:
        """Number of terminal lines the region currently occupies."""
        return self._height

    @property
    def interactive(self) -> bool:
        """True when cursor control is available (otherwise plain-text mode)."""
        self._ensure_started()
        return self._session.capabilities.ansi

    @property
    def ascii_only(self) -> bool:
        self._ensure_started()
        return self._session.use_ascii

    # -- indicators ---------------------------------------------------------------------------

    def add(
        self, indicator: ProgressIndicator, position: int | None = None, *, leave: bool = True
    ) -> ProgressIndicator:
        """Add ``indicator`` below the existing ones (or at row ``position``)."""
        with self._lock:
            if self._closed:
                raise LifecycleError("progress manager is closed")
            if indicator in self._items:
                raise ValueError("indicator is already managed")
            self._ensure_started()
            self._unpark(rejoin=indicator.group is not None)
            indicator.leave = leave
            if indicator.state is LifecycleState.CREATED:
                indicator.mount()
            if indicator.state in (LifecycleState.MOUNTED, LifecycleState.STOPPED):
                indicator.start()  # a cleared indicator that is shown again is still running
            if position is None or position >= len(self._items):
                self._items.append(indicator)
            else:
                self._items.insert(max(0, position), indicator)  # others shift down: no overlap
            self.refresh(force=True)
            return indicator

    def remove(
        self, indicator: ProgressIndicator, leave: bool | None = None, *, close: bool = True
    ) -> None:
        """Remove ``indicator``; with ``leave`` its final line stays in scrollback.

        ``close=False`` keeps the indicator alive so it can be added again (used by ``clear``).
        """
        with self._lock:
            if indicator not in self._items:
                return
            keep = indicator.leave if leave is None else leave
            interactive = self.interactive
            if keep and interactive and close and indicator.group is not None:
                indicator.stop()  # finished, but it keeps its columns in the shared rows
                self._retained.append(indicator)
                self._paint([])
                return
            pre = self._lines_of(indicator) if (keep and interactive) else []
            final_plain = indicator.plain_text() if (keep and not interactive) else None
            self._items.remove(indicator)
            if close:
                indicator.close()
            if interactive:
                self._paint(pre)
            elif final_plain is not None:
                self._session.output.write_flush(final_plain + "\n")

    @property
    def parked(self) -> bool:
        """True while only finished (retained) indicators remain and the cursor is below them."""
        return self._parked_at is not None

    def park(self) -> None:
        """No indicator is active: end the region with a newline so ordinary output is safe."""
        with self._lock:
            if self._closed or self._parked_at is not None or not self._retained:
                return
            if not self.interactive:
                return
            self._parked_at = self._clock.now()
            self._parked_height = self._height
            self._session.output.write_flush(("\n" if self._height else "") + ansi.SHOW_CURSOR)
            self._cursor_hidden = False
            self._height = 0

    def _unpark(self, rejoin: bool) -> None:
        """Leave the parked state: re-open the region for a new grouped indicator or forget it."""
        if self._parked_at is None:
            return
        recent = self._clock.now() - self._parked_at <= self.join_window
        self._parked_at = None
        if rejoin and recent and self._parked_height:
            self._height = self._parked_height  # cursor is just below the region
            self._session.output.write_flush(f"{ansi.CSI}1A")
        else:
            for item in self._retained:
                self._items.remove(item)
                item.close()
            self._retained.clear()
        self._parked_height = 0

    def write(self, message: str) -> None:
        """Print ``message`` above the region and redraw the region (FR-PROG-011)."""
        with self._lock:
            text = sanitize_text(str(message), newlines="keep")
            lines = text.split("\n") if text else [""]
            if self.interactive and not self._closed and self._parked_at is None:
                self._paint(lines)
            else:
                self._session.output.write_flush(text + "\n")

    @property
    def clock(self) -> Clock:
        return self._clock

    def refresh(self, force: bool = False) -> bool:
        """Repaint if due (``force`` bypasses the TTY rate limit). True when output was produced."""
        with self._lock:
            if self._closed:
                return False
            if self._parked_at is not None:
                return False
            now = self._clock.now()
            dt = 0.0 if self._last_tick is None else max(0.0, now - self._last_tick)
            self._last_tick = now
            for item in self._items:
                item.tick(dt)
            if self.interactive:
                if not force and now - self._last_paint < self.mininterval:
                    return False
                self._last_paint = now
                self._paint([])
                return True
            if not self._items or now - self._last_plain < self.nontty_interval:
                return False
            self._last_plain = now
            self._session.output.write_flush("".join(i.plain_text() + "\n" for i in self._items))
            return True

    # -- lifecycle -------------------------------------------------------------------------------

    def close(self) -> None:
        """Finish: leave completed lines, put the cursor below the region, show the cursor."""
        with self._lock:
            if self._closed:
                return
            self._closed = True
            try:
                if self._started and self._parked_at is not None:
                    self._parked_at = None  # already printed; the cursor is below the region
                elif self._started and self._session.capabilities.ansi:
                    for item in [i for i in self._items if not i.leave]:
                        self._items.remove(item)
                    self._retained.clear()
                    self._paint([])
                    out = ansi.SHOW_CURSOR if self._cursor_hidden else ""
                    self._session.output.write_flush(("\n" if self._height else "") + out)
                    self._cursor_hidden = False
                elif self._started:
                    for item in self._items:
                        if item.leave:
                            self._session.output.write_flush(item.plain_text() + "\n")
            finally:
                for item in list(self._items):
                    item.close()
                self._items.clear()
                self._height = 0
                if self._owns_session:
                    self._session.close()

    def __enter__(self) -> ProgressManager:
        return self

    def __exit__(self, *exc_info: object) -> None:
        self.close()

    # -- internals ---------------------------------------------------------------------------------

    def _ensure_started(self) -> None:
        if self._started:
            return
        if not self._session.started:
            self._session.start()
        self._started = True
        self._session.cleanup.register(self.close)  # interruption / signal / atexit safety

    def _columns(self) -> int:
        columns = self._session.get_size()[0]
        return max(1, min(columns, self._ncols) if self._ncols else columns)

    def _lines_of(self, indicator: ProgressIndicator) -> list[str]:
        """The terminal lines of one indicator, at most ``columns - 1`` wide (no autowrap)."""
        width = max(1, self._columns() - 1)
        if indicator.expand:
            indicator.resize(width, indicator.height)
        indicator.move(0, 0)
        buffer = Buffer(width, indicator.height, policy=self._session.width_policy)
        indicator.draw(buffer)
        mode = self._session.capabilities.color_mode
        return [self._row_to_ansi(buffer, row, mode) for row in range(buffer.height)]

    @staticmethod
    def _row_to_ansi(buffer: Buffer, row: int, mode: ColorMode) -> str:
        ops = diff_buffers(None, buffer, Rect(0, row, buffer.width, 1))
        while ops and ops[-1].style.is_default and not ops[-1].text.strip():
            ops.pop()
        if ops and ops[-1].style.is_default:
            last = ops[-1]
            ops[-1] = type(last)(last.row, last.col, last.text.rstrip(), last.style)
        body = "".join(
            ("" if op.style.is_default else style_to_ansi(op.style, mode))
            + op.text
            + ("" if op.style.is_default else ansi.SGR_RESET)
            for op in ops
        )
        return body

    def _region_lines(self) -> list[str]:
        """Region lines; consecutive grouped indicators share rows (side by side)."""
        lines: list[str] = []
        run: list[ProgressIndicator] = []
        for item in self._items:
            if run and item.group != run[0].group:
                lines.extend(self._band_lines(run))
                run = []
            if item.group is None:
                lines.extend(self._lines_of(item))
            else:
                run.append(item)
        if run:
            lines.extend(self._band_lines(run))
        return lines

    def _band_lines(self, run: list[ProgressIndicator]) -> list[str]:
        """Lay ``run`` out left to right, wrapping into further bands when the line is full."""
        limit = max(1, self._columns() - 1)
        bands: list[list[ProgressIndicator]] = [[]]
        used = 0
        for item in run:
            need = item.width + (_GAP if bands[-1] else 0)
            if bands[-1] and used + need > limit:
                bands.append([])
                used, need = 0, item.width
            bands[-1].append(item)
            used += need
        lines: list[str] = []
        mode = self._session.capabilities.color_mode
        for band in bands:
            width = min(limit, sum(i.width for i in band) + _GAP * (len(band) - 1))
            height = max(i.height for i in band)
            buffer = Buffer(max(1, width), height, policy=self._session.width_policy)
            x = 0
            for item in band:
                item.move(x, 0)
                item.draw(buffer)
                x += item.width + _GAP
            lines.extend(self._row_to_ansi(buffer, row, mode) for row in range(buffer.height))
        return lines

    def _paint(self, pre_lines: list[str]) -> None:
        """Print ``pre_lines`` permanently, then (re)draw the region below them."""
        out: list[str] = []
        if not self._cursor_hidden:
            out.append(ansi.HIDE_CURSOR)
            self._cursor_hidden = True
        if self._height:
            out.append("\r")
            if self._height > 1:
                out.append(f"{ansi.CSI}{self._height - 1}A")
        out.append(f"{ansi.CSI}0J")
        out.extend(line + "\n" for line in pre_lines)
        lines = self._region_lines()
        out.append("\n".join(lines))
        self._height = len(lines)
        self._session.output.write_flush("".join(out))
