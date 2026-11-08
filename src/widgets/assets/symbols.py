"""Symbol catalogs (arrows, blocks, misc) and Unicode block table (FR-ASSET-007). Layer L1.

Canonical names are the Unicode character names lower-cased with ``-``; legacy labels
(``UP_ARROW``) are accepted as aliases.
"""

from __future__ import annotations

import unicodedata
from collections.abc import Iterator
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class Symbol:
    name: str
    char: str
    group: str

    @property
    def codepoint(self) -> int:
        return ord(self.char)

    @property
    def ascii(self) -> str:
        """ASCII fallback (FR-ASSET-009)."""
        return ascii_fallback(self.char)


_ARROW_FALLBACK = {"UP": "^", "DOWN": "v", "LEFT": "<", "RIGHT": ">"}


def ascii_fallback(ch: str) -> str:
    """Return an ASCII stand-in for ``ch`` (``ch`` itself if it is already ASCII)."""
    if ord(ch) < 128:
        return ch
    name = unicodedata.name(ch, "")
    if "ARROW" in name:
        for word, repl in _ARROW_FALLBACK.items():
            if word in name:
                return repl
        return ">"
    folded = unicodedata.normalize("NFKD", ch).encode("ascii", "ignore").decode()
    if folded:
        return folded
    if "SHADE" in name or "BLOCK" in name:
        return "#"
    if "LIGHT" in name or "HEAVY" in name or "BOX DRAWINGS" in name:
        return "|" if "VERTICAL" in name else "-" if "HORIZONTAL" in name else "+"
    return "*"


def _symbols() -> dict[str, Symbol]:
    import widgets.assets._symbol_data as _symbol_data

    return {n: Symbol(n, c, g) for n, c, g in _symbol_data.SYMBOLS}


_CACHE: dict[str, Symbol] = {}


def _catalog() -> dict[str, Symbol]:
    if not _CACHE:
        _CACHE.update(_symbols())
    return _CACHE


def list_symbol_groups() -> list[str]:
    """Return the names of the symbol groups."""
    return sorted({s.group for s in _catalog().values()})


def list_symbols(group: str | None = None) -> list[Symbol]:
    """Return the symbols of ``group``, or of every group when ``group`` is ``None``."""
    items = sorted(_catalog().values(), key=lambda s: (s.group, s.name))
    return [s for s in items if group is None or s.group == group]


def lookup(name: str) -> Symbol:
    """Find a symbol by canonical name or legacy alias; unknown names raise ``KeyError``."""
    import widgets.assets._symbol_data as _symbol_data

    key = name.strip().lower().replace("_", "-").replace(" ", "-")
    catalog = _catalog()
    if key in catalog:
        return catalog[key]
    char = _symbol_data.ALIASES.get(key)
    if char is not None:
        for sym in catalog.values():
            if sym.char == char:
                return sym
    raise KeyError(f"unknown symbol {name!r}; use search() to find names")


def search(query: str, group: str | None = None) -> list[Symbol]:
    """Case-insensitive substring search over canonical names."""
    needle = query.strip().lower().replace("_", "-").replace(" ", "-")
    return [s for s in list_symbols(group) if needle in s.name]


@dataclass(frozen=True, slots=True)
class UnicodeBlock:
    name: str
    start: int
    end: int
    category: str

    def contains(self, codepoint: int) -> bool:
        return self.start <= codepoint <= self.end


def list_unicode_blocks(category: str | None = None) -> list[UnicodeBlock]:
    """Return the Unicode blocks, optionally limited to one ``category``."""
    import widgets.assets._block_data as _block_data

    blocks = [UnicodeBlock(*b) for b in _block_data.BLOCKS]
    return [b for b in blocks if category is None or b.category == category]


def find_block(char_or_codepoint: str | int) -> UnicodeBlock | None:
    """Return the block containing a character or code point, or ``None``."""
    cp = ord(char_or_codepoint) if isinstance(char_or_codepoint, str) else char_or_codepoint
    for block in list_unicode_blocks():
        if block.contains(cp):
            return block
    return None


def search_blocks(query: str) -> list[UnicodeBlock]:
    """Return the blocks whose name contains ``query`` (case-insensitive)."""
    needle = query.lower()
    return [b for b in list_unicode_blocks() if needle in b.name.lower()]


def list_categories() -> list[str]:
    """Names of the block categories (hierarchy level above blocks)."""
    return sorted({b.category for b in list_unicode_blocks()})


def get_block(name: str) -> UnicodeBlock:
    """Return the block called ``name``; raises ``KeyError`` when it does not exist."""
    for block in list_unicode_blocks():
        if block.name.lower() == name.lower().replace(" ", "_"):
            return block
    raise KeyError(f"unknown Unicode block {name!r}")


def iter_block_chars(block: str | UnicodeBlock, *, printable_only: bool = True) -> Iterator[str]:
    """Characters of a block (assigned, and printable unless ``printable_only`` is False)."""
    b = get_block(block) if isinstance(block, str) else block
    for cp in range(b.start, b.end + 1):
        ch = chr(cp)
        if printable_only and (
            not ch.isprintable() or unicodedata.category(ch) in ("Cn", "Co", "Cs")
        ):
            continue
        yield ch


def get_block_chars(block: str | UnicodeBlock, *, printable_only: bool = True) -> list[str]:
    """Return the characters of a block; unprintable ones are skipped when ``printable_only``."""
    return list(iter_block_chars(block, printable_only=printable_only))


def codepoint_info(char_or_codepoint: str | int) -> dict[str, object]:
    """Name, code point, general category, block and category of one character."""
    cp = ord(char_or_codepoint) if isinstance(char_or_codepoint, str) else char_or_codepoint
    ch = chr(cp)
    block = find_block(cp)
    return {
        "char": ch,
        "codepoint": cp,
        "hex": f"U+{cp:04X}",
        "name": unicodedata.name(ch, ""),
        "general_category": unicodedata.category(ch),
        "block": block.name if block else None,
        "category": block.category if block else None,
        "ascii": ascii_fallback(ch),
    }
