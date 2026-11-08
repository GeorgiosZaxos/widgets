"""Applies buffer diffs to the terminal (FR-RENDER-004..008, 012, 013, 015; FR-COLOR-009). Layer L2.

The renderer keeps a copy of the previous frame. ``render`` diffs against it and writes the
resulting operations through the :class:`~widgets.terminal.session.OutputGate` in one write:
cursor positioning, style transition, text; a style reset ends every non-empty frame; output is
flushed once. Identical frames produce no output at all.

Without ANSI support (non-TTY, ``TERM=dumb``) incremental output is meaningless, so frames are
only remembered and :meth:`ScreenRenderer.finish` prints the last frame as plain text lines
(FR-TERM-009).
"""

from __future__ import annotations

from collections.abc import Iterable

from widgets.base_elements.color_manager import ColorMode, style_to_ansi
from widgets.base_elements.widget_types import DEFAULT_STYLE, Rect, RenderOp, Style
from widgets.render.buffer import Buffer
from widgets.render.diff import diff_buffers
from widgets.render.width import DEFAULT_WIDTH_POLICY, WidthPolicy
from widgets.terminal import ansi
from widgets.terminal.session import OutputGate, TerminalSession


class ScreenRenderer:
    """Diff-based renderer for one output gate."""

    def __init__(
        self,
        output: OutputGate,
        *,
        color_mode: ColorMode = ColorMode.TRUECOLOR,
        ansi_enabled: bool = True,
        autowrap_disabled: bool = True,
        policy: WidthPolicy = DEFAULT_WIDTH_POLICY,
        synchronized_output: bool = False,
    ) -> None:
        self._output = output
        self._color_mode = color_mode
        self._ansi = ansi_enabled
        self._autowrap_disabled = autowrap_disabled
        self._policy = policy
        self._sync = synchronized_output
        self._previous: Buffer | None = None
        self._clear_pending = False

    @classmethod
    def from_session(
        cls, session: TerminalSession, *, synchronized_output: bool = False
    ) -> ScreenRenderer:
        caps = session.capabilities
        return cls(
            session.output,
            color_mode=caps.color_mode,
            ansi_enabled=caps.ansi,
            autowrap_disabled=session.autowrap_disabled,
            policy=session.width_policy,
            synchronized_output=synchronized_output,
        )

    # -- state ----------------------------------------------------------------------

    @property
    def color_mode(self) -> ColorMode:
        return self._color_mode

    def invalidate(self, *, clear_screen: bool = False) -> None:
        """Forget the previous frame so the next render is a full repaint (FR-RENDER-004)."""
        self._previous = None
        self._clear_pending = self._clear_pending or clear_screen

    # -- rendering ---------------------------------------------------------------------

    def render(self, buffer: Buffer) -> int:
        """Render the whole buffer (diffed against the previous frame). Returns characters written."""
        if not self._ansi:
            self._previous = buffer.copy()
            return 0
        ops = diff_buffers(self._previous, buffer)
        self._previous = buffer.copy()
        return self._emit(ops, buffer, clear=self._take_clear())

    def render_region(self, buffer: Buffer, region: Rect) -> int:
        """Render only ``region``; the previous-frame cache is updated for that region only (D-03).

        Falls back to a full repaint when no previous frame of the same size exists.
        """
        if not self._ansi:
            self._previous = buffer.copy()
            return 0
        previous = self._previous
        if previous is None or (previous.width, previous.height) != (buffer.width, buffer.height):
            return self.render(buffer)
        ops = diff_buffers(previous, buffer, region)
        previous.copy_region_from(buffer, region)
        return self._emit(ops, buffer, clear=False)

    def finish(self) -> None:
        """End of rendering: reset the style, or print the last frame as plain text."""
        if self._ansi:
            self._output.write_flush(ansi.SGR_RESET)
        elif self._previous is not None:
            lines = [line.rstrip() for line in self._previous.to_lines()]
            while lines and not lines[-1]:
                lines.pop()
            if lines:
                self._output.write_flush("\n".join(lines) + "\n")

    # -- cursor management (FR-RENDER-012) -----------------------------------------------

    def move_cursor(self, row: int, col: int) -> None:
        self._write_if_ansi(ansi.cursor_to(row, col))

    def hide_cursor(self) -> None:
        self._write_if_ansi(ansi.HIDE_CURSOR)

    def show_cursor(self) -> None:
        self._write_if_ansi(ansi.SHOW_CURSOR)

    def save_cursor(self) -> None:
        self._write_if_ansi(ansi.SAVE_CURSOR)

    def restore_cursor(self) -> None:
        self._write_if_ansi(ansi.RESTORE_CURSOR)

    def _write_if_ansi(self, data: str) -> None:
        if self._ansi:
            self._output.write_flush(data)

    # -- internals ----------------------------------------------------------------------

    def _take_clear(self) -> bool:
        clear, self._clear_pending = self._clear_pending, False
        return clear

    def _emit(self, ops: Iterable[RenderOp], buffer: Buffer, *, clear: bool) -> int:
        operations = list(ops)
        if not operations and not clear:
            return 0  # FR-RENDER-005: nothing changed, nothing written
        parts: list[str] = []
        if self._sync:
            parts.append(ansi.SYNC_UPDATE_BEGIN)
        if clear:
            parts.append(ansi.CLEAR_SCREEN)
        current: Style = DEFAULT_STYLE
        cursor: tuple[int, int] | None = None
        for op in operations:
            text = op.text
            if not self._autowrap_disabled:
                text = self._trim_last_cell(op, text, buffer)
                if not text:
                    continue
            if cursor != (op.row, op.col):
                parts.append(ansi.cursor_to(op.row, op.col))
            if op.style != current:
                parts.append(style_to_ansi(op.style, self._color_mode))
                current = op.style
            parts.append(text)
            cursor = (op.row, op.col + self._policy.display_width(text))
        if current != DEFAULT_STYLE:
            parts.append(ansi.SGR_RESET)
        if self._sync:
            parts.append(ansi.SYNC_UPDATE_END)
        payload = "".join(parts)
        self._output.write_flush(payload)
        return len(payload)

    def _trim_last_cell(self, op: RenderOp, text: str, buffer: Buffer) -> str:
        """Drop the glyph in the bottom-right cell when autowrap is on (FR-RENDER-013)."""
        if op.row != buffer.height - 1 or op.col + self._policy.display_width(text) != buffer.width:
            return text
        end = len(text)
        while end > 0 and self._policy.char_width(text[end - 1]) == 0:  # trailing combining marks
            end -= 1
        return text[: max(0, end - 1)]
