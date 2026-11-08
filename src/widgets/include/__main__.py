"""``python -m widgets.include`` - asset diagnostics (replaces the legacy entry point)."""

from __future__ import annotations

import sys

from widgets.assets.registry import list_asset_groups, list_assets


def main() -> int:
    groups = list_asset_groups()
    print("widgets assets")
    for group in groups:
        names = list_assets(group)
        print(f"  {group:10} {len(names):4} items  e.g. {', '.join(map(str, names[:5]))}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
