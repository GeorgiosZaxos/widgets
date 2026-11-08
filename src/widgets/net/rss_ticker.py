"""Multi-lane RSS news ticker (extends FR-RSS-* and FR-MARQUEE-*). Layer L3.

One scrolling line per feed; every lane has its own direction, speed and colour.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from widgets.base_elements.color_manager import get_gradient, parse_color
from widgets.base_elements.events import KeyEvent
from widgets.base_elements.interactive import InteractiveWidget
from widgets.base_elements.widget_types import RGB, Rect, Style, WidgetId
from widgets.display.marquee import Marquee
from widgets.net.http import DEFAULT_MAX_BYTES, HttpTransport
from widgets.net.rss import FeedSource, RssReader
from widgets.render.buffer import Canvas

PALETTE = ("#ff5f5f", "#5fd7ff", "#ffd75f", "#87ff87", "#d787ff", "#ff9f43")


@dataclass(frozen=True, slots=True)
class TickerLane:
    """One ticker line: a feed plus how it scrolls and how it looks."""

    source: FeedSource
    direction: str = "left"  # "left" = right-to-left reading flow, "right" = left-to-right
    speed: float = 8.0  # cells per second
    color: str | RGB | None = None  # None -> picked from PALETTE by lane index
    gradient: str | None = None  # optional palette name; overrides ``color`` per character
    separator: str = "   •   "
    label: bool = True  # show "name" fixed at the lane's start


class RssTicker(InteractiveWidget):
    """Several RSS feeds as parallel marquee lines.

    Keys: up/down select a lane, ``+``/``-`` change the selected lane's speed, ``[``/``]``
    scale all lanes, space pause, ``r`` refresh, ``d`` reverse every lane.
    """

    def __init__(
        self,
        x: int = 0,
        y: int = 0,
        width: int = 80,
        *,
        lanes: Sequence[TickerLane] = (),
        transport: HttpTransport | None = None,
        spacing: int = 0,
        max_items: int = 30,
        refresh_interval: float = 300.0,
        timeout: float = 10.0,
        max_response_bytes: int = DEFAULT_MAX_BYTES,
        show_speed: bool = False,
        name: WidgetId | None = None,
    ) -> None:
        if not lanes:
            raise ValueError("at least one lane is required")
        if spacing < 0 or max_items < 1 or refresh_interval <= 0:
            raise ValueError("invalid ticker options")
        for ln in lanes:
            if ln.direction not in ("left", "right"):
                raise ValueError("lane direction must be 'left' or 'right'")
            if ln.speed <= 0:
                raise ValueError("lane speed must be > 0")
        height = len(lanes) * (1 + spacing) - spacing
        super().__init__(x, y, width, height, name=name)
        self.lanes = list(lanes)
        self.spacing, self.max_items, self.refresh_interval = spacing, max_items, refresh_interval
        self.paused = False
        self.show_speed = show_speed
        self.selected = 0
        self._scale = 1.0
        self._since_refresh = refresh_interval  # fetch on the first update
        self._reader = RssReader(
            0,
            0,
            width,
            3,
            sources=[ln.source for ln in lanes],
            transport=transport,
            min_refresh_interval=0.0,
            max_items_per_feed=max_items,
            timeout=timeout,
            max_response_bytes=max_response_bytes,
        )
        self._marquees: list[Marquee] = []
        for i, ln in enumerate(lanes):
            color = parse_color(ln.color if ln.color is not None else PALETTE[i % len(PALETTE)])
            grad = get_gradient(ln.gradient) if ln.gradient else None
            self._marquees.append(
                Marquee(
                    0,
                    0,
                    width,
                    1,
                    direction=ln.direction,
                    speed=ln.speed,
                    gap=0,
                    style=Style(fg=color),
                    gradient=grad,
                )
            )

    # -- content -----------------------------------------------------------------------------
    def lane_text(self, index: int) -> str:
        """The text currently scrolling in lane ``index``."""
        lane = self.lanes[index]
        state = next((f for f in self._reader.feeds if f.source == lane.source), None)
        prefix = f"{lane.source.name} ▸ " if lane.label else ""
        if state is None or (not state.items and state.loading):
            return prefix + "loading…"
        if not state.items:
            return prefix + (f"error: {state.error}" if state.error else "no items")
        body = lane.separator.join(i.title for i in state.items[: self.max_items])
        return prefix + body + lane.separator

    @property
    def speed_scale(self) -> float:
        return self._scale

    def set_speed_scale(self, scale: float) -> None:
        if scale <= 0:
            raise ValueError("scale must be > 0")
        self._scale = scale
        for ln, m in zip(self.lanes, self._marquees, strict=True):
            m.set_speed(ln.speed * scale)

    def lane_speed(self, index: int) -> float:
        """Current speed of lane ``index`` in cells per second."""
        return self._marquees[index].speed

    def set_lane_speed(self, index: int, speed: float) -> None:
        if speed <= 0:
            raise ValueError("speed must be > 0")
        self._marquees[index].set_speed(speed)

    def adjust_lane_speed(self, index: int, factor: float) -> float:
        new = min(200.0, max(0.5, self.lane_speed(index) * factor))
        self.set_lane_speed(index, new)
        return new

    def refresh(self) -> int:
        self._since_refresh = 0.0
        return self._reader.refresh(force=True)

    def reverse(self) -> None:
        for m in self._marquees:
            m.direction = "right" if m.direction == "left" else "left"

    # -- lifecycle ---------------------------------------------------------------------------------
    def update(self, dt: float) -> None:
        self._since_refresh += dt
        if self._since_refresh >= self.refresh_interval:
            self.refresh()
        self._reader.update(dt)
        if not self.paused:
            for m in self._marquees:
                m.update(dt)

    def on_close(self) -> None:
        self._reader.on_close()

    def handle_key(self, event: KeyEvent) -> bool:
        if not self.effective_enabled:
            return False
        key = event.key
        if key in ("+", "="):
            self.adjust_lane_speed(self.selected, 1.25)
        elif key in ("-", "_"):
            self.adjust_lane_speed(self.selected, 0.8)
        elif key == "]":
            for i in range(len(self.lanes)):
                self.adjust_lane_speed(i, 1.25)
        elif key == "[":
            for i in range(len(self.lanes)):
                self.adjust_lane_speed(i, 0.8)
        elif key == "up":
            self.selected = (self.selected - 1) % len(self.lanes)
        elif key == "down":
            self.selected = (self.selected + 1) % len(self.lanes)
        elif key == "space":
            self.paused = not self.paused
        elif key == "r":
            self.refresh()
        elif key == "d":
            self.reverse()
        else:
            return False
        return True

    def render(self, canvas: Canvas) -> None:
        w = canvas.width
        for i, m in enumerate(self._marquees):
            m.resize(w, 1)
            m.text = self.lane_text(i)
            row = i * (1 + self.spacing)
            if self.show_speed:
                tag = f" {'>' if i == self.selected else ' '}{m.speed:5.1f}/s"
                m.resize(max(1, w - len(tag)), 1)
                m.draw(canvas.view(Rect(0, row, max(1, w - len(tag)), 1)))
                canvas.write_text(
                    row, w - len(tag), tag, Style(dim=i != self.selected, bold=i == self.selected)
                )
            else:
                m.draw(canvas.view(Rect(0, row, w, 1)))

    def describe(self) -> str:
        return f"RssTicker({len(self.lanes)} lanes{', paused' if self.paused else ''})"
