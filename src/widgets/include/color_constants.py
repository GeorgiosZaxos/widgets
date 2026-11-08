"""Deprecated legacy path ``widgets.include.color_constants``; use ``widgets.assets``."""

import warnings

from widgets.assets.colors import (
    get_gradient,
    get_palette,
    hex_to_rgb,
    list_colors,
    list_gradients,
    list_palettes,
    rgb_to_hex,
)

warnings.warn(
    "widgets.include.color_constants is deprecated; use widgets.assets",
    DeprecationWarning,
    stacklevel=2,
)

__all__ = [
    "get_gradient",
    "get_palette",
    "hex_to_rgb",
    "list_colors",
    "list_gradients",
    "list_palettes",
    "rgb_to_hex",
]
