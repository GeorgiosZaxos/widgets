# Software Requirements Specification: Widgets Terminal UI Toolkit

| Field | Value |
|---|---|
| **Document ID** | SRS-WIDGETS-002 (supersedes WRD-WIDGETS-001 v1.0) |
| **Version** | 2.0 (draft for approval) |
| **Date** | 6 November 2026 |
| **Product** | `widgets` Python package |
| **Target runtime** | CPython 3.13 |
| **Basis** | WRD-WIDGETS-001 v1.0 plus the gap/ambiguity/conflict review of 6 November 2026 |

> **Provenance note.** This specification was derived from the v1.0 requirements definition and the review of it. The 66-module source documentation cited by v1.0 was not available when this document was written. Where this document fixes a value, policy or default that v1.0 left open, it is recorded as a **Decision (D-xx)** in §3 so it can be confirmed or changed in one place.

---

## 0. Changes from v1.0

1. All v1.0 requirement IDs are retained. A **Δ** column marks each requirement: `=` retained, `✎` rewritten to be testable or unambiguous, `+` new.
2. Every requirement now has a **priority** (P1/P2/P3) and a **verification method** (T/I/D/A), defined in §2.2.
3. Conflicts found in the review are resolved by architecture decisions (§3). Examples: inline vs full-screen terminal ownership, buffered vs direct rendering, partial rendering vs diff cache, `update(dt)` vs push data, duplicated color/palette ownership, overlapping effect specifications.
4. Missing areas are added as new groups: lifecycle, layout/composition, event model, effects engine, text safety, calendar, terminal sessions, and testability seams.
5. "Documented" and "where practical" escape hatches are replaced by concrete behavior or an explicit default.
6. Python 3.13 specifics are added (`audioop` removal, typing, free-threaded build, curses on Windows, Unicode data version).
7. Milestones (§11) and a review-finding resolution log (Appendix A) are added.

---

## 1. Purpose and scope

### 1.1 Purpose

This document defines the required behavior, interfaces, quality attributes, constraints and acceptance conditions of the `widgets` package. Requirements describe what the product shall provide, independent of any current implementation state. A requirement is only removed, deferred or made optional by an explicit, versioned product decision (§12).

### 1.2 Product vision

`widgets` shall be a reusable, typed, dependency-light Python toolkit for building interactive, data-oriented and animated terminal user interfaces. It provides one consistent foundation (geometry, lifecycle, input, rendering, terminal control, color, cleanup, progress reporting) together with a library of widgets and visual assets.

### 1.3 In scope

1. Core widget abstractions, geometry, layout/composition, lifecycle, interaction, cleanup.
2. Color management, palettes, gradients, terminal styling.
3. Character-cell screen buffer and render/diff pipeline.
4. Terminal session management, I/O and platform compatibility.
5. Progress indicators, ETA calculation, concurrent progress management, `tqdm`-style helpers.
6. Text, typography, animation and visual-effect widgets (including a shared effects engine).
7. Data display, charts, tables, forms, editors, trees, dashboards, calendar/clock widgets.
8. Notifications and status displays.
9. RSS/feed and weather information widgets.
10. Audio playback and synchronized audio/visual presentation.
11. Reusable Unicode, border, bar, spinner, color and large-text assets.

### 1.4 Out of scope (explicit)

Graphical desktop GUI, browser UI, IDE, visual widget designer, remote terminal service, general-purpose application framework, **mouse input (v2.0)**, **screen-reader integration (v2.0; see NFR-ACC)**, bidirectional (RTL) text shaping, locale-specific number/date formatting beyond time zones (see NFR-I18N).

### 1.5 Intended users

Application developers, widget developers, integrators, end users of applications built with the package.

---

## 2. Conventions

### 2.1 Normative language

**shall** = mandatory; **should** = recommended, deviation needs justification; **may** = optional.

### 2.2 Priority and verification codes

| Code | Meaning |
|---|---|
| **P1** | Required for first release (core, rendering, progress, safety) |
| **P2** | Required for full-feature release |
| **P3** | Desirable; may be deferred by explicit decision |
| **T** | Verified by automated test |
| **I** | Verified by inspection/review (including static analysis, packaging checks) |
| **D** | Verified by demonstration (manual, interactive terminal) |
| **A** | Verified by analysis (e.g. dependency graph, complexity) |

### 2.3 Terms

- **Cell**: one terminal column position holding a glyph (or continuation marker) and a Style.
- **Frame**: a complete `Buffer` snapshot representing the intended screen content.
- **Session**: a `TerminalSession` object that owns the terminal for a period of time (§3, D-01).
- **Untrusted text**: any text originating outside the application's own literals (feeds, weather responses, filenames, file contents, user input, table/JSON/XML data).
- **Style**: immutable, hashable description of foreground, background and text attributes.

---

## 3. Architecture decisions (resolving v1.0 conflicts)

All decisions below are **proposed defaults**. They are normative for this specification until changed via §12.

| ID | Decision | Resolves |
|---|---|---|
| **D-01** | **Two terminal ownership modes.** A `TerminalSession` operates in `INLINE` mode (output flows in scrollback; used by progress bars and `tqdm`-style helpers; no alternate screen) or `FULLSCREEN` mode (alternate screen; used by frame-loop applications and full-screen widgets). Exactly one session may own a given output stream at a time. Nested or concurrent sessions on the same stream are rejected with `TerminalBusyError` unless explicitly shared via the session's registered-region mechanism (FR-TERM-007). | Inline vs full-screen conflict; FR-TERM-007 undefined ownership |
| **D-02** | **One rendering contract.** Every visual widget shall implement `render(buffer: Buffer) -> None`. No widget writes to stdout/stderr directly. Inline progress bars also implement `render(buffer)`; the *inline renderer* maps their buffer region to relative-cursor terminal operations. There are no "direct-terminal widgets". | Buffered vs direct rendering conflict; open decision 4 |
| **D-03** | **Previous-frame cache semantics.** Partial rendering emits operations only for the requested region and **shall update the renderer's previous-frame cache for exactly that region**, so the next diff is correct. | Partial rendering vs diffing |
| **D-04** | **Concurrency model.** One UI thread owns the buffer, widget tree and terminal writes. Worker threads (network, filesystem, audio, timers) never touch widgets directly; they deliver results through a thread-safe `EventQueue` consumed by the frame loop, or call documented thread-safe APIs (cleanup manager, event queue, `Notifier.post`, progress `update`). asyncio is not required; an asyncio bridge is P3. Free-threaded CPython 3.13t is best-effort (D-14). | Missing concurrency model; `update(dt)` vs push-based data |
| **D-05** | **Single lifecycle protocol** (`Widget` base class, FR-LIFE) used by all widgets including dashboard widgets. | Open decision 5; dashboard vs base widget relationship |
| **D-06** | **Unicode cell-width policy.** Width is computed by a built-in implementation based on `unicodedata` (East Asian Width `W`/`F` = 2 cells; combining marks `Mn`/`Me`/`Cf` zero-width; control characters rejected, see FR-SAN). East Asian Ambiguous = 1 cell by default, configurable per session. If the third-party `wcwidth` package is installed, it may be used instead via a documented switch. | FR-BUF-009, NFR-ACC-003 dependencies on open decision 6 |
| **D-07** | **Single enforcement point for text safety.** `Buffer.write_text` treats input as plain text and removes/replaces control characters and escape sequences. Raw ANSI sequences are generated only from `Style` by the renderer. Hence untrusted text cannot inject terminal control sequences through any widget. | Missing escape-injection protection |
| **D-08** | **Layering rule** (§4.2). Lower layers never import higher layers; composite widgets use primitive widgets only through public APIs and lazily. | Composability vs inter-widget dependencies |
| **D-09** | **One owner for color data.** `base_elements/color_manager.py` owns colors, palettes, gradients and conversions. `include/` assets re-export these (FR-ASSET-003); they do not define independent copies. | Duplicated color/palette ownership |
| **D-10** | **One effects engine.** Easing, seeded randomness, injectable clock, flash limiting and reduced-motion policy live in a shared engine (FR-FX) used by animated text, marquee, matrix, neon, sign, spinner, vertical-print and notification fades. | Overlapping effect specifications |
| **D-11** | **Injectable seams.** Clock, output stream, input source, HTTP transport, filesystem root (where practical) and audio backend are injectable via constructor arguments or session configuration; defaults use real implementations. | Missing testability seams |
| **D-12** | **Zero required third-party runtime dependencies.** Optional extras: `audio`, `data` (pandas), `excel`, `unicode` (wcwidth). Optional libraries are imported lazily only by the features that need them. | Open decision 7; dependency set unstated |
| **D-13** | **Python version.** `requires-python = ">=3.13"`. Standard-library modules removed in 3.13 (PEP 594, e.g. `audioop`, `cgi`, `imghdr`, `sndhdr`, `telnetlib`) shall not be used. | `audioop` removal; version pin |
| **D-14** | **Free-threaded build.** CPython 3.13t is best-effort (P3): shared mutable state is lock-protected by design (FR-CLEAN-007, NFR-REL-005), but 3.13t is not in the mandatory test matrix until promoted. | Thread-safety scope |
| **D-15** | **Terminal I/O stack.** Pure ANSI/VT output; input via `termios`/`tty` (POSIX) and `msvcrt`/Windows console API (Windows). The `curses` module is not used (not available on Windows in the 3.13 standard library). | Terminal stack choice |
| **D-16** | **Space-crawl widget naming/content.** Public class `SpaceCrawlWidget` with original default text and procedurally generated or original assets. Any alias or legacy module name containing third-party trademarks (e.g. `star_wars_widget`) is a deprecated compatibility shim only, and no third-party-owned text, music or art is bundled. | Trademark/licensing risk |
| **D-17** | **Weather provider.** Open-Meteo (geocoding + forecast, no API key) is the default; providers implement a `WeatherProvider` Protocol so alternatives can be plugged in. Provider selection is not a mandatory product feature. | Open decision 8 |
| **D-18** | **`tqdm` compatibility subset** is the list in FR-PROG-013. Anything else is not guaranteed. | Open decision 11 |

---

## 4. System context and architecture

### 4.1 Logical components

| Component | Responsibility |
|---|---|
| Package API | Public imports, exports, aliases, lazy loading, metadata |
| Core widget model | Geometry, state, visibility, enabled state |
| Lifecycle | State machine, hooks, runtime ordering |
| Layout/composition | Containers, z-order, clipping, sub-buffers, overlays |
| Event/Interaction model | Event schema, key reader, focus manager, event queue |
| Resource management | Cleanup registration, deterministic release |
| Color service | Parsing, conversion, capability selection, palettes, gradients, ANSI |
| Screen buffer | Cell storage, clipping, text write, resize, width policy |
| Rendering engine | Diffing, operations, full/partial render, frame loop |
| Terminal service | Sessions, output gate, cursor/screen/title, dimensions, signals, platform compat |
| Effects engine | Easing, clock, seeded RNG, flash limiter, reduced motion |
| Progress subsystem | State, statistics, renderers, manager, `tqdm`-style API |
| Widget library | Concrete visual, data, navigation, productivity, network, audio widgets |
| Asset library | Glyphs, fonts, borders, bars, spinners, Unicode catalogs |

### 4.2 Layering and dependency rule (D-08)

```
L0  types, import_helper, cleanup
L1  color_manager, terminal (session, output gate, compat), buffer (+ width policy, sanitizing)
L2  base widget + lifecycle, layout, events/interactive, effects engine, render (diff, renderer, frame loop)
L3  include/ assets (depend on L0/L1 only)
L4  primitive widgets: box, spinner, marquee, matrix, neon, sign, animated text, vprint, gauge, chart, table, tree, form, calendar, notification, code editor, directory tree, dashboard base
L5  composite widgets: rss_reader, weather_widget, audio players, synchronized player, space crawl
```

Rules:

- A module shall import only from its own layer's siblings (where unavoidable) and lower layers.
- L5 widgets may use L4 widgets only through their public API and via lazy import.
- `import widgets` shall not import any L4/L5 module, any optional dependency, `urllib`/network libraries or audio libraries (FR-API-003).

### 4.3 Rendering model

1. A widget updates its state (`update(dt)` or event handlers) on the UI thread.
2. The frame loop creates/clears the frame buffer and calls `render(buffer)` on visible widgets in z-order.
3. The renderer diffs the new buffer with the previous-frame cache.
4. The renderer converts operations to terminal bytes via the session's output gate.
5. The output gate writes under a lock and flushes once per frame.

### 4.4 Configuration model

Widget configuration uses documented constructor arguments and/or `@dataclass(slots=True)` configuration objects. Each configuration field has a documented default, accepted type, valid range and invalid-value behavior (`ValueError`/`TypeError`). Mutable defaults are never shared between instances (FR-CORE-010).

---

## 5. Functional requirements

Column legend: **Δ** `=` retained, `✎` rewritten, `+` new. **P** priority. **V** verification.

### 5.1 Package API and composition

| ID | Requirement | Δ | P | V |
|---|---|---|---|---|
| FR-API-001 | The package shall expose a public API for core abstractions, commonly used widgets, progress helpers and shared rendering types. | = | P1 | T |
| FR-API-002 | Every symbol listed in the API reference shall be importable from its documented path. Public aliases shall be the same object as their targets (`alias is target`). | ✎ | P1 | T |
| FR-API-003 | Optional and expensive widget modules shall load lazily via module-level `__getattr__` (PEP 562). After `import widgets`, `sys.modules` shall contain no L4/L5 widget modules, no optional third-party modules and no network/audio libraries. | ✎ | P1 | T |
| FR-API-004 | Each public module shall define `__all__` matching its documented public symbols; a test shall assert that every `__all__` entry resolves and every documented public symbol is in `__all__`. | ✎ | P1 | T |
| FR-API-005 | An application shall be able to create, position, update, render and dispose of multiple widgets within one session. | = | P1 | T |
| FR-API-006 | The package shall expose `__version__` and follow semantic versioning. Public API removals require a deprecation period of at least one minor release. | + | P2 | I |
| FR-API-007 | The package shall ship `py.typed` and complete type annotations on public APIs. | + | P1 | I |
| FR-API-008 | Legacy import paths documented in the compatibility table (FR-PROG-014 and the API reference) shall resolve and may emit `DeprecationWarning`. | + | P2 | T |

### 5.2 Core widget model

| ID | Requirement | Δ | P | V |
|---|---|---|---|---|
| FR-CORE-001 | Each widget shall expose a stable `name`/`id` (unique within its container; auto-generated if not given) and integer `x`, `y`, `width`, `height`. | ✎ | P1 | T |
| FR-CORE-002 | Each widget shall expose boolean `visible` and `enabled`. Changing either takes effect no later than the next frame/event. | ✎ | P1 | T |
| FR-CORE-003 | Widgets shall support `move(x, y)`, `resize(width, height)` and geometry queries returning current values. | = | P1 | T |
| FR-CORE-004 | Widgets shall implement the lifecycle protocol of FR-LIFE, including `on_mount` and `on_unmount` hooks. | ✎ | P1 | T |
| FR-CORE-005 | `close()` shall be idempotent: a second call performs no cleanup and leaves state unchanged. | ✎ | P1 | T |
| FR-CORE-006 | Widgets owning resources shall be usable as context managers (`__enter__` mounts/starts, `__exit__` stops/unmounts/closes). | ✎ | P1 | T |
| FR-CORE-007 | A widget with `visible=False` shall write nothing to the buffer. A widget with `enabled=False` shall not consume key events (`handle_key` returns `False`), unless its documentation states otherwise. | ✎ | P1 | T |
| FR-CORE-008 | Time-dependent widgets shall implement `update(dt: float)` with `dt` in seconds. Animation state shall advance by elapsed time, not by frame count, so output at time *t* is independent of frame rate within one frame interval. | ✎ | P1 | T |
| FR-CORE-009 | Geometry validation: non-`int` dimensions raise `TypeError`; negative `width`/`height` raise `ValueError`; zero size is valid and renders nothing; negative `x`/`y` are valid (partially off-screen, clipped). | + | P1 | T |
| FR-CORE-010 | Constructors shall copy or freeze mutable default configuration so two instances never share mutable state. | + | P1 | T |
| FR-CORE-011 | Every widget shall provide a plain-text description (`describe() -> str`) summarizing its current state for logging, tests and non-visual fallbacks. | + | P2 | T |

### 5.3 Lifecycle

| ID | Requirement | Δ | P | V |
|---|---|---|---|---|
| FR-LIFE-001 | Widgets shall have an observable `state` of `CREATED`, `MOUNTED`, `RUNNING`, `PAUSED`, `STOPPED`, `UNMOUNTED` or `CLOSED`. | + | P1 | T |
| FR-LIFE-002 | Operations `mount(ctx)`, `start()`, `pause()`, `resume()`, `stop()`, `unmount()`, `close()` shall implement these transitions: CREATED→MOUNTED→RUNNING⇄PAUSED→STOPPED→UNMOUNTED→CLOSED. `close()` is permitted from any state and performs stop/unmount as needed. | + | P1 | T |
| FR-LIFE-003 | Repeating the operation that produced the current state is a no-op. An operation illegal for the current state raises `LifecycleError`. Widgets for which an operation is meaningless inherit a no-op default. | + | P1 | T |
| FR-LIFE-004 | `stop()` shall terminate any worker threads/timers owned by the widget before returning (join with documented timeout), and `unmount()` shall release layout/session registrations. | + | P1 | T |
| FR-LIFE-005 | The runtime shall invoke lifecycle operations in this order: mount parents before children, start children after parents, stop children before parents, unmount children before parents. | + | P1 | T |
| FR-LIFE-006 | Dashboard widgets (FR-DASH) shall use this same protocol; their `refresh` capability is an additional operation, not a different lifecycle. | + | P1 | I |

### 5.4 Layout and composition

| ID | Requirement | Δ | P | V |
|---|---|---|---|---|
| FR-LAYOUT-001 | A widget's `x`,`y` are relative to its parent container's origin (column 0,row 0 at top-left). Top-level widgets are relative to the screen. | + | P1 | T |
| FR-LAYOUT-002 | A `Container` shall hold child widgets, propagate lifecycle (FR-LIFE-005), `update(dt)`, `render` and key events, and expose add/remove/lookup by name. | + | P1 | T |
| FR-LAYOUT-003 | Children render in ascending `z` then insertion order. A later child overwrites cells of an earlier child where they overlap. | + | P1 | T |
| FR-LAYOUT-004 | A child's rendering shall be clipped to its parent's rectangle and to the buffer. | + | P1 | T |
| FR-LAYOUT-005 | The buffer shall provide a `BufferView(buffer, rect)` giving widgets a coordinate-translated, clipped window so widgets render with local coordinates and cannot write outside their rectangle. | + | P1 | T |
| FR-LAYOUT-006 | The runtime shall provide an overlay layer rendered above all containers for dropdowns, notifications and dialogs, with its own z-order. | + | P2 | T |
| FR-LAYOUT-007 | On terminal resize, the runtime shall resize the screen buffer and root container, notify widgets via `on_resize(width, height)`, and perform a full repaint. | + | P1 | T |
| FR-LAYOUT-008 | Widgets whose content cannot fit their rectangle shall clip or truncate (documented per widget), never raise, and never write outside their rectangle. | + | P1 | T |

### 5.5 Interaction and events

| ID | Requirement | Δ | P | V |
|---|---|---|---|---|
| FR-INPUT-001 | Interactive widgets shall implement `handle_key(event: KeyEvent) -> bool`, returning `True` if the event was consumed. | ✎ | P1 | T |
| FR-INPUT-002 | Interactive widgets shall implement `focus()`, `blur()` and expose `focused: bool`; `on_focus`/`on_blur` hooks fire exactly once per transition. | ✎ | P1 | T |
| FR-INPUT-003 | Widgets with selectable content shall support their documented navigation keys and keep the current selection within valid bounds (including for empty content, where the selection is `None`/-1 by documented convention). | ✎ | P1 | T |
| FR-INPUT-004 | OS-specific keyboard APIs shall be isolated behind a `KeyReader` interface. The same byte/key sequences shall yield the same `KeyEvent` on every supported OS. | ✎ | P1 | T |
| FR-INPUT-005 | Callback-exposing widgets shall document, for every callback: name, argument types, invocation thread (always the UI thread), invocation timing and error behavior. Exceptions raised in callbacks shall be logged, shall not corrupt widget state and shall not stop the frame loop, unless the application configures `raise_callback_errors=True`. | ✎ | P1 | T |
| FR-INPUT-006 | `KeyEvent` shall be an immutable object with fields `key: str`, `char: str \| None`, `ctrl`, `alt`, `shift: bool`. Key names: `up, down, left, right, home, end, pageup, pagedown, insert, delete, backspace, tab, backtab, enter, escape, space, f1…f12`; printable keys use `char` with `key == char`. | + | P1 | T |
| FR-INPUT-007 | The key reader shall decode CSI/SS3 escape sequences (cursor, navigation and function keys, modifier variants), bare ESC after a configurable timeout (default 50 ms), UTF-8 multi-byte input and unknown sequences (reported as `key="unknown"` with the raw bytes, never raising). | + | P1 | T |
| FR-INPUT-008 | A `FocusManager` shall maintain tab order (insertion order unless overridden), move focus on `tab`/`backtab`, skip invisible and disabled widgets, and route key events to the focused widget first, then to ancestors. | + | P1 | T |
| FR-INPUT-009 | The event model shall include `ResizeEvent` and `PasteEvent` (bracketed paste, P2). Key, resize and custom events are delivered through the `EventQueue`. | + | P2 | T |
| FR-INPUT-010 | The frame loop shall poll input without blocking longer than the remaining frame time. | + | P1 | T |
| FR-INPUT-011 | When input is not a TTY, interactive features shall be disabled with a clear error or fallback rather than hanging. | + | P2 | T |

### 5.6 Resource cleanup

| ID | Requirement | Δ | P | V |
|---|---|---|---|---|
| FR-CLEAN-001 | The resource manager shall accept callables and objects with `close()`, returning a unique token for each registration. | = | P1 | T |
| FR-CLEAN-002 | Cleanup shall run in reverse registration order. Dependencies requiring another order must be expressed by registration order. | ✎ | P1 | T |
| FR-CLEAN-003 | Repeated `cleanup()` calls are safe; each registered action runs at most once. | = | P1 | T |
| FR-CLEAN-004 | An exception in one cleanup action shall be logged (via `logging`) and shall not prevent remaining actions. | = | P1 | T |
| FR-CLEAN-005 | Registering after cleanup has completed shall execute the action immediately (this is mandatory, not preferred). | ✎ | P1 | T |
| FR-CLEAN-006 | A registered action can be cancelled by token before execution; cancelling an executed or unknown token is a no-op returning `False`. | = | P1 | T |
| FR-CLEAN-007 | The cleanup manager shall be thread-safe (register, cancel, cleanup callable from any thread; actions never run twice under concurrent calls). | + | P1 | T |
| FR-CLEAN-008 | The runtime shall run the session's cleanup manager at normal exit, on exceptions, on `KeyboardInterrupt`, from an `atexit` hook, and from POSIX `SIGTERM`/`SIGHUP` handlers. | + | P1 | T |

### 5.7 Shared types and optional dependencies

| ID | Requirement | Δ | P | V |
|---|---|---|---|---|
| FR-TYPE-001 | The package shall define types `WidgetId`, `Size`, `Point`, `Rect` (with `intersect`, `contains`, `clip`) and `RGB`. | = | P1 | T |
| FR-TYPE-002 | `Cell` shall be an immutable (`frozen`, `slots`) value of `glyph: str` and `style: Style`. `Style` shall be immutable, hashable, comparable, with fields foreground, background (each `None`, a palette index or `RGB`) and boolean attributes bold, dim, italic, underline, blink, reverse, strike. The default style is `Style()`. | ✎ | P1 | T |
| FR-TYPE-003 | `RenderOp` shall be an immutable value of `row: int`, `col: int`, `text: str`, `style: Style`. | ✎ | P1 | T |
| FR-TYPE-004 | Style/Cell equality and hashing shall be value-based and stable across processes. | + | P1 | T |
| FR-IMPORT-001 | `optional_import(name, feature=...)` shall return the module or `None` without raising and without logging at WARNING or above. | ✎ | P1 | T |
| FR-IMPORT-002 | `require_import(name, feature=..., extra=...)` shall raise `MissingDependencyError` naming the module, the feature and the pip extra to install. | ✎ | P1 | T |
| FR-IMPORT-003 | Optional integrations shall be imported only inside the feature that needs them. | = | P1 | T |

### 5.8 Color and styling

| ID | Requirement | Δ | P | V |
|---|---|---|---|---|
| FR-COLOR-001 | The color service shall accept named colors, `#RGB`, `#RRGGBB`, `(r,g,b)` ints 0–255 and `RGB` values; invalid input raises `ValueError` naming the offending value. | ✎ | P1 | T |
| FR-COLOR-002 | The service shall convert among RGB tuple, HEX string, 256-color index and 16-color index and validate ranges. | ✎ | P1 | T |
| FR-COLOR-003 | Color modes are exactly `NONE`, `ANSI16`, `ANSI256`, `TRUECOLOR`. Detection order: explicit application override; `NO_COLOR` set and non-empty → `NONE`; `FORCE_COLOR` (nonzero) → at least `ANSI16`; non-TTY output → `NONE`; `COLORTERM` in `truecolor`/`24bit` → `TRUECOLOR`; `TERM` containing `256color` → `ANSI256`; otherwise `ANSI16`; `TERM=dumb` → `NONE`. | ✎ | P1 | T |
| FR-COLOR-004 | The service shall generate foreground, background and attribute sequences for each mode, using the correct SGR parameters (e.g. `38;2;r;g;b`, `38;5;n`, `30–37/90–97`). | ✎ | P1 | T |
| FR-COLOR-005 | Predefined palettes plus registration (`register_palette(name, colors)`) and lookup; duplicate names raise unless `replace=True`. | ✎ | P2 | T |
| FR-COLOR-006 | Predefined gradients plus registration, validation (≥2 stops, positions ascending in [0,1]), lookup and interpolation. | ✎ | P2 | T |
| FR-COLOR-007 | Text styling supports foreground, background, bold, dim, italic, underline, blink, reverse and strike. | ✎ | P1 | T |
| FR-COLOR-008 | Palettes and gradients shall export to JSON (documented schema with a `version` field) and CSS custom properties. | = | P3 | T |
| FR-COLOR-009 | The renderer shall emit a style reset (`SGR 0`) at the end of every frame and whenever the active style would otherwise leak into untouched cells, including in `finally` paths after failures. | ✎ | P1 | T |
| FR-COLOR-010 | Downgrade from a higher to a lower mode shall pick the nearest palette entry by Euclidean distance in sRGB, deterministically (ties → lower index). | + | P1 | T |
| FR-COLOR-011 | Gradient interpolation shall be per-channel linear in sRGB with rounding to nearest integer; stop endpoints are exact. | + | P1 | T |

### 5.9 Screen buffer

| ID | Requirement | Δ | P | V |
|---|---|---|---|---|
| FR-BUF-001 | A buffer shall have integer `width`, `height` ≥ 0. | = | P1 | T |
| FR-BUF-002 | Each position shall store a `Cell`. | = | P1 | T |
| FR-BUF-003 | `set_cell(row, col, cell)` and `get_cell(row, col)`; out-of-range `set_cell` is a silent no-op; out-of-range `get_cell` raises `IndexError`. | ✎ | P1 | T |
| FR-BUF-004 | `write_text(row, col, text, style=…)` shall write left-to-right using the width policy and return the number of columns consumed. | ✎ | P1 | T |
| FR-BUF-005 | Writes (including negative origins and over-long text) shall be clipped without exceptions and without modifying any cell outside the buffer or the active `BufferView` clip. | ✎ | P1 | T |
| FR-BUF-006 | `clear(cell=None)` fills all cells with the given cell or a blank (space, default style). | = | P1 | T |
| FR-BUF-007 | `resize(w, h)` preserves the overlapping top-left region and fills new cells with blank; excess cells are discarded. | ✎ | P1 | T |
| FR-BUF-008 | `row(r)` returns the row's cells as an immutable sequence; invalid row raises `IndexError`. | ✎ | P1 | T |
| FR-BUF-009 | Cell-width policy (D-06): wide glyphs occupy 2 cells (glyph in the first cell, continuation marker in the second); combining marks are appended to the preceding cell's glyph and occupy 0 cells; if a wide glyph would be split by a clip boundary or buffer edge, the visible half is replaced by a space. Writing over either half of a wide glyph blanks the other half. | ✎ | P1 | T |
| FR-BUF-010 | The width of a string shall be queryable via `display_width(text)` consistent with FR-BUF-009. | + | P1 | T |
| FR-BUF-011 | Control characters (C0 except none allowed, DEL, C1) and escape sequences in `text` shall be removed or replaced with U+FFFD per FR-SAN-001; tab expands to spaces only through an explicit helper, not in `write_text`. | + | P1 | T |

### 5.10 Text safety (new group)

| ID | Requirement | Δ | P | V |
|---|---|---|---|---|
| FR-SAN-001 | No text passed through the public rendering API shall be able to emit terminal control sequences. `write_text` neutralizes ESC, C0, C1 and DEL characters and complete CSI/OSC/DCS sequences (D-07). | + | P1 | T |
| FR-SAN-002 | A `sanitize_text(text, *, newlines=…)` helper shall be public for applications handling untrusted text outside the buffer. | + | P2 | T |
| FR-SAN-003 | Window-title setting (FR-TERM-003) shall strip control characters from the title string. | + | P1 | T |
| FR-SAN-004 | Bidirectional override characters (U+202A–U+202E, U+2066–U+2069) in untrusted text shall be removed or replaced by default. | + | P2 | T |

### 5.11 Rendering engine and runtime

| ID | Requirement | Δ | P | V |
|---|---|---|---|---|
| FR-RENDER-001 | A widget shall paint its full visual region into the supplied buffer and shall not write to stdout/stderr. | ✎ | P1 | T |
| FR-RENDER-002 | The renderer shall compare the previous-frame cache with the new buffer and identify exactly the changed cells. | = | P1 | T |
| FR-RENDER-003 | Adjacent changed cells on one row with equal `Style` shall be merged into a single `RenderOp`. | ✎ | P1 | T |
| FR-RENDER-004 | A full repaint shall be generated when no previous frame exists, when dimensions differ, after resize, or after an explicit `invalidate()`. | ✎ | P1 | T |
| FR-RENDER-005 | Identical consecutive frames shall produce zero bytes of terminal output (including no cursor movement). | ✎ | P1 | T |
| FR-RENDER-006 | The terminal renderer shall apply per operation in order: cursor positioning, style transition, text; then style reset and a single flush at end of frame. | ✎ | P1 | T |
| FR-RENDER-007 | Full rendering of an entire buffer shall be supported. | = | P1 | T |
| FR-RENDER-008 | Partial rendering of a rectangle/row set shall emit operations only inside that region (D-03). | ✎ | P1 | T |
| FR-RENDER-009 | The frame loop shall: poll input, deliver events, `update(dt)` all widgets, render, diff, write; honor `fps` (default 30, valid 1–240) and `duration` (`None` = until stopped); `dt` shall be derived from a monotonic clock and clamped to a configurable maximum (default 0.25 s) after stalls. | ✎ | P1 | T |
| FR-RENDER-010 | If `update`, `render` or a callback raises, the runtime shall stop and unmount all widgets, restore the terminal, and re-raise the original exception (unless handled per FR-INPUT-005). | ✎ | P1 | T |
| FR-RENDER-011 | The runtime shall read terminal dimensions at start and on resize (SIGWINCH on POSIX, polling on Windows) and apply FR-LAYOUT-007. | ✎ | P1 | T |
| FR-RENDER-012 | The renderer shall support cursor move, hide/show, save/restore and absolute/relative positioning. | = | P1 | T |
| FR-RENDER-013 | Writing in the bottom-right cell shall not cause scrolling or autowrap corruption (the renderer uses a safe strategy such as disabling autowrap or avoiding the final cell). | + | P1 | T |
| FR-RENDER-014 | The diff algorithm shall be deterministic: identical inputs produce identical operations (testable with golden operation lists). | + | P1 | T |
| FR-RENDER-015 | Synchronized output (DEC mode 2026) shall be used when the terminal supports it and the application enables it. | + | P3 | D |

### 5.12 Terminal service and portability

| ID | Requirement | Δ | P | V |
|---|---|---|---|---|
| FR-TERM-001 | All output goes through a `TerminalSession` output gate bound to a configurable text stream (default `sys.stdout` for FULLSCREEN, `sys.stderr` for progress INLINE). Shared rendering code shall not reference `sys.stdout` directly. | ✎ | P1 | T |
| FR-TERM-002 | Explicit `flush()` shall be provided; the renderer flushes once per frame. | = | P1 | T |
| FR-TERM-003 | Screen clear, cursor movement, cursor visibility, alternate-screen enter/exit (FULLSCREEN only) and title setting shall be provided; unsupported operations are silent no-ops (e.g. non-TTY). | ✎ | P1 | T |
| FR-TERM-004 | `get_size()` returns `(columns, lines)` from the output stream's terminal; fallback `(80, 24)` when unknown; `COLUMNS`/`LINES` environment variables are honored when the size cannot be queried. | ✎ | P1 | T |
| FR-TERM-005 | Platform-specific code (raw input, VT enabling, size query, signals) shall live behind a compatibility module with POSIX and Windows implementations. | = | P1 | I |
| FR-TERM-006 | A session shall restore cursor visibility, input mode (cooked/echo), alternate screen, autowrap, bracketed-paste mode, colors/attributes and title on normal exit, exceptions, `KeyboardInterrupt`, `SIGTERM`, `SIGHUP`, `SIGTSTP` (restore, then suspend) and on `SIGCONT` (re-enter and fully repaint). | ✎ | P1 | T |
| FR-TERM-007 | A stream has at most one active session (D-01). Independent widgets sharing a session write only through the session's output gate; the gate serializes writes with a lock so sequences from different threads never interleave mid-operation. A second session on a busy stream raises `TerminalBusyError`. | ✎ | P1 | T |
| FR-TERM-008 | `INLINE` sessions never use the alternate screen and keep output in scrollback; `FULLSCREEN` sessions use the alternate screen and restore the original screen on exit. | + | P1 | T |
| FR-TERM-009 | If the output stream is not a TTY, the session degrades to plain-text, no-cursor-control output (no ANSI unless `FORCE_COLOR`/explicit override). | + | P1 | T |
| FR-TERM-010 | On Windows, VT processing shall be enabled on session start and the previous console mode restored on exit; if enabling fails, the session reports `TerminalCapabilityError` or falls back to plain text (configurable, default fallback). | + | P1 | T |
| FR-TERM-011 | Signal handlers installed by a session shall chain to previously installed handlers and be uninstalled on exit; handlers are installed only from the main thread. | + | P1 | T |
| FR-TERM-012 | Terminal capability queries (color mode, Unicode support, size) shall be exposed via a `Capabilities` object that applications and widgets can read (used by glyph fallback, FR-ASSET-009). | + | P1 | T |

### 5.13 Effects engine (new group)

| ID | Requirement | Δ | P | V |
|---|---|---|---|---|
| FR-FX-001 | A single effects module shall provide easing, clock, seeded RNG, flash limiting and reduced-motion handling for all animated widgets (D-10). | + | P1 | I |
| FR-FX-002 | Easing functions map t∈[0,1]→[0,1] with f(0)=0 and f(1)=1: `linear` f=t; `ease_in` f=t²; `ease_out` f=1−(1−t)²; `ease_in_out` f=2t² for t<0.5 else 1−(−2t+2)²/2; `bounce` = standard easeOutBounce; `elastic` = standard easeOutElastic (Penner/easings.net definitions). Values outside [0,1] input are clamped. | + | P1 | T |
| FR-FX-003 | A `Clock` protocol (`now() -> float` monotonic seconds) shall be injectable; tests use a manual clock. | + | P1 | T |
| FR-FX-004 | Effects with randomness take an optional `seed`; with the same seed, configuration and sequence of `update(dt)` calls, output is bit-identical. | + | P1 | T |
| FR-FX-005 | **Flash limiter:** no effect shall change the luminance of more than 25% of the screen area between light and dark states more than 3 times per second (WCAG 2.3.1-derived). Effects that would exceed it (e.g. glitch, neon flicker, strobe) are throttled. | + | P1 | T |
| FR-FX-006 | **Reduced motion:** if `WIDGETS_REDUCED_MOTION=1` or the session option `reduced_motion=True` is set, animated widgets render a static or minimal-change representation (no scrolling, flashing, rain, glitch or wave). | + | P1 | T |
| FR-FX-007 | Effect parameters shall be validated (speed > 0, durations ≥ 0, density in [0,1]); invalid values raise `ValueError`. | + | P2 | T |

### 5.14 Progress subsystem

| ID | Requirement | Δ | P | V |
|---|---|---|---|---|
| FR-PROG-001 | A progress object has `n` (current), optional `total`, `update(n=1)`, `set(n)`, `finish()`, `close()`; `n` is never negative; if `n` exceeds `total`, `total` stays as given and percentage is clamped at 100%. | ✎ | P1 | T |
| FR-PROG-002 | A helper shall wrap any iterable, yielding its items unchanged and updating progress per item; `total` is taken from `len()` when available; closing occurs on exhaustion, `break` (via generator close), or exception. | ✎ | P1 | T |
| FR-PROG-003 | Progress supports `description` and postfix data (`set_postfix(**kv)` and string form). | = | P1 | T |
| FR-PROG-004 | Statistics: elapsed (monotonic); speed = exponential moving average of items/s with smoothing factor default 0.3 (configurable); percentage = n/total; ETA = (total−n)/speed when speed > 0 and total known, else `None`; **stalled** = no update for longer than `stall_timeout` (default 10 s, configurable). | ✎ | P1 | T |
| FR-PROG-005 | Horizontal bar: configurable width, fill/empty glyphs, percentage/ETA/speed display, brackets, colors. | ✎ | P1 | T |
| FR-PROG-006 | Vertical bar: configurable height, glyph set (including sub-cell block glyphs), orientation (bottom-up/top-down). | ✎ | P2 | T |
| FR-PROG-007 | Circular indicator: configurable diameter, glyph set and style, rendering 0%–100% within its rectangle. | ✎ | P2 | T |
| FR-PROG-008 | Spinner indicator for indeterminate progress using the asset spinner styles; frame advance driven by `update(dt)`. | ✎ | P1 | T |
| FR-PROG-009 | Predefined and custom styles (glyph sets, colors, gradients); unknown style names raise `KeyError` listing the valid names. | ✎ | P2 | T |
| FR-PROG-010 | A progress manager shall maintain multiple concurrent indicators in an INLINE session, each assigned a unique row; rows never overlap; adding/removing an indicator updates the region height. | ✎ | P1 | T |
| FR-PROG-011 | `manager.write(msg)` (and `tqdm.write`) shall print the message above the progress region and then redraw the region, so messages are never overwritten by or interleaved into bars. | ✎ | P1 | T |
| FR-PROG-012 | On finish, exception or interruption the manager shall move the cursor below the region, restore cursor visibility, and leave completed bars in scrollback (unless `leave=False`). | ✎ | P1 | T |
| FR-PROG-013 | **`tqdm`-style subset (D-18):** `tqdm(iterable=None, desc, total, leave=True, file=sys.stderr, ncols, mininterval=0.1, miniters, disable=False, unit='it', unit_scale=False, dynamic_ncols=False, smoothing=0.3, initial=0, position, postfix)`; methods `update`, `close`, `refresh`, `reset`, `set_description`, `set_postfix`, `clear`, class method `tqdm.write`, iteration protocol and context manager; `trange(*args, **kw)` equivalent to `tqdm(range(*args), **kw)`. `bar_format` support is limited to documented fields (`{l_bar}{bar}{r_bar}`, `{n}`, `{total}`, `{elapsed}`, `{remaining}`, `{rate}`, `{desc}`, `{percentage}`). Unsupported arguments are accepted and ignored with documentation, or raise `TypeError` if the name is unknown. | ✎ | P1 | T |
| FR-PROG-014 | Documented legacy progress import paths shall resolve to the current objects (FR-API-008). | = | P2 | T |
| FR-PROG-015 | Progress output defaults to `stderr` (not `stdout`) so program output redirection is not polluted. | + | P1 | T |
| FR-PROG-016 | When the stream is not a TTY (FR-TERM-009), progress shall emit plain text lines at most every `mininterval` (default 10 s for non-TTY) and a final line on close, with no cursor control. | + | P1 | T |
| FR-PROG-017 | `update` and `write` shall be thread-safe; rendering occurs on a manager-owned refresh thread or the caller's thread under the output-gate lock (documented), and never exceeds the `mininterval` rate. | + | P1 | T |
| FR-PROG-018 | Rendering shall fit the available width: bars shrink and optional fields drop in a documented priority order; no wrapped lines. | + | P1 | T |

### 5.15 Text, typography and visual widgets

#### 5.15.1 Animated text

| ID | Requirement | Δ | P | V |
|---|---|---|---|---|
| FR-ANIM-001 | Configuration accepts text, position, dimensions, speed, colors, gradients, text styles, looping, duration, easing and mode-specific options, validated per FR-FX-007. | ✎ | P1 | T |
| FR-ANIM-002 | Modes with defined behavior (table below). Each mode is deterministic given seed and `dt` sequence. | ✎ | P2 | T |
| FR-ANIM-003 | Spinner placement: `before`, `after`, `both`, or `replace` (spinner instead of text). | = | P2 | T |
| FR-ANIM-004 | `start`, `stop`, `update`, looping and duration-limited playback conform to FR-LIFE; when duration elapses the widget enters `STOPPED` and fires its completion callback once. | ✎ | P1 | T |
| FR-ANIM-005 | Easing per FR-FX-002. | ✎ | P1 | T |
| FR-ANIM-006 | Random effects use the seeded RNG of FR-FX-004. | ✎ | P1 | T |
| FR-ANIM-007 | Audio-driven timing: when a beat/event source (Protocol `BeatSource.poll() -> list[float]`) is supplied, animation steps advance on its events; `audio_sync_active` reports whether a source is delivering events, and if the source is unavailable the animation continues in time-driven mode and reports `False`. | ✎ | P3 | T |

**Animated text mode definitions (FR-ANIM-002):**

| Mode | Defined behavior |
|---|---|
| bidirectional scroll | Text scrolls horizontally in a configured direction, reverses at the end when `bidirectional=True`. |
| bounce | Text moves back and forth within the width, reversing at edges. |
| dual marquee | Two copies scroll in opposite directions on two rows. |
| typewriter | Characters appear one at a time at `speed` chars/s; optional cursor glyph. |
| fade-in / fade-out | Per-character opacity/color interpolates between background and foreground over `duration` using easing. |
| wave | Characters offset vertically by a sine function of position and time (amplitude, wavelength configurable). |
| explode | Characters move outward from the center along seeded vectors and fade over `duration`. |
| rain | Characters fall from the top into position, staggered by seeded delays. |
| glitch | Seeded random characters/offsets replace glyphs for brief intervals, subject to FR-FX-005. |
| matrix | Characters resolve from falling random glyphs into the text. |
| neon | Foreground color cycles with periodic dimming per FR-FX-005. |
| fire | Per-character color mapped from a warm gradient with seeded flicker. |
| gradient scroll | Gradient offset advances over time across the text. |
| character dance | Characters alternate vertical offsets in a seeded pattern. |
| morph | Characters transition from source text to target text via intermediate glyphs over `duration`. |

#### 5.15.2 Box, marquee, matrix, neon, sign

| ID | Requirement | Δ | P | V |
|---|---|---|---|---|
| FR-BOX-001 | Draws rectangular borders using named border styles (FR-ASSET-002) at the given size; sizes below the minimum for the style (2×2) draw as much as fits without error. | ✎ | P1 | T |
| FR-BOX-002 | Text content with horizontal/vertical alignment, padding, foreground/background colors and gradients; overflow is truncated or wrapped per option `overflow`. | ✎ | P1 | T |
| FR-BOX-003 | Optional shadow (offset, glyph, style) and documented effects, rendered within the buffer. | = | P2 | T |
| FR-MARQUEE-001 | Single-line and multi-line content. | = | P2 | T |
| FR-MARQUEE-002 | Directions left, right, up, down; bounce, loop, speed (cells/s), `pause()`/`resume()`. | ✎ | P2 | T |
| FR-MARQUEE-003 | Large-character fonts, borders, padding, alignment, colors and gradients. | = | P2 | T |
| FR-MATRIX-001 | Falling-character effect plus text reveal and fade modes. | = | P2 | T |
| FR-MATRIX-002 | Character sets, colors/gradients, density (0–1), speed and effect parameters; seedable. | ✎ | P2 | T |
| FR-NEON-001 | Renders text with configurable neon colors/gradients. | = | P2 | T |
| FR-NEON-002 | Color cycling, fading, speed, `pause()`/`resume()`, alignment and wrapping, subject to FR-FX-005/006. | ✎ | P2 | T |
| FR-SIGN-001 | Font styles/sizes (from FR-ASSET-004), borders, alignment, padding and text colors. | = | P2 | T |
| FR-SIGN-002 | Static display and typewriter, bounce, marquee, wave, fade, neon and gradient-scroll modes. | = | P2 | T |

#### 5.15.3 Spinner, space crawl, vertical print, calendar

| ID | Requirement | Δ | P | V |
|---|---|---|---|---|
| FR-SPINNER-001 | Named frame sequences (from FR-ASSET-006) and configurable speed in frames/s (default 10). | ✎ | P1 | T |
| FR-SPINNER-002 | Optional text, alignment, foreground/background and gradients. | = | P1 | T |
| FR-SPINNER-003 | Text, style, speed and colors may be changed while running; changes take effect no later than the next `update`. | ✎ | P1 | T |
| FR-SPINNER-004 | A `SpinnerGroup` controller manages multiple spinners (add, remove, start/stop all) with non-overlapping rows. | ✎ | P2 | T |
| FR-SPACE-001 | `SpaceCrawlWidget` shows a perspective text crawl (lines narrow and dim toward the horizon) with a star field. Default text is original (D-16). | ✎ | P3 | T/D |
| FR-SPACE-002 | Configurable galaxies, nebulae, pulsars and other space objects with type and density; seedable. | = | P3 | T |
| FR-SPACE-003 | Start, stop, pause, resume, speed adjustment and keys (documented, including `+`/`-` for speed and `space` for pause). | ✎ | P3 | T |
| FR-SPACE-004 | Optional soundtrack via a configured music file using the audio backend (FR-AUDIO-006); failure to play audio does not stop the visuals. | ✎ | P3 | T |
| FR-VPRINT-001 | Displays text vertically and in large-character layouts. | = | P2 | T |
| FR-VPRINT-002 | Fonts, colors, gradients, spacing, direction, borders and padding. | = | P2 | T |
| FR-VPRINT-003 | Helpers: vertical text, countdown, loading, rainbow-text and clock/timer presentation. | = | P2 | T |
| FR-CAL-001 | A calendar widget shall display a month grid with weekday headers, configurable first weekday, current-day highlight and selectable day with keyboard navigation. | + | P2 | T |
| FR-CAL-002 | Clock and countdown presentations shall use the injectable `Clock` (FR-FX-003) and `zoneinfo` time zones; a countdown reaching zero fires its completion callback once. | + | P2 | T |
| FR-CAL-003 | Invalid dates/time zones raise `ValueError`/`ZoneInfoNotFoundError` with clear messages. | + | P2 | T |

### 5.16 Data, productivity and navigation widgets

| ID | Requirement | Δ | P | V |
|---|---|---|---|---|
| FR-CHART-001 | Bar, line, pie, scatter and area charts. | = | P2 | T |
| FR-CHART-002 | One or more datasets of labels and numeric values; empty datasets render an empty-state message; non-finite values (NaN/inf) are skipped with a documented placeholder. | ✎ | P2 | T |
| FR-CHART-003 | Titles, axes/labels, grid, legend, value display, colors, gradients and per-dataset visibility toggles. | = | P2 | T |
| FR-CHART-004 | `set_data(...)` replaces data; `invalidate()`/next frame redraws. | ✎ | P2 | T |
| FR-CHART-005 | Chart output remains readable at small sizes (minimum documented; below it shows a "too small" message). | + | P2 | T |
| FR-CODE-001 | Text buffer (list of lines) and cursor (line, column) model. | = | P2 | T |
| FR-CODE-002 | Cursor movement, viewport scrolling, line navigation (home/end/pageup/pagedown, goto line) and key input. | = | P2 | T |
| FR-CODE-003 | Python and JavaScript syntax highlighting (keywords, strings, comments, numbers) and line numbers; highlighting failures degrade to plain text. | ✎ | P2 | T |
| FR-CODE-004 | Open, load, edit and save text files; encoding UTF-8 by default (configurable), newline style detected and preserved; undecodable files raise a clear error or open read-only with replacement characters (option). | ✎ | P2 | T |
| FR-CODE-005 | Insert/delete characters and lines; cursor and viewport remain valid after every edit (property-tested). | ✎ | P2 | T |
| FR-CODE-006 | Saves shall be explicit (never automatic), atomic (write temp file in the same directory then replace) and preserve file mode where possible; a `dirty` flag tracks unsaved changes. | + | P2 | T |
| FR-CODE-007 | Undo/redo of edits (bounded history, default 1000 operations). | + | P2 | T |
| FR-CODE-008 | Files above a configurable size limit (default 10 MiB) are refused or opened read-only. | + | P2 | T |
| FR-CODE-009 | Selection, clipboard and search/replace. | + | P3 | T |
| FR-DASH-001 | A reusable `DashboardWidget` base that fetches/receives data and renders it; data fetching runs off the UI thread (D-04). | ✎ | P2 | T |
| FR-DASH-002 | Periodic refresh (interval ≥ 0.1 s) and event-driven updates via `push(data)`. | ✎ | P2 | T |
| FR-DASH-003 | Bounded history of data points (`history_size`, default 100); oldest dropped first. | ✎ | P2 | T |
| FR-DASH-004 | `on_update` callbacks run on the UI thread after each successful update. | ✎ | P2 | T |
| FR-DASH-005 | Start, pause, resume, stop; `error` state/`last_error` populated on fetch failure; a failing fetch does not stop other widgets; refresh resumes at the next interval. | ✎ | P2 | T |
| FR-DASH-006 | Text, metric and chart-oriented dashboard variants. | = | P2 | T |
| FR-DIR-001 | Directories and files with path and metadata (size, mode, mtime, is_dir, is_symlink). | = | P2 | T |
| FR-DIR-002 | Children load on demand when a directory is first expanded, off the UI thread for slow directories. | ✎ | P2 | T |
| FR-DIR-003 | Expand/collapse, navigate, select paths, refresh. | = | P2 | T |
| FR-DIR-004 | Sort by name/size/mtime (asc/desc); optional display of hidden files, sizes, permissions and dates. | ✎ | P2 | T |
| FR-DIR-005 | Incremental filter/search (`/` key) matching names case-insensitively. | ✎ | P2 | T |
| FR-DIR-006 | Symlinks are not followed by default (marked with an indicator); following them is opt-in and shall detect cycles (by resolved path/inode) and stop expanding on a loop. | + | P2 | T |
| FR-DIR-007 | Permission errors, vanished entries and invalid paths are shown as inline error entries; they never crash the widget. | + | P2 | T |
| FR-FORM-001 | Text, numeric, checkbox and dropdown fields. | = | P2 | T |
| FR-FORM-002 | Label, initial value, `required`, numeric `min`/`max`, max text length. | ✎ | P2 | T |
| FR-FORM-003 | Validation: required, type, range and custom validators (`callable(value) -> str \| None` error message); errors displayed next to the field and block submit. | ✎ | P2 | T |
| FR-FORM-004 | `get(name)` and `values()` (copy); numeric fields return `int`/`float`, checkbox `bool`. | ✎ | P2 | T |
| FR-FORM-005 | `on_submit(values)`, `on_cancel()`, `on_change(name, value)`. | = | P2 | T |
| FR-FORM-006 | Keyboard navigation (tab/shift-tab or up/down) and per-field interaction (typing, space toggles checkbox, up/down/enter in dropdown rendered via the overlay layer). | ✎ | P2 | T |
| FR-GAUGE-001 | Circular, speedometer, semi-circular and thermometer styles. | = | P2 | T |
| FR-GAUGE-002 | Value within `[min, max]`; out-of-range values are clamped and flagged; `min >= max` raises `ValueError`. | ✎ | P2 | T |
| FR-GAUGE-003 | Title, ticks, current value, min/max labels, threshold or gradient coloring, plus a text form of the value (FR-ACC-001). | ✎ | P2 | T |
| FR-TABLE-001 | Rows/columns with optional header, borders and row numbers. | = | P2 | T |
| FR-TABLE-002 | Column widths (fixed, auto, proportional) and alignments. | ✎ | P2 | T |
| FR-TABLE-003 | Scrolling, row/column navigation, sorting, show/hide columns. | = | P2 | T |
| FR-TABLE-004 | Load from CSV, TSV, pipe-delimited, JSON (list of objects or list of lists), Excel (`excel` extra) and pandas DataFrame (`data` extra); missing optional dependency raises `MissingDependencyError`. | ✎ | P2 | T |
| FR-TABLE-005 | Malformed, empty or ragged input raises `TableDataError` (with row number) or yields an empty table, per the documented `strict` option; table state is never partially replaced. | ✎ | P2 | T |
| FR-TABLE-006 | Sorting is stable; numbers sort numerically, strings case-insensitively, `None`/NaN last; mixed types sort by type group (numbers, strings, others). | + | P2 | T |
| FR-TABLE-007 | Input size limits (default 1,000,000 cells, configurable) and encoding (UTF-8, configurable); larger inputs are truncated with an indicator or rejected per option. | + | P2 | T |
| FR-TREE-001 | Parent/child nodes with expand/collapse; node labels and optional data payload. | ✎ | P2 | T |
| FR-TREE-002 | Navigate visible nodes; current selection is queryable and highlighted. | = | P2 | T |
| FR-TREE-003 | Load from JSON, XML and Python dicts; XML parsing shall reject DOCTYPE/entity declarations before parsing (FR-SEC-002) and apply a size limit. | ✎ | P2 | T |
| FR-TREE-004 | Interactive display and rendering into the common buffer. | = | P2 | T |
| FR-NOTIFY-001 | INFO, SUCCESS, WARNING, ERROR and CUSTOM types, each with a text prefix/icon so type is not conveyed by color alone (NFR-ACC-004). | ✎ | P2 | T |
| FR-NOTIFY-002 | Message plus optional icon, timestamp and `expires_at`. | ✎ | P2 | T |
| FR-NOTIFY-003 | Top/bottom placement, queueing and optional fade (subject to FR-FX-005/006), rendered in the overlay layer. | ✎ | P2 | T |
| FR-NOTIFY-004 | `dismiss(id)`, `dismiss_all()`; `default_duration` (default 5 s) applies to notifications without an explicit `expires_at`, and an explicit `expires_at` overrides it; `max_queue` bounds the queue (default 50; overflow policy `drop_oldest`/`drop_newest`, documented). `post()` is thread-safe. | ✎ | P2 | T |

### 5.17 Network and information widgets

| ID | Requirement | Δ | P | V |
|---|---|---|---|---|
| FR-RSS-001 | Multiple feed sources, grouped by category, with category/feed selection. | = | P2 | T |
| FR-RSS-002 | Retrieve and parse RSS 2.0 and Atom feeds into items (title, link, summary, published); `refresh()` triggers retrieval off the UI thread. | ✎ | P2 | T |
| FR-RSS-003 | List, marquee and box presentations (built on the corresponding widgets via public APIs, D-08). | = | P2 | T |
| FR-RSS-004 | Pagination, scrolling, pause/resume, speed and direction control. | = | P2 | T |
| FR-RSS-005 | Callbacks: `on_update(feed, items)`, `on_error(feed, error)`, `on_select(item)`. | ✎ | P2 | T |
| FR-RSS-006 | Invalid URLs, network failures, timeouts, HTTP errors, malformed XML and unavailable endpoints produce a typed `FeedError` (`FeedTimeoutError`, `FeedConnectionError`, `FeedHttpError`, `FeedParseError`), are reported via `on_error`/status text, and affect only that feed. Previously fetched items are kept and flagged stale. | ✎ | P2 | T |
| FR-RSS-007 | Configurable `max_response_bytes` (default 1 MiB), `max_items_per_feed` (default 100), and refresh interval (minimum 60 s by default). | ✎ | P2 | T |
| FR-RSS-008 | Only `http` and `https` URLs are accepted by default; redirects are limited to 5, never downgrade `https`→`http`, and cannot leave an optional allowed-host list. TLS certificates are verified. | + | P2 | T |
| FR-RSS-009 | Conditional GET (`ETag`/`Last-Modified`) is used when available; the HTTP transport is injectable (D-11). | + | P3 | T |
| FR-RSS-010 | Item text is treated as untrusted (FR-SAN-001); HTML tags/entities in summaries are stripped or decoded to plain text. | + | P2 | T |
| FR-WEATHER-001 | Resolve a place name to coordinates through the provider's geocoder; ambiguous names choose the top match and expose the candidate list; no match raises `LocationNotFoundError`. | ✎ | P2 | T |
| FR-WEATHER-002 | Retrieve current conditions and a forecast (default 5 days, 1–16) from the provider. | ✎ | P2 | T |
| FR-WEATHER-003 | Data model includes: temperature, apparent temperature, humidity, wind speed/direction, precipitation, weather code with text description; absent measures are `None` and rendered as "n/a". Units (metric/imperial) are configurable. | ✎ | P2 | T |
| FR-WEATHER-004 | Responses are cached for `cache_ttl` (default 600 s); `refresh(force=True)` bypasses the cache; if refresh fails and cached data exists, stale data is shown with a visible "stale" indicator. | ✎ | P2 | T |
| FR-WEATHER-005 | Text plus Unicode symbols with ASCII fallback; multi-day forecast display. | ✎ | P2 | T |
| FR-WEATHER-006 | `set_location(name)` changes location and refreshes asynchronously. | ✎ | P2 | T |
| FR-WEATHER-007 | Documented keyboard controls (at least: refresh, change location, switch day/units) and rendering via the common interface. | ✎ | P2 | T |
| FR-WEATHER-008 | Provider access is behind a `WeatherProvider` Protocol (D-17) with an Open-Meteo implementation; HTTP transport is injectable. | + | P2 | T |
| FR-WEATHER-009 | The documentation shall state that location text is sent to a third-party service. | + | P2 | I |

### 5.18 Audio and synchronized presentation

| ID | Requirement | Δ | P | V |
|---|---|---|---|---|
| FR-AUDIO-001 | List supported audio files in a selected directory (extension filter from backend capabilities) and navigate the list; non-readable directories show an error entry. | ✎ | P3 | T |
| FR-AUDIO-002 | Play, pause, resume, stop, next/previous and select track; operations unsupported by the backend are disabled and reported. | ✎ | P3 | T |
| FR-AUDIO-003 | Display state, elapsed time, duration (when available) and volume. | = | P3 | T |
| FR-AUDIO-004 | Volume adjustment in steps of 5% within 0–100%. | ✎ | P3 | T |
| FR-AUDIO-005 | Equalizer visualization with N configurable bands and selectable presets. Band levels come from backend-provided spectrum/level data; when none is available the widget shall indicate that the display is simulated or disabled. Decoding PCM for analysis shall not use `audioop` (D-13). | ✎ | P3 | T |
| FR-AUDIO-006 | `AudioBackend` Protocol: `capabilities()`, `load(path)`, `play()`, `pause()`, `resume()`, `stop()`, `seek(seconds)` (optional), `position()`, `duration()`, `set_volume()`, `close()`. Initialization failure, missing device and unsupported format raise `AudioBackendError` subclasses (`AudioUnavailableError`, `UnsupportedFormatError`). A `NullBackend` is provided for tests. | ✎ | P3 | T |
| FR-AUDIO-007 | Facilities to run visual widgets alongside audio playback. | = | P3 | T |
| FR-AUDIO-008 | `SynchronizedPlayer` coordinates start, duration, pause/stop and cleanup of audio and visuals; stopping either side stops the other; cleanup runs even if the backend fails. | ✎ | P3 | T |
| FR-AUDIO-009 | MIDI (`.mid`) playback is supported only if a backend declares it in `capabilities()`; otherwise it is reported as unsupported. | + | P3 | T |
| FR-AUDIO-010 | Track metadata (title/artist) shall be displayed when the backend provides it. | + | P3 | T |
| FR-AUDIO-011 | External player processes shall be invoked with an argument list (`shell=False`), never a shell string (NFR-SEC-005). | + | P3 | T |

### 5.19 Shared visual assets

| ID | Requirement | Δ | P | V |
|---|---|---|---|---|
| FR-ASSET-001 | At least 8 named horizontal and 8 named vertical bar glyph styles, with `list_bar_styles()` and `get_bar_style(name)`; unknown names raise `KeyError` listing valid names. | ✎ | P1 | T |
| FR-ASSET-002 | At least 10 named border styles including `ascii`, `single`, `double`, `rounded`, `heavy`, with `list_border_styles()`/`get_border_style(name)`; each defines all required box-drawing characters. | ✎ | P1 | T |
| FR-ASSET-003 | Named colors, palettes, gradients and conversion helpers are re-exports of the color service (D-09). | ✎ | P1 | T |
| FR-ASSET-004 | At least one large-character font covering printable ASCII (0x20–0x7E), with uniform height per font, validation of glyph rows, `font_height(name)` and `render_text(text, font)` that substitutes a documented placeholder for unsupported characters. | ✎ | P2 | T |
| FR-ASSET-005 | At least one vertical font and `render_vertical(text, font)`. | ✎ | P2 | T |
| FR-ASSET-006 | At least 20 named spinner sequences with metadata (frame list, default interval, whether ASCII-safe), `list_spinners()` and `get_spinner(name)`. | ✎ | P1 | T |
| FR-ASSET-007 | Catalogs for arrows, blocks, miscellaneous symbols and character sets, with documented `lookup(name)` and `search(query)` functions. | ✎ | P2 | T |
| FR-ASSET-008 | `list_asset_groups()` and per-group `list_*` functions enumerate all assets. | ✎ | P2 | T |
| FR-ASSET-009 | Every Unicode-dependent asset (borders, bars, spinners, weather symbols, arrows) shall have an ASCII fallback; widgets select it automatically when `Capabilities.unicode` is false or the application sets `ascii_only=True`. | + | P1 | T |
| FR-ASSET-010 | Bundled fonts and assets shall carry licensing information (I); no asset of unclear license is bundled. | + | P1 | I |

---

## 6. Non-functional requirements

### 6.1 Reliability

| ID | Requirement | P | V |
|---|---|---|---|
| NFR-REL-001 | Expected input, filesystem, network, terminal and optional-dependency failures shall be raised as typed exceptions (or reported through callbacks/status) and shall not terminate unrelated widgets. | P1 | T |
| NFR-REL-002 | Widget shutdown shall release owned resources, join worker threads (documented timeout, default 2 s) and restore terminal modes. | P1 | T |
| NFR-REL-003 | Exceptions during update/render shall not leave the terminal corrupted (FR-RENDER-010, FR-TERM-006). | P1 | T |
| NFR-REL-004 | Repeated lifecycle and cleanup operations are safe (FR-LIFE-003, FR-CLEAN-003). | P1 | T |
| NFR-REL-005 | Shared mutable state (cleanup manager, event queue, output gate, notification queue, progress state) shall be protected by locks or thread-safe structures; thread-safety of each public API is documented. | P1 | T/I |
| NFR-REL-006 | Worker threads shall be daemon threads or be joined at session exit so the interpreter can always exit. | P1 | T |

### 6.2 Performance

Numbers are **provisional baseline targets** on a reference developer machine (to be re-baselined, §12); they are verified by benchmark tests tracked in CI.

| ID | Requirement | P | V |
|---|---|---|---|
| NFR-PERF-001 | The diff of an unchanged 200×60 buffer shall emit no output and complete in under 5 ms; a diff with 1% changed cells shall emit output proportional to the changed cells. | P1 | T |
| NFR-PERF-002 | The frame loop sleeps until the next frame deadline (no busy waiting); an idle application at 30 fps shall use under 5% of one core. | P1 | T |
| NFR-PERF-003 | Histories, feed entries, notifications, undo stacks and similar collections have configurable bounds with defaults documented in the relevant requirement. | P1 | T |
| NFR-PERF-004 | Network retrieval, filesystem traversal and file loading shall run off the UI thread; the UI thread shall not block for more than one frame interval on them. | P1 | T |
| NFR-PERF-005 | `import widgets` shall complete in under 100 ms on the reference machine (lazy loading). | P2 | T |
| NFR-PERF-006 | Rendering a full 200×60 frame of a typical widget tree shall take under 16 ms (60 fps budget) on the reference machine. | P2 | T |

### 6.3 Portability and compatibility (resolves open decisions 1, 2)

| ID | Requirement | P | V |
|---|---|---|---|
| NFR-PORT-001 | Supported: CPython 3.13 (`requires-python = ">=3.13"`). OS: Linux (glibc, current LTS distributions), macOS (current and previous major release), Windows 10 version 1809+ and Windows 11. These are the mandatory CI matrix. | P1 | T |
| NFR-PORT-002 | Platform-specific terminal/keyboard code is isolated in compatibility modules (FR-TERM-005). | P1 | I |
| NFR-PORT-003 | Core imports shall not fail when an optional or platform-specific capability is unavailable. | P1 | T |
| NFR-PORT-004 | Terminal features degrade gracefully: truecolor→256→16→none; Unicode→ASCII; no cursor control→plain lines. | P1 | T |
| NFR-PORT-005 | Reference terminals for manual verification (D): Windows Terminal, iTerm2/Terminal.app, GNOME Terminal, Alacritty/kitty/WezTerm (any two), and `tmux`/`screen` multiplexers. Required VT level: ECMA-48/xterm subset (CSI cursor, SGR, erase, DECSET 25/1049/7, optional 2004/2026). | P1 | D |
| NFR-PORT-006 | CPython 3.13t (free-threaded) is best-effort (D-14); Python implementations other than CPython are unsupported. | P3 | T |

### 6.4 Usability and documentation

| ID | Requirement | P | V |
|---|---|---|---|
| NFR-USE-001 | All public classes, functions, configuration fields and keyboard controls are documented with docstrings (parameters, return values, exceptions, threading); documentation is built in CI. | P1 | I |
| NFR-USE-002 | Invalid configuration raises `ValueError`/`TypeError` naming the parameter, received value and valid range (or applies a documented fallback). | P1 | T |
| NFR-USE-003 | Interactive widgets show visible focus and selection indications that do not rely on color alone (e.g. reverse video, marker glyph). | P1 | T/D |
| NFR-USE-004 | Widget output remains readable within the available dimensions (truncate/clip/"too small" message), never wrapping or overflowing. | P1 | T |

### 6.5 Maintainability

| ID | Requirement | P | V |
|---|---|---|---|
| NFR-MAINT-001 | Absolute package imports or explicit relative imports only; nothing depends on the working directory or `sys.path` changes. | P1 | T |
| NFR-MAINT-002 | Consistent naming and signatures: `update(dt)`, `render(buffer)`, `handle_key(event)`, snake_case parameters, keyword-only options after positional essentials. | P1 | I |
| NFR-MAINT-003 | Library code shall use `logging.getLogger(__name__)`, shall not `print`, and shall attach only a `NullHandler` to the package logger. | P1 | T |
| NFR-MAINT-004 | Optional dependencies and external services are listed in `pyproject.toml` extras and in the documentation, with minimum versions. | P1 | I |
| NFR-MAINT-005 | Automated tests cover public APIs, rendering, lifecycle and each widget; coverage targets: ≥ 90% line coverage for core/render/terminal/progress, ≥ 80% overall (provisional, §12). | P1 | T |
| NFR-MAINT-006 | Static quality gates in CI: `ruff` (lint+format), `mypy --strict` or `pyright` strict on the package, and a dependency-layer check (D-08) that fails on upward imports. | P1 | A |
| NFR-MAINT-007 | Package metadata uses PEP 621 `pyproject.toml`; builds produce an sdist and wheel; `python -m build` and `twine check` pass. | P1 | T |

### 6.6 Security and data handling

| ID | Requirement | P | V |
|---|---|---|---|
| NFR-SEC-001 | Network widgets use configurable timeouts (default connect 5 s, read 10 s), verify TLS certificates and validate status, content type and size before parsing. | P1 | T |
| NFR-SEC-002 | Feed retrieval handles malformed URLs, unsupported schemes, redirect-policy violations, oversized responses and malformed content per FR-RSS-006/007/008. | P1 | T |
| NFR-SEC-003 | Filesystem widgets handle permission errors, invalid paths, symlinks (FR-DIR-006) and inaccessible entries without crashing. | P1 | T |
| NFR-SEC-004 | No feature writes or overwrites a file unless the caller explicitly requests it; saves are atomic (FR-CODE-006). | P1 | T |
| NFR-SEC-005 | Subprocess/external tool invocation uses argument lists with `shell=False`; untrusted input is never interpolated into shell commands. | P1 | T/I |
| NFR-SEC-006 | Untrusted text cannot inject terminal control sequences (FR-SAN). | P1 | T |
| FR-SEC-002 (cross-ref) | XML input (RSS, Atom, tree) shall be parsed only after rejecting documents containing DOCTYPE or ENTITY declarations; response and document size limits apply (stdlib parsers are otherwise vulnerable to entity-expansion attacks). | P1 | T |
| NFR-SEC-007 | The package shall not transmit data to any network service except as the application explicitly configures (RSS URLs, weather provider); no telemetry. | P1 | I |
| NFR-SEC-008 | Dependencies are pinned by lower bound and scanned in CI (e.g. `pip-audit`). | P2 | A |

### 6.7 Accessibility and terminal compatibility

| ID | Requirement | P | V |
|---|---|---|---|
| NFR-ACC-001 | Information conveyed by color or glyphs shall also be available as text (labels, values, `describe()` per FR-CORE-011). | P1 | T |
| NFR-ACC-002 | Documentation lists the Unicode glyph requirements per widget; every Unicode glyph asset has an ASCII fallback (FR-ASSET-009). | P1 | I |
| NFR-ACC-003 | Wide characters and combining marks follow FR-BUF-009. | P1 | T |
| NFR-ACC-004 | Color is never the sole carrier of critical status (errors, warnings, selection, focus); a text label, icon glyph or attribute is always present. | P1 | T |
| NFR-ACC-005 | Photosensitivity and reduced-motion requirements FR-FX-005/006 apply to all animated widgets. | P1 | T |
| NFR-ACC-006 | Screen-reader support is out of scope; `NO_COLOR`, ASCII-only and reduced-motion modes shall nevertheless be available to improve compatibility. | P2 | I |

### 6.8 Internationalization (scope declaration)

| ID | Requirement | P | V |
|---|---|---|---|
| NFR-I18N-001 | Text is Unicode (`str`); input decoding is UTF-8 with explicit handling of invalid bytes. | P1 | T |
| NFR-I18N-002 | Time zones use `zoneinfo`; no locale-dependent formatting is applied implicitly. | P2 | T |
| NFR-I18N-003 | Bidirectional text shaping, locale-specific number/date formatting and IME composition are out of scope for v2.0. | P1 | I |

---

## 7. External interfaces

### 7.1 Python API
Public classes, functions, configuration objects, type aliases, Protocols and compatibility imports are documented with names, types, defaults, return values, exceptions, threading and lifecycle obligations (NFR-USE-001). Protocols (`KeyReader`, `Clock`, `AudioBackend`, `WeatherProvider`, `HttpTransport`, `BeatSource`) are the extension points.

### 7.2 Terminal interface
Via configured streams and `TerminalSession`; required ANSI/VT capabilities and fallbacks per NFR-PORT-005 and FR-TERM-009/010.

### 7.3 Filesystem interface
Paths accepted as `str` or `os.PathLike`; access and format errors identify the path and operation without exposing unrelated data (ER-004).

### 7.4 Network interface
HTTP(S) only, injectable transport, documented timeouts, validation and cache behavior (§5.17, NFR-SEC-001/002). External service dependencies and data fields (Open-Meteo endpoints, RSS/Atom) are documented.

### 7.5 Optional libraries and tools
Extras: `audio`, `data`, `excel`, `unicode`. Missing optional dependencies raise `MissingDependencyError` at feature use (FR-IMPORT-002), never at package import.

---

## 8. Data and configuration requirements

| ID | Requirement | P | V |
|---|---|---|---|
| DR-001 | Each configurable widget documents its defaults; a test shall assert documented defaults equal actual defaults. | P1 | T |
| DR-002 | Configuration is validated for type, range and allowed enumerations (NFR-USE-002). | P1 | T |
| DR-003 | For each widget supporting runtime changes, the documentation lists changeable settings; changes take effect no later than the next `update`/`render`. | P1 | T |
| DR-004 | Data ownership: supplied collections are copied on input unless the parameter is documented as retained by reference; getters return copies or immutable views. | P1 | T |
| DR-005 | Bounded data: default bounds defined in each widget requirement (e.g. history 100, notifications 50, feed items 100, undo 1000). | P1 | T |
| DR-006 | Serialized formats (palette/gradient JSON, any configuration export) carry a `version` field; readers reject unknown major versions with a clear error. | P3 | T |

---

## 9. Error handling and diagnostics

| ID | Requirement | P | V |
|---|---|---|---|
| ER-001 | The package defines a base `WidgetsError` and typed subclasses: `LifecycleError`, `TerminalBusyError`, `TerminalCapabilityError`, `MissingDependencyError`, `TableDataError`, `FeedError` family, `LocationNotFoundError`, `AudioBackendError` family. Programming errors use built-in `ValueError`/`TypeError`/`KeyError`/`IndexError` as specified. | P1 | T |
| ER-002 | Missing-dependency errors name the missing module, the requiring feature and the install extra. | P1 | T |
| ER-003 | Network errors distinguish timeout, connection, HTTP status and parse failures. | P2 | T |
| ER-004 | Filesystem errors identify the affected path and operation (the user-supplied path, not unrelated environment data). | P1 | T |
| ER-005 | Cleanup failures are logged and do not block remaining cleanup (FR-CLEAN-004). | P1 | T |
| ER-006 | Logging is controlled by the application; the package never calls `logging.basicConfig` and never configures the root logger. | P1 | T |
| ER-007 | Log records never contain secrets or full file contents; URLs are logged without credentials. | P2 | T |

---

## 10. Verification and acceptance

### 10.1 Test strategy

- **Unit tests** (`pytest`) for every public API, using injected seams (D-11): manual clock, in-memory output stream, scripted key input, fake HTTP transport, `NullBackend`.
- **Golden-frame tests**: buffers/operation lists and rendered ANSI bytes at fixed seed and time for every effect, widget mode and style (FR-RENDER-014, FR-FX-004).
- **Property tests** (`hypothesis`, dev-only dependency) for buffer clipping/width handling, diff round-trip (applying ops to the previous frame yields the new frame), cursor/viewport validity after edits, gradient endpoints.
- **Pseudo-terminal tests** (POSIX `pty`; Windows ConPTY where available) for session restoration, signals, raw input and resize.
- **Concurrency tests** for cleanup manager, output gate, progress manager and event queue.
- **Security tests** for escape injection, XML entity bombs, oversized responses, redirect policy, symlink loops.
- **Benchmarks** for NFR-PERF.
- **Packaging tests**: clean-environment install (wheel) and import checks; `import widgets` module-set assertion (FR-API-003).

### 10.2 Acceptance criteria

The product conforms to this specification when:

**Package and API**
1. Every documented public import resolves in a clean virtual environment on every OS in NFR-PORT-001.
2. `import widgets` loads no L4/L5 modules or optional dependencies; each widget imports independently of unrelated optional dependencies.
3. Aliases and legacy paths resolve to the documented objects; imports work from any working directory.
4. Type checking (strict) and lint gates pass; `py.typed` is shipped.

**Core, lifecycle, layout, input**
5. State transitions, idempotency, ordering and error cases in FR-LIFE hold for every widget class (parametrized test over the widget registry).
6. Layout clipping, z-order and `BufferView` prevent out-of-rectangle writes (property-tested).
7. Key decoding yields identical `KeyEvent`s for the reference byte-sequence corpus on all OSes.
8. Cleanup ordering, fault isolation, idempotency, thread safety and registration-after-closure behave per FR-CLEAN.

**Rendering and terminal**
9. Buffer set/get/write/clear/resize/clip and width handling pass the golden and property tests, including wide/combining/emoji cases.
10. Diff output satisfies: full repaint cases, unchanged frames → 0 bytes, merged operations, partial-render cache consistency, round-trip property.
11. After normal exit, exception, `KeyboardInterrupt`, SIGTERM and suspend/resume the terminal is restored (verified in pty tests).
12. Non-TTY runs produce plain text without escape sequences or hangs.
13. Concurrent widgets/threads never interleave escape sequences (output-gate test).

**Progress**
14. State, iterator accounting, elapsed, speed (EMA), ETA, stall and completion are correct against the manual clock.
15. All indicator orientations render correctly at 0%, 1%, 50%, 99%, 100% and at overflow (n > total).
16. Concurrent indicators never overlap; `write()` messages are never overwritten; cursor visibility is restored after completion and exceptions.
17. The `tqdm` subset of FR-PROG-013 passes its compatibility test suite (adapted from `tqdm` behavior tests).

**Widgets**
18. Every FR group has tests demonstrating each "shall" for its widgets, including keyboard navigation, callbacks and invalid configuration.
19. Effects are deterministic under seed, honor FR-FX-005/006 (measured flash-rate test) and fall back to static rendering in reduced-motion mode.
20. Data widgets handle empty, malformed and oversized inputs within documented limits.
21. Network widgets handle timeouts, HTTP errors, redirects, oversized and malformed responses using the fake transport; no live network access in the test suite (live tests are opt-in).
22. Audio widgets behave correctly with `NullBackend`, with a missing backend and with unavailable devices, without affecting other widgets.
23. Asset libraries meet minimum counts, expose lookup/enumeration functions and provide ASCII fallbacks.

**Quality and portability**
24. The CI matrix (§6.3) passes on all declared OSes with CPython 3.13.
25. Core functionality works with no optional dependency installed.
26. Coverage targets (NFR-MAINT-005) and benchmark targets (NFR-PERF) are met or deviations are approved.
27. Logging is silent by default and fully controllable by the application.
28. Documentation builds, covers all public APIs and keyboard controls, and states Unicode/terminal requirements and third-party data disclosures.

---

## 11. Delivery milestones (recommended build order)

| Milestone | Content | Main requirement groups |
|---|---|---|
| **M0 Foundation** | Types, import helpers, cleanup, errors, logging policy, packaging, CI, layering check | FR-TYPE, FR-IMPORT, FR-CLEAN, ER, NFR-MAINT |
| **M1 Output core** | Color service, width policy, buffer (+sanitizing), diff, renderer, terminal session/output gate/compat | FR-COLOR, FR-BUF, FR-SAN, FR-RENDER, FR-TERM |
| **M2 Runtime** | Widget base, lifecycle, layout, events/key reader, focus manager, frame loop, effects engine | FR-CORE, FR-LIFE, FR-LAYOUT, FR-INPUT, FR-FX |
| **M3 Progress** | Progress state/stats, indicators, manager, `tqdm`/`trange`, non-TTY mode | FR-PROG, assets (bars, spinners) |
| **M4 Core widgets** | Assets, box, spinner, marquee, animated text, sign, neon, matrix, vprint, gauge, notification, calendar | FR-ASSET, FR-BOX…FR-CAL, FR-GAUGE, FR-NOTIFY |
| **M5 Data widgets** | Table, chart, tree, form, directory tree, dashboard, code editor | FR-TABLE…FR-CODE, FR-DASH, FR-DIR |
| **M6 Network** | RSS reader, weather widget (transport/provider seams) | FR-RSS, FR-WEATHER |
| **M7 Audio and showpieces** | Audio backend, players, synchronized player, space crawl | FR-AUDIO, FR-SPACE, FR-ANIM-007 |
| **M8 Hardening** | Docs, benchmarks, security review, compatibility matrix, release | NFR-*, §10 |

Priorities (P1–P3) set the minimum scope of each milestone; P3 items may slip to a later release by explicit decision.

---

## 12. Remaining decisions to confirm

D-01…D-18 (§3) are proposed defaults. The following items still need explicit confirmation before release:

| # | Decision | Proposed default |
|---|---|---|
| 1 | Exact OS versions in the mandatory CI matrix | NFR-PORT-001 |
| 2 | Promote CPython 3.13t to supported | Not before M8 |
| 3 | Reference audio backend(s) for the `audio` extra, and MIDI support | One cross-platform backend plus subprocess player; MIDI P3 |
| 4 | Excel reading library for the `excel` extra | `openpyxl` |
| 5 | Provisional performance numbers (NFR-PERF) and coverage targets | Re-baseline at M3 |
| 6 | Redirect/host allow-list and refresh limits for RSS | FR-RSS-007/008 defaults |
| 7 | Minimum counts of assets (spinners, borders, bars) and font coverage beyond ASCII | FR-ASSET minimums |
| 8 | Whether a deprecated `star_wars_widget` compatibility alias is retained | Retain as alias only, no bundled third-party content |
| 9 | Project license and licensing of bundled fonts/assets | To be decided before M4 |
| 10 | Whether asyncio integration (P3) is in the 1.x scope | Defer |

---

## 13. Traceability to package areas

The module layout below is carried over from v1.0; modules marked **(new)** are proposed by this specification.

| Package area / module | Requirement groups |
|---|---|
| `widgets/__init__.py` | FR-API |
| `base_elements/base.py` | FR-CORE |
| `base_elements/lifecycle.py` (new) | FR-LIFE |
| `base_elements/layout.py` (new) | FR-LAYOUT |
| `base_elements/events.py` (new) | FR-INPUT-006…009 |
| `base_elements/interactive.py` | FR-INPUT, FR-CORE-007 |
| `base_elements/cleanup.py` | FR-CLEAN |
| `base_elements/widget_types.py` | FR-TYPE |
| `base_elements/import_helper.py` | FR-IMPORT |
| `base_elements/color_manager.py` | FR-COLOR |
| `base_elements/effects.py` (new) | FR-FX |
| `render/buffer.py` | FR-BUF, FR-SAN |
| `render/diff.py` | FR-RENDER-002…005, 014 |
| `render/run.py` | FR-RENDER-009…011, FR-INPUT-010 |
| `render/screen_renderer.py` | FR-RENDER-006…008, 012, 013, 015; FR-TERM |
| `terminal/` (incl. `session.py` (new)) | FR-TERM |
| `progress_bars/` | FR-PROG |
| `animated_text_widget.py` | FR-ANIM |
| `box_widget.py` | FR-BOX |
| `calendar_widget.py` | FR-CAL (new group), FR-VPRINT-003 |
| `marquee_widget.py` | FR-MARQUEE |
| `matrix_widget.py` | FR-MATRIX |
| `neon_signs_widget.py` | FR-NEON |
| `sign_widget.py` | FR-SIGN |
| `spinners_widget.py` | FR-SPINNER |
| `star_wars_widget.py` (public name `SpaceCrawlWidget`) | FR-SPACE |
| `vprint_widget.py` | FR-VPRINT |
| `chart_widget.py` | FR-CHART |
| `code_editor_widget.py` | FR-CODE |
| `dashboard_widget.py` | FR-DASH |
| `directory_tree_widget.py` | FR-DIR |
| `form_widget.py` | FR-FORM |
| `gauge_widget.py` | FR-GAUGE |
| `table_widget.py` | FR-TABLE |
| `tree_widget.py` | FR-TREE |
| `notification_widget.py` | FR-NOTIFY |
| `rss_reader.py` | FR-RSS |
| `weather_widget.py` | FR-WEATHER |
| `mid_player_widget.py` | FR-AUDIO |
| `music_play_widget.py` | FR-AUDIO |
| `include/` | FR-ASSET |

Coverage caveat: the 66-module source documentation was not available during this revision. Any module not listed above shall be mapped to a requirement group (or flagged as having no requirement) in the next revision.

---

## 14. Document governance

This document is the baseline specification for the `widgets` package. Scope or externally visible behavior changes result in a versioned update. Every requirement has a stable identifier that implementations and tests shall reference (e.g. test names or markers `@pytest.mark.req("FR-BUF-005")`), enabling automated requirement-to-test traceability. A requirement is marked optional, deferred or removed only through an explicit product decision recorded in §12 or a change log; implementation state never determines whether a requirement belongs here.

---

## Appendix A: Resolution log of review findings

| Review finding | Resolution |
|---|---|
| Buffered vs direct rendering conflict | D-02; FR-RENDER-001; FR-PROG-010/011 use the inline renderer over the buffer contract |
| Inline vs full-screen ownership | D-01; FR-TERM-007/008/009 |
| Partial rendering vs diff cache | D-03; FR-RENDER-008 |
| Composability vs dependencies | D-08; §4.2; FR-API-003; NFR-MAINT-006 |
| Duplicate color/palette ownership | D-09; FR-ASSET-003 |
| Overlapping effects | D-10; FR-FX group |
| Expiry vs duration (notifications) | FR-NOTIFY-004 |
| `update(dt)` vs push data / threading | D-04; FR-CORE-008; FR-DASH-001/002; FR-INPUT-005 |
| Layout/composition missing | FR-LAYOUT group |
| Input pipeline missing | FR-INPUT-006…011 |
| Concurrency model missing | D-04; NFR-REL-005/006; FR-CLEAN-007; FR-PROG-017 |
| Terminal capabilities (alt screen, non-TTY, env vars, Windows VT, signals) | FR-TERM-006…012; FR-COLOR-003; FR-RENDER-013/015 |
| Testability seams | D-11; FR-FX-003; FR-RSS-009; FR-WEATHER-008; FR-AUDIO-006 |
| Terminal escape injection | D-07; FR-SAN group; NFR-SEC-006 |
| XML hardening | FR-SEC-002; FR-TREE-003; FR-RSS-002 |
| Network details (TLS, redirects, SSRF-like policy, privacy) | FR-RSS-008/009; NFR-SEC-001/007; FR-WEATHER-009 |
| Code editor safety (atomic save, encoding, undo, size) | FR-CODE-004…009 |
| Photosensitivity/reduced motion | FR-FX-005/006; NFR-ACC-005 |
| Screen-reader position | NFR-ACC-006; §1.4 |
| ASCII fallbacks for assets | FR-ASSET-009; NFR-ACC-002 |
| Calendar widget lacked requirements | FR-CAL group |
| MIDI/audio seek/metadata | FR-AUDIO-009/010; FR-AUDIO-006 `seek` |
| Internationalization scope | NFR-I18N; §1.4 |
| Circular "documented" requirements | Concrete behavior in FR-BUF-007/009, FR-INPUT-005, FR-CLEAN-005 and others |
| "Where practical/appropriate/equivalent mechanism" | Removed or replaced (FR-CORE-008, FR-API-003, FR-CORE-006) |
| Undefined animation modes and easing | FR-ANIM-002 table; FR-FX-002 |
| Progress statistics undefined | FR-PROG-004 |
| `tqdm` scope vague | FR-PROG-013; D-18 |
| Color modes/downgrade/interpolation undefined; Style type missing | FR-COLOR-003/010/011; FR-TYPE-002/004 |
| Equalizer realism | FR-AUDIO-005 |
| Asset content unmeasurable | FR-ASSET minimum counts |
| Symlink, table sort and weather ambiguities | FR-DIR-006; FR-TABLE-006; FR-WEATHER-001/003/004 |
| Circular acceptance criteria | §10 rewritten with measurable tests |
| Python 3.13 specifics | D-12…D-15; NFR-PORT-001/006; FR-AUDIO-005; FR-API-007 |
| No priorities / verification / phasing | §2.2; P and V columns; §11 |
| Space-crawl trademark/licensing | D-16; FR-SPACE-001; FR-ASSET-010 |
| Weather provider policy | D-17; FR-WEATHER-008 |
| Unicode policy | D-06; FR-BUF-009/010 |
| Performance targets absent | NFR-PERF (provisional numbers) |

**End of document**
