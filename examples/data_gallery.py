"""Live gallery of the M5 data widgets.

    python examples/data_gallery.py [--page N] [--duration S]

F1..F7 switch pages: table, chart, tree, form, directory tree, dashboard, code editor.
Each page's widget gets the keyboard: arrows/PgUp/PgDn/Home/End navigate; page specific keys are
shown in the footer.  F10 or Ctrl+Q quits.  (PyCharm: enable "Emulate terminal in output console".)
"""

from __future__ import annotations

import argparse
import math
import os
import random
import tempfile
import time
from pathlib import Path

from widgets.base_elements.base import Widget
from widgets.base_elements.events import Event, KeyEvent
from widgets.base_elements.interactive import InteractiveWidget
from widgets.base_elements.layout import Container, Screen
from widgets.base_elements.widget_types import RGB, Style
from widgets.data.chart import Chart, Dataset
from widgets.data.code import CodeEditor
from widgets.data.dashboard import MetricDashboard, TextDashboard
from widgets.data.dirtree import DirectoryTree
from widgets.data.form import Field, Form
from widgets.data.table import Table
from widgets.data.tree import Tree, from_json, from_xml
from widgets.render.buffer import Canvas
from widgets.render.run import run_app

W, H = 100, 30
PAGES = ["Table", "Chart", "Tree", "Form", "Files", "Dashboard", "Code"]
HINTS = [
    "arrows move | s sort by column",
    "c cycle chart kind | 1/2 toggle datasets",
    "arrows expand/collapse | enter select | x toggle JSON/XML",
    "type | tab/shift+tab/up/down move | space toggles | enter submits / opens dropdown",
    "arrows | enter expands | / filter | . hidden files | r refresh",
    "live data from a worker thread | p pause/resume",
    "type to edit | ctrl+z / ctrl+y undo/redo | ctrl+s saves to a temp file",
]
BAR = Style(fg=RGB(255, 255, 255), bg=RGB(40, 60, 140), bold=True)
HEAD = Style(bold=True, fg=RGB(255, 200, 60))

CSV = """name,language,stars,updated
widgets,Python,1200,2026-11-01
tqdm,Python,29000,2026-10-12
rich,Python,50000,2026-10-30
ratatui,Rust,12000,2026-11-03
bubbletea,Go,28000,2026-09-18
blessed,JavaScript,11000,2024-02-11
textual,Python,26000,2026-11-04
ncurses,C,
"""
JSON = '{"project": "widgets", "layers": {"L0": ["types", "errors"], "L1": ["terminal", "buffer"], "L2": ["base", "layout"]}, "tests": 323, "zero_deps": true}'
XML = '<project name="widgets"><layer id="L0"><module>types</module></layer><layer id="L1"><module>terminal</module></layer></project>'
SAMPLE = '''def fib(n):
    """Return the n-th Fibonacci number."""
    a, b = 0, 1
    for _ in range(n):
        a, b = b, a + b
    return a   # try editing me


print([fib(i) for i in range(10)], "done")
'''


class Label(Widget):
    def __init__(self, x: int, y: int, text: str, style: Style) -> None:
        super().__init__(x, y, len(text), 1)
        self.text, self.style = text, style

    def render(self, canvas: Canvas) -> None:
        canvas.write_text(0, 0, self.text, self.style)


class Bar(Widget):
    def __init__(self, y: int, kind: str) -> None:
        super().__init__(0, y, W, 1)
        self.kind, self.page, self.msg = kind, 0, ""

    def render(self, canvas: Canvas) -> None:
        if self.kind == "head":
            text = "  ".join(
                f"[F{i + 1}] {p}" if i == self.page else f" F{i + 1}  {p}"
                for i, p in enumerate(PAGES)
            )
            canvas.write_text(0, 0, text.ljust(canvas.width), BAR)
        else:
            text = f" {HINTS[self.page]}   {self.msg}   | F10 quit"
            canvas.write_text(0, 0, text.ljust(canvas.width), Style(dim=True))


def build() -> tuple[Screen, list[Container], list[Widget], Bar, Bar, dict[str, object]]:
    ctx: dict[str, object] = {}
    rng = random.Random(1)
    table = Table(2, 2, 96, 14, row_numbers=True, align=["left", "left", "right", "left"])
    table.load_csv(CSV, strict=False) if False else table.load_csv(
        CSV.replace("ncurses,C,\n", "ncurses,C,9000,2025-01-01\n")
    )
    chart = Chart(2, 2, 96, 20, kind="bar", title="Monthly stats")
    months = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug"]
    chart.set_data(
        [
            Dataset("visits", [rng.randint(20, 90) for _ in months], labels=months),
            Dataset("signups", [rng.randint(5, 50) for _ in months], labels=months),
        ]
    )
    ctx["chart"] = chart
    tree = Tree(2, 2, 60, 22, root=from_json(JSON))
    ctx["tree"] = tree
    form = Form(
        2,
        3,
        70,
        fields=[
            Field("name", "text", "Name", required=True, max_length=20),
            Field("age", "int", "Age", minimum=0, maximum=120),
            Field("score", "float", "Score", minimum=0, maximum=10),
            Field("agree", "checkbox", "Accept terms", required=True),
            Field("colour", "dropdown", "Colour", options=["red", "green", "blue"], value="green"),
        ],
    )
    result = Label(2, 10, "", Style(fg=RGB(120, 200, 120)))
    ctx["result"] = result

    def on_submit(v: object) -> None:
        result.text = f"submitted: {v}"[:96]
        result.width = 96

    form.on_submit = on_submit
    dirs = DirectoryTree(2, 2, 96, 24, root=os.getcwd())
    cpu = MetricDashboard(
        2,
        3,
        46,
        3,
        label="CPU",
        unit="%",
        interval=0.2,
        fetch=lambda: round(50 + 40 * math.sin(time.monotonic() * 0.8) + random.uniform(-5, 5), 1),
    )
    mem = MetricDashboard(
        52,
        3,
        46,
        3,
        label="Latency",
        unit=" ms",
        interval=0.3,
        fetch=lambda: round(
            80 + 30 * math.sin(time.monotonic() * 0.3) + random.uniform(-10, 10), 1
        ),
    )
    flaky_state = {"n": 0}

    def flaky() -> str:
        flaky_state["n"] += 1
        if flaky_state["n"] % 4 == 0:
            raise ConnectionError("upstream timed out")
        return f"poll #{flaky_state['n']} ok at {time.strftime('%H:%M:%S')}"

    status = TextDashboard(2, 9, 96, 3, interval=1.0, fetch=flaky)
    ctx["dash"] = [cpu, mem, status]
    editor = CodeEditor(2, 2, 96, 24, text=SAMPLE, language="python")
    editor.path = Path(tempfile.gettempdir()) / "widgets_demo.py"
    ctx["editor"] = editor
    pages: list[Container] = []
    interactive: list[Widget] = [table, chart, tree, form, dirs, cpu, editor]

    def page(*children: Widget) -> Container:
        c = Container(0, 1, W, H - 2)
        for child in children:
            c.add(child)
        pages.append(c)
        return c

    screen = Screen(W, H)
    page(Label(2, 1, "Sortable table loaded from CSV (empty cell = None sorts last)", HEAD), table)
    page(chart)
    page(
        Label(2, 1, "Tree from JSON (press x for XML; DOCTYPE/ENTITY would be rejected)", HEAD),
        tree,
    )
    page(
        Label(2, 1, "Form with validation (submit with an empty name to see errors)", HEAD),
        form,
        result,
    )
    page(Label(2, 1, f"Directory tree of {os.getcwd()}", HEAD), dirs)
    page(
        Label(2, 1, "Dashboards (worker threads; the last one fails every 4th poll)", HEAD),
        cpu,
        mem,
        status,
    )
    page(Label(2, 1, "Code editor with Python highlighting", HEAD), editor)
    head, foot = Bar(0, "head"), Bar(H - 1, "foot")
    for p in pages:
        screen.add(p)
    screen.add(head)
    screen.add(foot)
    return screen, pages, interactive, head, foot, ctx


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--page", type=int, default=1)
    parser.add_argument("--duration", type=float, default=None)
    args = parser.parse_args()
    screen, pages, interactive, head, foot, ctx = build()
    current = {"i": 0}
    chart: Chart = ctx["chart"]  # type: ignore[assignment]
    tree: Tree = ctx["tree"]  # type: ignore[assignment]
    kinds = ["bar", "line", "area", "scatter", "pie"]

    def show(i: int) -> None:
        current["i"] = i
        for k, p in enumerate(pages):
            p.visible = k == i
        head.page = foot.page = i
        for k, w in enumerate(interactive):
            if isinstance(w, InteractiveWidget):
                w.blur() if k != i else w.focus()

    show(max(0, min(len(pages) - 1, args.page - 1)))

    def on_event(event: Event) -> None:
        if not isinstance(event, KeyEvent):
            return
        i = current["i"]
        if (
            event.key.startswith("f")
            and event.key[1:].isdigit()
            and 1 <= int(event.key[1:]) <= len(pages)
        ):
            show(int(event.key[1:]) - 1)
            return
        if i == 1 and event.key in ("c", "1", "2"):
            if event.key == "c":
                chart.kind = kinds[(kinds.index(chart.kind) + 1) % len(kinds)]
                chart.title = f"Monthly stats ({chart.kind})"
            else:
                chart.toggle(["visits", "signups"][int(event.key) - 1])
            return
        if i == 2 and event.key == "x":
            tree.root = (
                from_xml(XML)
                if tree.root.label.startswith("project") and not tree.root.label.startswith("<")
                else from_json(JSON)
            )
            tree.root.expanded = True
            return
        if i == 5 and event.key == "p":
            for w in ctx["dash"]:  # type: ignore[attr-defined]
                (w.resume if w.state.name == "PAUSED" else w.pause)()
            return
        interactive[i].handle_key(event)
        foot.msg = str(getattr(interactive[i], "message", ""))[:60]

    run_app(
        screen,
        fps=30,
        duration=args.duration,
        quit_keys=("ctrl+q", "f10"),
        on_event=on_event,
        title="widgets data gallery",
    )


if __name__ == "__main__":
    main()
