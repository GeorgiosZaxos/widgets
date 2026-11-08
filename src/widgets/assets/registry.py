"""Asset group registry (FR-ASSET-008). Layer L1."""

from __future__ import annotations

_GROUPS = ("bars", "borders", "colors", "fonts", "spinners", "symbols")


def list_asset_groups() -> list[str]:
    """Names of the asset groups; each has a ``list_*`` function in its module (FR-ASSET-008)."""
    return list(_GROUPS)


def list_assets(group: str) -> list[str]:
    """Names of every asset in ``group``."""
    if group == "bars":
        import widgets.assets.bars as bars

        return [f"{o}:{n}" for o in ("horizontal", "vertical") for n in bars.list_bar_styles(o)]
    if group == "borders":
        import widgets.assets.borders as borders

        return borders.list_border_styles()
    if group == "colors":
        import widgets.assets.colors as colors

        return colors.list_colors()
    if group == "fonts":
        import widgets.assets.fonts as fonts

        return fonts.list_fonts() + ["vertical:" + n for n in fonts.list_vertical_fonts()]
    if group == "spinners":
        import widgets.assets.spinners as spinners

        return spinners.list_spinners()
    if group == "symbols":
        import widgets.assets.symbols as symbols

        return [s.name for s in symbols.list_symbols()]
    raise KeyError(f"unknown asset group {group!r}; available: {list(_GROUPS)}")
