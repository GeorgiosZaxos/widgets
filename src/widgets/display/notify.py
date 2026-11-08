"""Notification centre (FR-NOTIFY-001..004). Layer L3."""

from __future__ import annotations

import enum
import itertools
import threading
from dataclasses import dataclass, field

from widgets.base_elements.base import Widget
from widgets.base_elements.effects import (
    Clock,
    MonotonicClock,
    reduced_motion_enabled,
    require_positive,
)
from widgets.base_elements.widget_types import RGB, Style, WidgetId
from widgets.display._common import clip_cells
from widgets.render.buffer import Canvas


class NotificationType(enum.Enum):
    """Notification severities; each has a text prefix so colour is never the only cue."""

    INFO = ("i", "[INFO]", RGB(80, 160, 255))
    SUCCESS = ("✓", "[OK]", RGB(60, 200, 90))
    WARNING = ("!", "[WARN]", RGB(240, 190, 40))
    ERROR = ("✗", "[ERROR]", RGB(230, 70, 70))
    CUSTOM = ("•", "[NOTE]", RGB(200, 200, 200))


@dataclass(slots=True)
class Notification:
    id: int
    message: str
    type: NotificationType
    created: float
    expires_at: float
    icon: str | None = None
    timestamp: str | None = None
    extra: dict[str, object] = field(default_factory=dict)

    def prefix(self, ascii_only: bool = False) -> str:
        glyph, tag, _ = self.type.value
        icon = self.icon or glyph
        return tag if ascii_only or not icon.strip() else f"{icon} {tag}"


class NotificationCenter(Widget):
    """Thread-safe queue of timed notifications with a bounded size."""

    def __init__(
        self,
        x: int = 0,
        y: int = 0,
        width: int = 40,
        height: int = 5,
        *,
        placement: str = "top",
        default_duration: float = 5.0,
        max_queue: int = 50,
        overflow: str = "drop_oldest",
        max_visible: int | None = None,
        clock: Clock | None = None,
        fade: bool = True,
        ascii_only: bool = False,
        reduced_motion: bool | None = None,
        name: WidgetId | None = None,
    ) -> None:
        super().__init__(x, y, width, height, name=name)
        if placement not in ("top", "bottom"):
            raise ValueError("placement must be 'top' or 'bottom'")
        if overflow not in ("drop_oldest", "drop_newest"):
            raise ValueError("overflow must be 'drop_oldest' or 'drop_newest'")
        if max_queue < 1:
            raise ValueError("max_queue must be >= 1")
        self.placement, self.overflow, self.max_queue = placement, overflow, max_queue
        self.default_duration = require_positive("default_duration", default_duration)
        self.max_visible = max_visible or height
        self.fade, self.ascii_only = fade, ascii_only
        self.reduced_motion = reduced_motion_enabled(override=reduced_motion)
        self._clock = clock or MonotonicClock()
        self._lock = threading.Lock()
        self._items: list[Notification] = []
        self._ids = itertools.count(1)

    def post(
        self,
        message: str,
        type: NotificationType = NotificationType.INFO,
        *,
        duration: float | None = None,
        expires_at: float | None = None,
        icon: str | None = None,
        timestamp: str | None = None,
    ) -> int | None:
        """Queue a notification (thread-safe); returns its id, or ``None`` if dropped."""
        now = self._clock.now()
        deadline = (
            expires_at if expires_at is not None else now + (duration or self.default_duration)
        )
        with self._lock:
            if len(self._items) >= self.max_queue:
                if self.overflow == "drop_newest":
                    return None
                self._items.pop(0)
            nid = next(self._ids)
            self._items.append(Notification(nid, message, type, now, deadline, icon, timestamp))
            return nid

    def dismiss(self, nid: int) -> bool:
        with self._lock:
            before = len(self._items)
            self._items = [n for n in self._items if n.id != nid]
            return len(self._items) != before

    def dismiss_all(self) -> None:
        with self._lock:
            self._items.clear()

    def _prune(self) -> None:
        now = self._clock.now()
        with self._lock:
            self._items = [n for n in self._items if n.expires_at > now]

    def update(self, dt: float) -> None:
        self._prune()

    @property
    def active(self) -> list[Notification]:
        self._prune()
        with self._lock:
            return list(self._items)

    def render(self, canvas: Canvas) -> None:
        now = self._clock.now()
        visible = self.active[: min(self.max_visible, canvas.height)]
        for i, n in enumerate(visible):
            row = i if self.placement == "top" else canvas.height - len(visible) + i
            remaining = n.expires_at - now
            dim = self.fade and not self.reduced_motion and remaining < 0.5
            text = clip_cells(f"{n.prefix(self.ascii_only)} {n.message}", canvas.width)
            canvas.write_text(
                row, 0, text.ljust(canvas.width), Style(fg=n.type.value[2], dim=dim, reverse=False)
            )

    def describe(self) -> str:
        return f"NotificationCenter({len(self.active)} active, {self.placement})"
