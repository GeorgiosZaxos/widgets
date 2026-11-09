"""Generate docs/MANUAL.md from the live code (signatures) plus tools/manual_content.py.

    python tools/gen_manual.py            # write docs/MANUAL.md
    python tools/gen_manual.py --strict   # fail if any public parameter has no description
    python tools/gen_manual.py --check    # also execute every example headlessly

Because parameter tables come from ``inspect.signature``, the manual cannot silently drift from the
code: a new parameter without a description makes ``--strict`` fail (run it in CI).
"""

from __future__ import annotations

import importlib
import inspect
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

import manual_content as mc  # type: ignore[import-not-found,unused-ignore]
import widgets

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "docs" / "MANUAL.md"

TQDM_PARAMS = {
    "iterable": "Iterable to wrap. Omit it and drive the bar manually with `update()` (needs `total`).",
    "desc": "Prefix text (`desc: 42%|...`).",
    "total": "Expected number of iterations; default `len(iterable)`. `None`/unknown shows only a counter and rate.",
    "leave": "Keep the finished bar on screen (`True`) or erase it (`False`).",
    "file": "Output stream (default `sys.stderr`).",
    "ncols": "Total width in columns; the bar shrinks to fit. Default: terminal width.",
    "mininterval": "Minimum seconds between redraws (default 0.1).",
    "miniters": "Minimum iterations between redraws (default: automatic).",
    "disable": "`True` turns the bar into a silent pass-through; `None` disables it when the output is not a TTY.",
    "unit": "Unit name (`'it'`, `'B'`, `'files'`).",
    "unit_scale": "`True`/number: SI-scale counts and rates (`1.5k`, `2.3MB/s`).",
    "dynamic_ncols": "Re-read the terminal width on every redraw.",
    "smoothing": "Exponential-average factor for speed/ETA (0 = average since start, 1 = instantaneous).",
    "initial": "Initial counter value (resume a partially finished job).",
    "position": "Row offset for several concurrent bars (0 = first). Vertical bars of `vtqdm` share lines by group instead.",
    "postfix": "Extra statistics: a dict (`{'loss': 0.3}`) or string shown after the rate.",
    "bar_format": "Custom layout string (fields: `{l_bar}{bar}{r_bar}`, `{bar:N}`, `{n_fmt}`, `{total_fmt}`, `{percentage:3.0f}`, `{elapsed}`, `{remaining}`, `{rate_fmt}`, `{desc}`, `{postfix}`, `{unit}`).",
    "unit_divisor": "1000 (SI) or 1024 (binary) for `unit_scale`.",
    "delay": "Seconds to wait before the bar first appears (short jobs never flash a bar).",
    "write_bytes": "Accepted for compatibility; output is always text.",
    "manager": "A `ProgressManager` to draw into (default: shared per stream). Use your own to isolate bars.",
    "maxinterval": "Accepted for compatibility (monitor-thread interval in real tqdm).",
    "ascii": "`True` = ASCII bar (`#`); a string = the fill characters from empty to full (`' 123456789#'`).",
    "lock_args": "Accepted for compatibility.",
    "nrows": "Limit on the number of rows used by the bar region.",
    "colour": "Bar colour: name (`'green'`), `'#rrggbb'`.",
    "gui": "Accepted for compatibility (no separate window).",
    "style": "*widgets extra.* Bar style name from `list_bar_styles()`.",
    "fill": "*widgets extra.* Single character used for the filled part (`'#'`, `'■'`).",
    "empty": "*widgets extra.* Character used for the unfilled part.",
    "gradient": "*widgets extra.* Colours along the bar: list like `['#ff0000', '#00ff00']` or a `Gradient`.",
    "spinner": "*widgets extra.* Spinner name (`'dots'`, `'pulse'`, ...) drawn in front of the bar.",
    "empty_colour": "*widgets extra.* Colour of the unfilled part.",
    "kwargs": "Extra keyword arguments (unknown keys raise `TqdmKeyError`, like real tqdm).",
    "height": "*vtqdm only.* Bar height in rows (default 8).",
    "args": "Same positional arguments as `tqdm`.",
}

CHAPTERS: list[tuple[str, list[tuple[str, str]]]] = [
    (
        "Display widgets",
        [
            (m, n)
            for m, n in [
                ("display", "Box"),
                ("display", "Spinner"),
                ("display", "SpinnerGroup"),
                ("display", "Marquee"),
                ("display", "AnimatedText"),
                ("display", "Sign"),
                ("display", "Neon"),
                ("display", "MatrixRain"),
                ("display", "Gauge"),
                ("display", "Sparkline"),
                ("display", "Heatmap"),
                ("display", "Stepper"),
                ("display", "Tabs"),
                ("display", "SplitPane"),
                ("display", "NotificationCenter"),
                ("display", "CalendarWidget"),
                ("display", "ClockWidget"),
                ("display", "Countdown"),
                ("display", "TimerWidget"),
                ("display", "CommandPalette"),
                ("display", "GridGame"),
                ("display", "ImageView"),
                ("display", "QrView"),
                ("display", "VerticalPrint"),
                ("display", "SpaceCrawlWidget"),
            ]
        ],
    ),
    (
        "Progress indicators",
        [
            (m, n)
            for m, n in [
                ("progress", "ProgressState"),
                ("progress", "HorizontalBar"),
                ("progress", "VerticalBar"),
                ("progress", "CircularIndicator"),
                ("progress", "SpinnerIndicator"),
                ("progress", "VerticalTqdmBar"),
                ("progress", "ProgressManager"),
            ]
        ],
    ),
    (
        "Data widgets",
        [
            (m, n)
            for m, n in [
                ("data", "Table"),
                ("data", "Chart"),
                ("data", "Tree"),
                ("data", "CodeEditor"),
                ("data", "Form"),
                ("data", "DirectoryTree"),
                ("data", "LogViewer"),
                ("data", "KanbanBoard"),
                ("data", "MarkdownView"),
                ("data", "ProcessMonitor"),
                ("data", "DashboardGrid"),
                ("data", "DashboardWidget"),
                ("data", "MetricDashboard"),
                ("data", "TextDashboard"),
            ]
        ],
    ),
    (
        "Network widgets",
        [
            (m, n)
            for m, n in [
                ("net", "RssTicker"),
                ("net", "TickerLane"),
                ("net", "RssReader"),
                ("net", "WeatherWidget"),
            ]
        ],
    ),
    (
        "Audio widgets",
        [
            (m, n)
            for m, n in [
                ("audio", "MusicPlayer"),
                ("audio", "Equalizer"),
                ("audio", "Oscilloscope"),
                ("audio", "SynchronizedPlayer"),
                ("audio", "NullBackend"),
                ("audio", "SubprocessBackend"),
                ("audio", "WinsoundBackend"),
                ("audio", "SpectrumAnalyzer"),
            ]
        ],
    ),
]

missing: list[str] = []
_NAMES: dict[str, str] = {}


def _build_names() -> None:
    import pkgutil

    for pkg in ("display", "data", "net", "audio", "progress"):
        p = importlib.import_module(f"widgets.{pkg}")
        for mi in pkgutil.iter_modules(p.__path__):
            m = importlib.import_module(f"widgets.{pkg}.{mi.name}")
            for n, o in vars(m).items():
                if n.startswith("_") or getattr(o, "__module__", None) != m.__name__:
                    continue
                _NAMES.setdefault(n, f"widgets.{pkg}.{mi.name}")


def fix_imports(code: str) -> str:
    """Rewrite ``from widgets... import X`` lines to the module that really defines X."""
    import re

    if not _NAMES:
        _build_names()
    out: list[str] = []
    for line in code.split("\n"):
        m = re.match(r"^from (widgets[\w.]*) import (.+)$", line)
        if not m or m.group(1).startswith("widgets.progress"):
            out.append(line)
            continue
        groups: dict[str, list[str]] = {}
        for name in (n.strip() for n in m.group(2).split(",")):
            target = "widgets" if hasattr(widgets, name) else _NAMES.get(name, m.group(1))
            groups.setdefault(target, []).append(name)
        out.extend(f"from {mod} import {', '.join(names)}" for mod, names in groups.items())
    return "\n".join(out)


def find_class(pkg: str, name: str) -> Any:
    import pkgutil

    p = importlib.import_module(f"widgets.{pkg}")
    if hasattr(p, name):
        return getattr(p, name)
    for mi in pkgutil.iter_modules(p.__path__):
        m = importlib.import_module(f"widgets.{pkg}.{mi.name}")
        if hasattr(m, name):
            return getattr(m, name)
    raise LookupError(f"{pkg}.{name}")


def fmt_default(p: inspect.Parameter) -> str:
    if p.default is inspect.Parameter.empty:
        return "**required**"
    d = p.default
    text = repr(d)
    if len(text) > 60:
        text = text[:57] + "..."
    return f"`{text.replace('|', chr(92) + '|')}`"


def fmt_type(p: inspect.Parameter) -> str:
    a = p.annotation
    if a is inspect.Parameter.empty:
        return ""
    s = a if isinstance(a, str) else getattr(a, "__name__", str(a))
    return "`" + s.replace("|", "\\|") + "`"


def param_table(cls_name: str, cls: Any, extra: dict[str, str] | None = None) -> list[str]:
    lines = ["| Parameter | Type | Default | Meaning |", "|---|---|---|---|"]
    try:
        sig = inspect.signature(cls)
    except (TypeError, ValueError):
        return ["_No constructor parameters._"]
    for pname, p in sig.parameters.items():
        if pname == "self":
            continue
        doc = (
            (extra or {}).get(pname) or mc.PARAMS.get(f"{cls_name}.{pname}") or mc.COMMON.get(pname)
        )
        if not doc:
            missing.append(f"{cls_name}.{pname}")
            doc = "*(undocumented)*"
        star = "*" if p.kind is p.VAR_POSITIONAL else "**" if p.kind is p.VAR_KEYWORD else ""
        lines.append(f"| `{star}{pname}` | {fmt_type(p)} | {fmt_default(p)} | {doc} |")
    return lines


def methods_table(cls: Any) -> list[str]:
    from widgets.base_elements.base import Widget

    base = set(dir(Widget))
    rows = []
    for mn, mo in vars(cls).items():
        if mn.startswith("_") or mn in base:
            continue
        if isinstance(mo, property):
            first = (inspect.getdoc(mo) or "").split("\n")[0]
            rows.append(f"| `{mn}` | property | {first} |")
        elif isinstance(mo, (classmethod, staticmethod)) or inspect.isfunction(mo):
            f = mo.__func__ if isinstance(mo, (classmethod, staticmethod)) else mo
            try:
                s = (
                    str(inspect.signature(f))
                    .replace("self, ", "")
                    .replace("(self)", "()")
                    .replace("cls, ", "")
                )
            except (TypeError, ValueError):
                s = "(...)"
            first = (inspect.getdoc(f) or "").split("\n")[0]
            s = s.replace("|", "\\|")
            rows.append(f"| `{mn}{s}` |  | {first} |")
    if not rows:
        return []
    return [
        "**Methods and properties**",
        "",
        "| Member | Kind | Notes |",
        "|---|---|---|",
        *rows,
        "",
    ]


def class_section(pkg: str, name: str, level: str = "###") -> list[str]:
    cls = find_class(pkg, name)
    out = [f"{level} {name}", ""]
    doc = inspect.getdoc(cls) or ""
    if doc and not doc.startswith(f"{name}("):
        out += [doc, ""]
    importline = (
        f"`from widgets.{pkg} import {name}`"
        if not hasattr(widgets, name)
        else f"`from widgets import {name}`"
    )
    out += [f"Import: {importline}", ""]
    if name in mc.NOTES:
        out += [mc.NOTES[name], ""]
    out += ["**Parameters**", "", *param_table(name, cls), ""]
    out += methods_table(cls)
    for title, code in mc.EXAMPLES.get(name, []):
        out += [f"**Example - {title}**", "", "```python", fix_imports(code), "```", ""]
    return out


def tqdm_section() -> list[str]:
    from widgets.progress.tqdm import tqdm

    out = [
        "## tqdm and vtqdm (drop-in progress bars)",
        "",
        "`widgets.tqdm` is a horizontal bar and `widgets.vtqdm` a vertical bar. Both accept **every** argument of real "
        "tqdm, so `from widgets import tqdm` (or `vtqdm as tqdm`) replaces `from tqdm import tqdm` without other changes.",
        "",
        "### Constructor parameters",
        "",
        *param_table("tqdm", tqdm, TQDM_PARAMS),
        "",
        "`vtqdm(*args, height=8, **kwargs)` takes the same arguments plus `height`. Vertical bars drawn in a loop share the "
        "same terminal lines and sit side by side (up to the terminal width, then they wrap into bands).",
        "",
        "### Methods",
        "",
        *methods_table(tqdm)[2:],
        "",
    ]
    snippets = [
        (
            "Basic loop",
            'import time\nfrom widgets import tqdm\n\nfor i in tqdm(range(100), desc="work"):\n    time.sleep(0.02)',
        ),
        (
            "Manual updates with units",
            'from widgets import tqdm\n\nwith tqdm(total=5_000_000, unit="B", unit_scale=True, unit_divisor=1024, desc="download") as bar:\n    for _ in range(50):\n        bar.update(100_000)',
        ),
        (
            "Postfix and description",
            'import time\nfrom widgets import tqdm\n\nbar = tqdm(range(50), desc="train")\nfor i in bar:\n    bar.set_postfix(loss=1 / (i + 1), epoch=i // 10)\n    bar.set_description(f"step {i}")\n    time.sleep(0.02)',
        ),
        (
            "Custom bar_format",
            'from widgets import tqdm\n\nfor _ in tqdm(range(100), bar_format="{desc} |{bar:30}| {n_fmt}/{total_fmt} [{elapsed}<{remaining}, {rate_fmt}]", desc="fmt"):\n    pass',
        ),
        (
            "Looks: fill, gradient, spinner, colour",
            'import time\nfrom widgets import tqdm\n\nfor _ in tqdm(range(100), desc="look", fill="■", empty="·", gradient=["#ff3b30", "#ffcc00", "#34c759"], spinner="dots", empty_colour="#444444"):\n    time.sleep(0.02)',
        ),
        (
            "Vertical bars side by side",
            'import time\nfrom widgets import vtqdm\n\nfor job in range(4):\n    for _ in vtqdm(range(40), height=8, desc=f"job {job}", gradient=["#00c6ff", "#0072ff"]):\n        time.sleep(0.01)',
        ),
        (
            "Several concurrent bars (position)",
            'import time\nfrom widgets import tqdm\n\na = tqdm(total=50, desc="a", position=0)\nb = tqdm(total=80, desc="b", position=1)\nfor _ in range(80):\n    b.update(1)\n    if _ < 50:\n        a.update(1)\n    time.sleep(0.02)\na.close(); b.close()',
        ),
        (
            "Print without breaking the bars",
            'from widgets import tqdm\n\nfor i in tqdm(range(20)):\n    if i % 5 == 0:\n        tqdm.write(f"checkpoint {i}")',
        ),
        (
            "Progress for file reads (wrapattr)",
            'from widgets import tqdm\n\nwith open(__file__, "rb") as f, tqdm.wrapattr(f, "read", total=1000, desc="reading") as wrapped:\n    while wrapped.read(100):\n        pass',
        ),
        (
            "pandas",
            'import pandas as pd\nfrom widgets import tqdm\n\ntqdm.pandas()\ndf = pd.DataFrame({"a": range(1000)})\ndf["b"] = df["a"].progress_apply(lambda v: v * 2)',
        ),
        (
            "asyncio",
            'import asyncio\nfrom widgets.progress.asyncio import tqdm_asyncio\n\nasync def work(i):\n    await asyncio.sleep(0.01 * i)\n    return i\n\nasync def main():\n    return await tqdm_asyncio.gather(*(work(i) for i in range(20)), desc="gather")\n\nasyncio.run(main())',
        ),
        (
            "Helpers: trange, tenumerate, tzip, tmap",
            'from widgets import trange\nfrom widgets.progress.contrib import tenumerate, tzip, tmap\n\nfor _ in trange(10): pass\nfor i, x in tenumerate("abc"): pass\nfor a, b in tzip(range(3), "xyz"): pass\nlist(tmap(str, range(5)))',
        ),
        (
            "Threads",
            'from widgets.progress.contrib.concurrent import thread_map\n\nthread_map(lambda x: x * 2, range(100), max_workers=4, desc="threads")',
        ),
        (
            "Logging into the bar's stream",
            'import logging\nfrom widgets.progress.contrib.logging import logging_redirect_tqdm\nfrom widgets import tqdm\n\nwith logging_redirect_tqdm():\n    for i in tqdm(range(5)):\n        logging.info("step %s", i)',
        ),
        (
            "Not a terminal (PyCharm Run window, files, CI)",
            '# Output that is not a TTY gets one plain line every 10 s.\n# Change the interval:  set WIDGETS_NONTTY_INTERVAL=1   (PowerShell: $env:WIDGETS_NONTTY_INTERVAL=1)\n# For real bars in PyCharm: Run > Edit Configurations > tick "Emulate terminal in output console".',
        ),
    ]
    out += ["### Examples", ""]
    for title, code in snippets:
        out += [f"**{title}**", "", "```python", code, "```", ""]
    out += [
        "### Formatting helpers (identical output to real tqdm)",
        "",
        "```python",
        "from widgets.progress.meter import format_meter, format_interval, format_sizeof, format_num",
        "format_interval(3725)            # '1:02:05'",
        "format_sizeof(1_500_000, 'B')    # '1.50MB'",
        "format_meter(50, 100, 12.0)      # ' 50%|█████     | 50/100 [00:12<00:12,  4.17it/s]'",
        "```",
        "",
        "### Compatibility shims",
        "",
        "`widgets.progress.auto`, `std`, `asyncio`, `notebook`, `gui`, `rich`, `tk`, `keras`, `dask` and `contrib.*` mirror the "
        "tqdm module layout; `tqdm_class=` hooks accept `tqdm` or `vtqdm`. Optional extras: `rich` (rich renderer), "
        "`tk` (small window; needs a display).",
        "",
    ]
    return out


def asset_section() -> list[str]:
    out = ["## Catalogues: bar styles, spinners, borders, fonts, colours, symbols", ""]
    out += [
        "Each catalogue has `list_*()` and `get_*()` functions. Names below are generated from the installed version.",
        "",
    ]
    for title, fn in [
        ("Bar styles", widgets.list_bar_styles),
        ("Border styles", widgets.list_border_styles),
        ("Fonts", widgets.list_fonts),
        ("Spinners", widgets.list_spinners),
    ]:
        names = fn()
        out += [f"### {title} ({len(names)})", "", ", ".join(f"`{n}`" for n in names), ""]
    try:
        groups = widgets.list_asset_groups()
        out += ["### Asset groups", "", ", ".join(f"`{g}`" for g in groups), ""]
    except Exception:  # pragma: no cover
        pass
    return out


INTRO = (
    """# widgets - the complete manual

*Generated by `tools/gen_manual.py` from the code: every constructor parameter of every widget is listed with its type,
default and meaning. Do not edit by hand - edit `tools/manual_content.py` and regenerate.*

## 1. Getting started

```powershell
pip install termwidgets               # zero runtime dependencies; import name stays `widgets`
pip install "termwidgets[unicode,tz,images]" # optional extras
```

| Extra | Adds | Used by |
|---|---|---|
| `unicode` | `wcwidth` exact character widths | everything with wide glyphs |
| `tz` | `tzdata` (Windows time zones) | `ClockWidget(tz=...)`, `WeatherWidget` |
| `data` | `pandas` | `Table.load_dataframe` |
| `excel` | `openpyxl` | `Table.load_excel` |
| `audio` | `numpy` | spectrum / equalizer analysis |
| `rich` | `rich` | `widgets.progress.rich` |
| `system` | `psutil` | `ProcessMonitor` |
| `images` | `pillow`, `qrcode` | `ImageView.from_file`, `QrView` |

### The `show()` helper used in every example

Almost all examples call `show(widget, ...)`. Put this at the top of your script:

```python
"""
    + mc.SHOW
    + """```

Run in a **real terminal** (Windows Terminal / PowerShell) or enable *Emulate terminal in output console* in PyCharm.
Press `q` to quit. Widgets are positioned with `x, y` (cells, relative to their parent) and sized with `width, height`.

### Concepts

* **Coordinates** - `(0, 0)` is the top-left cell of the parent. `Container(x, y, w, h)` groups children (`add`, `remove`, `get(name)`).
* **Lifecycle** - `CREATED -> MOUNTED -> RUNNING <-> PAUSED -> STOPPED -> UNMOUNTED -> CLOSED`. `run_app` does this for you; manual use: `mount()`, `start()`, `update(dt)`, `stop()`, `close()`.
* **Time-driven** - animations advance only through `update(dt)`; with a `ManualClock` they are fully deterministic.
* **Focus and keys** - interactive widgets (`InteractiveWidget`) get keys when focused: Tab / Shift+Tab move focus.
* **Safety** - all text is sanitised, so untrusted text cannot inject terminal escape sequences.
* **Accessibility** - `ascii_only=True`, `reduced_motion=True`, status never relies on colour alone, flashing is rate-limited.

### run_app

```python
run_app(root, *, fps=30.0, duration=None, mode=TerminalMode.FULLSCREEN, on_event=None,
        quit_keys=(), interactive=True, stream=None, input_stream=None, title=None)
```

| Parameter | Meaning |
|---|---|
| `root` | Root widget (usually a `Screen(width, height)` holding pages/containers). |
| `fps` | Frames per second of the render loop. |
| `duration` | Stop automatically after N seconds (`None` = run until quit). Handy for demos and tests. |
| `mode` | `TerminalMode.FULLSCREEN` (alternate screen) or `TerminalMode.INLINE` (draw in the scrollback). |
| `on_event` | Callback `fn(event)` receiving `KeyEvent`, `PasteEvent`, `ResizeEvent`, `CustomEvent`. |
| `quit_keys` | Keys that end the loop, e.g. `("q", "ctrl+c")`. |
| `interactive` | `False` = draw only, do not read the keyboard. |
| `stream` / `input_stream` | Output / input text streams (default stdout / stdin). |
| `title` | Terminal window title. |

```python
from widgets import Screen, Container, Box, run_app

screen = Screen(100, 30)
page = Container(0, 0, 100, 30, name="main")
page.add(Box(2, 1, 40, 5, text="left", border="single"))
page.add(Box(50, 1, 40, 5, text="right", border="rounded"))
screen.add(page)

def on_event(event):
    print(event)          # KeyEvent(key='a') ... use it for global shortcuts

run_app(screen, fps=30, on_event=on_event, quit_keys=("q",), title="my app")
```

## 2. Styling toolkit

### Style

`Style(fg=None, bg=None, bold=False, dim=False, italic=False, underline=False, blink=False, reverse=False, strike=False)`
- `fg`/`bg` accept a colour spec: `RGB(255, 0, 0)`, `"#ff0000"`, `"#f00"`, a CSS-like name (`"orange"`), or `None` (terminal default).
- Styles are immutable; combine with `dataclasses.replace(style, bold=True)`.
- `parse_color(value) -> RGB`, `style_to_ansi(style)`, `apply_style(text, style)` help in plain scripts.

```python
from widgets import Style, RGB, parse_color, apply_style
title = Style(fg="#ffffff", bg=RGB(40, 60, 140), bold=True, underline=True)
print(apply_style("Hello", title))      # ANSI string; colours are downgraded automatically
print(parse_color("orange"), parse_color("#336699"))
```

### Colour modes

`detect_color_mode()` returns `ColorMode.NONE | ANSI16 | ANSI256 | TRUECOLOR`. Environment: `NO_COLOR` (no colour),
`COLORTERM=truecolor`, `TERM`. Colours are quantised automatically to what the terminal supports.

### Gradients and palettes

```python
from widgets import Gradient, get_gradient, register_gradient, register_palette, get_palette, Marquee

g = Gradient.from_colors(["#ff0000", "#ffff00", "#00ff00"])   # any number of colours
print(g.at(0.5), g.sample(10))                                  # colour at a position / 10 evenly spaced
register_gradient("traffic", g)                                  # name it: replace=True to overwrite
print(get_gradient("traffic"))
register_palette("brand", ["#0ea5e9", "#22c55e", "#f59e0b"])
Marquee(0, 0, 40, 1, text="gradient text", gradient=get_gradient("traffic"))
```

Parameters: `Gradient.from_colors(colors)`, `register_gradient(name, gradient, *, replace=False)`,
`register_palette(name, colors, *, replace=False)`. Wherever a widget takes `gradient=`, pass a `Gradient`
(some widgets also accept a registered name).

### Large fonts

```python
from widgets import render_text, list_fonts, get_font, font_height
for line in render_text("HI", "rounded-5", spacing=1):   # list of strings
    print(line)
print(font_height("original-5"))
```

`render_text(text, font, *, spacing=1)` - `font` is a `Font` or a name from `list_fonts()`. Widgets with a `font=` parameter
(`Sign`, `Neon`, `Marquee`, `VerticalPrint`, `ClockWidget`, `TimerWidget`) use the same names.

### Border, bar-style and spinner lookups

```python
from widgets import get_border_style, get_bar_style, get_spinner, spinner_frames
print(get_border_style("rounded"))
print(get_bar_style("smooth"))
print(spinner_frames("dots"))
```

### Easing, clocks and testing helpers

`ease(name, t)` with `linear, ease_in, ease_out, ease_in_out, bounce, elastic`; `Clock`, `MonotonicClock`, `ManualClock`
(`clock.advance(1.0)`), `FlashLimiter`, `reduced_motion_enabled()`, `make_rng(seed)`.

```python
from widgets import ManualClock, Countdown
clock = ManualClock()
cd = Countdown(5, clock=clock)
cd.mount(); cd.start()
clock.advance(5); cd.update(0)
print(cd.remaining)
```
"""
)

CLOSING = """
## 3. Environment variables

| Variable | Effect |
|---|---|
| `NO_COLOR` | Disable colours. |
| `COLORTERM`, `TERM` | Colour capability detection. |
| `WIDGETS_REDUCED_MOTION` | `1` = reduced motion for all widgets (when `reduced_motion=None`). |
| `WIDGETS_NONTTY_INTERVAL` | Seconds between plain progress lines when output is not a terminal (default 10). |
| `WT_SESSION` | Windows Terminal detection (truecolor). |

## 4. Troubleshooting

* **Plain lines instead of a bar** - the output is not a terminal (PyCharm Run window, redirect, CI). Use a real terminal or
  *Emulate terminal in output console*.
* **`ZoneInfoNotFoundError` on Windows** - `pip install termwidgets[tz]`.
* **Boxes look misaligned** - install `widgets[unicode]` (exact East-Asian/emoji widths) or set `ascii_only=True`.
* **`LifecycleError`** - call `mount()` before `start()`; `run_app` does it for you.
* **Nothing moves** - animations advance with `update(dt)`; inside `run_app` this is automatic. `reduced_motion=True` freezes them on purpose.
"""


def check_examples() -> int:
    from widgets import Screen

    failures = 0

    def fake_show(*ws: Any, width: int = 80, height: int = 24) -> None:
        screen = Screen(width, height)
        for w in ws:
            screen.add(w)
        screen.mount()
        screen.start()
        screen.update(0.2)
        screen.update(0.2)
        screen.stop()
        screen.close()

    for cls, items in mc.EXAMPLES.items():
        for title, code in items:
            if cls == "QrView":  # needs the optional qrcode package
                continue
            code = fix_imports(code)
            ns: dict[str, Any] = {"show": fake_show, "__file__": __file__}
            try:
                exec(compile(code, f"<{cls}:{title}>", "exec"), ns)
            except Exception as exc:
                failures += 1
                print(f"EXAMPLE FAILED {cls} / {title}: {type(exc).__name__}: {exc}")
    return failures


def main(argv: list[str]) -> int:
    parts = [INTRO]
    for chapter, entries in CHAPTERS:
        parts.append(f"\n## {chapter}\n")
        for pkg, name in entries:
            parts.append("\n".join(class_section(pkg, name)))
    parts.append("\n".join(tqdm_section()))
    parts.append("\n".join(asset_section()))
    parts.append(CLOSING)
    text = "\n".join(parts)
    status = 0
    if missing:
        print("Undocumented parameters:", ", ".join(sorted(set(missing))))
        if "--strict" in argv or "--check" in argv:
            status = 1
    if "--check" in argv:
        status |= 1 if check_examples() else 0
    OUT.parent.mkdir(exist_ok=True)
    OUT.write_text(text, encoding="utf-8")
    print(f"wrote {OUT} ({len(text.splitlines())} lines)")
    return status


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
