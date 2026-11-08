"""Adapters that drive the widgets ``tqdm`` from other frameworks. Layer L3.

They need nothing from the frameworks at import time: Keras and dask call plain methods on a
callback object, so a duck-typed class is enough. ``tqdm_tk`` and ``tqdm_rich`` import tkinter /
rich lazily, and ``tqdm_notebook`` is the terminal bar (Jupyter shows it as text output).
"""

from __future__ import annotations

from collections.abc import Iterable
from typing import Any

from widgets.base_elements.import_helper import optional_import, require_import
from widgets.progress.tqdm import tqdm, trange

tqdm_notebook = tqdm
tnrange = trange


class TqdmKerasCallback:
    """Keras ``Callback`` duck type: one bar for epochs and (optionally) one per epoch's batches."""

    def __init__(self, epochs: int | None = None, verbose: int = 1, **tqdm_kwargs: Any) -> None:
        self.epochs, self.verbose, self.kwargs = epochs, verbose, tqdm_kwargs
        self.params: dict[str, Any] = {}
        self.model: Any = None
        self.epoch_bar: tqdm | None = None
        self.batch_bar: tqdm | None = None

    def set_params(self, params: dict[str, Any]) -> None:
        self.params = dict(params)

    def set_model(self, model: Any) -> None:
        self.model = model

    def on_train_begin(self, logs: dict[str, Any] | None = None) -> None:
        total = self.epochs or self.params.get("epochs")
        self.epoch_bar = tqdm(total=total, desc="Training", disable=not self.verbose, **self.kwargs)

    def on_epoch_begin(self, epoch: int, logs: dict[str, Any] | None = None) -> None:
        if self.verbose > 1 and self.params.get("steps"):
            self.batch_bar = tqdm(
                total=self.params["steps"], desc=f"Epoch {epoch + 1}", leave=False, **self.kwargs
            )

    def on_batch_end(self, batch: int, logs: dict[str, Any] | None = None) -> None:
        if self.batch_bar is not None:
            self.batch_bar.update(1)

    def on_epoch_end(self, epoch: int, logs: dict[str, Any] | None = None) -> None:
        if self.batch_bar is not None:
            self.batch_bar.close()
            self.batch_bar = None
        if self.epoch_bar is not None:
            if logs:
                self.epoch_bar.set_postfix({k: f"{v:.4g}" for k, v in logs.items()}, refresh=False)
            self.epoch_bar.update(1)

    def on_train_end(self, logs: dict[str, Any] | None = None) -> None:
        for bar in (self.batch_bar, self.epoch_bar):
            if bar is not None:
                bar.close()


class TqdmDaskCallback:
    """dask scheduler callback duck type (use ``with dask.callbacks.Callback`` subclass or this)."""

    def __init__(self, **tqdm_kwargs: Any) -> None:
        self.kwargs = tqdm_kwargs
        self.bar: tqdm | None = None

    def _start_state(self, dsk: Any, state: Any) -> None:
        total = sum(len(state[k]) for k in ("ready", "waiting", "running", "finished"))
        self.bar = tqdm(total=total, desc="dask", **self.kwargs)

    def _posttask(self, key: Any, result: Any, dsk: Any, state: Any, worker_id: Any) -> None:
        if self.bar is not None:
            self.bar.update(1)

    def _finish(self, dsk: Any, state: Any, errored: bool) -> None:
        if self.bar is not None:
            self.bar.close()

    def __enter__(self) -> TqdmDaskCallback:
        cb = require_import("dask.callbacks", feature="dask progress", extra="data")
        self._registered = cb.Callback(
            start_state=self._start_state, posttask=self._posttask, finish=self._finish
        )
        self._registered.__enter__()
        return self

    def __exit__(self, *exc: object) -> None:
        self._registered.__exit__(*exc)


class tqdm_tk(tqdm):
    """tqdm that also shows a small tkinter window with a progress bar (needs a display)."""

    def __init__(self, iterable: Iterable[Any] | None = None, **kwargs: Any) -> None:
        super().__init__(iterable, **kwargs)
        tk = require_import("tkinter", feature="tqdm_tk")
        ttk = require_import("tkinter.ttk", feature="tqdm_tk")
        self._root = tk.Tk()
        self._root.title(self.desc or "progress")
        self._tk_bar = ttk.Progressbar(self._root, length=320, maximum=self.total or 100)
        self._tk_bar.pack(padx=12, pady=12)

    def update(self, n: float = 1) -> None:
        super().update(n)
        if self.total:
            self._tk_bar["value"] = self.n
        self._root.update_idletasks()

    def close(self) -> None:
        super().close()
        root = getattr(self, "_root", None)
        if root is not None:
            root.destroy()
            self._root = None


class tqdm_rich(tqdm):
    """tqdm that renders with ``rich.progress`` when rich is installed (else the normal bar)."""

    def __init__(self, iterable: Iterable[Any] | None = None, **kwargs: Any) -> None:
        rich_progress = optional_import("rich.progress", feature="tqdm_rich")
        if rich_progress is None:
            super().__init__(iterable, **kwargs)
            self._rich: Any = None
            return
        kwargs["disable"] = True  # our own renderer is replaced by rich
        super().__init__(iterable, **kwargs)
        self._rich = rich_progress.Progress()
        self._rich.start()
        self._task = self._rich.add_task(self.desc or "", total=self.total)

    def update(self, n: float = 1) -> None:
        super().update(n)
        if getattr(self, "_rich", None) is not None:
            self._rich.advance(self._task, n)

    def close(self) -> None:
        super().close()
        if getattr(self, "_rich", None) is not None:
            self._rich.stop()
            self._rich = None


__all__ = [
    "TqdmDaskCallback",
    "TqdmKerasCallback",
    "tnrange",
    "tqdm_notebook",
    "tqdm_rich",
    "tqdm_tk",
]
