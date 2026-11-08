"""Spinner widget and SpinnerGroup (FR-SPINNER-001..004). Layer L3."""

from __future__ import annotations

from widgets.assets.spinners import get_spinner, spinner_frames
from widgets.base_elements.base import Widget
from widgets.base_elements.color_manager import Gradient
from widgets.base_elements.effects import (
    BeatSource,
    BeatSync,
    reduced_motion_enabled,
    require_positive,
)
from widgets.base_elements.widget_types import DEFAULT_STYLE, Style, WidgetId
from widgets.display._common import aligned_col, char_style
from widgets.render.buffer import Canvas
from widgets.render.width import display_width


class Spinner(Widget):
    """Animated spinner with optional text."""

    def __init__(
        self,
        x: int = 0,
        y: int = 0,
        width: int = 20,
        *,
        spinner: str = "line",
        text: str = "",
        speed: float = 10.0,
        align: str = "left",
        style: Style = DEFAULT_STYLE,
        gradient: Gradient | None = None,
        ascii_only: bool = False,
        reduced_motion: bool | None = None,
        beat_source: BeatSource | None = None,
        name: WidgetId | None = None,
    ) -> None:
        super().__init__(x, y, width, 1, name=name)
        get_spinner(spinner)
        aligned_col(0, 1, align)
        self.spinner, self.text, self.align, self.style = spinner, text, align, style
        self.gradient, self.ascii_only = gradient, ascii_only
        self.speed = require_positive("speed", speed)
        self.reduced_motion = reduced_motion_enabled(override=reduced_motion)
        self._phase = 0.0
        self._beats = BeatSync(beat_source)

    def set_beat_source(self, source: BeatSource | None) -> None:
        """Step one frame per beat while the source delivers events (FR-ANIM-007)."""
        self._beats.set_source(source)

    @property
    def audio_sync_active(self) -> bool:
        return self._beats.active

    def set_spinner(self, name: str) -> None:
        get_spinner(name)
        self.spinner = name

    def set_text(self, text: str) -> None:
        self.text = text

    def set_speed(self, speed: float) -> None:
        self.speed = require_positive("speed", speed)

    def set_style(self, style: Style) -> None:
        self.style = style

    def update(self, dt: float) -> None:
        beats = self._beats.poll(dt)
        advance = float(beats) if self._beats.active else dt * self.speed
        self._phase = (self._phase + advance) % 1_000_000.0

    @property
    def frame(self) -> str:
        frames = spinner_frames(self.spinner, self.ascii_only)
        return frames[0] if self.reduced_motion else frames[int(self._phase) % len(frames)]

    def render(self, canvas: Canvas) -> None:
        frames = spinner_frames(self.spinner, self.ascii_only)
        frame = self.frame
        content = f"{frame} {self.text}" if self.text else frame
        col = aligned_col(display_width(content), canvas.width, self.align)
        idx = int(self._phase) % len(frames)
        for k, ch in enumerate(content):
            st = char_style(k, len(content), self.style, self.gradient, idx / len(frames))
            canvas.write_text(0, col + k, ch, st)

    def describe(self) -> str:
        return f"Spinner({self.spinner}, text={self.text!r}, {self.speed} fps)"


class SpinnerGroup:
    """Controls several spinners placed on consecutive, non-overlapping rows."""

    def __init__(self, x: int = 0, y: int = 0, width: int = 30) -> None:
        self.x, self.y, self.width = x, y, width
        self._spinners: list[Spinner] = []

    @property
    def spinners(self) -> tuple[Spinner, ...]:
        return tuple(self._spinners)

    def add(self, spinner: Spinner) -> Spinner:
        if spinner in self._spinners:
            raise ValueError("spinner already in group")
        self._spinners.append(spinner)
        self._layout()
        return spinner

    def remove(self, spinner: Spinner) -> None:
        self._spinners.remove(spinner)
        self._layout()

    def _layout(self) -> None:
        for row, spinner in enumerate(self._spinners):
            spinner.move(self.x, self.y + row)
            spinner.resize(self.width, 1)

    def start_all(self) -> None:
        for s in self._spinners:
            if s.state.name in ("CREATED", "UNMOUNTED"):
                s.mount()
            s.start()

    def stop_all(self) -> None:
        for s in self._spinners:
            s.stop()

    def update(self, dt: float) -> None:
        for s in self._spinners:
            s.tick(dt)
