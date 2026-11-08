"""Deprecated legacy path ``widgets.include.border_types``; use ``widgets.assets``."""

import warnings

from widgets.assets.borders import get_border_style as get_border
from widgets.assets.borders import list_border_styles as list_borders

warnings.warn(
    "widgets.include.border_types is deprecated; use widgets.assets",
    DeprecationWarning,
    stacklevel=2,
)

__all__ = ["get_border", "list_borders"]
