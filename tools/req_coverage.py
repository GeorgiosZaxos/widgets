"""List requirement IDs referenced by ``@pytest.mark.req(...)`` markers in ``tests/``.

Usage::

    python tools/req_coverage.py                     # IDs that have tests
    python tools/req_coverage.py --spec FILE.md      # also report spec IDs without tests
    python tools/req_coverage.py --spec FILE.md --groups FR-BUF,FR-RENDER
"""

from __future__ import annotations

import argparse
import ast
import re
from collections.abc import Sequence
from pathlib import Path

ID_PATTERN = re.compile(r"\b((?:FR|NFR|DR|ER)-[A-Z0-9]+(?:-\d+)?)\b")


def _marker_ids(node: ast.AST) -> list[str]:
    ids: list[str] = []
    for sub in ast.walk(node):
        if not isinstance(sub, ast.Call):
            continue
        func = sub.func
        if isinstance(func, ast.Attribute) and func.attr == "req":
            ids.extend(
                arg.value
                for arg in sub.args
                if isinstance(arg, ast.Constant) and isinstance(arg.value, str)
            )
    return ids


def tested_ids(tests_dir: Path) -> set[str]:
    found: set[str] = set()
    for path in sorted(tests_dir.rglob("test_*.py")):
        found.update(_marker_ids(ast.parse(path.read_text(encoding="utf-8"))))
    return found


def spec_ids(spec: Path) -> set[str]:
    text = spec.read_text(encoding="utf-8")
    ids: set[str] = set()
    for line in text.splitlines():
        match = re.match(r"\|\s*((?:FR|NFR|DR|ER)-[A-Z0-9]+-\d+)\s*\|", line)
        if match:
            ids.add(match.group(1))
    return ids


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--tests", type=Path, default=Path(__file__).resolve().parent.parent / "tests"
    )
    parser.add_argument("--spec", type=Path)
    parser.add_argument("--groups", help="comma separated ID prefixes to restrict the report to")
    args = parser.parse_args(argv)

    covered = tested_ids(args.tests)
    prefixes = tuple(args.groups.split(",")) if args.groups else ()
    print(f"{len(covered)} requirement IDs referenced by tests")
    for rid in sorted(covered):
        print(f"  {rid}")
    if args.spec:
        missing = sorted(
            rid for rid in spec_ids(args.spec) - covered if not prefixes or rid.startswith(prefixes)
        )
        print(f"\n{len(missing)} spec IDs without a test marker")
        for rid in missing:
            print(f"  {rid}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
