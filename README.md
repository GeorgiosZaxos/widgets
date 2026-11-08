# widgets

[![CI](https://github.com/GeorgiosZaxos/widgets/actions/workflows/ci.yml/badge.svg)](https://github.com/GeorgiosZaxos/widgets/actions/workflows/ci.yml)
[![Python 3.13](https://img.shields.io/badge/python-3.13-blue.svg)](https://www.python.org/)
[![License: MIT](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)
[![Typed](https://img.shields.io/badge/typing-strict-informational.svg)](https://mypy.readthedocs.io/)

A terminal UI widget toolkit for **Python 3.13** with **zero required runtime dependencies**,
strict typing, and a diffing renderer. Progress bars (tqdm-compatible), display effects, data
widgets, network widgets (RSS, weather) and audio widgets, all behind one widget lifecycle.

> Status: release candidate (`1.0.0rc1`). See [`CHANGELOG.md`](CHANGELOG.md) and
> [`docs/COMPATIBILITY.md`](docs/COMPATIBILITY.md) for what has been verified on which platform.

## Install

```bash
pip install .                       # from a checkout; core has no dependencies
pip install ".[unicode,data,images]"  # optional extras, see below
```

| Extra | Adds | Used for |
|---|---|---|
| `unicode` | `wcwidth` | more accurate character widths |
| `tz` | `tzdata` (Windows) | named time zones |
| `data` / `excel` | `pandas` / `openpyxl` | `Table` loading, `tqdm.pandas()` |
| `audio` | `numpy` | spectrum analysis of WAV files |
| `rich` | `rich` | `tqdm_rich` |
| `system` | `psutil` | `ProcessMonitor` |
| `images` | `pillow`, `qrcode` | `ImageView.from_file`, `QrView` |
| `dev` | test and lint tools | development |

Missing extras raise `MissingDependencyError` with the install hint; imports never fail.

## Quick start

```python
from widgets.progress.tqdm import tqdm

for item in tqdm(range(1000), desc="work"):  # bar on stderr; plain lines when not a TTY
    ...
```

```python
from widgets.base_elements.layout import Screen
from widgets.display.marquee import Marquee
from widgets.render.run import run_app

screen = Screen(60, 3)
screen.add(Marquee(0, 1, 60, 1, text="  hello, widgets  ", speed=10))
run_app(screen, quit_keys=("q",))
```

Several RSS feeds as parallel marquee lines, each with its own direction, speed and colour:

```python
from widgets.net.rss import FeedSource
from widgets.net.rss_ticker import RssTicker, TickerLane

ticker = RssTicker(
    0,
    0,
    100,
    spacing=1,
    show_speed=True,
    lanes=[
        TickerLane(
            FeedSource("World", "https://example.org/world.xml"), "left", 8, color="#ff5f5f"
        ),
        TickerLane(
            FeedSource("Tech", "https://example.org/tech.xml"), "right", 18, gradient="rainbow"
        ),
    ],
)
```

Keys: up/down select a lane, `+`/`-` its speed, `[`/`]` all lanes, space pause, `d` reverse, `r` refresh.

## What is included

| Package | Widgets |
|---|---|
| `widgets.progress` | horizontal/vertical bars, multi-bar manager, tqdm-compatible `tqdm` (`bar_format`, `delay`, `unit_divisor`, `write_bytes`, `tqdm.pandas()`), Keras/dask/notebook/tk/rich shims |
| `widgets.display` | `Box`, `Spinner`, `Marquee`, `Neon`, `Sign`, `MatrixRain`, `VerticalPrint`, gauges, notifications, calendar/clock/countdown, `SpaceCrawlWidget`, `Tabs`, `SplitPane`, `Stepper`, `Sparkline`, `Heatmap`, `CommandPalette`, `TimerWidget`, `ImageView`, `QrView`, `GridGame` |
| `widgets.data` | `Table`, `Chart`, `Tree`, `Form`, `DirectoryTree`, dashboards, `CodeEditor`, `LogViewer`, `KanbanBoard`, `MarkdownView`, `ProcessMonitor` |
| `widgets.net` | `RssReader`, `RssTicker`, `WeatherWidget`, injectable `HttpTransport` |
| `widgets.audio` | `MusicPlayer`, `Equalizer`, `SynchronizedPlayer`, `SpectrumAnalyzer`, `Oscilloscope`, backends |
| `widgets.assets` | borders, fonts, symbols, spinner and bar styles, colours and gradients |

Every widget shares one lifecycle (`mount/start/pause/resume/stop/close`), `update(dt)`,
`render(canvas)` and `handle_key(event)`. Animated widgets honour `reduced_motion` /
`WIDGETS_REDUCED_MOTION=1`; colour honours `NO_COLOR` and `COLORTERM`.

## Demos

Run these in a real terminal (PyCharm: *Emulate terminal in output console*):

```bash
python examples/dev_showcase.py   # code + live result for 40 widgets (n/p, q)
python examples/all_widgets.py    # visual tour
python examples/color_gallery.py  # every colour, gradient and palette (--text prints once)
python examples/rss_ticker.py     # multi-lane RSS ticker (--live for real feeds)
python examples/net_gallery.py    # RSS reader + weather, offline by default
python examples/progress_demo.py  # progress bars
```

## Documentation

* [User guide](docs/USER_GUIDE.md) - layers, packages, keys, privacy
* [Compatibility](docs/COMPATIBILITY.md) - what is verified on Linux, macOS, Windows
* [Security](docs/SECURITY.md) and [security policy](SECURITY.md)
* [Benchmarks](docs/BENCHMARKS.md), [requirements traceability](docs/TRACEABILITY.md)
* [Contributing](CONTRIBUTING.md), [changelog](CHANGELOG.md), [bundled asset provenance](LICENSES.md)

Weather sends the location text you type to a third-party service (Open-Meteo); RSS fetches only
URLs you configure. The library has no telemetry.

## Development

```bash
python -m venv .venv && . .venv/bin/activate      # Windows: .venv\Scripts\activate
pip install -e ".[dev]"
ruff check . && ruff format --check .
mypy
python tools/check_layers.py
pytest
```

Tests carry `@pytest.mark.req("FR-...")` markers; `python tools/req_coverage.py --spec <SRS file>`
lists requirement coverage. Layers are enforced by `tools/check_layers.py`:
`widgets` -> `render/terminal/assets` -> `base_elements` -> widget packages; nothing imports upward.

## Layout

```
src/widgets/   errors, base_elements, render, terminal, assets, progress, display, data, net, audio
tests/         pytest suite (unit, property, pty integration)
tools/         check_layers.py, req_coverage.py, benchmarks.py, gen_asset_data.py
examples/      demos and galleries
docs/          guides and reports
```

## License

MIT - see [`LICENSE`](LICENSE). Bundled glyph catalogues: see [`LICENSES.md`](LICENSES.md).
