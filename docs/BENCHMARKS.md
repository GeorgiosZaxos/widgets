# Benchmarks (NFR-PERF)

Run `python tools/benchmarks.py`. Numbers below (re-measured after the M15 widgets and `RssTicker`): Linux container (shared vCPU), CPython 3.13, median of
20-30 runs; the reference machine of the SRS is not defined yet, so treat them as a baseline.

| Metric | Target | Measured |
|---|---|---|
| Diff of unchanged 200x60 buffer (no output) | < 5 ms | 0.08 ms |
| Diff with 1 % cells changed | proportional | 2.127 ms |
| Full 200x60 frame (table + chart + box + marquee + spinner) | < 16 ms | 13.76 ms |
| `import widgets` (lazy) | < 100 ms | 13.0 ms |

The frame number is within budget but has little headroom on this machine; the table and chart are
the heaviest parts of the benchmark scene. `tests/test_m8_hardening.py` asserts the budgets with a 4x
tolerance so shared CI runners do not flake. NFR-PERF-002 (idle CPU) and NFR-PERF-004 (UI thread never
blocked) are covered by the frame-loop and worker-thread tests of M2-M7.

## Coverage (NFR-MAINT-005)

Measured with `coverage run -m pytest`: **overall 90 %** (target 80 %; the newer modules lowered the earlier 94 %). Core subset (base_elements,
render, terminal, progress) **89 %** (target 90 %): the shortfall is Windows-only code in
`terminal/compat.py` (see COMPATIBILITY.md) - `terminal/compat.py` alone is 41 % on Linux. Requirement markers: 290 spec IDs are referenced by tests and 7 have none (inspection, measurement or manual items, see `TRACEABILITY.md`) (`tools/req_coverage.py`). Deviation recorded,
not approved.
