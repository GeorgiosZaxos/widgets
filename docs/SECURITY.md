# Security review (M8, updated for M10-M15 additions)

Scope: SRS NFR-SEC-001..008, FR-SAN, FR-RSS-008, FR-WEATHER-009. Reviewed by reading every module that
touches the network, the file system, subprocesses, XML or terminal output. Status: **no open
findings**; residual risks are listed below.

| Area | Control | Evidence |
|---|---|---|
| Terminal escape injection (NFR-SEC-006) | All untrusted text (feed items, file names, table cells, weather names, track names) passes `sanitize_text`; control characters are removed or made visible | `tests/test_m1*`, `test_m6_network.py` |
| XML (FR-TREE-003, FR-RSS-002) | DOCTYPE/ENTITY declarations rejected before parsing (no entity bombs); standard-library parser only | `test_xml_hardening`, `test_m5_data.py` |
| Network (NFR-SEC-001/002, FR-RSS-008) | http/https only, 5-redirect cap, https->http downgrade refused, host allow-list, size cap enforced while reading, timeouts, TLS verified by default context, 304 handling | `test_real_transport_redirects_size_and_etag` (local server), `test_https_downgrade_refused` |
| Telemetry (NFR-SEC-007) | Network modules exist only in `widgets.net`; nothing contacts a service unless the app configures it | `test_network_access_only_in_net_package` |
| Subprocess (NFR-SEC-005, FR-AUDIO-011) | `SubprocessBackend` builds an argument list, `shell=False`, absolute resolved path so a file name can never look like an option; a string command is rejected; no `os.system`, `eval`, `exec` anywhere | `test_no_shell_invocation_anywhere` |
| File writes (NFR-SEC-004) | Only `CodeEditor.save`/explicit save paths write; atomic replace; never implicit | `test_m5_data.py` |
| Filesystem (NFR-SEC-003) | Permission errors, symlink loops and unreadable entries become entries/messages, not crashes | `test_m5_data.py` |
| New widgets (M15) | `LogViewer`, `KanbanBoard`, `MarkdownView`, `CommandPalette`, `ProcessMonitor` and `RssTicker` draw text through the sanitising canvas path; `RssTicker` reuses `RssReader`'s fetch path (same URL, redirect, size and XML controls) | `tests/test_m15_new_widgets.py`, `test_m6_network.py` |
| Dependencies (NFR-SEC-008) | Zero runtime dependencies; extras have lower bounds. Run `pip-audit` in CI against the dev environment | `test_packaging_metadata` |

## Residual risks / notes

* `UrllibTransport` resolves hostnames normally: a feed URL can target a private address (SSRF-like). Use
  `allowed_hosts=[...]` when feeds come from untrusted configuration.
* Weather location text is sent to Open-Meteo in clear text inside an HTTPS request (documented).
* External players (ffplay, mpv, ...) parse untrusted media with their own vulnerabilities; keep them updated.
* `RssTicker` refreshes every configured feed on a timer (default 300 s) through background workers; only the URLs the application configures are fetched.
* `ImageView.from_file` and `QrView` rely on pillow / qrcode; keep them updated. Pass only paths the application chose.
* The tqdm framework shims call into third-party frameworks the application installs; they add no network access.
* `pip-audit` runs in CI on every push (job `audit`); a local run on the dev environment reported no known vulnerabilities.
* Free-threaded CPython 3.13t is best effort (D-14).
