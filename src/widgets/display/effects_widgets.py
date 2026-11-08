"""Neon, sign and matrix-rain widgets (FR-NEON-*, FR-SIGN-*, FR-MATRIX-*). Layer L3."""

from __future__ import annotations

import math
import random

from widgets.assets.borders import get_border_style
from widgets.assets.fonts import Font, get_font, render_text
from widgets.base_elements.color_manager import Gradient, get_gradient, parse_color
from widgets.base_elements.effects import FlashLimiter, require_fraction, require_positive
from widgets.base_elements.widget_types import DEFAULT_STYLE, RGB, Style, WidgetId
from widgets.display._common import Animated, aligned_col, char_style
from widgets.render.buffer import Canvas
from widgets.render.width import display_width


class Neon(Animated):
    """Text whose colour cycles through a gradient with throttled flicker."""

    def __init__(
        self,
        x: int = 0,
        y: int = 0,
        width: int = 30,
        height: int = 1,
        *,
        text: str = "",
        colors: tuple[str, str] = ("#ff00ff", "#00ffff"),
        gradient: Gradient | None = None,
        palette: str | None = None,
        font: Font | str | None = None,
        outline: bool = False,
        speed: float = 0.5,
        flicker: bool = True,
        fade: bool = False,
        align: str = "left",
        wrap: bool = False,
        reduced_motion: bool | None = None,
        name: WidgetId | None = None,
    ) -> None:
        super().__init__(x, y, width, height, speed=speed, reduced_motion=reduced_motion, name=name)
        aligned_col(0, 1, align)
        self.text, self.align, self.wrap, self.flicker, self.fade = text, align, wrap, flicker, fade
        if palette is not None:
            gradient = get_gradient(palette)
        self.gradient = gradient or Gradient.from_colors([parse_color(c) for c in colors])
        self.font = get_font(font) if isinstance(font, str) else font
        self.outline = outline
        self._limiter = FlashLimiter()
        self._dim = False
        self._last_toggle = -1.0

    def advance(self, dt: float) -> None:
        if self.flicker and not self.reduced_motion and self.t - self._last_toggle >= 0.4:
            want = math.sin(self.t * 37.0) > 0.85
            if want != self._dim and self._limiter.allow(self.t):
                self._dim = want
                self._last_toggle = self.t

    def colour(self) -> RGB:
        if self.reduced_motion:
            return self.gradient.at(0.0)
        return self.gradient.at(0.5 + 0.5 * math.sin(2 * math.pi * self.speed * self.t))

    def render(self, canvas: Canvas) -> None:
        import textwrap

        if self.font is not None:
            lines = render_text(self.text, self.font)
        else:
            lines = textwrap.wrap(self.text, canvas.width) if self.wrap else self.text.split("\n")
        rgb = self.colour()
        if self.fade and not self.reduced_motion:
            k = 0.6 + 0.4 * math.sin(self.t * 2)
            rgb = RGB(int(rgb.r * k), int(rgb.g * k), int(rgb.b * k))
        style = Style(fg=rgb, bold=True, dim=self._dim)
        glow = Style(fg=RGB(rgb.r // 3, rgb.g // 3, rgb.b // 3), dim=True)
        for r, line in enumerate(lines[: canvas.height]):
            col = aligned_col(display_width(line), canvas.width, self.align)
            if self.outline:
                for k, ch in enumerate(line):
                    if ch == " ":
                        continue
                    for dr, dc in ((0, -1), (0, 1), (-1, 0), (1, 0)):
                        rr, cc = r + dr, col + k + dc
                        if 0 <= rr < canvas.height and 0 <= cc < canvas.width:
                            nxt = lines[rr] if 0 <= rr < len(lines) else ""
                            idx = cc - aligned_col(display_width(nxt), canvas.width, self.align)
                            if not (0 <= idx < len(nxt) and nxt[idx] != " "):
                                canvas.write_text(rr, cc, "░", glow)
            canvas.write_text(r, col, line, style)


SIGN_MODES = (
    "static",
    "typewriter",
    "bounce",
    "marquee",
    "wave",
    "fade",
    "neon",
    "gradient-scroll",
)


class Sign(Animated):
    """Large-font text with optional border and animation mode."""

    def __init__(
        self,
        x: int = 0,
        y: int = 0,
        width: int = 40,
        height: int = 9,
        *,
        text: str = "",
        font: Font | str = "original-5",
        mode: str = "static",
        border: str | None = None,
        align: str = "center",
        padding: int = 0,
        style: Style = DEFAULT_STYLE,
        gradient: Gradient | None = None,
        speed: float = 8.0,
        ascii_only: bool = False,
        reduced_motion: bool | None = None,
        name: WidgetId | None = None,
    ) -> None:
        super().__init__(x, y, width, height, speed=speed, reduced_motion=reduced_motion, name=name)
        if mode not in SIGN_MODES:
            raise ValueError(f"mode must be one of {SIGN_MODES}")
        aligned_col(0, 1, align)
        if border is not None:
            get_border_style(border)
        self.text, self.mode, self.border, self.align, self.padding = (
            text,
            mode,
            border,
            align,
            padding,
        )
        self.font = get_font(font) if isinstance(font, str) else font
        self.style, self.gradient, self.ascii_only = style, gradient, ascii_only

    def render(self, canvas: Canvas) -> None:
        w, h = canvas.width, canvas.height
        inset = 1 if self.border else 0
        if self.border:
            tl, tr, bl, br, hc, vc = get_border_style(self.border).chars(self.ascii_only)
            for c in range(w):
                canvas.write_text(0, c, hc, self.style)
                canvas.write_text(h - 1, c, hc, self.style)
            for r in range(h):
                canvas.write_text(r, 0, vc, self.style)
                canvas.write_text(r, w - 1, vc, self.style)
            for r, c, g in ((0, 0, tl), (0, w - 1, tr), (h - 1, 0, bl), (h - 1, w - 1, br)):
                canvas.write_text(r, c, g, self.style)
        rows = render_text(self.text, self.font)
        iw = w - 2 * (inset + self.padding)
        top = inset + self.padding + max(0, (h - 2 * (inset + self.padding) - len(rows)) // 2)
        width_of = max((len(r) for r in rows), default=0)
        left = inset + self.padding + aligned_col(width_of, iw, self.align)
        mode = "static" if self.reduced_motion else self.mode
        shift = 0
        if mode == "marquee":
            shift = -int(self.t * self.speed) % (width_of + iw) - width_of
        elif mode == "bounce":
            span = max(1, iw - width_of)
            ph = (self.t * self.speed) % (2 * span)
            shift = int(ph if ph <= span else 2 * span - ph) - (left - inset - self.padding)
        reveal = int(self.t * self.speed) if mode == "typewriter" else width_of
        neon = Neon(text="", speed=0.5).gradient if mode == "neon" else None
        for r, row in enumerate(rows):
            for k, ch in enumerate(row):
                if ch == " " or k >= reveal:
                    continue
                col = left + k + shift
                if not inset + self.padding <= col < w - inset - self.padding:
                    continue
                dy = round(math.sin(self.t * self.speed / 3 + k / 3)) if mode == "wave" else 0
                st = self.style
                if self.gradient is not None:
                    st = char_style(
                        k,
                        width_of,
                        st,
                        self.gradient,
                        self.t * 0.2 if mode == "gradient-scroll" else 0.0,
                    )
                elif mode == "gradient-scroll":
                    st = char_style(k, width_of, st, get_gradient("rainbow"), self.t * 0.2)
                if neon is not None:
                    st = st.replace(fg=neon.at(0.5 + 0.5 * math.sin(self.t * 3 + k / 5)))
                if mode == "fade":
                    st = st.replace(dim=(self.t * 0.5) % 2 > 1)
                canvas.write_text(top + r + dy, col, ch, st)


def create_sign(text: str, *, width: int | None = None, **options: object) -> Sign:
    """Build a :class:`Sign` sized to its text (large font + optional border)."""
    font = options.get("font", "original-5")
    rows = render_text(text, get_font(font) if isinstance(font, str) else font)  # type: ignore[arg-type]
    inset = 2 if options.get("border") else 0
    pad = int(options.get("padding", 0))  # type: ignore[call-overload]
    w = width or (max((len(r) for r in rows), default=0) + 2 * (inset // 2 + pad) + inset)
    h = len(rows) + inset + 2 * pad
    return Sign(0, 0, w, h, text=text, **options)  # type: ignore[arg-type]


def create_banner(text: str, *, width: int = 40, border: str = "double", **options: object) -> Sign:
    """A bordered, centred banner sign of the given width."""
    options.setdefault("font", "original-5")
    options.setdefault("align", "center")
    sign = create_sign(text, border=border, **options)  # type: ignore[arg-type]
    sign.resize(width, sign.height)
    return sign


MATRIX_MODES = ("rain", "reveal", "fade", "vt", "encrypted")


class MatrixRain(Animated):
    """Falling characters with optional text reveal (FR-MATRIX-001/002)."""

    def __init__(
        self,
        x: int = 0,
        y: int = 0,
        width: int = 40,
        height: int = 12,
        *,
        text: str = "",
        charset: str = "01ｱｲｳｴｵｶｷｸｹｺ",
        density: float = 0.5,
        speed: float = 8.0,
        seed: int | None = None,
        gradient: Gradient | None = None,
        mode: str = "rain",
        reveal_after: float = 2.0,
        reduced_motion: bool | None = None,
        name: WidgetId | None = None,
    ) -> None:
        super().__init__(x, y, width, height, speed=speed, reduced_motion=reduced_motion, name=name)
        if mode not in MATRIX_MODES:
            raise ValueError(f"mode must be one of {MATRIX_MODES}")
        self.density = require_fraction("density", density)
        self.text, self.charset, self.mode, self.reveal_after = (
            text,
            charset or "01",
            mode,
            reveal_after,
        )
        self.gradient = gradient or Gradient.from_colors(
            [RGB(0, 40, 0), RGB(0, 255, 70), RGB(220, 255, 220)]
        )
        self._seed = 0 if seed is None else seed
        rng = random.Random(self._seed)
        self._cols = [
            (
                rng.random() < self.density,
                rng.uniform(0.5, 1.5),
                rng.randrange(4, 10),
                rng.uniform(0, 20),
            )
            for _ in range(width)
        ]
        self._reveal = [rng.uniform(0, 1.5) for _ in text]

    def _glyph(self, col: int, row: int, tick: int) -> str:
        return random.Random(hash((self._seed, col, row, tick)) & 0xFFFFFFFF).choice(self.charset)

    def render(self, canvas: Canvas) -> None:
        w, h = canvas.width, canvas.height
        if self.mode == "vt":
            self._render_vt(canvas)
            return
        text_row, text_col = h // 2, max(0, (w - len(self.text)) // 2)
        revealing = self.mode in ("reveal", "fade") and self.t >= self.reveal_after
        fade = self.mode == "fade" and self.t >= self.reveal_after
        tick = 0 if self.reduced_motion else int(self.t * 6)
        for c in range(min(w, len(self._cols))):
            active, spd, length, phase = self._cols[c]
            if not active:
                continue
            head = (
                0
                if self.reduced_motion
                else int((self.t * self.speed * spd + phase) % (h + length))
            )
            for tail in range(length):
                r = head - tail
                if not 0 <= r < h:
                    continue
                if fade and self.t - self.reveal_after > 2.0:
                    continue
                shade = 1.0 - tail / length
                canvas.write_text(
                    r, c, self._glyph(c, r, tick), Style(fg=self.gradient.at(shade), bold=tail == 0)
                )
        if self.mode == "encrypted":
            tick2 = 0 if self.reduced_motion else int(self.t * 12)
            for i, ch in enumerate(self.text):
                if text_col + i >= w:
                    break
                done = self.t - self.reveal_after >= self._reveal[i]
                glyph = ch if done else self._glyph(text_col + i, text_row, tick2)
                st = Style(fg=RGB(255, 255, 255), bold=True) if done else Style(fg=RGB(0, 170, 70))
                canvas.write_text(text_row, text_col + i, glyph, st)
        elif revealing:
            for i, ch in enumerate(self.text):
                if self.t - self.reveal_after >= self._reveal[i]:
                    canvas.write_text(
                        text_row, text_col + i, ch, Style(fg=RGB(255, 255, 255), bold=True)
                    )

    def _render_vt(self, canvas: Canvas) -> None:
        """Terminal-style typing: text appears at ``speed`` chars/s with a blinking cursor."""
        w, h = canvas.width, canvas.height
        typed = len(self.text) if self.reduced_motion else int(self.t * self.speed)
        row = col = 0
        green = Style(fg=RGB(0, 255, 70))
        for ch in self.text[:typed]:
            if ch == "\n" or col >= w:
                row, col = row + 1, 0
                if ch == "\n":
                    continue
            if row >= h:
                break
            canvas.write_text(row, col, ch, green)
            col += 1
        blink = self.reduced_motion or int(self.t * 2) % 2 == 0
        if blink and row < h and col < w:
            canvas.write_text(row, col, "█", green)

    def describe(self) -> str:
        return f"MatrixRain({self.mode}, density={self.density}, t={self.t:.2f})"


__all__ = ["MATRIX_MODES", "MatrixRain", "Neon", "Sign", "create_banner", "create_sign"]
_ = require_positive
