"""ANSI/VT control sequences (FR-RENDER-012, FR-TERM-003). Layer L1.

Pure functions and constants; nothing here touches a stream.
"""

from __future__ import annotations

from widgets.render.sanitize import sanitize_title

ESC = "\x1b"
CSI = "\x1b["

SGR_RESET = f"{CSI}0m"

HIDE_CURSOR = f"{CSI}?25l"
SHOW_CURSOR = f"{CSI}?25h"
SAVE_CURSOR = f"{ESC}7"
RESTORE_CURSOR = f"{ESC}8"

ENTER_ALT_SCREEN = f"{CSI}?1049h"
EXIT_ALT_SCREEN = f"{CSI}?1049l"

CLEAR_SCREEN = f"{CSI}2J"
CLEAR_LINE = f"{CSI}2K"
CLEAR_TO_END_OF_SCREEN = f"{CSI}0J"
HOME = f"{CSI}H"

AUTOWRAP_OFF = f"{CSI}?7l"
AUTOWRAP_ON = f"{CSI}?7h"

BRACKETED_PASTE_ON = f"{CSI}?2004h"
BRACKETED_PASTE_OFF = f"{CSI}?2004l"

SYNC_UPDATE_BEGIN = f"{CSI}?2026h"
SYNC_UPDATE_END = f"{CSI}?2026l"

PUSH_TITLE = f"{CSI}22;0t"
POP_TITLE = f"{CSI}23;0t"


def cursor_to(row: int, col: int) -> str:
    """Absolute cursor position, zero-based ``row`` / ``col``."""
    return f"{CSI}{row + 1};{col + 1}H"


def cursor_up(n: int = 1) -> str:
    """Return the escape sequence that moves the cursor up ``n`` rows."""
    return f"{CSI}{n}A" if n > 0 else ""


def cursor_down(n: int = 1) -> str:
    """Return the escape sequence that moves the cursor down ``n`` rows."""
    return f"{CSI}{n}B" if n > 0 else ""


def cursor_forward(n: int = 1) -> str:
    """Return the escape sequence that moves the cursor right ``n`` columns."""
    return f"{CSI}{n}C" if n > 0 else ""


def cursor_back(n: int = 1) -> str:
    """Return the escape sequence that moves the cursor left ``n`` columns."""
    return f"{CSI}{n}D" if n > 0 else ""


def cursor_column(col: int) -> str:
    """Move to zero-based column on the current row."""
    return f"{CSI}{col + 1}G"


def set_title(title: str) -> str:
    """Window-title sequence; control characters are stripped first (FR-SAN-003)."""
    return f"{ESC}]2;{sanitize_title(title)}\x07"
