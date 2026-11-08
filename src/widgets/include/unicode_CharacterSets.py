"""Deprecated legacy path ``widgets.include.unicode_CharacterSets``; use ``widgets.assets``."""

import warnings

from widgets.assets.symbols import find_block, search_blocks
from widgets.assets.symbols import list_unicode_blocks as list_blocks

warnings.warn(
    "widgets.include.unicode_CharacterSets is deprecated; use widgets.assets",
    DeprecationWarning,
    stacklevel=2,
)

__all__ = ["find_block", "list_blocks", "search_blocks"]
