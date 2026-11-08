"""tqdm-style ``notebook`` module: names mapped to this library's terminal implementation."""

from __future__ import annotations

from widgets.progress.integrations import tnrange, tqdm_notebook
from widgets.progress.tqdm import tqdm, trange

__all__ = ["tnrange", "tqdm", "tqdm_notebook", "trange"]
