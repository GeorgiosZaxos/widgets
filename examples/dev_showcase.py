"""Developer showcase: for every widget, the exact code (top) and the live result (bottom).

python examples/dev_showcase.py          n / p = next / previous widget, q = quit

The snippet shown is the snippet that runs: each entry is executed and its ``widget`` variable
is placed under the code. Copy a snippet into your own program to get the same widget.
(Network widgets - RSS and weather - need internet; see examples/net_gallery.py.)
"""

from __future__ import annotations

import textwrap

from widgets.base_elements.events import Event, KeyEvent
from widgets.base_elements.layout import Container, Screen
from widgets.base_elements.widget_types import Style
from widgets.data.code import CodeEditor
from widgets.display.marquee import Marquee
from widgets.render.run import run_app

WIDTH, HEIGHT, CODE_H = 110, 34, 14

SNIPPETS: list[tuple[str, str]] = [
    (
        "Box",
        """
        from widgets.display.box import Box
        widget = Box(0, 0, 40, 7, text="Hello, widgets", align="center",
                     valign="middle", border="rounded")""",
    ),
    (
        "Spinner",
        """
        from widgets.display.spinner import Spinner
        widget = Spinner(0, 0, 30, spinner="dots", text="working...")""",
    ),
    (
        "Marquee",
        """
        from widgets.display.marquee import Marquee
        widget = Marquee(0, 0, 40, 1, text="  breaking news  ", speed=8, direction="left")""",
    ),
    (
        "Marquee (snake)",
        """
        from widgets.display.marquee import Marquee
        widget = Marquee(0, 0, 30, 5, text="snake!", direction="snake", speed=14)""",
    ),
    (
        "AnimatedText",
        """
        from widgets.display.marquee import AnimatedText
        widget = AnimatedText(0, 0, 40, 3, text="wavy text", mode="wave")""",
    ),
    (
        "Neon",
        """
        from widgets.display.effects_widgets import Neon
        widget = Neon(0, 0, 60, 6, text="NEON", palette="rainbow", font="original-5",
                      outline=True)""",
    ),
    (
        "Sign / banner",
        """
        from widgets.display.effects_widgets import create_banner
        widget = create_banner("HELLO", width=44, mode="neon")""",
    ),
    (
        "MatrixRain (reveal)",
        """
        from widgets.display.effects_widgets import MatrixRain
        widget = MatrixRain(0, 0, 50, 10, text="WAKE UP", mode="reveal",
                            reveal_after=1.0, seed=1)""",
    ),
    (
        "MatrixRain (vt typing)",
        """
        from widgets.display.effects_widgets import MatrixRain
        widget = MatrixRain(0, 0, 50, 8, text="login: neo\\naccess granted", mode="vt", speed=10)""",
    ),
    (
        "VerticalPrint",
        """
        from widgets.display.vprint import VerticalPrint
        widget = VerticalPrint(0, 0, 5, 10, text="VERT", border="single")""",
    ),
    (
        "Gauge",
        """
        from widgets.display.gauge import Gauge
        widget = Gauge(0, 0, 21, 10, kind="speedometer", value=72, title="CPU", unit="%")""",
    ),
    (
        "Notifications",
        """
        from widgets.display.notify import NotificationCenter, NotificationType
        widget = NotificationCenter(0, 0, 40, 4)
        widget.post("File saved", NotificationType.SUCCESS)
        widget.post("Disk almost full", NotificationType.WARNING)""",
    ),
    (
        "Calendar",
        """
        from widgets.display.calendar import CalendarWidget
        widget = CalendarWidget(0, 0)""",
    ),
    (
        "Clock (big font)",
        """
        from widgets.display.calendar import ClockWidget
        widget = ClockWidget(0, 0, font="original-5")""",
    ),
    (
        "Space crawl",
        """
        from widgets.display.space import SpaceCrawlWidget
        widget = SpaceCrawlWidget(0, 0, 90, 17, intro="Long ago, in a quiet corner\\nof the network...",
                                  intro_time=3, loop=True, seed=2)""",
    ),
    (
        "Horizontal progress bar",
        """
        from widgets.progress.indicators import HorizontalBar
        from widgets.progress.state import ProgressState
        state = ProgressState(100, description="demo"); state.update(60)
        widget = HorizontalBar(state, 60,
                               bar_format="{desc} {percentage:3.0f}%|{bar}| {n_fmt}/{total_fmt}")""",
    ),
    (
        "Vertical progress bar",
        """
        from widgets.progress.indicators import VerticalBar
        from widgets.progress.state import ProgressState
        state = ProgressState(100); state.update(70)
        widget = VerticalBar(state, 10, orientation="center-out", animate="scan")""",
    ),
    (
        "Circular progress",
        """
        from widgets.progress.indicators import CircularIndicator
        from widgets.progress.state import ProgressState
        state = ProgressState(100); state.update(75)
        widget = CircularIndicator(state, 7)""",
    ),
    (
        "Table",
        """
        from widgets.data.table import Table
        widget = Table(0, 0, 70, 10, row_numbers=True)
        widget.load_csv("lang,year,stars\\nPython,1991,9000\\nRust,2010,7000\\nGo,2009,6000")""",
    ),
    (
        "Chart",
        """
        from widgets.data.chart import Chart, Dataset
        widget = Chart(0, 0, 70, 14, kind="bar", title="Monthly stats")
        widget.set_data([Dataset("visits", [30, 60, 45, 80], labels=["Jan", "Feb", "Mar", "Apr"])])""",
    ),
    (
        "Tree",
        """
        from widgets.data.tree import Tree, from_json
        widget = Tree(0, 0, 50, 12, root=from_json('{"app": {"src": ["a.py", "b.py"], "docs": []}}'))""",
    ),
    (
        "Form",
        """
        from widgets.data.form import Field, Form
        widget = Form(0, 0, 60, fields=[
            Field("name", "text", "Name", required=True),
            Field("age", "int", "Age", minimum=0, maximum=120),
            Field("agree", "checkbox", "Accept terms"),
            Field("colour", "dropdown", "Colour", options=["red", "green"], value="green")])""",
    ),
    (
        "Code editor",
        """
        from widgets.data.code import CodeEditor
        widget = CodeEditor(0, 0, 70, 12, text="def hello():\\n    return 'hi'\\n", language="python")""",
    ),
    (
        "Directory tree",
        """
        import os
        from widgets.data.dirtree import DirectoryTree
        widget = DirectoryTree(0, 0, 70, 14, root=os.getcwd())""",
    ),
    (
        "Metric dashboard",
        """
        import math, time
        from widgets.data.dashboard import MetricDashboard
        widget = MetricDashboard(0, 0, 46, 3, label="CPU", unit="%", interval=0.2,
                                 fetch=lambda: round(50 + 40 * math.sin(time.monotonic()), 1))""",
    ),
    (
        "Tabs",
        '\nfrom widgets.display.box import Box\nfrom widgets.display.tabs import Tabs\nwidget = Tabs(0, 0, 50, 7)\nwidget.add_page("Home", Box(text="Welcome", border="rounded"))\nwidget.add_page("Logs", Box(text="No errors", border="double"))\nwidget.add_page("Help", Box(text="ctrl+pagedown / alt+1..9", border="single"))\nwidget.next()',
    ),
    (
        "Split pane",
        '\nfrom widgets.display.box import Box\nfrom widgets.display.tabs import SplitPane\nwidget = SplitPane(0, 0, 60, 8, first=Box(text="left", border="single"),\n                   second=Box(text="right", border="rounded"), ratio=0.4)',
    ),
    (
        "Stepper",
        '\nfrom widgets.display.stepper import Stepper\nwidget = Stepper(0, 0, 70, steps=["Fetch", "Build", "Test", "Deploy"], current=2)',
    ),
    (
        "Sparkline",
        '\nimport math\nfrom widgets.display.stepper import Sparkline\nwidget = Sparkline(0, 0, 50, values=[50 + 40 * math.sin(i / 3) for i in range(50)],\n                   maximum=100, gradient="red_yellow_green")',
    ),
    (
        "Heatmap",
        '\nfrom widgets.display.stepper import Heatmap\ndata = [[(r * 7 + c * 3) % 10 for c in range(16)] for r in range(6)]\nwidget = Heatmap(0, 0, data=data, row_labels=["Mon", "Tue", "Wed", "Thu", "Fri", "Sat"],\n                 gradient="heat")',
    ),
    (
        "Log viewer",
        '\nfrom widgets.data.logview import LogViewer\nwidget = LogViewer(0, 0, 80, 9, show_time=False)\nfor i, level in enumerate(["INFO", "DEBUG", "WARNING", "ERROR", "INFO"] * 3):\n    widget.log(f"event {i}: something happened", level)',
    ),
    (
        "Command palette",
        '\nfrom widgets.display.palette import CommandPalette\nwidget = CommandPalette(0, 0, 50, 7, commands={\n    "Open file": lambda: "open", "Save file": lambda: "save",\n    "Toggle theme": lambda: "theme", "Quit application": lambda: "quit"})\nwidget.query = "fi"',
    ),
    (
        "Timer (pomodoro)",
        '\nfrom widgets.display.palette import TimerWidget\nwidget = TimerWidget(0, 0, 40, 7, mode="pomodoro", phases=[("focus", 1500), ("break", 300)])',
    ),
    (
        "Oscilloscope",
        "\nfrom widgets.audio.scope import Oscilloscope\nwidget = Oscilloscope(0, 0, 70, 8)   # pass source=lambda n: samples for real audio",
    ),
    (
        "Image view",
        '\nfrom widgets.display.image import ImageView\nwidget = ImageView.gradient(60, 20)   # ImageView.from_file("pic.png") needs pillow',
    ),
    (
        "Kanban board",
        '\nfrom widgets.data.kanban import KanbanBoard\nwidget = KanbanBoard(0, 0, 72, 10, columns={\n    "Todo": ["write docs", "fix bug #12"], "Doing": ["new widget"], "Done": ["release"]})',
    ),
    (
        "Markdown viewer",
        '\nfrom widgets.data.kanban import MarkdownView\ntext = "# Release notes\\n\\nNew **widgets** and `modes`.\\n\\n- tabs\\n- split pane\\n\\n> quote\\n\\n[docs](https://example.org)"\nwidget = MarkdownView(0, 0, 70, 12, text=text)',
    ),
    (
        "Process monitor",
        '\nimport random\nfrom widgets.data.procmon import ProcessMonitor\nfake = lambda: [{"pid": 100 + i, "name": f"proc{i}", "cpu": random.uniform(0, 30),\n                 "mem": random.uniform(0, 5)} for i in range(15)]\nwidget = ProcessMonitor(0, 0, 70, 12, fetch=fake, interval=0.5)   # default needs psutil',
    ),
    (
        "Grid game",
        "\nfrom widgets.display.game import GridGame\nwidget = GridGame(0, 0, 40, 10)   # arrows / wasd to move, r restarts",
    ),
    (
        "Equalizer",
        """
        from widgets.audio.player import Equalizer
        widget = Equalizer(0, 0, 60, 8, bands=24)
        widget.adjust_band(3, 0.5)   # per-band gain""",
    ),
]


def build(index: int) -> tuple[str, str, object]:
    title, source = SNIPPETS[index]
    code = textwrap.dedent(source).strip("\n")
    namespace: dict[str, object] = {}
    exec(code, namespace)  # the displayed code is exactly what runs
    return title, code, namespace["widget"]


def main() -> None:
    screen = Screen(WIDTH, HEIGHT)
    state = {"i": 0}
    current: list[Container] = []

    def show(index: int, live: bool = True) -> None:
        for old in current:
            screen.remove(old)
        current.clear()
        title, code, widget = build(index)
        page = Container(0, 0, WIDTH, HEIGHT, name=f"page{index}")
        header = f"[{index + 1}/{len(SNIPPETS)}] {title}   (n next, p prev, q quit)"
        page.add(Marquee(1, 0, WIDTH - 2, 1, text=header, speed=1, reduced_motion=True))
        editor = CodeEditor(1, 1, WIDTH - 2, CODE_H, text=code, language="python")
        page.add(editor)
        page.add(
            Marquee(
                1,
                CODE_H + 2,
                WIDTH - 2,
                1,
                text="Result:",
                speed=1,
                style=Style(dim=True),
                reduced_motion=True,
            )
        )
        widget.move(2, CODE_H + 3)  # type: ignore[attr-defined]
        page.add(widget)  # type: ignore[arg-type]
        screen.add(page)
        current.append(page)
        if live:
            page.mount()
            page.start()

    def on_event(event: Event) -> bool:
        if isinstance(event, KeyEvent) and event.key in ("n", "p"):
            state["i"] = (state["i"] + (1 if event.key == "n" else -1)) % len(SNIPPETS)
            show(state["i"])
            return True
        return False

    show(0, live=False)
    run_app(screen, on_event=on_event, quit_keys=("q",), title="widgets developer showcase")


if __name__ == "__main__":
    main()
