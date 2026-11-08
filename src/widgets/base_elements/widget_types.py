"""Shared immutable value types (FR-TYPE-001..004). Layer L0."""

from __future__ import annotations

import dataclasses
from collections.abc import Iterator
from dataclasses import dataclass
from typing import TypeAlias

WidgetId: TypeAlias = str

CONTINUATION = ""
"""Glyph stored in the second cell of a double-width character (FR-BUF-009)."""


def _require_int(name: str, value: object) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise TypeError(f"{name} must be int, got {type(value).__name__}")
    return value


def _require_non_negative(name: str, value: object) -> int:
    number = _require_int(name, value)
    if number < 0:
        raise ValueError(f"{name} must be >= 0, got {number}")
    return number


@dataclass(frozen=True, slots=True)
class Size:
    """Width and height in terminal cells."""

    width: int
    height: int

    def __post_init__(self) -> None:
        _require_non_negative("width", self.width)
        _require_non_negative("height", self.height)


@dataclass(frozen=True, slots=True)
class Point:
    """A cell coordinate; ``x`` is the column, ``y`` the row."""

    x: int
    y: int

    def __post_init__(self) -> None:
        _require_int("x", self.x)
        _require_int("y", self.y)

    def offset(self, dx: int, dy: int) -> Point:
        return Point(self.x + dx, self.y + dy)


@dataclass(frozen=True, slots=True)
class Rect:
    """Axis-aligned rectangle. ``width``/``height`` may be zero (empty); ``x``/``y`` may be negative."""

    x: int
    y: int
    width: int
    height: int

    def __post_init__(self) -> None:
        _require_int("x", self.x)
        _require_int("y", self.y)
        _require_non_negative("width", self.width)
        _require_non_negative("height", self.height)

    @property
    def right(self) -> int:
        """Exclusive right edge."""
        return self.x + self.width

    @property
    def bottom(self) -> int:
        """Exclusive bottom edge."""
        return self.y + self.height

    @property
    def is_empty(self) -> bool:
        return self.width == 0 or self.height == 0

    def contains(self, x: int, y: int) -> bool:
        """Whether the cell at column ``x``, row ``y`` lies inside the rectangle."""
        return self.x <= x < self.right and self.y <= y < self.bottom

    def intersect(self, other: Rect) -> Rect:
        """The overlap of both rectangles (empty, with zero size, when disjoint)."""
        left = max(self.x, other.x)
        top = max(self.y, other.y)
        right = min(self.right, other.right)
        bottom = min(self.bottom, other.bottom)
        return Rect(left, top, max(0, right - left), max(0, bottom - top))

    def clip(self, bounds: Rect) -> Rect:
        """Clip this rectangle to ``bounds`` (alias of :meth:`intersect`)."""
        return self.intersect(bounds)

    def translate(self, dx: int, dy: int) -> Rect:
        return Rect(self.x + dx, self.y + dy, self.width, self.height)


@dataclass(frozen=True, slots=True)
class RGB:
    """24-bit color; each channel is an ``int`` in 0..255."""

    r: int
    g: int
    b: int

    def __post_init__(self) -> None:
        for name in ("r", "g", "b"):
            value = _require_int(name, getattr(self, name))
            if not 0 <= value <= 255:
                raise ValueError(f"RGB channel {name} must be in 0..255, got {value}")

    def __iter__(self) -> Iterator[int]:
        yield self.r
        yield self.g
        yield self.b

    def to_hex(self) -> str:
        return f"#{self.r:02x}{self.g:02x}{self.b:02x}"


ColorSpec: TypeAlias = int | RGB | None
"""A style color: ``None`` (terminal default), a 0..255 palette index, or an :class:`RGB`."""


@dataclass(frozen=True, slots=True)
class Style:
    """Immutable, hashable text style (FR-TYPE-002).

    ``fg`` / ``bg`` are ``None`` (terminal default), a palette index 0..255 or an :class:`RGB`.
    """

    fg: ColorSpec = None
    bg: ColorSpec = None
    bold: bool = False
    dim: bool = False
    italic: bool = False
    underline: bool = False
    blink: bool = False
    reverse: bool = False
    strike: bool = False

    def __post_init__(self) -> None:
        for name in ("fg", "bg"):
            value = getattr(self, name)
            if value is None or isinstance(value, RGB):
                continue
            if isinstance(value, bool) or not isinstance(value, int):
                raise TypeError(f"{name} must be None, int or RGB, got {type(value).__name__}")
            if not 0 <= value <= 255:
                raise ValueError(f"{name} palette index must be in 0..255, got {value}")

    @property
    def is_default(self) -> bool:
        return self == DEFAULT_STYLE

    def replace(self, **changes: object) -> Style:
        return dataclasses.replace(self, **changes)  # type: ignore[arg-type]


DEFAULT_STYLE = Style()


@dataclass(frozen=True, slots=True)
class Cell:
    """One terminal cell: a glyph (possibly with combining marks) and a style."""

    glyph: str = " "
    style: Style = DEFAULT_STYLE


BLANK_CELL = Cell()


@dataclass(frozen=True, slots=True)
class RenderOp:
    """Write ``text`` with ``style`` starting at zero-based ``row`` / ``col`` (FR-TYPE-003)."""

    row: int
    col: int
    text: str
    style: Style = DEFAULT_STYLE
