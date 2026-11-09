# widgets - user guide

Terminal UI widget toolkit for CPython 3.13+, zero runtime dependencies.

```bash
pip install -e ".[dev]"            # from a checkout (PyCharm: Terminal tool window)
python examples/demo.py            # core runtime
python examples/progress_demo.py   # progress bars (horizontal and vertical)
python examples/live_gallery.py    # M4 display widgets
python examples/data_gallery.py    # table, chart, tree, form, directory tree, dashboard, code editor
python examples/net_gallery.py     # RSS + weather (offline by default, --live for real HTTP)
python examples/audio_gallery.py   # player, synchronized visuals, space crawl (--null = silent)
python examples/all_widgets.py     # visual tour of every widget
python examples/dev_showcase.py    # code + live result for 40 widgets (n/p = next/previous, q = quit)
python examples/color_gallery.py   # every colour, gradient, palette (--text prints once)
python examples/rss_ticker.py      # multi-lane RSS ticker (--live for real feeds)
python examples/spectrum_demo.py   # spectrum analyser for a .wav file (needs the audio extra)
```

Run the demos in a real terminal (PyCharm: *Emulate terminal in output console*). Windows 10 build
14931+ and Windows 11 are treated as truecolor; if colours still look flat set `COLORTERM=truecolor`
(PowerShell: `$env:COLORTERM="truecolor"`). Pass `--ascii` where offered
for terminals without Unicode.

## Layers (D-08)

L0 `widgets` / `widgets.errors` - L1 `render`, `terminal`, `assets` - L2 `base_elements` - L3 widget
packages `display`, `data`, `net`, `audio`, `progress` - nothing imports upward (`tools/check_layers.py`).
`import widgets` loads none of the widget packages; import what you use, e.g.
`from widgets.data.table import Table`.

## Widget packages

| Package | Widgets |
|---|---|
| `widgets.progress` | progress bars, multi-bar manager (horizontal and vertical), tqdm-compatible `tqdm` (`bar_format`, `delay`, `unit_divisor`, `write_bytes`, `tqdm.pandas()`) and framework shims (Keras, dask, notebook, tk, rich) |
| `widgets.display` | `Box`, `Spinner`, `Marquee` (incl. diagonal/snake), `Neon`, `Sign`/`create_banner`, `MatrixRain`, `VerticalPrint`, gauges, notifications, calendar/clock/countdown, `SpaceCrawlWidget`, `Tabs`, `SplitPane`, `Stepper`, `Sparkline`, `Heatmap`, `CommandPalette`, `TimerWidget`, `ImageView`, `QrView`, `GridGame` |
| `widgets.data` | `Table`, `Chart`, `Tree`, `Form`, `DirectoryTree`, dashboards, `CodeEditor`, `LogViewer`, `KanbanBoard`, `MarkdownView`, `ProcessMonitor` |
| `widgets.net` | `RssReader`, `RssTicker` (multi-lane marquee, per-lane direction/speed/colour), `WeatherWidget`, injectable `HttpTransport` |
| `widgets.audio` | `AudioBackend` protocol, `NullBackend`, `SubprocessBackend`, `WinsoundBackend`, `MusicPlayer` (file browser), `Equalizer` (`set_band_gain`/`adjust_band`/`reset_bands`), `SynchronizedPlayer`, `SpectrumAnalyzer`, `Oscilloscope` |
| `widgets.assets` | borders, fonts, symbols, spinner and bar styles, colours |

All widgets share one lifecycle (`mount/start/pause/resume/stop/close`), `update(dt)`, `render(canvas)`,
`handle_key(event)`. Animated widgets accept `reduced_motion` (or `WIDGETS_REDUCED_MOTION=1`).

## Optional dependencies (minimum versions)

| Extra | Package | Used for |
|---|---|---|
| `unicode` | `wcwidth>=0.2.13` | more accurate character widths |
| `tz` | `tzdata>=2024.1` (Windows) | named time zones in `ClockWidget` |
| `data` | `pandas>=2.2` | `Table` DataFrame loading |
| `excel` | `openpyxl>=3.1` | Excel loading |
| `audio` | `numpy>=1.26` | spectrum analysis of PCM WAV files |
| `rich` | `rich>=13` | `tqdm_rich` |
| `system` | `psutil>=5.9` | `ProcessMonitor` (or pass your own `fetch`) |
| `images` | `pillow>=10`, `qrcode>=7` | `ImageView.from_file`, `QrView` |

Missing optional packages raise `MissingDependencyError` with the install hint; imports never fail.

## External services and privacy

* **RSS/Atom**: only the URLs you configure are fetched (http/https, <=5 redirects, no https->http,
  optional host allow-list, default 1 MiB limit, >=60 s between refreshes, conditional GET).
* **Weather**: `WeatherWidget` sends the **location text you type to a third-party service** -
  Open-Meteo (`geocoding-api.open-meteo.com`, `api.open-meteo.com`) - by default. Provide your own
  `WeatherProvider` to use another service or an offline source.
* **Audio**: files are played locally; external player processes are started with argument lists only.
* The library has **no telemetry** and contacts nothing unless configured by the application.

## Keyboard reference

* RSS: arrows/PgUp/PgDn, `tab`/`[`/`]` feed, `enter` select, `r` refresh, demo: `v` view, `+`/`-` speed.
* Weather: `r` refresh, `u` units, `l` change location, left/right day.
* Player: up/down, `enter` play, `space` pause, `s` stop, `n`/`p`, `+`/`-` volume (5 % steps), `e` EQ preset.
* Space crawl: `space` pause/resume, `+`/`-` speed, `r` restart.
* RSS ticker: up/down select lane, `+`/`-` lane speed, `[`/`]` all lanes, `space` pause, `d` reverse, `r` refresh.
* Tabs: ctrl+PgUp/PgDn, alt+1..9. SplitPane: alt+arrows.
* LogViewer: arrows/PgUp/PgDn/Home/End, `f` follow, `c` clear. KanbanBoard: arrows, `[`/`]` move card, `d` delete.
* CommandPalette: type to filter, up/down, `enter` run, `escape` close. GridGame: arrows, `r` restart.

## Quality gates

```bash
ruff check . && ruff format --check .
mypy --strict
python tools/check_layers.py
pytest                             # ~480 tests; a few skip per platform and per missing optional package
python tools/req_coverage.py --spec requirementsspecification.md
python tools/benchmarks.py
```

## Replacing tqdm

```python
from widgets import tqdm  # horizontal bar, drop-in for ``from tqdm import tqdm``
from widgets import vtqdm as tqdm  # vertical bar, same API (extra ``height=8`` option)
```

`trange`/`vtrange`, `tqdm.write`, `tqdm.pandas()`, `wrapattr`, `format_meter`, nested bars and the
`contrib` helpers (`tenumerate`, `tzip`, `tmap`, `thread_map`, `product`, logging redirect) behave as in tqdm.
Submodules mirror tqdm's: `widgets.progress.auto`, `.std`, `.asyncio`, `.contrib.*`. The test
`tests/test_m17_tqdm_compat.py` checks this against recorded tqdm output and, if installed, live tqdm.

### Looks and mixed layouts

Both `tqdm` and `vtqdm` accept extra keyword-only options that plain tqdm code never uses:

```python
from widgets import tqdm, vtqdm

tqdm(total=100, spinner="dots", gradient=["#ff3b30", "#ffcc00", "#34c759"])
tqdm(total=100, fill="=", empty=".", colour="yellow")
vtqdm(total=100, height=8, ascii=" ▁▂▃▄▅▆▇█", gradient=["#001f3f", "#7fdbff"])
```

Vertical bars sit side by side in the same rows; horizontal bars take one row each, so one horizontal
bar above four vertical ones (or the reverse) just works: create them with `position=0..4`.
`python examples/tqdm_mixed_demo.py [looks|h1v4|v1h4]` shows all of it.

### The complete demo

`examples/tqdm_complete_demo.py` exercises every tqdm feature with either bar type:

```powershell
python examples\tqdm_complete_demo.py --worker                    # terminal, horizontal bars
python examples\tqdm_complete_demo.py --worker --bars vertical    # terminal, vertical bars
python examples\tqdm_complete_demo.py                             # split-screen GUI (needs PySide6)
```

Only `select_bars()` differs between the two: it binds `tqdm`, `trange` and `tqdm_asyncio` to the horizontal
or vertical classes. Helpers that create bars of their own accept `tqdm_class=` (`thread_map`, `process_map`,
`logging_redirect_tqdm`).
