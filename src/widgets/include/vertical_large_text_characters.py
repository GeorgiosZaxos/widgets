"""Deprecated legacy path ``widgets.include.vertical_large_text_characters``; use ``widgets.assets``."""

import warnings

from widgets.assets.fonts import get_vertical_font, list_vertical_fonts
from widgets.assets.fonts import render_vertical as render_vertical_text

warnings.warn(
    "widgets.include.vertical_large_text_characters is deprecated; use widgets.assets",
    DeprecationWarning,
    stacklevel=2,
)

__all__ = ["get_vertical_font", "list_vertical_fonts", "render_vertical_text"]
