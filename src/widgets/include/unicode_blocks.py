"""Deprecated legacy path ``widgets.include.unicode_blocks``; use ``widgets.assets``."""

import warnings

from widgets.assets.symbols import lookup, search

warnings.warn(
    "widgets.include.unicode_blocks is deprecated; use widgets.assets",
    DeprecationWarning,
    stacklevel=2,
)

__all__ = ["lookup", "search"]
