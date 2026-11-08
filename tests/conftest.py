"""Shared fixtures and helpers for the test-suite."""

from __future__ import annotations

import io
from collections.abc import Callable, Sequence

import pytest

from widgets.base_elements.color_manager import ColorMode
from widgets.base_elements.widget_types import CONTINUATION, Cell, RenderOp, Style
from widgets.render.buffer import Buffer
from widgets.render.screen_renderer import ScreenRenderer
from widgets.render.width import DEFAULT_WIDTH_POLICY, WidthPolicy
from widgets.terminal.session import OutputGate, TerminalMode, TerminalSession

XTERM_ENV = {"TERM": "xterm-256color", "COLORTERM": "truecolor"}


class FakeTTY(io.StringIO):
    """A text stream that claims to be a UTF-8 terminal."""

    encoding = "utf-8"  # type: ignore[assignment]

    def isatty(self) -> bool:
        return True


@pytest.fixture
def tty() -> FakeTTY:
    return FakeTTY()


@pytest.fixture
def make_session() -> Callable[..., TerminalSession]:
    sessions: list[TerminalSession] = []

    def factory(
        mode: TerminalMode = TerminalMode.FULLSCREEN,
        *,
        stream: io.StringIO | None = None,
        **kwargs: object,
    ) -> TerminalSession:
        options: dict[str, object] = {
            "env": dict(XTERM_ENV),
            "handle_signals": False,
            "use_atexit": False,
        }
        options.update(kwargs)
        session = TerminalSession(mode, stream=stream or FakeTTY(), **options)  # type: ignore[arg-type]
        sessions.append(session)
        return session

    yield factory
    for session in sessions:
        session.close()


def make_renderer(
    stream: io.StringIO | None = None,
    *,
    color_mode: ColorMode = ColorMode.TRUECOLOR,
    ansi: bool = True,
    autowrap_disabled: bool = True,
    policy: WidthPolicy = DEFAULT_WIDTH_POLICY,
) -> tuple[ScreenRenderer, io.StringIO]:
    out = io.StringIO() if stream is None else stream
    renderer = ScreenRenderer(
        OutputGate(out),
        color_mode=color_mode,
        ansi_enabled=ansi,
        autowrap_disabled=autowrap_disabled,
        policy=policy,
    )
    return renderer, out


Grid = list[list[tuple[str, Style]]]


def buffer_grid(buffer: Buffer) -> Grid:
    """A buffer as rows of ``(glyph, style)`` tuples (continuation cells are ``""``)."""
    return [[(c.glyph, c.style) for c in buffer.row(r)] for r in range(buffer.height)]


def apply_ops(
    grid: Grid, ops: Sequence[RenderOp], policy: WidthPolicy = DEFAULT_WIDTH_POLICY
) -> Grid:
    """Simulate a terminal applying render operations to a screen state."""
    screen = [list(row) for row in grid]
    for op in ops:
        col = op.col
        last_base: int | None = None
        for ch in op.text:
            width = policy.char_width(ch)
            if width == 0:
                if last_base is not None:
                    glyph, style = screen[op.row][last_base]
                    screen[op.row][last_base] = (glyph + ch, style)
                continue
            if 0 <= col < len(screen[op.row]):
                screen[op.row][col] = (ch, op.style)
                last_base = col
            if width == 2 and 0 <= col + 1 < len(screen[op.row]):
                screen[op.row][col + 1] = (CONTINUATION, op.style)
            col += width
    return screen


def text_rows(buffer: Buffer) -> list[str]:
    return buffer.to_lines()


def cell(glyph: str = " ", **style: object) -> Cell:
    return Cell(glyph, Style(**style))  # type: ignore[arg-type]
