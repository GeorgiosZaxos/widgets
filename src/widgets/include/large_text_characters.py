"""Deprecated legacy path ``widgets.include.large_text_characters``; use ``widgets.assets``."""

import warnings

from widgets.assets.fonts import font_height as glyph_height
from widgets.assets.fonts import get_font, list_fonts
from widgets.assets.fonts import render_text as render_large_text

warnings.warn(
    "widgets.include.large_text_characters is deprecated; use widgets.assets",
    DeprecationWarning,
    stacklevel=2,
)

__all__ = ["get_font", "glyph_height", "list_fonts", "render_large_text"]
