"""Command palette (fuzzy launcher) and big-font timer. Layer L3."""

from __future__ import annotations

from collections.abc import Callable, Mapping

from widgets.assets.fonts import render_text
from widgets.base_elements.events import KeyEvent
from widgets.base_elements.interactive import InteractiveWidget
from widgets.base_elements.widget_types import RGB, Style, WidgetId
from widgets.display._common import Animated, clip_cells
from widgets.render.buffer import Canvas


def fuzzy_score(query: str, text: str) -> int | None:
    """Subsequence match score (higher is better); ``None`` when ``query`` does not match."""
    if not query:
        return 0
    q, t = query.lower(), text.lower()
    pos, score, prev = 0, 0, -2
    for ch in q:
        found = t.find(ch, pos)
        if found < 0:
            return None
        score += 10 - min(9, found - pos)
        if found == prev + 1:
            score += 5
        if found == 0 or t[found - 1] in " -_/":
            score += 8
        pos, prev = found + 1, found
    return score - len(t) // 8


class CommandPalette(InteractiveWidget):
    """Type to filter commands, up/down to choose, enter to run, escape to close."""

    def __init__(
        self,
        x: int = 0,
        y: int = 0,
        width: int = 50,
        height: int = 10,
        *,
        commands: Mapping[str, Callable[[], object]],
        on_close: Callable[[], object] | None = None,
        name: WidgetId | None = None,
    ) -> None:
        super().__init__(x, y, width, height, name=name)
        self.commands = dict(commands)
        self.query = ""
        self.index = 0
        self.last_result: object = None
        self.closed_callback = on_close

    def matches(self) -> list[str]:
        scored = [(fuzzy_score(self.query, n), n) for n in self.commands]
        return [
            n
            for s, n in sorted(
                (p for p in scored if p[0] is not None), key=lambda p: (-(p[0] or 0), p[1])
            )
        ]

    def run(self) -> bool:
        found = self.matches()
        if not found:
            return False
        self.last_result = self.commands[found[min(self.index, len(found) - 1)]]()
        return True

    def handle_key(self, event: KeyEvent) -> bool:
        key = event.key
        if key == "enter":
            return self.run()
        if key == "escape":
            self.invoke_callback(self.closed_callback)
            return True
        if key in ("up", "down"):
            self.index = max(
                0, min(max(0, len(self.matches()) - 1), self.index + (1 if key == "down" else -1))
            )
            return True
        if key == "backspace":
            self.query = self.query[:-1]
            self.index = 0
            return True
        if event.char and not event.ctrl and not event.alt and event.char.isprintable():
            self.query += event.char
            self.index = 0
            return True
        return False

    def render(self, canvas: Canvas) -> None:
        canvas.write_text(0, 0, clip_cells("> " + self.query + "▏", canvas.width), Style(bold=True))
        for i, cmd in enumerate(self.matches()[: max(0, canvas.height - 1)]):
            marker = "›" if i == self.index else " "
            style = Style(reverse=True) if i == self.index else Style()
            canvas.write_text(
                i + 1, 0, clip_cells(f"{marker} {cmd}", canvas.width).ljust(canvas.width), style
            )


class TimerWidget(Animated):
    """Stopwatch or countdown in a big font; pomodoro via ``phases``.

    ``phases`` is a list of ``(label, seconds)`` that run one after another (e.g.
    ``[("focus", 1500), ("break", 300)]``); ``on_finish`` fires once at the end.
    """

    def __init__(
        self,
        x: int = 0,
        y: int = 0,
        width: int = 40,
        height: int = 7,
        *,
        font: str = "original-5",
        mode: str = "stopwatch",
        duration: float = 60.0,
        phases: list[tuple[str, float]] | None = None,
        on_finish: Callable[[], object] | None = None,
        autostart: bool = True,
        reduced_motion: bool | None = None,
        name: WidgetId | None = None,
    ) -> None:
        super().__init__(x, y, width, height, reduced_motion=reduced_motion, name=name)
        if mode not in ("stopwatch", "countdown", "pomodoro"):
            raise ValueError("mode must be stopwatch, countdown or pomodoro")
        self.font, self.mode, self.on_finish = font, mode, on_finish
        self.autostart = autostart
        self.phases = phases or (
            [("work", duration)] if mode != "pomodoro" else [("focus", 1500.0), ("break", 300.0)]
        )
        self.elapsed = 0.0
        self.running = False
        self.finished = False

    def on_start(self) -> None:
        self.running = self.autostart

    def pause_timer(self) -> None:
        self.running = False

    def resume_timer(self) -> None:
        self.running = True

    def reset(self) -> None:
        self.elapsed, self.finished = 0.0, False

    def advance(self, dt: float) -> None:
        if not self.running or self.finished:
            return
        self.elapsed += dt
        if self.mode != "stopwatch" and self.elapsed >= sum(s for _l, s in self.phases):
            self.elapsed = sum(s for _l, s in self.phases)
            self.finished, self.running = True, False
            self.invoke_callback(self.on_finish)

    def phase(self) -> tuple[str, float]:
        """``(label, seconds left in the phase)`` for countdown modes."""
        left = self.elapsed
        for label, seconds in self.phases:
            if left < seconds:
                return label, seconds - left
            left -= seconds
        return self.phases[-1][0], 0.0

    def clock_text(self) -> str:
        value = self.elapsed if self.mode == "stopwatch" else self.phase()[1]
        total = int(value)
        return f"{total // 60:02d}:{total % 60:02d}"

    def render(self, canvas: Canvas) -> None:
        rows = render_text(self.clock_text(), self.font)
        colour = RGB(90, 220, 140) if self.running else RGB(230, 190, 80)
        if self.finished:
            colour = RGB(245, 90, 90)
        for r, row in enumerate(rows[: canvas.height - 1]):
            canvas.write_text(r, 0, row, Style(fg=colour, bold=True))
        label = self.phase()[0] if self.mode != "stopwatch" else "stopwatch"
        state = "done" if self.finished else ("running" if self.running else "paused")
        canvas.write_text(
            min(len(rows), canvas.height - 1), 0, f"{label} - {state}", Style(dim=True)
        )


__all__ = ["CommandPalette", "TimerWidget", "fuzzy_score"]
