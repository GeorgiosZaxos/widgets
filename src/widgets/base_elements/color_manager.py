"""Color service: parsing, conversion, capability selection, palettes, gradients, SGR.

Implements FR-COLOR-001..011. Layer L1 (depends only on ``widget_types``).
"""

from __future__ import annotations

import enum
import functools
import json
import math
import os
import re
import sys
import threading
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass

from widgets.base_elements.widget_types import RGB, ColorSpec, Style

RESET = "\x1b[0m"


class ColorMode(enum.IntEnum):
    """Terminal color depth, ordered from least to most capable (FR-COLOR-003)."""

    NONE = 0
    ANSI16 = 1
    ANSI256 = 2
    TRUECOLOR = 3


# ---------------------------------------------------------------------------
# Palettes of the xterm color model
# ---------------------------------------------------------------------------

ANSI16_RGB: tuple[RGB, ...] = (
    RGB(0, 0, 0),
    RGB(205, 0, 0),
    RGB(0, 205, 0),
    RGB(205, 205, 0),
    RGB(0, 0, 238),
    RGB(205, 0, 205),
    RGB(0, 205, 205),
    RGB(229, 229, 229),
    RGB(127, 127, 127),
    RGB(255, 0, 0),
    RGB(0, 255, 0),
    RGB(255, 255, 0),
    RGB(92, 92, 255),
    RGB(255, 0, 255),
    RGB(0, 255, 255),
    RGB(255, 255, 255),
)

_CUBE_LEVELS = (0, 95, 135, 175, 215, 255)


def _build_256() -> tuple[RGB, ...]:
    palette = list(ANSI16_RGB)
    for r in _CUBE_LEVELS:
        for g in _CUBE_LEVELS:
            for b in _CUBE_LEVELS:
                palette.append(RGB(r, g, b))
    for i in range(24):
        level = 8 + 10 * i
        palette.append(RGB(level, level, level))
    return tuple(palette)


ANSI256_RGB: tuple[RGB, ...] = _build_256()

_NAMED: dict[str, RGB] = {
    "black": RGB(0, 0, 0),
    "white": RGB(255, 255, 255),
    "red": RGB(255, 0, 0),
    "green": RGB(0, 255, 0),
    "blue": RGB(0, 0, 255),
    "yellow": RGB(255, 255, 0),
    "magenta": RGB(255, 0, 255),
    "cyan": RGB(0, 255, 255),
    "gray": RGB(128, 128, 128),
    "orange": RGB(255, 165, 0),
    "pink": RGB(255, 192, 203),
    "purple": RGB(128, 0, 128),
    "brown": RGB(165, 42, 42),
    "teal": RGB(0, 128, 128),
    "navy": RGB(0, 0, 128),
    "gold": RGB(255, 215, 0),
}

NAMED_COLORS: Mapping[str, RGB] = _NAMED

_HEX = re.compile(r"^#(?:[0-9a-fA-F]{3}|[0-9a-fA-F]{6})$")


# ---------------------------------------------------------------------------
# Parsing and conversion
# ---------------------------------------------------------------------------


def hex_to_rgb(value: str) -> RGB:
    """Parse ``#RGB`` or ``#RRGGBB``."""
    text = value.strip() if isinstance(value, str) else value
    if not isinstance(text, str) or not _HEX.match(text):
        raise ValueError(f"invalid hex color {value!r}; expected #RGB or #RRGGBB")
    digits = text[1:]
    if len(digits) == 3:
        digits = "".join(ch * 2 for ch in digits)
    return RGB(int(digits[0:2], 16), int(digits[2:4], 16), int(digits[4:6], 16))


def rgb_to_hex(rgb: RGB) -> str:
    """Return ``rgb`` as a ``#rrggbb`` string."""
    return rgb.to_hex()


def parse_color(value: object) -> RGB:
    """Accept named colors, ``#RGB``/``#RRGGBB``, 3-sequences of 0..255 ints and :class:`RGB`.

    Raises ``ValueError`` naming the offending value for anything else (FR-COLOR-001).
    """
    if isinstance(value, RGB):
        return value
    if isinstance(value, str):
        text = value.strip()
        if text.startswith("#"):
            return hex_to_rgb(text)
        key = text.lower().replace("-", "_").replace(" ", "_")
        if key in NAMED_COLORS:
            return NAMED_COLORS[key]
        raise ValueError(f"unknown color name {value!r}")
    if isinstance(value, tuple | list) and len(value) == 3:
        try:
            return RGB(*value)
        except (TypeError, ValueError) as exc:
            raise ValueError(f"invalid RGB color {value!r}: {exc}") from exc
    raise ValueError(f"unsupported color value {value!r}")


def index_to_rgb(index: int) -> RGB:
    """RGB value of a 0..255 xterm palette index."""
    if isinstance(index, bool) or not isinstance(index, int) or not 0 <= index <= 255:
        raise ValueError(f"palette index must be an int in 0..255, got {index!r}")
    return ANSI256_RGB[index]


def _nearest(rgb: RGB, indices: range) -> int:
    best = indices.start
    best_distance = math.inf
    for index in indices:  # ascending, strict '<' => ties resolve to the lower index
        candidate = ANSI256_RGB[index]
        distance = (
            (rgb.r - candidate.r) ** 2 + (rgb.g - candidate.g) ** 2 + (rgb.b - candidate.b) ** 2
        )
        if distance < best_distance:
            best, best_distance = index, distance
    return best


@functools.lru_cache(maxsize=4096)
def rgb_to_ansi256(rgb: RGB) -> int:
    """Nearest xterm 256-palette index in 16..255 (sRGB Euclidean distance, FR-COLOR-010)."""
    return _nearest(rgb, range(16, 256))


@functools.lru_cache(maxsize=4096)
def rgb_to_ansi16(rgb: RGB) -> int:
    """Nearest of the 16 standard colors (sRGB Euclidean distance, ties -> lower index)."""
    return _nearest(rgb, range(0, 16))


# ---------------------------------------------------------------------------
# Capability detection
# ---------------------------------------------------------------------------


def detect_color_mode(
    env: Mapping[str, str] | None = None,
    *,
    isatty: bool = True,
    override: ColorMode | None = None,
    platform: str | None = None,
    windows_build: int | None = None,
) -> ColorMode:
    """Select the color mode (FR-COLOR-003).

    Order: explicit ``override``; ``NO_COLOR`` (non-empty) -> NONE; non-TTY output -> NONE unless
    ``FORCE_COLOR`` is set to a non-zero value (then at least ANSI16); ``TERM=dumb`` -> NONE;
    ``COLORTERM`` truecolor/24bit -> TRUECOLOR; ``TERM`` containing ``256color`` -> ANSI256;
    on Windows (where ``TERM`` is normally unset) Windows Terminal (``WT_SESSION``), ConEmu,
    VS Code and consoles from Windows 10 build 14931 on -> TRUECOLOR; otherwise ANSI16.
    ``platform`` / ``windows_build`` exist for tests and default to the running system.
    """
    if override is not None:
        return override
    environment = os.environ if env is None else env
    if environment.get("NO_COLOR"):
        return ColorMode.NONE
    forced = environment.get("FORCE_COLOR", "") not in ("", "0")
    if not isatty and not forced:
        return ColorMode.NONE
    term = environment.get("TERM", "")
    if term == "dumb" and not forced:
        return ColorMode.NONE
    if environment.get("COLORTERM", "").lower() in ("truecolor", "24bit"):
        return ColorMode.TRUECOLOR
    if "256color" in term:
        return ColorMode.ANSI256
    if _windows_supports_truecolor(environment, platform, windows_build):
        return ColorMode.TRUECOLOR
    return ColorMode.ANSI16


def _windows_build() -> int:
    if sys.platform != "win32":
        return 0
    return int(sys.getwindowsversion().build)


def _windows_supports_truecolor(
    environment: Mapping[str, str], platform: str | None, build: int | None
) -> bool:
    if (sys.platform if platform is None else platform) != "win32":
        return False
    if (
        environment.get("WT_SESSION")
        or environment.get("ConEmuANSI", "").upper() == "ON"
        or environment.get("TERM_PROGRAM")
    ):
        return True
    return (
        _windows_build() if build is None else build
    ) >= 14931  # first Windows 10 release with 24-bit color in the console


# ---------------------------------------------------------------------------
# SGR generation
# ---------------------------------------------------------------------------

_ATTRIBUTES: tuple[tuple[str, int], ...] = (
    ("bold", 1),
    ("dim", 2),
    ("italic", 3),
    ("underline", 4),
    ("blink", 5),
    ("reverse", 7),
    ("strike", 9),
)


def _ansi16_code(index: int, background: bool) -> int:
    if index < 8:
        return (40 if background else 30) + index
    return (100 if background else 90) + (index - 8)


def color_params(color: ColorSpec, mode: ColorMode, *, background: bool = False) -> str:
    """SGR parameter string for one color (``""`` for no color / mode NONE)."""
    if color is None or mode is ColorMode.NONE:
        return ""
    base = 48 if background else 38
    if isinstance(color, RGB):
        if mode is ColorMode.TRUECOLOR:
            return f"{base};2;{color.r};{color.g};{color.b}"
        if mode is ColorMode.ANSI256:
            return f"{base};5;{rgb_to_ansi256(color)}"
        return str(_ansi16_code(rgb_to_ansi16(color), background))
    if isinstance(color, bool) or not isinstance(color, int) or not 0 <= color <= 255:
        raise ValueError(f"palette index must be an int in 0..255, got {color!r}")
    if mode is ColorMode.ANSI16:
        index = color if color < 16 else rgb_to_ansi16(index_to_rgb(color))
        return str(_ansi16_code(index, background))
    return f"{base};5;{color}"


def style_to_ansi(style: Style, mode: ColorMode) -> str:
    """Complete escape sequence selecting ``style`` (it resets first, so it never leaks)."""
    params: list[str] = [str(code) for name, code in _ATTRIBUTES if getattr(style, name)]
    for color, background in ((style.fg, False), (style.bg, True)):
        text = color_params(color, mode, background=background)
        if text:
            params.append(text)
    if not params:
        return RESET
    return f"\x1b[0;{';'.join(params)}m"


def apply_style(text: str, style: Style, mode: ColorMode) -> str:
    """Wrap ``text`` in the style's escape sequence and a trailing reset (FR-COLOR-007)."""
    opening = style_to_ansi(style, mode)
    if opening == RESET:
        return text
    return f"{opening}{text}{RESET}"


# ---------------------------------------------------------------------------
# Gradients
# ---------------------------------------------------------------------------


def _round_half_up(value: float) -> int:
    return math.floor(value + 0.5)


@dataclass(frozen=True, slots=True)
class Gradient:
    """Piecewise-linear sRGB gradient with ascending stop positions in ``[0, 1]``."""

    stops: tuple[tuple[float, RGB], ...]

    def __post_init__(self) -> None:
        if len(self.stops) < 2:
            raise ValueError("a gradient needs at least 2 stops")
        previous = -math.inf
        for position, color in self.stops:
            if not isinstance(color, RGB):
                raise ValueError(f"gradient stop color must be RGB, got {color!r}")
            if not 0.0 <= position <= 1.0 or math.isnan(position):
                raise ValueError(f"gradient stop position must be in [0, 1], got {position!r}")
            if position < previous:
                raise ValueError("gradient stop positions must be ascending")
            previous = position

    @classmethod
    def from_colors(cls, colors: Iterable[object]) -> Gradient:
        parsed = [parse_color(color) for color in colors]
        if len(parsed) < 2:
            raise ValueError("a gradient needs at least 2 colors")
        last = len(parsed) - 1
        return cls(tuple((i / last, color) for i, color in enumerate(parsed)))

    def at(self, t: float) -> RGB:
        """Color at ``t`` (clamped to the stop range); endpoints are exact (FR-COLOR-011)."""
        if math.isnan(t):
            raise ValueError("gradient position must not be NaN")
        first_pos, first_color = self.stops[0]
        last_pos, last_color = self.stops[-1]
        if t <= first_pos:
            return first_color
        if t >= last_pos:
            return last_color
        for (p0, c0), (p1, c1) in zip(self.stops, self.stops[1:], strict=False):
            if p0 <= t <= p1:
                if p1 == p0:
                    return c1
                f = (t - p0) / (p1 - p0)
                return RGB(
                    _round_half_up(c0.r + (c1.r - c0.r) * f),
                    _round_half_up(c0.g + (c1.g - c0.g) * f),
                    _round_half_up(c0.b + (c1.b - c0.b) * f),
                )
        return last_color  # pragma: no cover - unreachable

    def sample(self, count: int) -> list[RGB]:
        if count < 1:
            raise ValueError("count must be >= 1")
        if count == 1:
            return [self.at(0.0)]
        return [self.at(i / (count - 1)) for i in range(count)]


# ---------------------------------------------------------------------------
# Registries (FR-COLOR-005/006, D-09: single owner of color data)
# ---------------------------------------------------------------------------

_lock = threading.RLock()
_palettes: dict[str, tuple[RGB, ...]] = {}
_gradients: dict[str, Gradient] = {}


def _key(name: str) -> str:
    if not isinstance(name, str) or not name.strip():
        raise ValueError("name must be a non-empty string")
    return name.strip().lower()


def register_palette(name: str, colors: Iterable[object], *, replace: bool = False) -> None:
    """Register a named palette; an existing name needs ``replace=True``, otherwise ``ValueError``."""
    key = _key(name)
    parsed = tuple(parse_color(color) for color in colors)
    if not parsed:
        raise ValueError("a palette needs at least one color")
    with _lock:
        if key in _palettes and not replace:
            raise ValueError(f"palette {key!r} already exists (use replace=True)")
        _palettes[key] = parsed


def get_palette(name: str) -> tuple[RGB, ...]:
    """Return the colours of the named palette; raises ``KeyError`` when unknown."""
    with _lock:
        try:
            return _palettes[_key(name)]
        except KeyError:
            raise KeyError(f"unknown palette {name!r}; available: {sorted(_palettes)}") from None


def list_palettes() -> list[str]:
    """Return the names of all registered palettes."""
    with _lock:
        return sorted(_palettes)


def register_gradient(
    name: str,
    gradient: Gradient | Sequence[object],
    *,
    replace: bool = False,
) -> None:
    """Register a :class:`Gradient`, a sequence of colors, or ``(position, color)`` pairs."""
    key = _key(name)
    if isinstance(gradient, Gradient):
        value = gradient
    else:
        items = list(gradient)
        # (position, color) pairs have length 2; every color form has length 3 or is not a tuple
        pairs = [i for i in items if isinstance(i, tuple) and len(i) == 2]
        if items and len(pairs) == len(items):
            stops: list[tuple[float, RGB]] = []
            for position, color in pairs:
                if isinstance(position, bool) or not isinstance(position, int | float):
                    raise ValueError(f"gradient stop position must be a number, got {position!r}")
                stops.append((float(position), parse_color(color)))
            value = Gradient(tuple(stops))
        else:
            value = Gradient.from_colors(items)
    with _lock:
        if key in _gradients and not replace:
            raise ValueError(f"gradient {key!r} already exists (use replace=True)")
        _gradients[key] = value


def get_gradient(name: str) -> Gradient:
    """Return the named gradient; raises ``KeyError`` when unknown."""
    with _lock:
        try:
            return _gradients[_key(name)]
        except KeyError:
            raise KeyError(f"unknown gradient {name!r}; available: {sorted(_gradients)}") from None


def list_gradients() -> list[str]:
    """Return the names of all registered gradients."""
    with _lock:
        return sorted(_gradients)


def _install_defaults() -> None:
    register_palette("ansi16", ANSI16_RGB)
    register_palette("pastel", ["#FFB3BA", "#FFDFBA", "#FFFFBA", "#BAFFC9", "#BAE1FF"])
    register_palette("neon", ["#FF073A", "#39FF14", "#FFFF33", "#04D9FF", "#FF10F0"])
    register_gradient("rainbow", ["#ff0000", "#ffff00", "#00ff00", "#00ffff", "#0000ff", "#ff00ff"])
    register_gradient("fire", ["#330000", "#ff0000", "#ff9900", "#ffff00", "#ffffff"])
    register_gradient("ocean", ["#001f3f", "#0074d9", "#7fdbff"])
    register_gradient("sunset", ["#ff512f", "#dd2476", "#4a00e0"])
    register_gradient("grayscale", ["#000000", "#ffffff"])


_install_defaults()


def register_color(name: str, value: object, *, replace: bool = False) -> None:
    """Register a named colour usable anywhere a colour is accepted."""
    key = _key(name).replace("-", "_").replace(" ", "_")
    rgb = parse_color(value)
    with _lock:
        if key in _NAMED and not replace:
            raise ValueError(f"color {key!r} already exists (use replace=True)")
        _NAMED[key] = rgb


def list_colors() -> list[str]:
    """Return the names of all named colours."""
    with _lock:
        return sorted(_NAMED)


def _install_bundled() -> None:
    """Install the bundled colour catalogue (never overrides the defaults above)."""
    import widgets.base_elements.color_data as color_data

    for name, hex_value in color_data.COLORS.items():
        _NAMED.setdefault(name.replace("-", "_"), hex_to_rgb(hex_value))
    for name, colors in color_data.PALETTES.items():
        if name not in _palettes:
            register_palette(name, colors)
    for name, colors in color_data.GRADIENTS.items():
        if name not in _gradients and len(colors) >= 2:
            register_gradient(name, colors)


_install_bundled()


# ---------------------------------------------------------------------------
# Export (FR-COLOR-008)
# ---------------------------------------------------------------------------

EXPORT_FORMAT_VERSION = 1


def palette_to_json(name: str) -> str:
    """Return the named palette as a JSON array of hex strings."""
    colors = [color.to_hex() for color in get_palette(name)]
    payload = {
        "version": EXPORT_FORMAT_VERSION,
        "kind": "palette",
        "name": _key(name),
        "colors": colors,
    }
    return json.dumps(payload, indent=2)


def gradient_to_json(name: str) -> str:
    """Return the named gradient as JSON (stops and colours)."""
    gradient = get_gradient(name)
    payload = {
        "version": EXPORT_FORMAT_VERSION,
        "kind": "gradient",
        "name": _key(name),
        "stops": [{"position": pos, "color": color.to_hex()} for pos, color in gradient.stops],
    }
    return json.dumps(payload, indent=2)


def palette_to_css(name: str) -> str:
    """Return the named palette as CSS custom properties."""
    key = _key(name)
    lines = [
        f"  --palette-{key}-{i}: {color.to_hex()};" for i, color in enumerate(get_palette(key))
    ]
    return ":root {\n" + "\n".join(lines) + "\n}\n"


def gradient_to_css(name: str, direction: str = "to right") -> str:
    """Return the named gradient as a CSS ``linear-gradient(...)`` in ``direction``."""
    stops = ", ".join(
        f"{color.to_hex()} {round(pos * 100, 2):g}%" for pos, color in get_gradient(name).stops
    )
    return f"linear-gradient({direction}, {stops})"
