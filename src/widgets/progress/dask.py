"""tqdm-style ``dask`` module: names mapped to this library's terminal implementation."""

from __future__ import annotations

from widgets.progress.integrations import TqdmDaskCallback

__all__ = ["TqdmDaskCallback"]
