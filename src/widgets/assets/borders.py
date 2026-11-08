"""Named border styles with ASCII fallbacks (FR-ASSET-002, FR-ASSET-009). Layer L1."""

from __future__ import annotations

from dataclasses import dataclass

import widgets.assets._border_data as _extra


@dataclass(frozen=True, slots=True)
class BorderStyle:
    """Box-drawing characters: corners (``tl tr bl br``), ``h`` horizontal, ``v`` vertical."""

    name: str
    tl: str
    tr: str
    bl: str
    br: str
    h: str
    v: str
    decorative: bool = False

    def chars(self, ascii_only: bool = False) -> tuple[str, str, str, str, str, str]:
        """``(tl, tr, bl, br, h, v)``; with ``ascii_only`` every non-ASCII glyph is replaced."""
        raw = (self.tl, self.tr, self.bl, self.br, self.h, self.v)
        if not ascii_only:
            return raw
        corner, horizontal, vertical = "+", "-", "|"
        out = []
        for index, ch in enumerate(raw):
            if ord(ch) < 128:
                out.append(ch)
            else:
                out.append(corner if index < 4 else horizontal if index == 4 else vertical)
        return (out[0], out[1], out[2], out[3], out[4], out[5])


def _box(name: str, c: str, *, decorative: bool = False) -> BorderStyle:
    return BorderStyle(name, c[0], c[1], c[2], c[3], c[4], c[5], decorative)


_STYLES: dict[str, BorderStyle] = {
    s.name: s
    for s in (
        _box("single", "┌┐└┘─│"),
        _box("double", "╔╗╚╝═║"),
        _box("rounded", "╭╮╰╯─│"),
        _box("heavy", "┏┓┗┛━┃"),
        _box("ascii", "++++-|"),
        _box("double-single", "╓╖╙╜═║"),
        _box("single-double", "╒╕╘╛═│"),
        _box("corners", "⌜⌝⌞⌟  "),
        _box("thick-blocks", "▛▜▙▟▀▌"),
        _box("arrows", "↘↙↗↖→↓"),
        _box("diamond", "◈◈◈◈─│"),
        _box("plus", "++++++", decorative=True),
        _box("hash", "######", decorative=True),
        _box("equals", "======", decorative=True),
        _box("tilde", "~~~~~~", decorative=True),
        _box("dots", "······", decorative=True),
        _box("block", "██████", decorative=True),
        _box("shade-light", "░░░░░░", decorative=True),
        _box("shade-medium", "▒▒▒▒▒▒", decorative=True),
        _box("shade-dark", "▓▓▓▓▓▓", decorative=True),
        _box("hearts", "♥♥♥♥♥♥", decorative=True),
        _box("diamonds", "◆◆◆◆◆◆", decorative=True),
    )
}
_STYLES.update(
    {n: _box(n, c, decorative=True) for n, c in _extra.BORDERS.items() if n not in _STYLES}
)
_ALIASES = {"bold": "heavy", "thick": "thick-blocks", "double_heavy": "double-single"}


def list_border_styles() -> list[str]:
    """Return the names of all registered border styles."""
    return sorted(_STYLES)


def get_border_style(name: str) -> BorderStyle:
    """The style called ``name`` (aliases accepted); unknown names raise ``KeyError``."""
    key = _ALIASES.get(name, name.replace("_", "-") if name not in _STYLES else name)
    try:
        return _STYLES[key]
    except KeyError:
        raise KeyError(f"unknown border style {name!r}; available: {sorted(_STYLES)}") from None
