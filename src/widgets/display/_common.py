"""Shared helpers for display widgets. Layer L3."""

from __future__ import annotations

from widgets.base_elements.base import Widget
from widgets.base_elements.color_manager import Gradient
from widgets.base_elements.effects import (
    BeatSource,
    BeatSync,
    reduced_motion_enabled,
    require_positive,
)
from widgets.base_elements.widget_types import DEFAULT_STYLE, Style, WidgetId
from widgets.render.width import display_width


def aligned_col(text_width: int, width: int, align: str) -> int:
    """Left column for text of ``text_width`` cells inside ``width`` for ``align``."""
    if align == "center":
        return max(0, (width - text_width) // 2)
    if align == "right":
        return max(0, width - text_width)
    if align == "left":
        return 0
    raise ValueError(f"align must be left, center or right, got {align!r}")


def char_style(
    index: int, count: int, base: Style, gradient: Gradient | None, shift: float = 0.0
) -> Style:
    """``base`` with the foreground taken from ``gradient`` at the character's position."""
    if gradient is None:
        return base
    t = (index / max(1, count - 1) + shift) % 1.0 if count > 1 else shift % 1.0
    return base.replace(fg=gradient.at(t))


def clip_cells(text: str, width: int) -> str:
    """Cut ``text`` to at most ``width`` display cells."""
    out, used = "", 0
    for ch in text:
        w = display_width(ch)
        if used + w > width:
            break
        out, used = out + ch, used + w
    return out


class Animated(Widget):
    """Base for time-driven widgets: elapsed ``t`` advances only through ``update(dt)``."""

    def __init__(
        self,
        x: int = 0,
        y: int = 0,
        width: int = 0,
        height: int = 0,
        *,
        speed: float = 1.0,
        reduced_motion: bool | None = None,
        beat_source: BeatSource | None = None,
        beat_step: float = 0.25,
        name: WidgetId | None = None,
    ) -> None:
        super().__init__(x, y, width, height, name=name)
        self.speed = require_positive("speed", speed)
        self.reduced_motion = reduced_motion_enabled(override=reduced_motion)
        self.t = 0.0
        self.beat_step = require_positive("beat_step", beat_step)
        self._beats = BeatSync(beat_source)

    def set_beat_source(self, source: BeatSource | None) -> None:
        """Advance on ``source`` events instead of time (FR-ANIM-007)."""
        self._beats.set_source(source)

    @property
    def audio_sync_active(self) -> bool:
        """True while a beat source is delivering events; False means time-driven mode."""
        return self._beats.active

    def set_speed(self, speed: float) -> None:
        self.speed = require_positive("speed", speed)

    def update(self, dt: float) -> None:
        if dt < 0:
            raise ValueError("dt must be >= 0")
        beats = self._beats.poll(dt)
        if self._beats.active:
            step = beats * self.beat_step
            self.t += step
            self.advance(step)
            return
        self.t += dt
        self.advance(dt)

    def advance(self, dt: float) -> None:
        """Hook for subclasses; ``self.t`` is already updated."""


STYLE = DEFAULT_STYLE
