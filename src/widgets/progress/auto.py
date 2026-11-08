"""``from widgets.progress.auto import tqdm`` - tqdm.auto equivalent (always the terminal bar)."""

from __future__ import annotations

from widgets.progress.tqdm import tqdm, trange

__all__ = ["tqdm", "trange"]
