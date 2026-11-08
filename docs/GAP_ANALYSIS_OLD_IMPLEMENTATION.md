# Gap analysis: `Old_Implementation` vs. the new `widgets` package

**Method.** I extracted every public class, method and constructor parameter of the 26 old modules (AST scan, ~700 KB) and compared them with the new package using targeted searches and the existing tests. I did **not** read each old function body, so "present" means the capability exists in the new package, not that behaviour is identical. Legacy asset files (borders, fonts, colours, spinners, bar styles, unicode tables) were already integrated in the earlier asset passes and are not repeated here.

Legend - **Effort**: S = under 1 h, M = a few hours, L = a day or more. **Done now** = implemented in this pass.

## A. Capabilities of the old code that are missing or reduced

| # | Old module | Old capability | New status | Implementable? (effort) | Done now |
|---|---|---|---|---|---|
| 1 | `code_editor_widget` + `syntax.json` | Highlighting for 10 languages (python, javascript, java, c, c++, go, rust, typescript, php, swift) | Only python and javascript | Yes (S) | **Yes** - 8 languages added (keyword + comment/string/number rules); the legacy regexes were double-escaped, so keywords were re-extracted |
| 2 | `code_editor_widget` | `open_file`/`load_file` with syntax auto-detect by extension | `language` must be passed explicitly | Yes (S) | No |
| 3 | `code_editor_widget` | Selection, clipboard, search (SRS FR-CODE-009) | Not implemented (known gap) | Yes (M) | No |
| 4 | `matrix_widget` | Modes `vt` (terminal-cursor typing emulation) and `encrypted` (scrambled text that reveals/fades, rolling chars), separate rain/text/encrypted gradients, `random_seed` | `MatrixRain` has `rain`, `reveal`, `fade`, one gradient, seed | Yes (M) - reveal/fade partly overlap `encrypted`; `vt` is new work | No |
| 5 | `neon_signs_widget` | Font styles (`FontStyles`), outline + outline colour, colour palettes, glow intensity/speed, colour-cycle speed | `Neon` has gradient cycling + flicker only | Yes (M) | No |
| 6 | `sign_widget` | Animation modes (typewriter, fade in/out, wave, bouncing, dual marquee, gradient scroll, neon), 7 border modes, `create_banner`, `create_animated_title` helpers | `Sign` has 6 modes and borders via `assets.borders`; no helper functions; no `fade-out`/`dual marquee` parity checked | Yes (S-M) | No |
| 7 | `marquee` | `Direction.SNAKE`; `ScrollDirection` diagonal and wave; colour modes solid/gradient/rainbow/line-gradient/vertical-gradient; `LargeFontMarquee` | left/right/up/down + bounce; gradients via `Gradient`; large font via `font=`; **no snake/diagonal**; rainbow only via a custom gradient | Yes (M) | No |
| 8 | `progress` (vertical) | `VerticalAnimationMode` (pulse, scan, wave, bounce, fill, rainbow, fire, spinner), `VerticalDirection` (bottom, top, center, split, rain), themes, emoji mode | `VerticalBar` bottom-up/top-down only; styles from the asset table | Yes (M-L) | No |
| 9 | `progress` (both) | tqdm ecosystem shims: `wrapattr`, `pandas()`, `contrib.tenumerate/tzip/tmap`, `tqdm.asyncio` (`gather`, `as_completed`), notebook/keras/dask/tk/rich stubs | Core `tqdm`, `trange`, context manager, `write` only | Partly: `wrapattr`, `contrib` (S), `asyncio` (S), `pandas` (S, optional dep). notebook/keras/dask/tk/rich were stubs and are better left out | No |
| 10 | `progress` (both) | `bar_format`, `ncols` auto layout, `lock_args`, `write_bytes`, `delay`, `unit_divisor` | `bar_format` accepted and ignored (documented); no `delay`/`unit_divisor`/`write_bytes` | Yes (M) | No |
| 11 | `progress` | `ETACalculator` (windowed speed, smoothing, stall threshold) | `ProgressState` has smoothing and `stall_timeout`; window differs | Equivalent for practical use | n/a |
| 12 | `star_wars_widget` | `LightsaberTextRoll` intro, object types (planet, tie, falcon), star gradients, `trigger_lightsaber_roll` | Original-content `SpaceCrawlWidget`: stars, galaxies, nebulae, pulsars | Lightsaber roll yes (M). **TIE fighter / Falcon / the title are third-party trademarks (D-16)** - will not be reproduced; original equivalents (e.g. a comet or ship sprite) are fine | No |
| 13 | `mid_player_widget` | Expandable audio **file tree** (`AudioNode`), per-band `FrequencyBand` info (name, typical sounds, palette), equalizer dB adjustment per band (`adjust_band`, reset), real-time spectrum, MIDI playback | `MusicPlayer` is a flat list; presets only; no per-band adjust or band info; levels only from a backend that provides them (none of the 3 real backends does); MIDI only if a backend declares it | Tree browser (M), band info/adjust (M); **real spectrum and MIDI need a decoder dependency** (e.g. pygame/numpy) - L, outside the zero-dependency rule unless made an optional extra | No |
| 14 | `music_play_widget` | `WidgetRunner` (run any widget with music), `SimpleAudioPlayer` | Covered by `SynchronizedPlayer` + `AudioBackend`; no one-line runner helper | Yes (S) | No |
| 15 | `chart_widget` | `show_legend`, `show_grid`, `show_values` flags | Chart supports 5 kinds; need to verify the three flags | Check (S) | No |
| 16 | `gauge_widget` | Circular, semi-circular, speedometer, thermometer, ticks/min-max/gradient | Same four kinds present; options not diff-checked | Check (S) | No |
| 17 | `form_widget` | Field types `date`, `textarea`; custom `validation` callable per field; `get_values/set_values` | Types: text, int, float, checkbox, dropdown. **No date, no textarea** | Yes (M) | No |
| 18 | `dashboard_widget` | **Grid host** of arbitrary widgets (`add_widget(row, col, rowspan, colspan)`, `remove_widget`, `save_layout`) | `TextDashboard`/`MetricDashboard` poll data sources; **no grid container for arbitrary widgets** (the generic `Container` does free placement only) | Yes (M) | No |
| 19 | `calendar_widget` | Big-digit clock using derived fonts (`derive_font_by_rows`, `build_font_set`, `render_big_text`) with colour blocks | `ClockWidget` renders plain text; the large fonts exist in `assets.fonts` but are not wired to the clock | Yes (S) | No |
| 20 | `tree_widget` | `expand_all`, `collapse_all`, `move_to_root/parent/first_child/bottom`, page keys, tree info panel | Arrow/home/end navigation and expand/collapse per node; **no expand-all/collapse-all, no info panel** | Yes (S) | No |
| 21 | `table_widget` | `load_excel_simple`, `load_pipe_delimited`, `show_file_info` | `load_excel` (needs openpyxl), `load_pipe`, tsv, csv, json, dataframe; no file-info panel | Mostly covered | n/a |
| 22 | `notification_widget` | `position` top/bottom, `custom_colors` | Types and fade present; configurable position/custom colours need checking | Check (S) | No |
| 23 | `rss_reader` | `RSSShow` curated categories, `speed_up/down`, `switch_dir`, `BoxRSSShow` | All present as keys/views (`+`/`-`, `v`) in the demo; box view built in | Covered | n/a |
| 24 | `weather_widget` | Open-Meteo forecast + geocoding | Same endpoints, plus provider protocol, cache, stale, units | Covered (superset) | n/a |
| 25 | `text_animator` | `TextAnimator.animate/multi_line_animate` | `AnimatedText` (8 modes) | Covered | n/a |
| 26 | `spinner_widget` | `SpinnerWidget`, `MultiSpinner` | `Spinner`, `SpinnerGroup` (+ beat sync) | Covered | n/a |
| 27 | `box_widget` | Shadow (offset, colour, intensity), gradient border, `set_colors/set_border/set_shadow` | Shadow tuple and gradient present; per-property setters/intensity not diff-checked | Check (S) | No |
| 28 | `vprint_widget` | Vertical printing | Covered | n/a | n/a |
| 29 | `include/__main__.py`, `include/__init__.py` | Asset browser / listing entry point (`python -m include`) | `widgets.assets.registry.list_asset_groups/list_assets`; no `python -m` command | Yes (S) | No |

## B. Things the new implementation does that the old one did not

Typed API and strict mypy, lifecycle and cleanup guarantees, Windows/POSIX terminal compatibility layer, text sanitising against escape injection, diff-based renderer, deterministic clock/RNG seams, RSS and weather transports with redirect/size/TLS policy, audio backend protocol with `shell=False` subprocess playback, 400+ requirement-tagged tests, benchmarks, security review.

## C. Recommended order if you want these closed

1. Quick wins (S, one pass of ~1 h): #2, #17 partially (date field), #19, #20, #29, and the "Check" items (#15, #16, #22, #27).
2. Visual parity (M): #4, #5, #6, #7, #8, #18.
3. Needs a decision: #13 (real spectrum and MIDI require an optional dependency), #12 (original replacements for trademarked sprites), #9 (which tqdm integrations you actually use).

## D. Implemented in this pass

* Row 1: `widgets/data/_syntax_data.py` (generated keyword tables) and `widgets/data/code.py` (`LANGUAGES`, per-language rules), plus 8 parametrized tests (`FR-CODE-004`). Full suite: 409 tests pass; ruff, `mypy --strict` and the layer check are clean.

---

# E. The `include/` folder (assets and constants)

**Key finding: `Old_Implementation/include` is newer than the legacy files I integrated earlier** (it has more bar styles, spinners and borders). The asset data in `widgets.assets` was generated from the earlier snapshot, so it is a subset in several places. Comparison is by **name** (case/underscore-normalised) and, for borders and symbols, by **glyph content**.

| # | Old file | Old properties | New equivalent | Result | Implementable? |
|---|---|---|---|---|---|
| E1 | `border_types.py` | `BORDER_TYPES_1` - 39 styles (dict of `tl tr bl br h v`) | `assets.borders` - 22 styles | **16 old styles have no glyph-equivalent**: arrow, music, flame, sparkle, flower, moon, bullet, double_vert, triple_dash, bold_dashed, retro_slash, brackets, parentheses, solid_thick, modern_slim, bold_rounded. Names also differ (`double_heavy`, `shade_dark` ... are covered under other names) | Yes (S) - add to generator data |
| E2 | `barstyles.py` | `HorizontalBarStyle` (113 members), `VerticalBarStyle` (113), `BarStyle` alias, `get_all_styles/get_horizontal_styles/get_vertical_styles`, categories (`get_styles_by_category`), `is_gradient` flag, `demo_styles` | `assets.bars` - 59 horizontal, 90 vertical, `get_bar_style`, `list_bar_styles` | **60 horizontal and 86 vertical old names missing by name** (e.g. battery, bike, bolt, book, car, clock, coffee, fire, gradient-1..4, hourglass, lock, money, rocket, pizza, ...). Some vertical names are renamed rather than absent; 6 horizontal and 63 vertical new names are not in the old file. **No category lookup, no `is_gradient`** | Yes (M) - regenerate + add categories |
| E3 | `spinners.py` | `SPINNER_STYLES` (118), `get_spinner_style`, `get_all_styles`, `get_styles_by_category`, `get_style_info` | `assets.spinners` - 115 styles, `get_spinner`, `list_spinners`, `spinner_frames` | **12 missing**: bounce5, dna, dots11, dots12, earth, emoji-moon, fish, moon, progress-bars, radar, snake, spin. **8 have different frames** than the old file: balloon, bounce, box, circle, flip, line, star, triangle (e.g. old `line` starts `\| / - \`, mine starts `- \ \| /`; old `bounce` is a `[    ]` bracket animation). No category / info API | Yes (S) |
| E4 | `color_constants.py` | `ColorConstants`: 161 colours (basic 37, backgrounds 16, HTML 108), 24 monochromatic + 32 multicolour + special gradients (97 total), 28 palettes, `hex_to_rgb`, `rgb_to_hex`, `is_valid_hex`, `normalize_hex`, `get_all_*_names`, plus module constants BLACK...GRAY | `base_elements.color_manager` / `assets.colors`: 161 colours, 133 gradients, 30 palettes | **Complete** - no colour, gradient or palette is missing (mine is a superset) | n/a |
| E5 | `large_text_characters.py` | `ascii_4x7` (69 chars), `BASE_CHARS`, 6 `BORDER_STYLES`, `HEIGHT_TO_KEEP_ROWS_1BASED` (heights 3-7), `derive_height_font`, `style_font`, `get_styled_font`, `render_large_text`, `glyph_height`, `validate_font` | `assets.fonts` - 30 horizontal fonts (6 styles x 5 heights), `render_text`, `validate_font`, `font_height` | Same structure (6 x 5). **Glyph-level diff not done**; the old file is newer, so glyph changes are possible | Check (S) |
| E6 | `unicode_arrows.py` | `ARROWS_EXTENDED` (119) | `assets.symbols` group `arrows` | All characters present except 8 emoji-presentation arrows (`↖️ ↗️ ↘️ ↙️ ➡️ ⬅️ ⬆️ ⬇️`, which carry a variation selector) | Yes (S) |
| E7 | `unicode_blocks.py` | `BLOCK_ELEMENTS` 16, `BOX_DRAWING` 39, `GEOMETRIC_SHAPES` 37, `ARROWS` 20, `CharacterSet` selector | `symbols` groups block-elements, box-drawing, geometric-shapes, arrows | **All characters present** | n/a |
| E8 | `unicode_misc.py` | `MISC_CHARACTERS` (231) | `symbols` group `misc` | All present except `☉` (U+2609) | Yes (S) |
| E9 | `unicode_CharacterSets.py` | `UNICODE_BLOCKS_HIERARCHICAL` (16 categories, 100 blocks), `list_categories`, `list_blocks`, `search_blocks`, `find_block_by_char`, `find_block_by_codepoint`, `iter_block_chars`, `get_block_chars`, `codepoint_info`, `print_tree/category/block/char_info` | `symbols`: 219 flat blocks, `list_unicode_blocks`, `search_blocks`, `find_block` | Block data is a superset (219 vs 100). **Missing API**: hierarchical categories (`list_categories`), `iter_block_chars/get_block_chars`, `codepoint_info`, text printers | Yes (S-M) |
| E10 | `__init__.py` | Lazy registry of all asset modules, `get_load_stats()`, eager `BORDER_TYPES`, `ColorConstants`, `SPINNER_STYLES`, `HorizontalBarStyle`, ... | `assets.registry.list_asset_groups/list_assets`; `widgets.include` shims | Equivalent for lookup; **no load statistics** | Yes (S) |
| E11 | `__main__.py` | `python -m widgets.include` diagnostics (lists borders, lazy-load stats) | None | **Missing** | Yes (S) |
| E12 | (not in the folder) `vertical_large_text_characters.py` | Vertical fonts (33 in mine) | `assets.fonts` vertical | The folder you gave me does not contain this file; the 33 vertical fonts come from the earlier snapshot | n/a |

## What I tried and did not apply

I re-ran `tools/gen_asset_data.py` on a scratch copy against this newer `include` folder (merged over the earlier snapshot so the vertical fonts are kept). It does **not** work unchanged: `ColorConstants.ALL_MATRIX_HEX` no longer exists (I patched that with a fallback, but the matrix gradients would then be lost - gradients would drop from 133 to about 98), and the generator's Unicode-block step fails (`_flat_blocks` was removed from the new `unicode_CharacterSets.py`). Nothing was changed in your project for this. To close E1-E3 and E6/E8 I would (1) keep the earlier snapshot as the source of the matrix gradients and blocks, (2) overlay the newer borders, bars and spinners, (3) regenerate and re-run the tests (an asset test pins the gradient count, so it must be updated deliberately).

## G. Visual-parity pass

Closed: #4 MatrixRain `vt` (typed text, blinking cursor) and `encrypted` (scrambled glyphs resolving to text) modes; #5 Neon `palette=`, `font=` and `outline=`; #6 `create_sign` / `create_banner`; #7 Marquee `diagonal` and `snake` directions; #8 VerticalBar fills `center-out` / `edges-in` and `animate="pulse"|"scan"`. Tests: `tests/test_m10_visual_gaps.py`.

Still open: #10 `bar_format`/`delay`/`unit_divisor`/`write_bytes`/pandas hook; #12 original-content roll intro; #13 audio file tree, band adjust, spectrum, MIDI (needs a decoder dependency decision); #14 `WidgetRunner`; parity checks #15, #16, #22, #27.

## H. tqdm options pass

Closed #10: `bar_format` (tqdm placeholders), `delay`, `unit_divisor`, `write_bytes`, `tqdm.pandas()` (`progress_apply`, `progress_map`, groupby). Tests: `tests/test_m11_tqdm_options.py`. (The framework shims were added later; see section J.)

## I. Final closure pass

Closed: #12 `SpaceCrawlWidget(intro=..., intro_time=...)` (original text, fade-in intro before the crawl); #13 (partly) `Equalizer.set_band_gain/adjust_band/reset_bands` and `MusicPlayer.browse/enter_directory` (file tree); #14 `WidgetRunner`. Tests: `tests/test_m12_final_gaps.py`.

Not implemented: MIDI playback and MP3/other decoders (spectrum analysis was added later, section K; the equalizer is simulated and labelled as such without a source); parity checks #15/#16/#22/#27 remain manual review items.

## J. tqdm framework shims

Implemented in `widgets.progress.integrations`: `TqdmKerasCallback`, `TqdmDaskCallback`, `tqdm_notebook`/`tnrange` (terminal bar), `tqdm_tk`, `tqdm_rich`. Tests: `tests/test_m14_integrations.py` (fake frameworks; real Keras/dask/tk/rich not exercised).

## K. Spectrum analysis, new widgets and ticker

* Spectrum: `widgets.audio.spectrum.SpectrumAnalyzer` (numpy FFT over PCM WAV decoded by stdlib `wave`; extra `audio`), demo `examples/spectrum_demo.py`, tests `tests/test_m13_spectrum.py`. MP3 and MIDI remain unsupported.
* `WidgetRunner` (`widgets.render.run`) and `run_app(..., on_event=)` cover the old launcher.
* 14 new widgets (M15): `Tabs`, `SplitPane`, `Stepper`, `Sparkline`, `Heatmap`, `LogViewer`, `CommandPalette`, `TimerWidget`, `ImageView`, `QrView`, `KanbanBoard`, `MarkdownView`, `Oscilloscope`, `ProcessMonitor`, `GridGame`. Tests `tests/test_m15_new_widgets.py`; showcase `examples/dev_showcase.py` (40 entries) and `examples/color_gallery.py`.
* `RssTicker` / `TickerLane` (`widgets.net.rss_ticker`): several feeds on separate marquee lines with per-lane direction, speed and colour or gradient; keys for per-lane and global speed. Demo `examples/rss_ticker.py`.

## L. Remaining open items

* Parity checks #15, #16, #22, #27 (manual review).
* MIDI playback and MP3 decoding.
* No macOS run; Windows suite verified by the user (455 passed, 7 platform skips); no Windows CI job.
* 7 spec IDs without a test marker (inspection, measurement or manual items, see `TRACEABILITY.md`); `pip-audit` runs in CI only; `LICENSES.md` authorship confirmation outstanding.
* Greek sports feed URLs are unverified from this environment (target sites reject the fetch tool); test them on your machine.
