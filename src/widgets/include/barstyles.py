"""Deprecated legacy path ``widgets.include.barstyles``; use ``widgets.assets``."""

import warnings

from widgets.assets.bars import get_bar_style, list_bar_styles

warnings.warn(
    "widgets.include.barstyles is deprecated; use widgets.assets", DeprecationWarning, stacklevel=2
)

__all__ = ["get_bar_style", "list_bar_styles"]
