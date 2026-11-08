"""Deprecated legacy path ``widgets.include.unicode_arrows``; use ``widgets.assets``."""

import warnings

from widgets.assets.symbols import lookup as get_arrow
from widgets.assets.symbols import search as search_arrows

warnings.warn(
    "widgets.include.unicode_arrows is deprecated; use widgets.assets",
    DeprecationWarning,
    stacklevel=2,
)

__all__ = ["get_arrow", "search_arrows"]
