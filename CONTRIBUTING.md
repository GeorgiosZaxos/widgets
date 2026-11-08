# Contributing

Thanks for helping. Please open an issue before large changes.

## Setup

```bash
python -m venv .venv && . .venv/bin/activate      # Windows: .venv\Scripts\activate
pip install -e ".[dev]"
```

## Before you push

All of these must pass (CI runs them on Linux, macOS and Windows):

```bash
ruff check . && ruff format --check .
mypy
python tools/check_layers.py
pytest
```

## Rules

* Python 3.13, zero required runtime dependencies. Optional packages go in an extra and are imported
  lazily; a missing one raises `MissingDependencyError`.
* Respect the layering (`tools/check_layers.py`): nothing imports upward.
* Every public module, class and function needs a docstring (a test enforces this).
* Untrusted text (feeds, file names, user input) must go through the sanitising path.
* Network access lives only in `widgets.net` and must be injectable for tests.
* New behaviour needs tests; tag them with `@pytest.mark.req("ID")` when they verify a requirement.
* Widget methods must not collide with `Widget` attributes (`move`, `state`, `start`, `visible`, ...).
* Update `CHANGELOG.md` under *Unreleased*.

## Pull requests

Keep them focused, describe what changed and how you tested it, and note the terminal(s) you tried for visual changes.
