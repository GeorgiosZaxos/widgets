"""Perspective text crawl over a seeded star field (FR-SPACE-001..004). Layer L3.

All default text and visuals are original and procedurally generated (decision D-16).
"""

from __future__ import annotations

import contextlib
import math
import textwrap
from collections.abc import Sequence
from pathlib import Path

from widgets.audio.backend import AudioBackend, default_backend
from widgets.base_elements.effects import make_rng, reduced_motion_enabled, require_positive
from widgets.base_elements.events import KeyEvent
from widgets.base_elements.interactive import InteractiveWidget
from widgets.base_elements.widget_types import RGB, Style, WidgetId
from widgets.display._common import clip_cells
from widgets.errors import AudioBackendError
from widgets.render.buffer import Canvas

DEFAULT_TEXT = """THE LONG QUIET

In the year 3012 the lantern keepers of the Orrery Belt
lit their last beacon and fell silent.

Far beyond the charted dark, a single pulse
kept counting the hours of a forgotten sea.

One courier, one battered ship and a map
drawn by nobody still alive set out to follow it...
"""

KINDS = ("star", "galaxy", "nebula", "pulsar")
DEFAULT_OBJECTS: tuple[tuple[str, float], ...] = (
    ("star", 0.05),
    ("galaxy", 0.004),
    ("nebula", 0.003),
    ("pulsar", 0.003),
)
CRAWL_COLOR = RGB(255, 210, 60)
MIN_SPEED, MAX_SPEED = 0.1, 20.0


class SpaceCrawlWidget(InteractiveWidget):
    """Text that recedes toward the horizon (narrowing and dimming) in front of a star field.

    Keys: ``space`` pause/resume | ``+`` / ``-`` speed | ``r`` restart.
    ``speed`` is in text lines per second. ``objects`` is a sequence of ``(kind, density)`` with kind
    in ``star``, ``galaxy``, ``nebula``, ``pulsar`` and density as the fraction of cells used.
    An optional ``soundtrack`` file plays through ``backend`` (default: the first real backend);
    audio problems are reported in ``audio_error`` and never stop the visuals (FR-SPACE-004).
    """

    def __init__(
        self,
        x: int = 0,
        y: int = 0,
        width: int = 80,
        height: int = 24,
        *,
        text: str = DEFAULT_TEXT,
        speed: float = 1.2,
        objects: Sequence[tuple[str, float]] = DEFAULT_OBJECTS,
        seed: int | None = None,
        text_width: int = 44,
        loop: bool = False,
        color: RGB = CRAWL_COLOR,
        intro: str | None = None,
        intro_time: float = 3.0,
        soundtrack: str | Path | None = None,
        backend: AudioBackend | None = None,
        ascii_only: bool = False,
        reduced_motion: bool | None = None,
        name: WidgetId | None = None,
    ) -> None:
        super().__init__(x, y, width, height, name=name)
        self.speed = require_positive("speed", speed)
        if text_width < 4:
            raise ValueError("text_width must be >= 4")
        for kind, density in objects:
            if kind not in KINDS:
                raise ValueError(f"unknown space object {kind!r}; choose from {KINDS}")
            if not 0.0 <= density <= 1.0:
                raise ValueError("density must be within 0..1")
        self.objects = tuple(objects)
        self.seed, self.loop, self.color, self.ascii_only = seed, loop, color, ascii_only
        self.text_width = text_width
        self.reduced_motion = reduced_motion_enabled(override=reduced_motion)
        self.soundtrack, self.backend = soundtrack, backend
        self.intro = intro
        self.intro_time = max(0.0, intro_time) if intro else 0.0
        self.audio_error: str | None = None
        self.audio_playing = False
        self.t = 0.0
        self._lines: list[str] = []
        self.set_text(text)
        self._field: list[tuple[int, int, str, float]] = []
        self._field_size = (-1, -1)

    # -- content ---------------------------------------------------------------------------
    def set_text(self, text: str) -> None:
        lines: list[str] = []
        for para in text.splitlines():
            lines.extend(textwrap.wrap(para, self.text_width) or [""])
        self._lines = lines
        self.t = 0.0

    @property
    def lines(self) -> list[str]:
        return list(self._lines)

    def _build_field(self, w: int, h: int) -> None:
        rng = make_rng(self.seed)
        field: list[tuple[int, int, str, float]] = []
        for kind, density in self.objects:
            for _ in range(round(density * w * h)):
                field.append((rng.randrange(w), rng.randrange(h), kind, rng.random() * 6.28))
        self._field, self._field_size = field, (w, h)

    def star_field(self) -> list[tuple[int, int, str]]:
        """The generated objects as ``(col, row, kind)`` (deterministic for a given seed/size)."""
        if self._field_size != (self.width, self.height):
            self._build_field(self.width, self.height)
        return [(c, r, k) for c, r, k, _ in self._field]

    # -- speed / controls ---------------------------------------------------------------------
    def set_speed(self, speed: float) -> None:
        self.speed = min(MAX_SPEED, max(MIN_SPEED, require_positive("speed", speed)))

    @property
    def position(self) -> float:
        """Crawl position in text lines."""
        return max(0.0, self.t - self.intro_time) * self.speed

    @property
    def finished(self) -> bool:
        return not self.loop and self.position > len(self._lines) + self.height

    def restart(self) -> None:
        self.t = 0.0

    def update(self, dt: float) -> None:
        if dt < 0:
            raise ValueError("dt must be >= 0")
        self.t += dt

    def handle_key(self, event: KeyEvent) -> bool:
        if not self.effective_enabled:
            return False
        key = event.key
        if key in ("space", " "):
            if self.state.name == "RUNNING":
                self.pause()
            elif self.state.name == "PAUSED":
                self.resume()
        elif key in ("+", "="):
            self.set_speed(self.speed * 1.25)
        elif key in ("-", "_"):
            self.set_speed(self.speed / 1.25)
        elif key == "r":
            self.restart()
        else:
            return False
        return True

    # -- soundtrack (FR-SPACE-004) --------------------------------------------------------------
    def on_start(self) -> None:
        if self.soundtrack is None:
            return
        try:
            if self.backend is None:
                self.backend = default_backend()
            self.backend.load(self.soundtrack)
            self.backend.play()
            self.audio_playing, self.audio_error = True, None
        except (AudioBackendError, OSError) as exc:
            self.audio_playing, self.audio_error = False, str(exc)

    def on_pause(self) -> None:
        if self.audio_playing and self.backend is not None:
            with contextlib.suppress(AudioBackendError):
                self.backend.pause()

    def on_resume(self) -> None:
        if self.audio_playing and self.backend is not None:
            with contextlib.suppress(AudioBackendError):
                self.backend.resume()

    def on_stop(self) -> None:
        if self.audio_playing and self.backend is not None:
            with contextlib.suppress(AudioBackendError):
                self.backend.stop()
        self.audio_playing = False

    def on_close(self) -> None:
        if self.backend is not None:
            with contextlib.suppress(AudioBackendError):
                self.backend.close()

    # -- rendering -------------------------------------------------------------------------------
    def _draw_objects(self, canvas: Canvas) -> None:
        w, h = canvas.width, canvas.height
        if self._field_size != (w, h):
            self._build_field(w, h)
        still = self.reduced_motion
        for c, r, kind, phase in self._field:
            tw = 1.0 if still else 0.5 + 0.5 * math.sin(self.t * 2.0 + phase)
            if kind == "star":
                glyph = "." if self.ascii_only or tw < 0.4 else ("*" if tw > 0.85 else "·")
                shade = int(90 + 120 * tw)
                canvas.write_text(r, c, glyph, Style(fg=RGB(shade, shade, min(255, shade + 30))))
            elif kind == "pulsar":
                on = still or (int(self.t * 3.0 + phase) % 4 == 0)
                canvas.write_text(
                    r,
                    c,
                    ("+" if self.ascii_only else "✦") if on else " ",
                    Style(fg=RGB(120, 200, 255), bold=on),
                )
            elif kind == "galaxy":
                canvas.write_text(
                    r,
                    c,
                    "(@)" if self.ascii_only else "◖@◗",
                    Style(fg=RGB(180, 140, 255), dim=tw < 0.5),
                )
            else:  # nebula
                tint = RGB(200, 70, 150) if int(phase * 10) % 2 else RGB(70, 130, 220)
                for dr, row in enumerate(
                    (" ░░ ", "░▒▒░", " ░░ ") if not self.ascii_only else (" .. ", ".::.", " .. ")
                ):
                    canvas.write_text(r + dr, c, row, Style(fg=tint, dim=True))

    def _crawl_pos(self) -> float:
        if self.reduced_motion:
            return len(self._lines) * 0.5 + self.height * 0.3
        pos = self.position
        if self.loop:
            pos %= len(self._lines) + self.height
        return pos

    def render(self, canvas: Canvas) -> None:
        w, h = canvas.width, canvas.height
        if self.intro and self.t < self.intro_time and not self.reduced_motion:
            fade = min(1.0, self.t / (self.intro_time * 0.4), (self.intro_time - self.t) / 0.6)
            blue = Style(fg=RGB(int(60 * fade), int(150 * fade), int(255 * fade)))
            for k, line in enumerate(self.intro.splitlines()):
                canvas.write_text(h // 2 - 1 + k, max(0, (w - len(line)) // 2), line[:w], blue)
            return
        self._draw_objects(canvas)
        horizon = max(1, int(h * 0.18))
        span = h - 1 - horizon
        if span <= 0 or not self._lines:
            return
        pos = self._crawl_pos()
        for r in range(horizon + 1, h):
            t = (r - horizon) / span  # 0 at the horizon .. 1 at the bottom
            if t < 0.06:
                continue
            u = 1.2 * (1.0 / t - 1.0)  # distance beyond the bottom edge, in lines
            index = math.floor(pos - u)
            if not 0 <= index < len(self._lines):
                continue
            line = self._lines[index]
            if not line.strip():
                continue
            width = max(1, round(self.text_width * t))
            padded = line.center(self.text_width)
            chars = [
                padded[min(len(padded) - 1, int(k * len(padded) / width))] for k in range(width)
            ]
            row = clip_cells("".join(chars), w)
            col = max(0, (w - len(row)) // 2)
            fade = 0.2 + 0.8 * t
            style = Style(
                fg=RGB(
                    int(self.color.r * fade), int(self.color.g * fade), int(self.color.b * fade)
                ),
                bold=t > 0.7,
            )
            canvas.write_text(r, col, row, style)

    def describe(self) -> str:
        return f"SpaceCrawlWidget({len(self._lines)} lines, speed={self.speed:g})"


__all__ = ["DEFAULT_TEXT", "SpaceCrawlWidget"]
