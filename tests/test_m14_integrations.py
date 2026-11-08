"""Framework adapters for tqdm (keras / dask / notebook / tk / rich)."""

from __future__ import annotations

import io
import sys

import pytest

from widgets.progress import integrations as it
from widgets.progress.tqdm import tqdm


def test_keras_callback_counts_epochs(monkeypatch: pytest.MonkeyPatch) -> None:
    out = io.StringIO()
    monkeypatch.setattr(sys, "stderr", out)
    cb = it.TqdmKerasCallback(verbose=2, mininterval=0)
    cb.set_params({"epochs": 3, "steps": 2})
    cb.on_train_begin()
    for epoch in range(3):
        cb.on_epoch_begin(epoch)
        for b in range(2):
            cb.on_batch_end(b)
        cb.on_epoch_end(epoch, {"loss": 0.5})
    assert cb.epoch_bar is not None and cb.epoch_bar.n == 3
    cb.on_train_end()
    assert "3/3" in out.getvalue()


def test_dask_callback_methods() -> None:
    out = io.StringIO()
    cb = it.TqdmDaskCallback(file=out, mininterval=0)
    state = {"ready": [1], "waiting": [2], "running": [], "finished": []}
    cb._start_state({}, state)
    cb._posttask("k", 1, {}, state, 0)
    cb._posttask("k2", 1, {}, state, 0)
    cb._finish({}, state, False)
    assert "2/2" in out.getvalue()


def test_notebook_alias_and_missing_extras(monkeypatch: pytest.MonkeyPatch) -> None:
    assert it.tqdm_notebook is tqdm
    monkeypatch.setitem(sys.modules, "rich.progress", None)
    out = io.StringIO()
    with it.tqdm_rich(total=2, file=out, mininterval=0) as bar:
        bar.update(2)
    assert "2/2" in out.getvalue()
    monkeypatch.setitem(sys.modules, "tkinter", None)
    with pytest.raises(ImportError):
        it.tqdm_tk(total=1, disable=True)


def test_tqdm_rich_with_real_rich() -> None:
    pytest.importorskip("rich")
    bar = it.tqdm_rich(total=3, desc="rich")
    for _ in range(3):
        bar.update(1)
    assert bar.n == 3
    bar.close()
