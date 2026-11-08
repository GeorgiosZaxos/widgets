# Changelog

All notable changes to this project are documented here. Format: [Keep a Changelog](https://keepachangelog.com/),
versioning: [Semantic Versioning](https://semver.org/).

## [Unreleased]

### Added
* tqdm drop-in compatibility: `from widgets import tqdm` (horizontal) or `vtqdm` (vertical) replaces
  `from tqdm import tqdm`. Adds `format_meter`/`format_interval`/`format_sizeof`/`format_num` (output identical
  to tqdm), full constructor options (`ascii`, `colour`, `maxinterval`, `nrows`, `lock_args`, ...), `n`/`total`
  setters, `format_dict`, `display`, `external_write_mode`, `wrapattr`, async iteration, tqdm exception classes,
  and the `widgets.progress.{auto,std,asyncio,notebook,gui,rich,tk,keras,dask,contrib}` modules.
* Look options for `tqdm` and `vtqdm` (keyword-only extras): `spinner`, `gradient`, `colour`, `empty_colour`,
  `style`, `fill` / `empty` glyphs and tqdm-style `ascii="  ▏▎▍█"` charsets.
* Vertical bars share terminal rows (side by side, wrapping at the terminal width); finished bars stay beside
  later ones. Horizontal and vertical bars can be mixed in one region. See `examples/tqdm_mixed_demo.py`.
* `vtqdm` / `vtrange`: vertical-bar variant with the same API (extra `height` option).
* `tests/test_m17_tqdm_compat.py`: demo-derived tests run against `widgets.tqdm`, `vtqdm` and (when installed)
  real tqdm, plus a source-swap test that runs unmodified `from tqdm import ...` code.

## [1.0.0rc1]

### Added
* Core: diffing renderer, colour/width/sanitising layers, widget lifecycle, layout, input, frame loop, `WidgetRunner`.
* Progress: horizontal/vertical bars, multi-bar manager, tqdm-compatible `tqdm` (`bar_format`, `delay`,
  `unit_divisor`, `write_bytes`, `tqdm.pandas()`), Keras/dask/notebook/tk/rich shims.
* Display: `Box`, `Spinner`, `Marquee` (incl. diagonal and snake), `Neon`, `Sign`, `MatrixRain`, `VerticalPrint`,
  gauges, notifications, calendar/clock/countdown, `SpaceCrawlWidget`, `Tabs`, `SplitPane`, `Stepper`,
  `Sparkline`, `Heatmap`, `CommandPalette`, `TimerWidget`, `ImageView`, `QrView`, `GridGame`.
* Data: `Table`, `Chart`, `Tree`, `Form`, `DirectoryTree`, dashboards, `CodeEditor`, `LogViewer`,
  `KanbanBoard`, `MarkdownView`, `ProcessMonitor`.
* Network: `RssReader`, `RssTicker` (multi-lane marquee with per-lane direction, speed and colour), `WeatherWidget`.
* Audio: backends, `MusicPlayer` with file browser, `Equalizer` band adjustment, `SpectrumAnalyzer`, `Oscilloscope`.
* Demos: `dev_showcase.py`, `all_widgets.py`, `color_gallery.py`, `rss_ticker.py`.
* Docstrings on every public class, function and module (enforced by a test); release-hardening tests
  for requirement traceability.
* GitHub project files: CI matrix (Linux, macOS, Windows), release workflow, security policy,
  contribution guide, issue and pull-request templates.

### Known limitations
* Not exercised on macOS by the maintainers; Windows verified on Windows 11 / Python 3.13.
* No MP3 or MIDI support; spectrum analysis reads PCM WAV only.
* Network timeout is a single value (default 10 s), not separate connect/read timeouts (NFR-SEC-001 deviation).
