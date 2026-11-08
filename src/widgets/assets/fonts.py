"""Large-character fonts (FR-ASSET-004, FR-ASSET-005). Layer L1.

Unsupported characters are rendered with the ``?`` glyph (or blank space if the font has none).
Fonts are uniform in height; glyph rows are padded to the glyph width.
Provenance and licence: see ``LICENSES.md`` (FR-ASSET-010).
"""

from __future__ import annotations

from dataclasses import dataclass
from functools import cache

PLACEHOLDER = "?"


@dataclass(frozen=True, slots=True)
class Font:
    name: str
    height: int
    glyphs: dict[str, tuple[str, ...]]

    def glyph(self, ch: str) -> tuple[str, ...]:
        found = self.glyphs.get(ch) or self.glyphs.get(PLACEHOLDER)
        if found is None:
            return ("",) * self.height
        return found


def validate_font(font: Font) -> None:
    """Raise ``ValueError`` unless every glyph has exactly ``font.height`` rows of equal width."""
    for ch, rows in font.glyphs.items():
        if len(rows) != font.height:
            raise ValueError(
                f"glyph {ch!r} of font {font.name!r} has {len(rows)} rows, not {font.height}"
            )
        if len({len(r) for r in rows}) > 1:
            raise ValueError(f"glyph {ch!r} of font {font.name!r} has rows of unequal width")


def _build(name: str, data: dict[str, list[str]]) -> Font:
    glyphs: dict[str, tuple[str, ...]] = {}
    for ch, rows in data.items():
        width = max((len(r) for r in rows), default=0)
        glyphs[ch] = tuple(r.ljust(width) for r in rows)
    height = len(next(iter(glyphs.values())))
    font = Font(name, height, glyphs)
    validate_font(font)
    return font


@cache
def _horizontal() -> dict[str, Font]:
    import widgets.assets._font_data as _font_data

    return {n: _build(n, d) for n, d in _font_data.FONTS.items()}


@cache
def _vertical() -> dict[str, Font]:
    import widgets.assets._font_data as _font_data

    return {n: _build(n, d) for n, d in _font_data.VERTICAL_FONTS.items()}


def list_fonts() -> list[str]:
    """Return the names of all registered large-text fonts."""
    return sorted(_horizontal())


def list_vertical_fonts() -> list[str]:
    """Return the names of all registered vertical-text fonts."""
    return sorted(_vertical())


def get_font(name: str) -> Font:
    """Return the font called ``name``; raises ``KeyError`` for an unknown name."""
    try:
        return _horizontal()[name]
    except KeyError:
        raise KeyError(f"unknown font {name!r}; available: {sorted(_horizontal())}") from None


def get_vertical_font(name: str) -> Font:
    """Return the vertical font called ``name``; raises ``KeyError`` for an unknown name."""
    try:
        return _vertical()[name]
    except KeyError:
        raise KeyError(
            f"unknown vertical font {name!r}; available: {sorted(_vertical())}"
        ) from None


def font_height(name: str) -> int:
    """Return the height in rows of the font called ``name``."""
    return get_font(name).height


def render_text(text: str, font: Font | str, *, spacing: int = 1) -> list[str]:
    """Render single-line ``text`` as ``font.height`` rows."""
    f = get_font(font) if isinstance(font, str) else font
    rows = [""] * f.height
    gap = " " * max(0, spacing)
    for index, ch in enumerate(text):
        glyph = f.glyph(ch)
        for r in range(f.height):
            rows[r] += glyph[r] + (gap if index < len(text) - 1 else "")
    return rows


def render_vertical(text: str, font: Font | str, *, spacing: int = 0) -> list[str]:
    """Render ``text`` top-to-bottom, one glyph block per character, stacked vertically."""
    f = get_vertical_font(font) if isinstance(font, str) else font
    out: list[str] = []
    for index, ch in enumerate(text):
        out.extend(f.glyph(ch))
        if index < len(text) - 1:
            out.extend([""] * max(0, spacing))
    return out
