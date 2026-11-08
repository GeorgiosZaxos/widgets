# Requirements traceability

Source of truth: [`requirements/requirementsspecification.md`](requirements/requirementsspecification.md)
(SRS-WIDGETS-002). Tests carry `@pytest.mark.req("ID")`; list coverage with

```bash
python tools/req_coverage.py --spec docs/requirements/requirementsspecification.md
```

At release candidate 1 every requirement ID is referenced by at least one test **except** the nine below,
which are verified by inspection, measurement or manual checks, or are known deviations. (NFR-USE-001 docstrings and NFR-MAINT-002 signature consistency are enforced by tests in `test_m16_requirements.py`.) CI runs the tool for information on every push.

| ID | Verification | Evidence / status |
|---|---|---|
| NFR-ACC-002 | Inspection | Every Unicode glyph asset has an ASCII fallback (FR-ASSET-009, tested); per-widget glyph requirements: [`USER_GUIDE.md`](USER_GUIDE.md) and `ascii_only=` options |
| NFR-ACC-006 | Inspection | Screen readers are out of scope; `NO_COLOR`, ASCII-only and reduced-motion modes exist and are tested |
| NFR-I18N-003 | Inspection | Bidirectional text, locale formatting and IME are out of scope (no code) |
| NFR-MAINT-005 | Measurement | Overall coverage 90 % (target 80 %); core subset 89 % (target 90 %), see [`BENCHMARKS.md`](BENCHMARKS.md). CI fails below 85 % overall |
| NFR-PORT-005 | Manual | Reference-terminal checklist: [`TERMINAL_CHECKLIST.md`](TERMINAL_CHECKLIST.md). Not yet completed on every terminal |
| NFR-PORT-006 | Best effort | CPython 3.13t is best effort; not run in CI |
| NFR-SEC-001 | Deviation | TLS verification, size and status validation are implemented and tested. The timeout is **one** value (default 10 s), not separate connect 5 s / read 10 s, because `urllib` exposes a single timeout |

Anything else that appears in the tool's "without a test marker" list after a future change is a regression
and should be fixed or added to this table with a reason.
