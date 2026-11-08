# Compatibility matrix

Mandatory targets (NFR-PORT-001): CPython **3.13** on Linux (glibc, current LTS), macOS (current and
previous major), Windows 10 1809+ and Windows 11. 3.13t is best effort. Other interpreters unsupported.

| Capability | Linux | macOS | Windows | Notes |
|---|---|---|---|---|
| Core, render, widgets, tests | verified (ruff, mypy --strict, layers, pytest 478 passed; also passes with no optional packages installed: 474 passed, 3 skipped); GitHub Actions matrix runs it on every push | not yet run locally; covered by the GitHub Actions `macos-latest` job once the repository is pushed | full pytest suite run by the user on Windows 11 / Python 3.13.2: 455 passed, 7 skipped (no pty, symlinks, POSIX signals); demos run in PyCharm | |
| Raw keyboard input | termios | termios | msvcrt + VT input | isolated in `terminal.compat` (NFR-PORT-002) |
| Colour | truecolor/256/16/none | same | same | `COLORTERM`, `NO_COLOR` honoured; on Windows, truecolor is assumed for Windows Terminal, ConEmu, `TERM_PROGRAM` or console build >= 14931 (Windows 10 1607+, Windows 11); older consoles fall back to 16 colours - set `COLORTERM=truecolor` to force |
| Unicode -> ASCII fallback | yes | yes | yes | `ascii_only=True` on widgets |
| Time zones | system tz database | system | needs `tzdata` (`pip install widgets[tz]`) | UTC always works |
| Audio | ffplay/mpv/mpg123/aplay/paplay | afplay/ffplay/mpv | `winsound` (.wav only) or ffplay/mpv | `NullBackend` everywhere |
| Network widgets (`RssReader`, `RssTicker`, `WeatherWidget`) | yes | yes | yes | injectable transport for offline use |
| `ProcessMonitor` | `psutil` or injected `fetch` | same | same | `pip install widgets[system]` |
| `ImageView.from_file`, `QrView` | pillow / qrcode | same | same | `pip install widgets[images]` |
| Spectrum / oscilloscope source | numpy + PCM WAV | same | same | `pip install widgets[audio]`; MP3 and MIDI not supported |
| pty-based tests | run | run | skipped | no `pty` module on Windows |

Reference terminals for manual verification (NFR-PORT-005): Windows Terminal, iTerm2/Terminal.app, GNOME
Terminal, two of Alacritty/kitty/WezTerm, tmux/screen. **Not yet exercised by this project** except where
the table says "verified".

Known platform-specific coverage gap: `terminal/compat.py` Windows branches cannot execute on Linux
(measured coverage of that file is 41 % on Linux); run the suite on Windows to cover them. Seven tests are skipped on Windows (pty, symlink privileges, POSIX signals). Tests that block modules to simulate missing platforms must not block `msvcrt` on Windows, because the standard-library `subprocess` module imports it.

## Continuous integration

`.github/workflows/ci.yml` runs lint (ruff, mypy --strict, layer check), the test suite with coverage on
Linux, macOS and Windows, a zero-optional-dependency run, a wheel build/install smoke test and `pip-audit`.
`.github/workflows/release.yml` repeats the gates on a `v*` tag, checks the tag against the package
version, builds the distributions, creates a GitHub release and (optionally) publishes to PyPI.
