"""Tiny grid adventure widget. Layer L3."""

from __future__ import annotations

from collections.abc import Callable, Sequence

from widgets.base_elements.events import KeyEvent
from widgets.base_elements.interactive import InteractiveWidget
from widgets.base_elements.widget_types import RGB, Style, WidgetId
from widgets.render.buffer import Canvas

LEVEL = (
    "####################",
    "#@     #       *   #",
    "# #### # ##### ### #",
    "# #  # #     # #   #",
    "# #  # ##### # # # #",
    "# #  #     # # # # #",
    "# #  ##### # # # # #",
    "#   *     #   #   *#",
    "####################",
)
TILE_STYLE = {
    "#": Style(fg=RGB(120, 120, 140)),
    "@": Style(fg=RGB(255, 220, 90), bold=True),
    "*": Style(fg=RGB(120, 230, 255), bold=True),
    "E": Style(fg=RGB(120, 255, 140), bold=True),
}


class GridGame(InteractiveWidget):
    """Collect every ``*`` in a maze. Arrows / wasd move, ``r`` restarts.

    A viewport follows the player, so the map may be larger than the widget.
    """

    def __init__(
        self,
        x: int = 0,
        y: int = 0,
        width: int = 40,
        height: int = 12,
        *,
        level: Sequence[str] = LEVEL,
        on_win: Callable[[int], object] | None = None,
        name: WidgetId | None = None,
    ) -> None:
        super().__init__(x, y, width, height, name=name)
        self._source = list(level)
        if not any("@" in r for r in self._source):
            raise ValueError("level needs a player '@'")
        self.on_win = on_win
        self.restart()

    def restart(self) -> None:
        self.grid = [list(r) for r in self._source]
        self.px, self.py = next((r.index("@"), y) for y, r in enumerate(self._source) if "@" in r)
        self.grid[self.py][self.px] = " "
        self.total = sum(r.count("*") for r in self.grid)
        self.score = 0
        self.moves = 0
        self.won = False

    def step(self, dx: int, dy: int) -> bool:
        if self.won:
            return False
        nx, ny = self.px + dx, self.py + dy
        if (
            not (0 <= ny < len(self.grid) and 0 <= nx < len(self.grid[ny]))
            or self.grid[ny][nx] == "#"
        ):
            return False
        self.px, self.py = nx, ny
        self.moves += 1
        if self.grid[ny][nx] == "*":
            self.grid[ny][nx] = " "
            self.score += 1
            if self.score == self.total:
                self.won = True
                self.invoke_callback(self.on_win, self.moves)
        return True

    def handle_key(self, event: KeyEvent) -> bool:
        deltas = {
            "up": (0, -1),
            "down": (0, 1),
            "left": (-1, 0),
            "right": (1, 0),
            "w": (0, -1),
            "s": (0, 1),
            "a": (-1, 0),
            "d": (1, 0),
        }
        if event.key == "r":
            self.restart()
            return True
        if event.key in deltas:
            self.step(*deltas[event.key])
            return True
        return False

    def render(self, canvas: Canvas) -> None:
        w, h = canvas.width, max(1, canvas.height - 1)
        left = max(0, min(self.px - w // 2, max(0, len(self.grid[0]) - w)))
        top = max(0, min(self.py - h // 2, max(0, len(self.grid) - h)))
        for r in range(h):
            gy = top + r
            if gy >= len(self.grid):
                break
            for c in range(w):
                gx = left + c
                if gx >= len(self.grid[gy]):
                    break
                ch = "@" if (gx, gy) == (self.px, self.py) else self.grid[gy][gx]
                if ch != " ":
                    canvas.write_text(r, c, ch, TILE_STYLE.get(ch, Style()))
        status = "YOU WIN!" if self.won else f"gems {self.score}/{self.total}  moves {self.moves}"
        canvas.write_text(canvas.height - 1, 0, status, Style(bold=self.won, dim=not self.won))


__all__ = ["GridGame"]
