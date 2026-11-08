"""Unicode cell-width policy (FR-BUF-009, NFR-ACC-003, decision D-06). Layer L1.

* East Asian Wide / Fullwidth characters occupy 2 cells.
* Combining marks (``Mn``, ``Me``) and format characters (``Cf``) occupy 0 cells and attach
  to the preceding base character.
* East Asian *Ambiguous* characters occupy ``ambiguous`` cells (default 1).
* Grapheme clusters are **not** merged beyond combining marks: each emoji in a ZWJ sequence
  is measured on its own, so such sequences may be wider than the terminal draws them.
* Control characters have width 0 (they never reach the buffer, see ``sanitize``).
"""

from __future__ import annotations

import functools
import unicodedata
from dataclasses import dataclass

from widgets.base_elements.import_helper import optional_import


@functools.cache
def _wcwidth_function() -> object | None:
    module = optional_import("wcwidth", feature="wcwidth cell-width provider")
    return getattr(module, "wcwidth", None) if module is not None else None


@dataclass(frozen=True, slots=True)
class WidthPolicy:
    """How many terminal cells a character occupies.

    ``use_wcwidth=True`` delegates to the optional ``wcwidth`` package when it is installed and
    silently falls back to the built-in rules otherwise.
    """

    ambiguous: int = 1
    use_wcwidth: bool = False

    def __post_init__(self) -> None:
        if self.ambiguous not in (1, 2):
            raise ValueError(f"ambiguous width must be 1 or 2, got {self.ambiguous!r}")

    def char_width(self, ch: str) -> int:
        if len(ch) != 1:
            raise ValueError("char_width expects exactly one character")
        if self.use_wcwidth:
            func = _wcwidth_function()
            if callable(func):
                return max(0, int(func(ch)))
        code = ord(ch)
        if code < 32 or 0x7F <= code < 0xA0:
            return 0
        if code < 0x7F:
            return 1
        if unicodedata.category(ch) in ("Mn", "Me", "Cf"):
            return 0
        east_asian = unicodedata.east_asian_width(ch)
        if east_asian in ("W", "F"):
            return 2
        if east_asian == "A":
            return self.ambiguous
        return 1

    def display_width(self, text: str) -> int:
        """Total cells occupied by ``text`` (0 for an empty string)."""
        if text.isascii() and text.isprintable():
            return len(text)
        return sum(self.char_width(ch) for ch in text)


DEFAULT_WIDTH_POLICY = WidthPolicy()


def display_width(text: str, policy: WidthPolicy = DEFAULT_WIDTH_POLICY) -> int:
    """Cells occupied by ``text`` under ``policy`` (FR-BUF-010)."""
    return policy.display_width(text)
