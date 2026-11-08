"""Deprecated legacy path ``widgets.include.spinners``; use ``widgets.assets``."""

import warnings

from widgets.assets.spinners import get_spinner, list_spinners, spinner_frames

warnings.warn(
    "widgets.include.spinners is deprecated; use widgets.assets", DeprecationWarning, stacklevel=2
)

__all__ = ["get_spinner", "list_spinners", "spinner_frames"]
