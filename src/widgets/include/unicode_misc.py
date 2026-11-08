"""Deprecated legacy path ``widgets.include.unicode_misc``; use ``widgets.assets``."""

import warnings

from widgets.assets.symbols import lookup as get_misc
from widgets.assets.symbols import search as search_misc

warnings.warn(
    "widgets.include.unicode_misc is deprecated; use widgets.assets",
    DeprecationWarning,
    stacklevel=2,
)

__all__ = ["get_misc", "search_misc"]
