"""Progress-bar glyph styles (FR-ASSET-001, FR-ASSET-009). Layer L1.

Every style has a Unicode glyph set and an ASCII fallback. ``partials`` are sub-cell glyphs in
increasing fill order (e.g. one eighth ... seven eighths); a full cell uses ``fill``.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class BarStyle:
    name: str
    fill: str
    empty: str
    partials: tuple[str, ...] = ()
    left: str = ""
    right: str = ""
    ascii_fill: str = "#"
    ascii_empty: str = "-"
    ascii_partials: tuple[str, ...] = ()
    ascii_left: str = ""
    ascii_right: str = ""

    def glyphs(self, ascii_only: bool) -> tuple[str, str, tuple[str, ...], str, str]:
        """``(fill, empty, partials, left, right)`` for the requested character set."""
        if ascii_only:
            return (
                self.ascii_fill,
                self.ascii_empty,
                self.ascii_partials,
                self.ascii_left,
                self.ascii_right,
            )
        return (self.fill, self.empty, self.partials, self.left, self.right)


_EIGHTHS_H = ("▏", "▎", "▍", "▌", "▋", "▊", "▉")
_EIGHTHS_V = ("▁", "▂", "▃", "▄", "▅", "▆", "▇")

_HORIZONTAL = (
    BarStyle("smooth", "█", " ", _EIGHTHS_H, "|", "|", "#", "-", (), "|", "|"),
    BarStyle("block", "█", "░", (), "|", "|", "#", "-", (), "|", "|"),
    BarStyle("shade", "▓", "░", (), "[", "]", "#", ".", (), "[", "]"),
    BarStyle("line", "━", "─", (), "", "", "=", "-"),
    BarStyle("dots", "●", "○", (), "", "", "*", "."),
    BarStyle("squares", "■", "□", (), "[", "]", "#", "-", (), "[", "]"),
    BarStyle("classic", "=", ".", (), "[", "]", "=", ".", (), "[", "]"),
    BarStyle("ascii", "#", "-", (), "[", "]", "#", "-", (), "[", "]"),
    BarStyle("arrow", "▶", "▷", (), "", "", ">", "-"),
)

_VERTICAL = (
    BarStyle("eighths", "█", " ", _EIGHTHS_V, "", "", "#", " "),
    BarStyle("block", "█", "░", (), "", "", "#", "."),
    BarStyle("shade", "▓", "░", (), "", "", "#", "."),
    BarStyle("line", "┃", "│", (), "", "", "|", ":"),
    BarStyle("dots", "●", "○", (), "", "", "*", "."),
    BarStyle("squares", "■", "□", (), "", "", "#", "."),
    BarStyle("solid", "█", " ", (), "", "", "#", " "),
    BarStyle("ascii", "#", ".", (), "", "", "#", "."),
)

_STYLES = {
    "horizontal": {style.name: style for style in _HORIZONTAL},
    "vertical": {style.name: style for style in _VERTICAL},
}


def _install_bundled() -> None:
    import widgets.assets._bar_data as _bar_data

    for orientation, data in (
        ("horizontal", _bar_data.HORIZONTAL),
        ("vertical", _bar_data.VERTICAL),
    ):
        catalog = _STYLES[orientation]
        for name, (fill, empty) in data.items():
            catalog.setdefault(name, BarStyle(name, fill, empty))


_install_bundled()


def list_bar_styles(orientation: str = "horizontal") -> list[str]:
    """Names of the bar styles for ``orientation`` (``"horizontal"`` or ``"vertical"``)."""
    return sorted(_catalog(orientation))


def get_bar_style(name: str, orientation: str = "horizontal") -> BarStyle:
    """The style called ``name``; unknown names raise ``KeyError`` listing the valid ones."""
    catalog = _catalog(orientation)
    try:
        return catalog[name]
    except KeyError:
        raise KeyError(
            f"unknown {orientation} bar style {name!r}; available: {sorted(catalog)}"
        ) from None


def _catalog(orientation: str) -> dict[str, BarStyle]:
    try:
        return _STYLES[orientation]
    except KeyError:
        raise ValueError("orientation must be 'horizontal' or 'vertical'") from None
