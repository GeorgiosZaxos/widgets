"""Hand-written text for the manual: parameter meanings and examples. Used by gen_manual.py.

Every public constructor parameter of every documented class must have a description here
(generic in COMMON, or specific in PARAMS["Class.param"]); ``gen_manual.py --strict`` fails otherwise.
"""

from __future__ import annotations

COMMON: dict[str, str] = {
    "x": "Column of the widget's top-left cell, relative to its parent container (0 = left edge).",
    "y": "Row of the widget's top-left cell, relative to its parent container (0 = top edge).",
    "width": "Width in terminal cells (columns).",
    "height": "Height in terminal rows.",
    "name": "Optional unique id (`WidgetId`). Lets you find the widget with `container.get(name)` and labels it in errors and `describe()`.",
    "style": "Base `Style` (fg, bg, bold, dim, italic, underline, blink, reverse, strike) used for the text.",
    "gradient": "A `Gradient` (or the name of a registered gradient, see *Gradients*) coloured across the content. `None` = plain `style` colour.",
    "ascii_only": "`True` replaces every non-ASCII glyph (borders, blocks, arrows, spinners) with an ASCII fallback. Use it for legacy consoles, logs and screen readers.",
    "reduced_motion": "`True` disables animation (static frame). `None` (default) follows the accessibility setting / `WIDGETS_REDUCED_MOTION` environment variable.",
    "speed": "Animation speed. Unit depends on the widget (cells/s, frames/s or cycles/s) - see the widget section.",
    "align": "Horizontal alignment: `'left'`, `'center'` or `'right'`.",
    "border": "Name of a border style (see *Border styles*), e.g. `'single'`, `'double'`, `'rounded'`; `None` = no border.",
    "font": "Large-character font: a `Font` or a font name from `list_fonts()` (e.g. `'original-5'`, `'rounded-3'`). `None` = plain text.",
    "text": "The text to display. Control characters and escape sequences are sanitised (never reach the terminal).",
    "seed": "Integer seed for the random generator; same seed = same animation (deterministic tests). `None` = random.",
    "clock": "Injectable `Clock` (`MonotonicClock` by default, `ManualClock` for tests).",
    "on_select": "Callback invoked when the user activates/selects an item. Called on the UI thread.",
    "on_complete": "Callback invoked once when the animation or countdown finishes.",
    "on_finish": "Callback invoked once when the work finishes.",
    "transport": "An `HttpTransport` (object with `get(url, *, headers, timeout, max_bytes) -> HttpResponse`). Inject one to work offline or in tests; default is the verified-TLS `UrllibTransport`.",
    "timeout": "Network timeout in seconds per request.",
    "max_response_bytes": "Hard limit on a response body; larger responses are rejected (protection against huge feeds).",
    "state": "The `ProgressState` this indicator displays. Several indicators may share one state.",
    "fill_style": "`Style` of the filled part of the bar (default green).",
    "empty_style": "`Style` of the unfilled part (default dim).",
    "unit": "Unit label shown after counts and rates, e.g. `'it'`, `'B'`, `'files'`.",
    "unit_scale": "`True`/number: scale counts with SI prefixes (1500 -> `1.5k`); with `unit='B'` shows `kB/MB`.",
    "unit_divisor": "Base for `unit_scale` (1000 for SI, 1024 for binary sizes).",
    "bar_format": "tqdm-style format string with fields `{l_bar}`, `{bar}`, `{bar:N}`, `{r_bar}`, `{n}`, `{n_fmt}`, `{total}`, `{total_fmt}`, `{percentage}`, `{elapsed}`, `{remaining}`, `{rate}`, `{rate_fmt}`, `{unit}`, `{desc}`, `{postfix}`.",
    "spinner": "Name of a spinner from `list_spinners()` drawn as a prefix (e.g. `'dots'`, `'line'`, `'moon'`).",
    "args": "Positional arguments forwarded to the parent class constructor.",
    "kwargs": "Keyword arguments forwarded to the parent class constructor.",
    "stream": "Text stream to draw on (default `sys.stderr` for progress, `sys.stdout` for apps).",
}

PARAMS: dict[str, str] = {
    # ---- AnimatedText
    "AnimatedText.mode": "Animation: `'static'`, `'typewriter'`, `'scroll'`, `'bounce'`, `'dual-marquee'`, `'fade-in'`, `'fade-out'`, `'wave'`, `'explode'` (also see `MODES`).",
    "AnimatedText.speed": "Characters (or cells) per second.",
    "AnimatedText.duration": "Total seconds for one pass; overrides `speed` when given. `None` = derive from `speed`.",
    "AnimatedText.loop": "`True` restarts after finishing; `False` stops and fires `on_complete`.",
    "AnimatedText.easing": "Easing curve name: `'linear'`, `'ease_in'`, `'ease_out'`, `'ease_in_out'`, `'bounce'`, `'elastic'`.",
    "AnimatedText.bidirectional": "`True` plays forward then backward (ping-pong).",
    "AnimatedText.amplitude": "Wave/explode strength in rows or cells.",
    "AnimatedText.wavelength": "Distance in characters of one wave period.",
    "AnimatedText.cursor": "Cursor glyph shown by `'typewriter'`.",
    "AnimatedText.spinner": "Spinner name shown next to the text while animating (`None` = none).",
    "AnimatedText.placement": "Where the spinner goes: `'before'`, `'after'`, `'both'` or `'replace'`.",
    "AnimatedText.background": "`Style` for the area behind the text (`None` = transparent).",
    # ---- Box
    "Box.border": "Border style name (`'single'`, `'double'`, `'rounded'`, `'heavy'`, ... see *Border styles*) or `None`.",
    "Box.valign": "Vertical alignment inside the box: `'top'`, `'middle'` or `'bottom'`.",
    "Box.padding": "Inner padding: one int (all sides) or `(top, right, bottom, left)`.",
    "Box.overflow": "`'truncate'` cuts long lines; `'wrap'` word-wraps them.",
    "Box.border_style": "`Style` of the border characters (colour them independently of the text).",
    "Box.shadow": "Drop shadow `(dx, dy, glyph, Style)`, e.g. `(1, 1, '░', Style(fg=RGB(60,60,60)))`; `None` = none.",
    # ---- Calendar / clock
    "CalendarWidget.year": "Year to show; `None` = current year.",
    "CalendarWidget.month": "Month 1-12 to show; `None` = current month.",
    "CalendarWidget.first_weekday": "0 = Monday ... 6 = Sunday as the first column.",
    "CalendarWidget.today": "`datetime.date` highlighted as today (default: the real date; inject for tests).",
    "CalendarWidget.selected": "Initially selected `datetime.date`.",
    "CalendarWidget.on_select": "Called with the `date` when the user presses Enter on a day.",
    "ClockWidget.tz": "IANA time-zone name (`'Europe/Athens'`). `'UTC'` always works; others need `tzdata` on Windows (`pip install termwidgets[tz]`).",
    "ClockWidget.seconds": "Show seconds (`HH:MM:SS`) or only `HH:MM`.",
    "ClockWidget.now_fn": "Callable returning a `datetime` - inject a fake time for tests.",
    "Countdown.seconds": "Number of seconds to count down from (required).",
    # ---- CommandPalette
    "CommandPalette.commands": "Mapping `label -> callable`. Typing filters labels (fuzzy); Enter runs the selected callable.",
    "CommandPalette.on_close": "Called when the palette closes (Escape or after running a command).",
    # ---- Gauge
    "Gauge.kind": "Shape: `'circular'`, `'speedometer'`, `'semicircular'` or `'thermometer'`.",
    "Gauge.value": "Current value; clamped to `[minimum, maximum]`; NaN is rejected.",
    "Gauge.minimum": "Lower bound of the range (must be < `maximum`).",
    "Gauge.maximum": "Upper bound of the range.",
    "Gauge.title": "Caption drawn above/below the dial.",
    "Gauge.unit": "Unit appended to the numeric readout (`'%'`, `'C'`, `'MB/s'`).",
    "Gauge.thresholds": "Tuple of `(value, RGB)`: the colour of the highest threshold not above the value is used, e.g. `((0, RGB(0,200,0)), (70, RGB(255,180,0)), (90, RGB(255,0,0)))`.",
    "Gauge.ticks": "Number of tick marks along the scale (0 = none).",
    # ---- GridGame
    "GridGame.level": "Maze as a sequence of strings: `#` wall, `@` player, `*` item, space floor.",
    "GridGame.on_win": "Called with the number of moves when every `*` is collected.",
    # ---- Heatmap
    "Heatmap.data": "Rows of numbers (2-D). Each value is normalised to the data min/max and mapped through the gradient.",
    "Heatmap.row_labels": "Labels printed to the left of each row.",
    "Heatmap.gradient": "A `Gradient` or registered gradient name (default `'heat'`).",
    # ---- Image / QR
    "ImageView.pixels": "2-D grid (`Sequence[Sequence[RGB]]`) of pixels; two pixel rows are drawn per terminal row using `▀`.",
    "QrView.text": "Text/URL to encode (needs `pip install termwidgets[images]` / `qrcode`).",
    "QrView.border": "Quiet-zone width in modules around the code (spec minimum is 4; 2 is scannable on most readers).",
    # ---- Marquee
    "Marquee.text": "Text to scroll; may contain several lines.",
    "Marquee.direction": "`'left'`, `'right'`, `'up'`, `'down'`, `'diagonal'` or `'snake'`.",
    "Marquee.mode": "`'loop'` wraps around endlessly; `'bounce'` reverses at the ends.",
    "Marquee.speed": "Scroll speed in cells per second.",
    "Marquee.gap": "Blank cells between the end of the text and its repeat (loop mode).",
    "Marquee.font": "Optional large font; the text is rendered with `render_text` before scrolling.",
    "Marquee.align": "Alignment of text shorter than the widget.",
    # ---- MatrixRain
    "MatrixRain.text": "Message revealed by the `'reveal'`/`'vt'`/`'encrypted'` modes.",
    "MatrixRain.charset": "Characters the rain draws from.",
    "MatrixRain.density": "Fraction (0..1) of columns active.",
    "MatrixRain.speed": "Fall speed in rows per second.",
    "MatrixRain.mode": "`'rain'`, `'reveal'`, `'fade'`, `'vt'` or `'encrypted'`.",
    "MatrixRain.reveal_after": "Seconds before the text starts to resolve (reveal-type modes).",
    # ---- Neon
    "Neon.colors": "Two colours `(a, b)` the glow cycles between when no `gradient`/`palette` is given.",
    "Neon.palette": "Name of a registered palette used for the cycle (see `get_palette`).",
    "Neon.outline": "`True` draws the large font as an outline.",
    "Neon.speed": "Colour cycles per second.",
    "Neon.flicker": "Occasional brightness flicker (limited by `FlashLimiter` for safety).",
    "Neon.fade": "Slow fade in/out of the glow.",
    "Neon.wrap": "Wrap long text over several font rows instead of clipping it.",
    # ---- NotificationCenter
    "NotificationCenter.placement": "`'top'` or `'bottom'` of the widget area.",
    "NotificationCenter.default_duration": "Seconds a notification stays when `post(..., duration=None)`.",
    "NotificationCenter.max_queue": "Maximum queued notifications (>= 1).",
    "NotificationCenter.overflow": "When the queue is full: `'drop_oldest'` or `'drop_newest'`.",
    "NotificationCenter.max_visible": "Maximum simultaneously visible items (`None` = as many as fit).",
    "NotificationCenter.fade": "Fade notifications out during their last moments.",
    # ---- Sign
    "Sign.font": "Font name or `Font` (default `'original-5'`).",
    "Sign.mode": "`'static'`, `'typewriter'`, `'bounce'`, `'marquee'`, `'wave'`, `'fade'`, `'neon'` or `'gradient-scroll'`.",
    "Sign.padding": "Blank cells between border and text.",
    "Sign.speed": "Animation speed (cells or colour cycles per second).",
    # ---- Sparkline
    "Sparkline.values": "Initial history (iterable of numbers). Add more with `push(value)`.",
    "Sparkline.maximum": "Value drawn as a full block; `None` = highest value seen.",
    "Sparkline.gradient": "`Gradient` or name; colours low->high values.",
    # ---- Spinner
    "Spinner.spinner": "Spinner name from `list_spinners()` (115 built in).",
    "Spinner.text": "Label drawn next to the spinner.",
    "Spinner.speed": "Frames per second.",
    "Spinner.beat_source": "Object with a beat/level API (`BeatSource`); the spinner then advances on audio beats instead of time.",
    # ---- SpaceCrawl
    "SpaceCrawlWidget.text": "Crawl text (lines separated by newlines).",
    "SpaceCrawlWidget.speed": "Crawl speed in text lines per second.",
    "SpaceCrawlWidget.objects": "Sequence `(kind, density)`; kind in `star`, `galaxy`, `nebula`, `pulsar`; density = fraction of cells.",
    "SpaceCrawlWidget.text_width": "Width in cells of the (perspective) text block.",
    "SpaceCrawlWidget.loop": "Restart after the text has scrolled out.",
    "SpaceCrawlWidget.color": "`RGB` of the crawl text.",
    "SpaceCrawlWidget.intro": "Optional one-line intro shown before the crawl.",
    "SpaceCrawlWidget.intro_time": "Seconds the intro stays.",
    "SpaceCrawlWidget.soundtrack": "Path of an audio file played while crawling.",
    "SpaceCrawlWidget.backend": "`AudioBackend` used for the soundtrack (default: first real backend).",
    # ---- SplitPane / Tabs / Stepper
    "SplitPane.first": "First child widget (left or top).",
    "SplitPane.second": "Second child widget (right or bottom).",
    "SplitPane.orientation": "`'horizontal'` (side by side) or `'vertical'` (stacked).",
    "SplitPane.ratio": "Share of the space given to `first` (0..1).",
    "Stepper.steps": "Step names in order.",
    "Stepper.current": "Index of the active step.",
    # ---- TimerWidget
    "TimerWidget.mode": "`'stopwatch'`, `'countdown'` or `'pomodoro'` (25 min focus + 5 min break).",
    "TimerWidget.duration": "Seconds for `'countdown'`.",
    "TimerWidget.phases": "List of `(label, seconds)` run one after another (overrides the mode's phases).",
    "TimerWidget.autostart": "Start counting as soon as the widget starts.",
    # ---- VerticalPrint
    "VerticalPrint.direction": "`'down'` (top to bottom) or `'up'`.",
    "VerticalPrint.padding": "Blank cells between border and text.",
    "VerticalPrint.spacing": "Blank rows between characters.",
    # ---- progress indicators
    "HorizontalBar.width": "Total width in cells (`None` = use all available width).",
    "HorizontalBar.style": "Bar style name from `list_bar_styles()` (e.g. `'smooth'`, `'classic'`, `'block'`, `'ascii'`) or a `BarStyle`.",
    "HorizontalBar.show_percentage": "Show `42%`.",
    "HorizontalBar.show_count": "Show `42/100`.",
    "HorizontalBar.show_time": "Show `elapsed<remaining`.",
    "HorizontalBar.show_speed": "Show the rate (`3.5it/s`).",
    "HorizontalBar.min_bar": "Narrowest bar (cells) before optional statistics are dropped to make room.",
    "HorizontalBar.gradient": "`Gradient` coloured along the filled part.",
    "VerticalBar.height": "Height in rows.",
    "VerticalBar.style": "Bar style name (`'eighths'` gives 8 sub-steps per cell) or a `BarStyle`.",
    "VerticalBar.orientation": "`'bottom-up'`, `'top-down'`, `'center-out'` or `'edges-in'`.",
    "VerticalBar.animate": "`'none'`, `'pulse'` (breathing fill) or `'scan'` (moving highlight).",
    "CircularIndicator.diameter": "Diameter in rows (width is doubled to look round).",
    "CircularIndicator.glyphs": "`(filled, empty)` glyphs.",
    "CircularIndicator.ascii_glyphs": "`(filled, empty)` glyphs used when `ascii_only`.",
    "SpinnerIndicator.state": "Optional `ProgressState`; omit for a pure indeterminate spinner.",
    "SpinnerIndicator.text": "Label next to the spinner.",
    "SpinnerIndicator.reduced_motion": "Freeze the frame (bool, default `False`).",
    "VerticalTqdmBar.width": "Total width of bar + statistics column (cells).",
    "VerticalTqdmBar.height": "Bar height in rows.",
    "VerticalTqdmBar.style": "Bar style name (`list_bar_styles()`).",
    "VerticalTqdmBar.spinner": "Spinner name drawn in the statistics column.",
    "ProgressState.total": "Total number of steps; `None` = unknown (indeterminate).",
    "ProgressState.n": "Initial completed count.",
    "ProgressState.description": "Short label shown by indicators.",
    "ProgressState.smoothing": "Exponential-average weight (0..1) for the speed; higher = reacts faster (default 0.3).",
    "ProgressState.stall_timeout": "Seconds without progress before `stalled` becomes `True`.",
    "ProgressManager.session": "An existing `TerminalSession` to draw on (advanced).",
    "ProgressManager.mininterval": "Minimum seconds between redraws.",
    "ProgressManager.nontty_interval": "Seconds between plain-text lines when output is not a terminal (override: `WIDGETS_NONTTY_INTERVAL`).",
    "ProgressManager.ncols": "Fixed width in columns (`None` = detect).",
    "ProgressManager.env": "Environment mapping used for capability detection (tests).",
    # ---- data widgets
    "Chart.kind": "`'bar'`, `'line'`, `'pie'`, `'scatter'` or `'area'`.",
    "Chart.title": "Title above the plot.",
    "Chart.grid": "Draw grid lines.",
    "Chart.legend": "Draw the dataset legend (click-free: toggle with `toggle(name)`).",
    "Chart.show_values": "Print the value next to each bar/point.",
    "CodeEditor.text": "Initial contents.",
    "CodeEditor.language": "Highlight language: `python`, `javascript` or any in `CodeEditor`'s language table (java, c, rust, go, ...); `None` = no highlighting.",
    "CodeEditor.line_numbers": "Show a line-number gutter.",
    "CodeEditor.read_only": "Disallow edits (navigation, selection and copy still work).",
    "CodeEditor.tab_width": "Spaces inserted by Tab.",
    "DashboardGrid.rows": "Number of grid rows.",
    "DashboardGrid.cols": "Number of grid columns.",
    "DashboardGrid.gap": "Cells of spacing between grid cells.",
    "DashboardWidget.fetch": "Zero-argument callable run on a worker thread; its return value is shown. Exceptions are caught and displayed.",
    "DashboardWidget.interval": "Seconds between fetches.",
    "DashboardWidget.history_size": "How many past values are kept.",
    "DashboardWidget.on_update": "Called on the UI thread with each new value.",
    "MetricDashboard.label": "Name shown before the number.",
    "MetricDashboard.unit": "Unit shown after the number.",
    "TextDashboard.formatter": "Callable turning the latest value into text (default `str`).",
    "DirectoryTree.root": "Directory to show (`str` or `Path`).",
    "DirectoryTree.show_hidden": "Show dot-files.",
    "DirectoryTree.follow_symlinks": "Descend into symbolic links (loops are detected and marked).",
    "DirectoryTree.sort": "`'name'`, `'size'` or `'mtime'`.",
    "DirectoryTree.descending": "Reverse the sort order.",
    "DirectoryTree.show_size": "Show file sizes.",
    "DirectoryTree.show_perms": "Show permission bits.",
    "DirectoryTree.show_date": "Show modification dates.",
    "DirectoryTree.lister": "Injectable `lister(path) -> list[Entry]` for virtual file systems and tests.",
    "Form.width": "Width in cells (height is the number of fields).",
    "Form.fields": "Sequence of `Field`; names must be unique.",
    "Form.on_submit": "Called with `{name: value}` when Enter is pressed and validation passes.",
    "Form.on_cancel": "Called when Escape is pressed.",
    "Form.on_change": "Called with `(field_name, value)` after every edit.",
    "KanbanBoard.columns": "Mapping `column title -> list of card texts`.",
    "LogViewer.max_entries": "Ring-buffer size; oldest entries are dropped.",
    "LogViewer.show_time": "Prefix each line with `HH:MM:SS`.",
    "MarkdownView.text": "Markdown source (headings, lists, quotes, code fences, rules, bold/italic).",
    "ProcessMonitor.fetch": "Callable returning rows `{'pid','name','cpu','mem'}`. Default uses `psutil` (`pip install termwidgets[system]`).",
    "ProcessMonitor.interval": "Seconds between refreshes.",
    "Table.columns": "Column titles.",
    "Table.rows": "Rows of cell values.",
    "Table.header": "Draw the header row.",
    "Table.borders": "Draw grid borders.",
    "Table.row_numbers": "Add a row-number column.",
    "Table.widths": "Per column: an `int` width, `'auto'` or a percentage string such as `'30%'`.",
    "Table.align": "Per column: `'left'`, `'center'` or `'right'`.",
    "Tree.root": "Root `TreeNode` (build with `TreeNode.add`, or `from_python`, `from_json`, `from_xml`).",
    "Tree.on_select": "Called with the `TreeNode` when Enter is pressed.",
    # ---- net
    "RssTicker.lanes": "Sequence of `TickerLane` - one scrolling line per feed.",
    "RssTicker.spacing": "Blank rows between lanes.",
    "RssTicker.max_items": "Headlines kept per lane.",
    "RssTicker.refresh_interval": "Seconds between feed refreshes.",
    "RssTicker.show_speed": "Print each lane's current speed at its end.",
    "TickerLane.source": "A `FeedSource(name, url, category)`.",
    "TickerLane.direction": "`'left'` (right-to-left reading) or `'right'`.",
    "TickerLane.speed": "Cells per second for this lane.",
    "TickerLane.color": "Colour of the lane (`'#rrggbb'`, a colour name, or `RGB`).",
    "TickerLane.gradient": "Name of a registered gradient (overrides `color`).",
    "TickerLane.separator": "Text between consecutive headlines.",
    "TickerLane.label": "Prefix every headline with the feed name.",
    "RssReader.sources": "Sequence of `FeedSource`.",
    "RssReader.view": "`'list'`, `'marquee'` or `'box'`.",
    "RssReader.max_items_per_feed": "Maximum items kept per feed.",
    "RssReader.min_refresh_interval": "Minimum seconds between refreshes of the same feed (politeness limit).",
    "RssReader.allowed_schemes": "URL schemes accepted for feeds (default http, https).",
    "RssReader.on_update": "Called with `(source, items)` after a feed refreshed.",
    "RssReader.on_error": "Called with `(source, FeedError)` when a feed fails.",
    "WeatherWidget.location": "Place name to geocode (`'Athens'`) or a `Location`.",
    "WeatherWidget.units": "`'metric'` or `'imperial'`.",
    "WeatherWidget.days": "Forecast days to show.",
    "WeatherWidget.cache_ttl": "Seconds a fetched forecast is reused.",
    "WeatherWidget.provider": "A `WeatherProvider` (default `OpenMeteoProvider`, no API key needed).",
    # ---- audio
    "MusicPlayer.backend": "An `AudioBackend` (required): `NullBackend`, `WinsoundBackend`, `SubprocessBackend`.",
    "MusicPlayer.directory": "Folder to scan for tracks.",
    "MusicPlayer.volume": "Initial volume 0-100 (percent).",
    "MusicPlayer.autoplay_next": "Play the next track when one ends.",
    "MusicPlayer.bands": "Equalizer bands.",
    "MusicPlayer.on_state": "Called with `'playing'`, `'paused'`, `'stopped'`, ...",
    "Equalizer.bands": "Number of bands.",
    "Equalizer.preset": "`'flat'`, `'bass'`, `'treble'` or `'vocal'`.",
    "Equalizer.levels": "Callable `levels(bands) -> list[float] | None` returning 0..1 levels (e.g. `backend.levels`).",
    "Equalizer.simulate": "Draw a labelled simulated spectrum when no real levels exist.",
    "Oscilloscope.source": "Callable `source(n) -> list[float] | None` returning n samples in -1..1.",
    "Oscilloscope.color": "`RGB` of the trace.",
    "SynchronizedPlayer.backend": "The audio backend.",
    "SynchronizedPlayer.visuals": "Widgets started/paused/stopped together with the audio.",
    "SynchronizedPlayer.duration": "Stop after this many seconds (`None` = until the audio ends).",
    "SynchronizedPlayer.drive_visuals": "Call `tick(dt)` on the visuals from `update(dt)`.",
    "SynchronizedPlayer.on_finish": "Called once after everything stopped.",
    "NullBackend.clock": "Clock providing time for the simulated playback.",
    "NullBackend.default_duration": "Track length in seconds when none is configured.",
    "NullBackend.durations": "Mapping file name -> duration.",
    "NullBackend.capabilities": "A `Capabilities` object describing what to simulate.",
    "NullBackend.metadata": "Mapping returned by `metadata()`.",
    "NullBackend.fail": "Mapping method name -> exception to raise (test error paths).",
    "NullBackend.require_exists": "Raise if the file does not exist.",
    "SubprocessBackend.command": "Argument *list* of the external player, e.g. `['mpv', '--no-video']` (never a shell string).",
    "SubprocessBackend.popen": "Injectable `Popen` factory (tests).",
    "SubprocessBackend.which": "Injectable `shutil.which` (tests).",
    "WinsoundBackend.winsound": "Injectable `winsound` module (tests).",
    "SpectrumAnalyzer.path": "Path of a PCM `.wav` file to analyse.",
}

# Allowed-value tables and other facts printed under the parameter table of a class.
NOTES: dict[str, str] = {
    "Gauge": "Gauge kinds: `circular`, `speedometer`, `semicircular`, `thermometer`.",
    "Chart": "Datasets are `Dataset(name, values, labels=[], xs=[], visible=True)`; pass them to `set_data([...])`.",
    "Form": "Field kinds: `text`, `int`, `float`, `checkbox`, `dropdown`, `date`, `textarea`. Validators are callables `value -> error text | None`.",
}

SHOW = '''from widgets import Screen, run_app

def show(*widgets, width=80, height=24):
    """Put widgets on a screen and run until you press q."""
    screen = Screen(width, height)
    for w in widgets:
        screen.add(w)
    run_app(screen, quit_keys=("q",))
'''

# Class -> list of (title, code). Code uses show(); `--check` replaces show() with a headless stub.
EXAMPLES: dict[str, list[tuple[str, str]]] = {}


def ex(cls: str, title: str, code: str) -> None:
    EXAMPLES.setdefault(cls, []).append((title, code.strip("\n")))


# ------------------------------------------------------------------ display
ex(
    "Box",
    "Titled box with padding",
    """
from widgets import Box
show(Box(2, 1, 40, 7, text="Hello,\\nworld", border="rounded", align="center", valign="middle", padding=1))
""",
)
ex(
    "Box",
    "Every parameter",
    """
from widgets import Box, Style, RGB, get_gradient
show(Box(
    x=2, y=1, width=44, height=9,
    text="Long text that wraps inside the box and shows the shadow",
    border="double", align="left", valign="top", padding=(0, 2, 0, 2), overflow="wrap",
    style=Style(fg=RGB(255, 255, 255), bold=True),
    border_style=Style(fg=RGB(80, 200, 255)),
    gradient=get_gradient("rainbow") if False else None,
    shadow=(1, 1, "░", Style(fg=RGB(70, 70, 70))),
    ascii_only=False, name="info",
))
""",
)
ex(
    "Spinner",
    "Spinner with text",
    """
from widgets import Spinner
show(Spinner(2, 2, 30, spinner="dots", text="Loading...", speed=12))
""",
)
ex(
    "Spinner",
    "Every parameter",
    """
from widgets import Spinner, Style, RGB
show(Spinner(
    x=2, y=2, width=30, spinner="pulse", text="Working", speed=8.0, align="left",
    style=Style(fg=RGB(255, 200, 0), bold=True), gradient=None,
    ascii_only=False, reduced_motion=False, beat_source=None, name="busy",
))
""",
)
ex(
    "SpinnerGroup",
    "Several spinners on consecutive rows",
    """
from widgets import Spinner
from widgets.display import SpinnerGroup
group = SpinnerGroup(2, 2, 30)
for name in ("dots", "line", "pulse", "arc"):
    group.add(Spinner(0, 0, 30, spinner=name, text=name))
group.start_all()
""",
)
ex(
    "Marquee",
    "Scrolling banner",
    """
from widgets import Marquee
show(Marquee(0, 2, 60, 1, text="Breaking news: widgets 1.0 released   ", direction="left", speed=12))
""",
)
ex(
    "Marquee",
    "Every parameter",
    """
from widgets import Marquee, Style, RGB
show(Marquee(
    x=0, y=2, width=50, height=1, text="BOUNCING TEXT", direction="left", mode="bounce",
    speed=10.0, gap=6, font=None, align="left",
    style=Style(fg=RGB(0, 255, 180)), gradient=None, reduced_motion=False, name="m",
))
""",
)
ex(
    "AnimatedText",
    "Typewriter",
    """
from widgets.display import AnimatedText
show(AnimatedText(2, 2, 40, 1, text="Typing one letter at a time", mode="typewriter", speed=12, cursor="█"))
""",
)
ex(
    "AnimatedText",
    "Every parameter",
    """
from widgets.display import AnimatedText
from widgets import Style, RGB
show(AnimatedText(
    x=2, y=2, width=40, height=3, text="WAVE", mode="wave", speed=10.0, duration=None, loop=True,
    easing="ease_in_out", bidirectional=False, amplitude=1.0, wavelength=8.0, cursor="_",
    spinner=None, placement="before", seed=1, style=Style(fg=RGB(255, 120, 200)),
    gradient=None, background=None, on_complete=None, ascii_only=False, reduced_motion=False, name="t",
))
""",
)
ex(
    "Sign",
    "Large-font sign",
    """
from widgets.display import Sign
show(Sign(0, 1, 60, 9, text="HELLO", font="original-5", mode="static", border="double"))
""",
)
ex(
    "Sign",
    "Every parameter",
    """
from widgets.display import Sign
from widgets import Style, RGB
show(Sign(
    x=0, y=1, width=60, height=9, text="NEON", font="rounded-5", mode="gradient-scroll",
    border="single", align="center", padding=1, style=Style(fg=RGB(255, 255, 0)),
    gradient=None, speed=6.0, ascii_only=False, reduced_motion=False, name="sign",
))
""",
)
ex(
    "Neon",
    "Neon sign",
    """
from widgets import Neon
show(Neon(2, 2, 50, 7, text="OPEN", font="original-5", colors=("#ff00ff", "#00ffff")))
""",
)
ex(
    "Neon",
    "Every parameter",
    """
from widgets import Neon
show(Neon(
    x=2, y=2, width=50, height=7, text="NEON", colors=("#ff2d95", "#2de2ff"), gradient=None,
    palette=None, font="original-5", outline=False, speed=0.5, flicker=True, fade=False,
    align="left", wrap=False, reduced_motion=False, name="neon",
))
""",
)
ex(
    "MatrixRain",
    "Matrix rain revealing a word",
    """
from widgets import MatrixRain
show(MatrixRain(0, 0, 60, 16, text="WAKE UP", mode="reveal", reveal_after=2.0, seed=7))
""",
)
ex(
    "MatrixRain",
    "Every parameter",
    """
from widgets import MatrixRain
show(MatrixRain(
    x=0, y=0, width=60, height=16, text="NEO", charset="01", density=0.5, speed=8.0, seed=3,
    gradient=None, mode="rain", reveal_after=2.0, reduced_motion=False, name="rain",
))
""",
)
ex(
    "Gauge",
    "Speedometer with colour thresholds",
    """
from widgets import Gauge, RGB
g = Gauge(2, 1, 30, 10, kind="speedometer", value=72, minimum=0, maximum=100, title="CPU", unit="%",
          thresholds=((0, RGB(0, 200, 0)), (60, RGB(255, 180, 0)), (85, RGB(255, 0, 0))), ticks=5)
show(g)
""",
)
ex(
    "Gauge",
    "Every parameter",
    """
from widgets import Gauge, RGB
show(Gauge(
    x=2, y=1, width=20, height=8, kind="thermometer", value=21.5, minimum=-10.0, maximum=40.0,
    title="Temp", unit="C", thresholds=((-10, RGB(0, 120, 255)), (25, RGB(255, 120, 0))),
    gradient=None, ticks=6, ascii_only=False, name="temp",
))
""",
)
ex(
    "Sparkline",
    "Live history",
    """
from widgets import Sparkline
s = Sparkline(2, 2, 40, values=[1, 3, 2, 5, 4, 8, 6])
s.push(9)
show(s)
""",
)
ex(
    "Heatmap",
    "Grid of values",
    """
from widgets import Heatmap
show(Heatmap(2, 1, data=[[0, 1, 2, 3], [3, 2, 1, 0], [1, 3, 1, 3]], row_labels=["a", "b", "c"], gradient="heat"))
""",
)
ex(
    "Stepper",
    "Wizard steps",
    """
from widgets import Stepper
s = Stepper(2, 2, 60, steps=["Fetch", "Build", "Test", "Deploy"], current=1)
s.advance()   # Build done, Test active; s.fail() marks the active step failed
show(s)
""",
)
ex(
    "Tabs",
    "Pages",
    """
from widgets import Tabs, Box
tabs = Tabs(0, 0, 60, 12)
tabs.add_page("One", Box(0, 0, 58, 10, text="first page"))
tabs.add_page("Two", Box(0, 0, 58, 10, text="second page"))
show(tabs)   # ctrl+pagedown / alt+1..9 switch
""",
)
ex(
    "SplitPane",
    "Two panes",
    """
from widgets import SplitPane, Box
show(SplitPane(0, 0, 70, 12, first=Box(0, 0, 10, 5, text="left"), second=Box(0, 0, 10, 5, text="right"),
               orientation="horizontal", ratio=0.4))
""",
)
ex(
    "NotificationCenter",
    "Post notifications",
    """
from widgets import NotificationCenter, NotificationType
nc = NotificationCenter(0, 0, 50, 6, placement="top", default_duration=5.0, max_queue=50,
                        overflow="drop_oldest", max_visible=3, fade=True)
nc.post("Saved", NotificationType.SUCCESS)
nc.post("Disk almost full", NotificationType.WARNING, duration=8)
show(nc)
""",
)
ex(
    "CalendarWidget",
    "Month picker",
    """
from widgets import CalendarWidget
show(CalendarWidget(2, 1, year=2026, month=11, first_weekday=0, on_select=lambda d: print(d)))
""",
)
ex(
    "ClockWidget",
    "World clock",
    """
from widgets import ClockWidget
show(ClockWidget(2, 2, tz="UTC", seconds=True, font="original-5"))
""",
)
ex(
    "Countdown",
    "10-second countdown",
    """
from widgets import Countdown
show(Countdown(10, 2, 2, on_complete=lambda: print("done")))
""",
)
ex(
    "TimerWidget",
    "Pomodoro",
    """
from widgets import TimerWidget
show(TimerWidget(2, 1, 40, 7, mode="pomodoro", font="original-5"))
""",
)
ex(
    "TimerWidget",
    "Custom phases",
    """
from widgets import TimerWidget
show(TimerWidget(2, 1, 40, 7, mode="countdown", phases=[("warm-up", 60), ("work", 300), ("cool-down", 60)],
                 autostart=True, on_finish=lambda: print("finished")))
""",
)
ex(
    "CommandPalette",
    "Ctrl-P style launcher",
    """
from widgets import CommandPalette
show(CommandPalette(5, 2, 50, 10, commands={"Say hi": lambda: print("hi"), "Quit": lambda: None}))
""",
)
ex(
    "GridGame",
    "Maze game",
    """
from widgets import GridGame
show(GridGame(2, 1, 40, 12, on_win=lambda moves: print("won in", moves)))
""",
)
ex(
    "ImageView",
    "Gradient image",
    """
from widgets import ImageView
show(ImageView.gradient(40, 16, 2, 1))   # ImageView.from_file("pic.png", max_width=60) needs Pillow
""",
)
ex(
    "QrView",
    "QR code",
    """
from widgets import QrView
show(QrView(2, 1, text="https://github.com/GeorgiosZaxos/widgets", border=2))   # needs: pip install qrcode
""",
)
ex(
    "VerticalPrint",
    "Vertical text",
    """
from widgets import VerticalPrint
show(VerticalPrint(2, 1, 6, 14, text="HELLO", direction="down", spacing=0, border="single", padding=0))
""",
)
ex(
    "VerticalPrint",
    "Every parameter",
    """
from widgets import VerticalPrint, Style, RGB
show(VerticalPrint(
    x=2, y=1, width=6, height=14, text="WIDGETS", font=None, direction="up", spacing=1,
    align="center", style=Style(fg=RGB(0, 255, 255)), gradient=None, border="rounded",
    padding=1, ascii_only=False, name="vp",
))
""",
)
ex(
    "SpaceCrawlWidget",
    "Star-Wars style crawl",
    """
from widgets.display import SpaceCrawlWidget
show(SpaceCrawlWidget(0, 0, 80, 24, text="EPISODE I\\n\\nA long time ago...", speed=1.2, seed=1, loop=False))
""",
)
# ------------------------------------------------------------------ progress
ex(
    "HorizontalBar",
    "State-driven bar",
    """
from widgets import HorizontalBar, ProgressState
st = ProgressState(100)
bar = HorizontalBar(st, 50, style="smooth")
st.set(42)
show(bar)
""",
)
ex(
    "HorizontalBar",
    "Every parameter",
    """
from widgets import HorizontalBar, ProgressState, Style, RGB
st = ProgressState(total=2_000_000, description="download")
st.set(500_000)
show(HorizontalBar(
    st, width=70, style="classic", ascii_only=False,
    fill_style=Style(fg=RGB(0, 200, 120)), empty_style=Style(dim=True), gradient=None, spinner="dots",
    show_percentage=True, show_count=True, show_time=True, show_speed=True,
    unit="B", unit_scale=True, unit_divisor=1024, bar_format=None, min_bar=5, name="dl",
))
""",
)
ex(
    "VerticalBar",
    "Vertical bar",
    """
from widgets import VerticalBar, ProgressState
st = ProgressState(100)
st.set(65)
show(VerticalBar(st, 10, style="eighths", orientation="bottom-up", animate="pulse"))
""",
)
ex(
    "CircularIndicator",
    "Ring",
    """
from widgets import CircularIndicator, ProgressState
st = ProgressState(100)
st.set(70)
show(CircularIndicator(st, diameter=7))
""",
)
ex(
    "SpinnerIndicator",
    "Indeterminate spinner",
    """
from widgets import SpinnerIndicator
show(SpinnerIndicator(spinner="dots", text="Thinking...", speed=10))
""",
)
ex(
    "ProgressState",
    "Counters and statistics",
    """
from widgets import ProgressState
st = ProgressState(total=200, description="files", smoothing=0.3, stall_timeout=10.0)
st.update(50)      # add 50
st.set_postfix(file="a.txt")
print(st.fraction, st.eta, st.speed, st.stalled, st.snapshot())
""",
)
ex(
    "ProgressManager",
    "Several bars in one inline region",
    """
import time
from widgets import ProgressManager, ProgressState, HorizontalBar
mgr = ProgressManager(mininterval=0.1)
a, b = ProgressState(50, description="a"), ProgressState(80, description="b")
mgr.add(HorizontalBar(a)); mgr.add(HorizontalBar(b))
for _ in range(50):
    a.update(1); b.update(1.6); mgr.refresh(); time.sleep(0.02)
mgr.write("a log line printed above the bars")
mgr.close()
""",
)
# ------------------------------------------------------------------ data
ex(
    "Table",
    "Sortable table",
    """
from widgets import Table
t = Table(0, 0, 60, 12, columns=["Name", "Qty", "Price"],
          rows=[["apple", 3, 1.5], ["pear", 10, 0.8]],
          header=True, borders=True, row_numbers=True, widths=["30%", 6, "auto"], align=["left", "right", "right"])
t.sort(1, reverse=True)
show(t)
""",
)
ex(
    "Table",
    "Loading data",
    """
from widgets import Table
t = Table(0, 0, 70, 12)
t.load_csv("a,b\\n1,2\\n3,4")
t.load_json('[{"a": 1, "b": 2}]')
t.load_delimited("x|y\\n1|2", delimiter="|")
# t.load_excel("file.xlsx")   # needs widgets[excel]
# t.load_dataframe(df)        # needs widgets[data] (pandas)
show(t)
""",
)
ex(
    "Chart",
    "Bar and line charts",
    """
from widgets import Chart
from widgets.data import Dataset
c = Chart(0, 0, 60, 14, kind="bar", title="Sales", grid=True, legend=True, show_values=True)
c.set_data([Dataset("Q1", [3, 5, 2], labels=["a", "b", "c"]), Dataset("Q2", [4, 1, 6])])
show(c)   # kinds: bar, line, pie, scatter, area
""",
)
ex(
    "Tree",
    "Tree from Python data",
    """
from widgets import Tree
from widgets.data import from_python
show(Tree(0, 0, 50, 14, root=from_python({"a": [1, 2], "b": {"c": 3}}, "data"), on_select=lambda n: print(n.label)))
""",
)
ex(
    "CodeEditor",
    "Highlighted editor",
    """
from widgets import CodeEditor
ed = CodeEditor(0, 0, 70, 16, text="def f(x):\\n    return x * 2\\n", language="python",
                line_numbers=True, read_only=False, tab_width=4)
ed.find("return")
show(ed)    # ctrl-s style saving is explicit: ed.save("out.py")
""",
)
ex(
    "Form",
    "Validated form",
    """
from widgets import Form
from widgets.data import Field
form = Form(0, 0, 60, fields=[
    Field("name", "text", "Name", required=True, max_length=20),
    Field("age", "int", "Age", minimum=0, maximum=120),
    Field("color", "dropdown", "Colour", options=["red", "green", "blue"]),
    Field("agree", "checkbox", "I agree"),
], on_submit=lambda values: print(values), on_cancel=lambda: print("cancel"), on_change=lambda n, v: None)
show(form)
""",
)
ex(
    "DirectoryTree",
    "File browser",
    """
from widgets import DirectoryTree
show(DirectoryTree(0, 0, 70, 18, root=".", show_hidden=False, sort="name", show_size=True, show_date=True))
""",
)
ex(
    "LogViewer",
    "Log with filter",
    """
from widgets import LogViewer
lv = LogViewer(0, 0, 80, 12, max_entries=500, show_time=True)
lv.log("started"); lv.log("careful", "WARNING"); lv.log("boom", "ERROR")
lv.set_filter("", min_level="WARNING")
show(lv)
""",
)
ex(
    "KanbanBoard",
    "Board",
    """
from widgets import KanbanBoard
show(KanbanBoard(0, 0, 72, 14, columns={"Todo": ["write docs"], "Doing": ["tests"], "Done": ["ci"]}))
""",
)
ex(
    "MarkdownView",
    "Markdown renderer",
    """
from widgets import MarkdownView
show(MarkdownView(0, 0, 70, 16, text="# Title\\n\\n- item\\n- **bold** item\\n\\n> quote"))
""",
)
ex(
    "ProcessMonitor",
    "Top processes",
    """
from widgets import ProcessMonitor
show(ProcessMonitor(0, 0, 70, 14, fetch=lambda: [{"pid": 1, "name": "init", "cpu": 0.5, "mem": 1.2}], interval=1.0))
""",
)
ex(
    "DashboardGrid",
    "Dashboard layout",
    """
from widgets import Gauge, Sparkline
from widgets.data import DashboardGrid
g = DashboardGrid(0, 0, 80, 20, rows=2, cols=2, gap=1)
g.add_widget(Gauge(0, 0, 10, 8, value=40), 0, 0)
g.add_widget(Sparkline(0, 0, 20, values=[1, 2, 3]), 0, 1, colspan=1)
show(g)
""",
)
ex(
    "MetricDashboard",
    "Live metric with sparkline",
    """
import random
from widgets.data import MetricDashboard
show(MetricDashboard(0, 0, 40, 4, fetch=lambda: random.random() * 100, interval=0.5,
                     history_size=60, label="load", unit="%"))
""",
)
ex(
    "TextDashboard",
    "Latest value as text",
    """
import time
from widgets.data import TextDashboard
show(TextDashboard(0, 0, 40, 3, fetch=lambda: time.strftime("%H:%M:%S"), interval=1.0, formatter=str))
""",
)
# ------------------------------------------------------------------ net
ex(
    "RssTicker",
    "Multi-lane ticker",
    """
from widgets import RssTicker, TickerLane
from widgets.net import FeedSource
lanes = [
    TickerLane(FeedSource("BBC", "https://feeds.bbci.co.uk/news/rss.xml"), direction="left", speed=10, color="#00ffff"),
    TickerLane(FeedSource("HN", "https://news.ycombinator.com/rss"), direction="right", speed=6, color="#ffaa00"),
]
show(RssTicker(0, 0, 80, lanes=lanes, spacing=1, max_items=30, refresh_interval=300.0, show_speed=True))
""",
)
ex(
    "RssReader",
    "Feed reader",
    """
from widgets.net import RssReader, FeedSource
show(RssReader(0, 0, 80, 20, sources=[FeedSource("BBC", "https://feeds.bbci.co.uk/news/rss.xml", "News")], view="list"))
""",
)
ex(
    "WeatherWidget",
    "Forecast",
    """
from widgets.net import WeatherWidget
show(WeatherWidget(0, 0, 60, 14, location="Athens", units="metric", days=5, cache_ttl=600.0))
""",
)
# ------------------------------------------------------------------ audio
ex(
    "MusicPlayer",
    "Player with the null backend",
    """
from widgets.audio import MusicPlayer, NullBackend
show(MusicPlayer(0, 0, 60, 18, backend=NullBackend(), directory=".", volume=70, autoplay_next=True, bands=24))
""",
)
ex(
    "Equalizer",
    "Equalizer",
    """
from widgets.audio import Equalizer
show(Equalizer(0, 0, 32, 6, bands=16, preset="bass", simulate=True))
""",
)
ex(
    "Oscilloscope",
    "Oscilloscope",
    """
import math, time
from widgets.audio import Oscilloscope
show(Oscilloscope(0, 0, 60, 8, source=lambda n: [math.sin(i / 3 + time.time()) for i in range(n)]))
""",
)
ex(
    "SynchronizedPlayer",
    "Audio + visuals together",
    """
from widgets.audio import NullBackend, SynchronizedPlayer, Equalizer
eq = Equalizer(0, 0, 32, 6)
with SynchronizedPlayer(NullBackend(), [eq], duration=5.0, drive_visuals=True) as sp:
    sp.start("song.wav")
    sp.update(0.1)
""",
)
