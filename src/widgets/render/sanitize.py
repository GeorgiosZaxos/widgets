"""Neutralising untrusted text before it reaches the terminal (FR-SAN-001..004, D-07). Layer L1.

Complete escape sequences (CSI, OSC, DCS/SOS/PM/APC and two-byte escapes) are removed. Any
remaining control character (C0, DEL, C1) is replaced by U+FFFD so that following characters can
never be interpreted as part of a sequence. Bidirectional override/isolate characters are removed.
"""

from __future__ import annotations

import re
from typing import Literal

REPLACEMENT = "�"

_ESCAPE_SEQUENCES = re.compile(
    r"\x1b\[[0-?]*[ -/]*[@-~]"  # CSI ... final byte
    r"|\x1b\][^\x07\x1b]*(?:\x07|\x1b\\)?"  # OSC, BEL or ST terminated (or unterminated)
    r"|\x1b[PX^_].*?(?:\x1b\\|\Z)"  # DCS / SOS / PM / APC
    r"|\x1b[ -/]*[0-~]",  # other escapes (ESC c, ESC 7, ESC ( B ...)
    re.DOTALL,
)

_BIDI_CONTROLS = {*range(0x202A, 0x202F), *range(0x2066, 0x206A)}
_CONTROL_CODES = (*range(0, 32), 127, *range(0x80, 0xA0))


def _table(newlines: str) -> dict[int, str | None]:
    table: dict[int, str | None] = dict.fromkeys(_CONTROL_CODES, REPLACEMENT)
    if newlines == "space":
        for code in (9, 10, 13):
            table[code] = " "
    elif newlines == "keep":
        table[10] = "\n"
    for code in _BIDI_CONTROLS:
        table[code] = None
    return table


_TABLES = {mode: _table(mode) for mode in ("replace", "space", "keep")}


def sanitize_text(text: str, *, newlines: Literal["replace", "space", "keep"] = "replace") -> str:
    """Return ``text`` with escape sequences and control characters neutralised.

    ``newlines``: ``"replace"`` (default) turns line breaks and tabs into U+FFFD, ``"space"`` into
    a space, ``"keep"`` preserves ``\\n`` (``\\r\\n`` and lone ``\\r`` are normalised to ``\\n``).
    """
    if newlines not in _TABLES:
        raise ValueError(f"newlines must be one of {sorted(_TABLES)}, got {newlines!r}")
    if text.isprintable():  # fast path: no controls, no bidi controls, no escapes
        return text
    if "\x1b" in text:
        text = _ESCAPE_SEQUENCES.sub("", text)
    if newlines == "keep":
        text = text.replace("\r\n", "\n").replace("\r", "\n")
    return text.translate(_TABLES[newlines])


def sanitize_title(text: str, *, max_length: int = 256) -> str:
    """Make ``text`` safe for the terminal window title (FR-SAN-003)."""
    return sanitize_text(text, newlines="space").strip()[:max_length]


def expand_tabs(text: str, tabsize: int = 8) -> str:
    """Explicit tab expansion helper (``write_text`` never expands tabs, FR-BUF-011)."""
    if tabsize < 1:
        raise ValueError("tabsize must be >= 1")
    return text.expandtabs(tabsize)
