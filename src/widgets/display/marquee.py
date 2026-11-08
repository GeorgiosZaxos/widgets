"""Marquee and animated text (FR-MARQUEE-*, FR-ANIM-*). Layer L3."""

from __future__ import annotations

import math
from collections.abc import Callable

from widgets.assets.fonts import Font, get_font, render_text
from widgets.assets.spinners import spinner_frames
from widgets.base_elements.color_manager import Gradient
from widgets.base_elements.effects import ease, make_rng, require_non_negative
from widgets.base_elements.widget_types import DEFAULT_STYLE, Style, WidgetId
from widgets.display._common import Animated, aligned_col, char_style, clip_cells
from widgets.render.buffer import Canvas
from widgets.render.width import display_width

DIRECTIONS = ("left", "right", "up", "down", "diagonal", "snake")


def _wrap_slice(strip: str, offset: int, width: int) -> str:
    if not strip:
        return " " * width
    reps = strip * (width // max(1, len(strip)) + 3)
    start = offset % len(strip)
    return reps[start : start + width]


class Marquee(Animated):
    """Scrolling single- or multi-line content (loop or bounce) at ``speed`` cells/s."""

    def __init__(
        self,
        x: int = 0,
        y: int = 0,
        width: int = 30,
        height: int = 1,
        *,
        text: str = "",
        direction: str = "left",
        mode: str = "loop",
        speed: float = 8.0,
        gap: int = 4,
        font: Font | str | None = None,
        align: str = "left",
        style: Style = DEFAULT_STYLE,
        gradient: Gradient | None = None,
        reduced_motion: bool | None = None,
        name: WidgetId | None = None,
    ) -> None:
        super().__init__(x, y, width, height, speed=speed, reduced_motion=reduced_motion, name=name)
        if direction not in DIRECTIONS:
            raise ValueError(f"direction must be one of {DIRECTIONS}")
        if mode not in ("loop", "bounce"):
            raise ValueError("mode must be 'loop' or 'bounce'")
        aligned_col(0, 1, align)
        self.text, self.direction, self.mode = text, direction, mode
        self.gap = int(require_non_negative("gap", gap))
        self.font = get_font(font) if isinstance(font, str) else font
        self.align, self.style, self.gradient = align, style, gradient

    def set_text(self, text: str) -> None:
        self.text = text

    def lines(self) -> list[str]:
        if self.font is not None:
            return render_text(self.text, self.font)
        return self.text.split("\n")

    def offset(self, extent: int, size: int) -> int:
        """Integer scroll offset along an axis with ``size`` visible cells and content ``extent``."""
        if self.reduced_motion:
            return 0
        distance = self.t * self.speed
        if self.mode == "bounce":
            travel = max(0, extent - size)
            if travel == 0:
                return 0
            phase = distance % (2 * travel)
            return int(phase if phase <= travel else 2 * travel - phase)
        return int(distance)

    def render(self, canvas: Canvas) -> None:
        w, h = canvas.width, canvas.height
        lines = self.lines()
        if self.direction in ("diagonal", "snake"):
            self._render_path(canvas, "".join(lines[:1]))
            return
        if self.direction in ("left", "right"):
            width_of = max((display_width(ln) for ln in lines), default=0)
            off = self.offset(width_of, w)
            sign = 1 if self.direction == "left" else -1
            for r, line in enumerate(lines[:h]):
                if self.mode == "bounce":
                    shift = off if self.direction == "left" else max(0, width_of - w) - off
                    visible = clip_cells(line.ljust(width_of)[shift : shift + w], w)
                    visible = (
                        visible
                        if width_of > w
                        else " " * aligned_col(width_of, w, self.align) + line
                    )
                else:
                    visible = _wrap_slice(line + " " * self.gap, sign * off, w)
                for k, ch in enumerate(visible[:w]):
                    canvas.write_text(r, k, ch, char_style(k, w, self.style, self.gradient))
        else:
            extent = len(lines) + self.gap if self.mode == "loop" else len(lines)
            off = self.offset(len(lines), h)
            for r in range(h):
                if self.mode == "loop":
                    idx = (r + (off if self.direction == "up" else -off)) % extent
                    line = lines[idx] if idx < len(lines) else ""
                else:
                    shift = off if self.direction == "up" else max(0, len(lines) - h) - off
                    idx = r + shift
                    line = lines[idx] if 0 <= idx < len(lines) else ""
                line = clip_cells(line, w)
                col = aligned_col(display_width(line), w, self.align)
                for k, ch in enumerate(line):
                    canvas.write_text(
                        r, col + k, ch, char_style(k, len(line), self.style, self.gradient)
                    )

    def _render_path(self, canvas: Canvas, text: str) -> None:
        """Diagonal (wrapping down-right) and snake (boustrophedon) scrolling of one line."""
        w, h = canvas.width, canvas.height
        if w <= 0 or h <= 0 or not text:
            return
        off = 0 if self.reduced_motion else int(self.t * self.speed)
        for k, ch in enumerate(text):
            if self.direction == "snake":
                p = (off - k) % (w * h)
                row, c = divmod(p, w)
                col = c if row % 2 == 0 else w - 1 - c
            else:
                row = (off - k) % h
                col = (off - k) % w
            canvas.write_text(row, col, ch, char_style(k, len(text), self.style, self.gradient))

    def describe(self) -> str:
        return f"Marquee({self.direction}, {self.mode}, {self.speed} cells/s, {self.text[:30]!r})"


MODES = ("scroll", "bounce", "dual-marquee", "typewriter", "fade-in", "fade-out", "wave", "explode")


class AnimatedText(Animated):
    """Single-text animations with deterministic, seedable behaviour (FR-ANIM-001..006)."""

    def __init__(
        self,
        x: int = 0,
        y: int = 0,
        width: int = 30,
        height: int = 1,
        *,
        text: str = "",
        mode: str = "typewriter",
        speed: float = 10.0,
        duration: float | None = None,
        loop: bool = False,
        easing: str = "linear",
        bidirectional: bool = False,
        amplitude: float = 1.0,
        wavelength: float = 8.0,
        cursor: str = "_",
        spinner: str | None = None,
        placement: str = "before",
        seed: int | None = None,
        style: Style = DEFAULT_STYLE,
        gradient: Gradient | None = None,
        background: Style | None = None,
        on_complete: Callable[[], object] | None = None,
        ascii_only: bool = False,
        reduced_motion: bool | None = None,
        name: WidgetId | None = None,
    ) -> None:
        super().__init__(x, y, width, height, speed=speed, reduced_motion=reduced_motion, name=name)
        if mode not in MODES:
            raise ValueError(f"mode must be one of {MODES}")
        if placement not in ("before", "after", "both", "replace"):
            raise ValueError("placement must be before, after, both or replace")
        ease("linear", 0.0)
        ease(easing, 0.5)
        if duration is not None:
            require_non_negative("duration", duration)
        self.text, self.mode, self.duration, self.loop, self.easing = (
            text,
            mode,
            duration,
            loop,
            easing,
        )
        self.bidirectional, self.amplitude, self.wavelength = bidirectional, amplitude, wavelength
        self.cursor, self.spinner, self.placement = cursor, spinner, placement
        self.style, self.gradient, self.on_complete, self.ascii_only = (
            style,
            gradient,
            on_complete,
            ascii_only,
        )
        self._rng = make_rng(seed)
        self._vectors = [(self._rng.uniform(-1, 1), self._rng.uniform(-1, 1)) for _ in text]
        self._completed = False

    def advance(self, dt: float) -> None:
        if self.duration is not None and self.t >= self.duration and not self._completed:
            if self.loop and self.duration > 0:
                self.t %= self.duration
            else:
                self._completed = True
                self.t = self.duration
                self.invoke_callback(self.on_complete)
                self.stop()

    @property
    def progress(self) -> float:
        """Eased progress in [0, 1] over ``duration`` (or over the typing time)."""
        total = self.duration if self.duration else max(len(self.text) / self.speed, 1e-9)
        raw = min(1.0, max(0.0, self.t / total))
        return ease(self.easing, raw)

    def _text_with_spinner(self) -> str:
        if self.spinner is None:
            return self.text
        frames = spinner_frames(self.spinner, self.ascii_only)
        frame = frames[0] if self.reduced_motion else frames[int(self.t * self.speed) % len(frames)]
        if self.placement == "replace":
            return frame
        return {
            "before": f"{frame} {self.text}",
            "after": f"{self.text} {frame}",
            "both": f"{frame} {self.text} {frame}",
        }[self.placement]

    def render(self, canvas: Canvas) -> None:
        w, h = canvas.width, canvas.height
        text = self._text_with_spinner()
        n = len(text)
        mode = "static" if self.reduced_motion and self.mode != "typewriter" else self.mode
        if self.reduced_motion:
            mode = "static"
        if mode == "static":
            self._draw(canvas, 0, 0, text, 0)
            return
        if mode == "typewriter":
            shown = min(n, int(self.t * self.speed))
            cur = self.cursor if shown < n else ""
            self._draw(canvas, 0, 0, text[:shown] + cur, 0)
        elif mode in ("scroll", "bounce"):
            span = max(1, n + w) if mode == "scroll" and not self.bidirectional else max(1, w - n)
            d = self.t * self.speed
            if mode == "bounce" or self.bidirectional:
                span = max(1, w - n)
                phase = d % (2 * span)
                x = phase if phase <= span else 2 * span - phase
                self._draw(canvas, 0, int(x), text, 0)
            else:
                self._draw(canvas, 0, w - int(d % span), text, 0)
        elif mode == "dual-marquee":
            d = int(self.t * self.speed)
            self._draw(canvas, 0, w - (d % (n + w)), text, 0)
            if h > 1:
                self._draw(canvas, 1, (d % (n + w)) - n, text, 0)
        elif mode in ("fade-in", "fade-out"):
            p = self.progress if mode == "fade-in" else 1 - self.progress
            self._draw(canvas, 0, 0, text, 0, fade=p)
        elif mode == "wave":
            for i, ch in enumerate(text):
                dy = round(
                    self.amplitude
                    * math.sin(2 * math.pi * (i / self.wavelength - self.t * self.speed / 10))
                )
                row = max(0, min(h - 1, h // 2 + dy))
                canvas.write_text(row, i, ch, char_style(i, n, self.style, self.gradient))
        elif mode == "explode":
            p = self.progress
            cx, cy = n / 2, h / 2
            for i, ch in enumerate(text):
                vx, vy = self._vectors[i % len(self._vectors)] if self._vectors else (0, 0)
                col = round(i + (i - cx + vx) * p * 2)
                row = round(cy + vy * p * h)
                if p < 1.0 and 0 <= row < h:
                    canvas.write_text(row, col, ch, char_style(i, n, self.style, self.gradient))

    def _draw(
        self, canvas: Canvas, row: int, col: int, text: str, _unused: int, fade: float = 1.0
    ) -> None:
        n = len(text)
        for i, ch in enumerate(text):
            st = char_style(i, n, self.style, self.gradient)
            if fade < 1.0:
                st = st.replace(dim=fade < 0.5, bold=fade >= 0.9) if fade > 0.05 else None  # type: ignore[assignment]
                if st is None:
                    continue
            canvas.write_text(row, col + i, ch, st)

    def describe(self) -> str:
        return f"AnimatedText({self.mode}, t={self.t:.2f}, text={self.text[:30]!r})"
