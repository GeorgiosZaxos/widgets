"""Progress indicator widgets (FR-PROG-005..009, 018). Layer L3.

Every indicator renders into a buffer (D-02); the inline manager maps those buffers to terminal
lines. Indicators read a :class:`ProgressState` and never touch the terminal.

Width fitting (FR-PROG-018): the horizontal bar keeps ``min_bar`` cells and drops optional fields
in this order until it fits: postfix, speed, time, count, percentage; then the description is
truncated. Nothing is ever wrapped.
"""

from __future__ import annotations

import math

from widgets.assets.bars import BarStyle, get_bar_style
from widgets.assets.spinners import get_spinner, spinner_frames
from widgets.base_elements.base import Widget
from widgets.base_elements.color_manager import Gradient
from widgets.base_elements.widget_types import DEFAULT_STYLE, RGB, Rect, Style, WidgetId
from widgets.progress.state import ProgressState, format_duration
from widgets.render.buffer import Canvas
from widgets.render.width import display_width

FILL_STYLE = Style(fg=RGB(80, 200, 120))
EMPTY_STYLE = Style(dim=True)
STALLED_STYLE = Style(fg=RGB(230, 180, 60))
_SUFFIXES = ((3, "G"), (2, "M"), (1, "k"))


class _SafeFields(dict[str, object]):
    """``str.format_map`` mapping that renders unknown placeholders as empty text."""

    def __missing__(self, key: str) -> str:
        return ""


def format_number(value: float, *, scale: bool = False, divisor: float = 1000) -> str:
    """``12`` / ``12.5``; with ``scale`` suffixes (``1.2k``; ``divisor=1024`` for bytes)."""
    if scale:
        for power, suffix in _SUFFIXES:
            factor = float(divisor) ** power
            if abs(value) >= factor:
                return f"{value / factor:.1f}{suffix}"
    if float(value).is_integer():
        return str(int(value))
    return f"{value:.1f}"


def _truncate(text: str, width: int) -> str:
    """Cut ``text`` to ``width`` display columns, marking the cut with an ellipsis."""
    if width <= 0:
        return ""
    if display_width(text) <= width:
        return text
    out, used = "", 0
    for ch in text:
        w = display_width(ch)
        if used + w > width - 1:
            break
        out, used = out + ch, used + w
    return out + "…"


def custom_bar_style(
    charset: str | None = None,
    fill: str | None = None,
    empty: str | None = None,
    *,
    frame: bool = False,
) -> BarStyle:
    """A bar style from a tqdm-style ``charset`` (empty glyph first, full glyph last, partial
    glyphs in between) and/or explicit ``fill`` / ``empty`` glyphs. ``frame`` adds ``|`` borders."""
    chars = charset if charset and len(charset) > 1 else (" " + charset if charset else None)
    full = fill or (chars[-1] if chars else "█")
    blank = empty or (chars[0] if chars else " ")
    partials = tuple(chars[1:-1]) if chars and not fill else ()
    edge = "|" if frame else ""
    return BarStyle("custom", full, blank, partials, edge, edge, full, blank, partials, edge, edge)


def _resolve_style(style: str | BarStyle, orientation: str) -> BarStyle:
    return style if isinstance(style, BarStyle) else get_bar_style(style, orientation)


def spinner_glyph(name: str, tick: float, ascii_only: bool, done: bool) -> str:
    """Frame for a spinner prefix; a finished bar shows a check mark instead."""
    if done:
        return "v" if ascii_only else "✓"
    frames = spinner_frames(name, ascii_only)
    return frames[int(tick) % len(frames)]


class ProgressIndicator(Widget):
    """Base class: a widget bound to a :class:`ProgressState`."""

    expand: bool = False
    """When True the manager stretches the widget to the terminal width."""
    leave: bool = True
    group: str | None = None
    """Consecutive indicators with the same group name are laid out side by side."""

    def __init__(
        self,
        state: ProgressState,
        width: int,
        height: int,
        *,
        name: WidgetId | None = None,
        ascii_only: bool = False,
    ) -> None:
        super().__init__(0, 0, width, height, name=name)
        self.progress = state
        self.ascii_only = ascii_only

    def plain_text(self) -> str:
        """One line of plain text (used for non-TTY output)."""
        raise NotImplementedError


class HorizontalBar(ProgressIndicator):
    """``desc: 42%|████▌     | 42/100 00:12<00:17 3.5it/s postfix``."""

    def __init__(
        self,
        state: ProgressState,
        width: int | None = None,
        *,
        style: str | BarStyle = "smooth",
        ascii_only: bool = False,
        fill_style: Style = FILL_STYLE,
        empty_style: Style = EMPTY_STYLE,
        gradient: Gradient | None = None,
        spinner: str | None = None,
        show_percentage: bool = True,
        show_count: bool = True,
        show_time: bool = True,
        show_speed: bool = True,
        unit: str = "it",
        unit_scale: bool = False,
        unit_divisor: float = 1000,
        bar_format: str | None = None,
        min_bar: int = 5,
        name: WidgetId | None = None,
    ) -> None:
        super().__init__(state, 40 if width is None else width, 1, name=name, ascii_only=ascii_only)
        if unit_divisor <= 1:
            raise ValueError("unit_divisor must be greater than 1")
        self.unit_divisor, self.bar_format = unit_divisor, bar_format
        self.expand = width is None
        self.bar_style = _resolve_style(style, "horizontal")  # KeyError lists valid names
        if spinner is not None:
            get_spinner(spinner)
        self.spinner = spinner
        self._spin = 0.0
        self.fill_style, self.empty_style, self.gradient = fill_style, empty_style, gradient
        self.show_percentage, self.show_count = show_percentage, show_count
        self.show_time, self.show_speed = show_time, show_speed
        self.unit, self.unit_scale, self.min_bar = unit, unit_scale, max(0, min_bar)
        self._phase = 0.0

    def update(self, dt: float) -> None:
        self._phase = (self._phase + 0.8 * dt) % 1_000_000.0
        self._spin = (self._spin + 10.0 * dt) % 1_000_000.0

    # -- text pieces -------------------------------------------------------------------------

    def _num(self, value: float) -> str:
        return format_number(value, scale=self.unit_scale, divisor=self.unit_divisor)

    def _format_fields(self) -> _SafeFields:
        """Placeholder values for ``bar_format`` (tqdm-compatible names)."""
        s = self.progress
        fraction = s.fraction
        speed = s.speed
        eta = format_duration(s.eta) if s.total is not None else "?"
        n_fmt = self._num(s.n)
        total_fmt = "?" if s.total is None else self._num(s.total)
        rate_fmt = "?" if speed is None else f"{self._num(speed)}{self.unit}/s"
        desc = s.description
        pct = 0.0 if fraction is None else fraction * 100
        l_bar = (f"{desc}: " if desc else "") + f"{pct:3.0f}%|"
        r_bar = f"| {n_fmt}/{total_fmt} [{format_duration(s.elapsed)}<{eta}, {rate_fmt}]"
        return _SafeFields(
            desc=desc, percentage=pct, n=s.n, total=s.total if s.total is not None else 0,
            n_fmt=n_fmt, total_fmt=total_fmt, elapsed=format_duration(s.elapsed),
            remaining=eta, rate_fmt=rate_fmt, postfix=s.postfix, unit=self.unit,
            l_bar=l_bar, r_bar=r_bar,
        )  # fmt: skip

    def _fields(self) -> list[str]:
        """Optional fields in decreasing priority (the last one is dropped first)."""
        s = self.progress
        fields: list[str] = []
        fraction = s.fraction
        if self.show_percentage and fraction is not None:
            fields.append(f"{int(fraction * 100):3d}%")
        if self.show_count:
            n = self._num(s.n)
            total = None if s.total is None else self._num(s.total)
            fields.append(f"{n}/{total}" if total is not None else n)
        if self.show_time:
            eta = format_duration(s.eta) if s.total is not None else None
            text = format_duration(s.elapsed) + (f"<{eta}" if eta is not None else "")
            fields.append(text + (" stalled" if s.stalled else ""))
        if self.show_speed:
            speed = s.speed
            fields.append(
                "?" + self.unit + "/s" if speed is None else (f"{self._num(speed)}{self.unit}/s")
            )
        if s.postfix:
            fields.append(s.postfix)
        return fields

    def plain_text(self) -> str:
        s = self.progress
        head = f"{s.description}: " if s.description else ""
        return head + " ".join(f.strip() for f in self._fields())

    # -- layout -----------------------------------------------------------------------------

    def layout(self, width: int) -> tuple[str, int, list[str]]:
        """``(prefix, bar_cells, fields)`` fitting into ``width`` columns."""
        _fill, _empty, _partials, left, right = self.bar_style.glyphs(self.ascii_only)
        frame = display_width(left) + display_width(right)
        prefix = f"{self.progress.description}: " if self.progress.description else ""
        fields = self._fields()

        def remaining(pre: str, parts: list[str]) -> int:
            return width - display_width(pre) - frame - sum(display_width(p) + 1 for p in parts)

        while fields and remaining(prefix, fields) < self.min_bar:
            fields.pop()
        if remaining(prefix, fields) < self.min_bar and prefix:
            budget = max(0, width - frame - self.min_bar)
            prefix = _truncate(prefix, budget)
        return prefix, max(0, remaining(prefix, fields)), fields

    # -- rendering --------------------------------------------------------------------------

    def render(self, canvas: Canvas) -> None:
        if self.spinner is not None:
            done = self.progress.fraction is not None and self.progress.fraction >= 1
            glyph = spinner_glyph(self.spinner, self._spin, self.ascii_only, done)
            used = canvas.write_text(0, 0, glyph, self.fill_style) + 1
            canvas = canvas.view(Rect(used, 0, max(0, canvas.width - used), 1))
        self._render_bar(canvas)

    def _render_bar(self, canvas: Canvas) -> None:
        fill, empty, partials, left, right = self.bar_style.glyphs(self.ascii_only)
        if self.bar_format is not None:
            prefix, suffix = self._split_format()
            cells = max(
                0,
                canvas.width - display_width(prefix) - display_width(suffix)
                - display_width(left) - display_width(right),
            )  # fmt: skip
            fields: list[str] = [suffix.strip()] if suffix.strip() else []
            if "{bar}" not in self.bar_format:
                cells = 0
        else:
            prefix, cells, fields = self.layout(canvas.width)
        col = 0
        col += canvas.write_text(0, col, prefix, DEFAULT_STYLE)
        if self.bar_format is not None and "{bar}" not in self.bar_format:
            for text in fields:
                col += canvas.write_text(0, col, text, DEFAULT_STYLE)
            return
        col += canvas.write_text(0, col, left, DEFAULT_STYLE)
        fraction = self.progress.fraction
        if fraction is None:
            block = max(1, min(3, cells // 3))
            span = max(1, cells - block)
            pos = int(abs((self._phase % 2.0) - 1.0) * span) if cells else 0
            for i in range(cells):
                inside = pos <= i < pos + block
                canvas.write_text(
                    0,
                    col + i,
                    fill if inside else empty,
                    self.fill_style if inside else self.empty_style,
                )
        else:
            exact = fraction * cells
            full = int(exact)
            part = int((exact - full) * (len(partials) + 1)) if partials and full < cells else 0
            for i in range(cells):
                if i < full:
                    style = self.fill_style
                    if self.gradient is not None:
                        style = style.replace(fg=self.gradient.at(i / max(1, cells - 1)))
                    canvas.write_text(0, col + i, fill, style)
                elif i == full and part:
                    canvas.write_text(0, col + i, partials[part - 1], self.fill_style)
                else:
                    canvas.write_text(0, col + i, empty, self.empty_style)
        col += cells
        col += canvas.write_text(0, col, right, DEFAULT_STYLE)
        for text in fields:
            style = STALLED_STYLE if text.endswith("stalled") else DEFAULT_STYLE
            col += canvas.write_text(0, col, ("" if self.bar_format else " ") + text, style)

    def _split_format(self) -> tuple[str, str]:
        """Render the text before and after ``{bar}`` of :attr:`bar_format`."""
        assert self.bar_format is not None
        fields = self._format_fields()
        head, _, tail = self.bar_format.partition("{bar}")
        try:
            return head.format_map(fields), tail.format_map(fields)
        except (ValueError, IndexError, AttributeError):
            return head, tail


VERTICAL_FILLS = ("bottom-up", "top-down", "center-out", "edges-in")
VERTICAL_ANIMATIONS = ("none", "pulse", "scan")


class VerticalBar(ProgressIndicator):
    """A one-column vertical bar, filling bottom-up or top-down (FR-PROG-006)."""

    def __init__(
        self,
        state: ProgressState,
        height: int = 8,
        *,
        style: str | BarStyle = "eighths",
        orientation: str = "bottom-up",
        animate: str = "none",
        ascii_only: bool = False,
        fill_style: Style = FILL_STYLE,
        empty_style: Style = EMPTY_STYLE,
        gradient: Gradient | None = None,
        name: WidgetId | None = None,
    ) -> None:
        if orientation not in VERTICAL_FILLS:
            raise ValueError(f"orientation must be one of {VERTICAL_FILLS}")
        if animate not in VERTICAL_ANIMATIONS:
            raise ValueError(f"animate must be one of {VERTICAL_ANIMATIONS}")
        self.animate = animate
        super().__init__(state, 1, height, name=name, ascii_only=ascii_only)
        self.bar_style = _resolve_style(style, "vertical")
        self.gradient = gradient
        self.orientation = orientation
        self._phase = 0.0
        self.fill_style, self.empty_style = fill_style, empty_style

    def column(self) -> list[str]:
        """Glyph per row, top to bottom (also the plain-text form)."""
        fill, empty, partials, _l, _r = self.bar_style.glyphs(self.ascii_only)
        height = self.height
        fraction = self.progress.fraction or 0.0
        exact = fraction * height
        full = int(exact)
        rows = [empty] * height
        if self.orientation == "bottom-up":
            for i in range(min(full, height)):
                rows[height - 1 - i] = fill
            part = int((exact - full) * (len(partials) + 1)) if partials and full < height else 0
            if part:
                rows[height - 1 - full] = partials[part - 1]
        elif self.orientation == "top-down":
            for i in range(min(round(exact), height)):
                rows[i] = fill
        else:
            count = min(round(exact), height)
            mid = height // 2
            if self.orientation == "center-out":
                order = sorted(range(height), key=lambda r: (abs(r - mid + 0.5), r))
            else:  # edges-in
                order = sorted(range(height), key=lambda r: (-abs(r - mid + 0.5), r))
            for r in order[:count]:
                rows[r] = fill
        return rows

    def update(self, dt: float) -> None:
        self._phase = (self._phase + 0.8 * dt) % 1_000_000.0

    def plain_text(self) -> str:
        fraction = self.progress.fraction
        pct = "?" if fraction is None else f"{int(fraction * 100)}%"
        return f"{self.progress.description}: {pct}" if self.progress.description else pct

    def render(self, canvas: Canvas) -> None:
        fill = self.bar_style.glyphs(self.ascii_only)[0]
        scan = int(self._phase * self.height * 2) % max(1, self.height)
        for row, glyph in enumerate(self.column()):
            filled = glyph != self.bar_style.glyphs(self.ascii_only)[1]
            style = self.fill_style if filled or glyph == fill else self.empty_style
            if filled and self.gradient is not None:  # bottom of the column = start of gradient
                style = style.replace(
                    fg=self.gradient.at((self.height - 1 - row) / max(1, self.height - 1))
                )
            if filled and self.animate == "pulse" and int(self._phase * 4) % 2:
                style = style.replace(bold=True)
            elif filled and self.animate == "scan" and row == self.height - 1 - scan:
                style = style.replace(bold=True, reverse=True)
            canvas.write_text(row, 0, glyph, style)


class CircularIndicator(ProgressIndicator):
    """A ring of cells that fills clockwise from the top (FR-PROG-007).

    ``diameter`` is in rows; the width is doubled to compensate for tall character cells.
    """

    def __init__(
        self,
        state: ProgressState,
        diameter: int = 5,
        *,
        glyphs: tuple[str, str] = ("●", "○"),
        ascii_glyphs: tuple[str, str] = ("#", "."),
        ascii_only: bool = False,
        fill_style: Style = FILL_STYLE,
        empty_style: Style = EMPTY_STYLE,
        name: WidgetId | None = None,
    ) -> None:
        if diameter < 3:
            raise ValueError("diameter must be >= 3")
        super().__init__(state, diameter * 2, diameter, name=name, ascii_only=ascii_only)
        self.glyphs, self.ascii_glyphs = glyphs, ascii_glyphs
        self.fill_style, self.empty_style = fill_style, empty_style

    def ring(self) -> list[tuple[int, int]]:
        """Ring cells as ``(row, col)``, clockwise from 12 o'clock, without duplicates."""
        w, h = self.width, self.height
        cx, cy, rx, ry = (w - 1) / 2, (h - 1) / 2, (w - 1) / 2, (h - 1) / 2
        steps = max(12, 4 * h)
        seen: dict[tuple[int, int], None] = {}
        for k in range(steps):
            angle = 2 * math.pi * k / steps
            seen.setdefault(
                (round(cy - ry * math.cos(angle)), round(cx + rx * math.sin(angle))), None
            )
        return list(seen)

    def plain_text(self) -> str:
        fraction = self.progress.fraction
        pct = "?" if fraction is None else f"{int(fraction * 100)}%"
        return f"{self.progress.description}: {pct}" if self.progress.description else pct

    def render(self, canvas: Canvas) -> None:
        fill, empty = self.ascii_glyphs if self.ascii_only else self.glyphs
        ring = self.ring()
        fraction = self.progress.fraction or 0.0
        lit = round(fraction * len(ring))
        for i, (row, col) in enumerate(ring):
            on = i < lit
            canvas.write_text(
                row, col, fill if on else empty, self.fill_style if on else self.empty_style
            )
        label = "?" if self.progress.fraction is None else f"{int(fraction * 100)}%"
        if len(label) <= self.width - 4:
            canvas.write_text(
                self.height // 2, (self.width - len(label)) // 2, label, DEFAULT_STYLE
            )


class SpinnerIndicator(ProgressIndicator):
    """Indeterminate spinner whose frame advances with ``update(dt)`` (FR-PROG-008)."""

    expand: bool = True

    def __init__(
        self,
        state: ProgressState | None = None,
        *,
        spinner: str = "line",
        text: str = "",
        speed: float = 10.0,
        style: Style = FILL_STYLE,
        ascii_only: bool = False,
        reduced_motion: bool = False,
        name: WidgetId | None = None,
    ) -> None:
        super().__init__(state or ProgressState(), 40, 1, name=name, ascii_only=ascii_only)
        get_spinner(spinner)  # validate eagerly: KeyError lists the valid names
        if not speed > 0:
            raise ValueError(f"speed must be > 0 frames/s, got {speed!r}")
        self.spinner, self.text, self.speed, self.style = spinner, text, speed, style
        self.reduced_motion = reduced_motion
        self._clock_acc = 0.0

    def set_spinner(self, name: str) -> None:
        get_spinner(name)
        self.spinner = name

    def set_text(self, text: str) -> None:
        self.text = text

    def set_speed(self, speed: float) -> None:
        if not speed > 0:
            raise ValueError(f"speed must be > 0 frames/s, got {speed!r}")
        self.speed = speed

    def update(self, dt: float) -> None:
        self._clock_acc = (self._clock_acc + dt * self.speed) % 1_000_000.0

    @property
    def frame(self) -> str:
        frames = spinner_frames(self.spinner, self.ascii_only)
        return frames[0] if self.reduced_motion else frames[int(self._clock_acc) % len(frames)]

    def _label(self) -> str:
        return self.text or self.progress.description

    def plain_text(self) -> str:
        return self._label()

    def render(self, canvas: Canvas) -> None:
        col = canvas.write_text(0, 0, self.frame, self.style)
        label = self._label()
        if label:
            canvas.write_text(0, col + 1, _truncate(label, canvas.width - col - 1), DEFAULT_STYLE)


__all__ = [
    "CircularIndicator",
    "HorizontalBar",
    "ProgressIndicator",
    "SpinnerIndicator",
    "VerticalBar",
    "custom_bar_style",
    "format_number",
]
