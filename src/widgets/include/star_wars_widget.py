"""Deprecated compatibility shim for the legacy module name; use ``widgets.display.space``.

The legacy name contains a third-party trademark and is kept only so old imports keep working
(decision D-16). No third-party text, music or art is bundled.
"""

import warnings

from widgets.display.space import SpaceCrawlWidget

warnings.warn(
    "widgets.include.star_wars_widget is deprecated; use widgets.display.space.SpaceCrawlWidget",
    DeprecationWarning,
    stacklevel=2,
)
StarWarsWidget = SpaceCrawlWidget

__all__ = ["SpaceCrawlWidget", "StarWarsWidget"]
