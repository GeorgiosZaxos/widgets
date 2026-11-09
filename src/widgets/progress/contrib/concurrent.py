"""``tqdm.contrib.concurrent`` equivalents: ``thread_map`` and ``process_map``."""

from __future__ import annotations

from collections.abc import Callable, Iterable
from concurrent.futures import ProcessPoolExecutor, ThreadPoolExecutor
from typing import Any

from widgets.progress.tqdm import tqdm


def _executor_map(
    pool_cls: type, fn: Callable[..., Any], *iterables: Iterable[Any], **tqdm_kwargs: Any
) -> list[Any]:
    kwargs = dict(tqdm_kwargs)
    max_workers = kwargs.pop("max_workers", None)
    chunksize = kwargs.pop("chunksize", 1)
    kwargs.pop("lock_name", None)
    tqdm_class = kwargs.pop("tqdm_class", tqdm)
    pool_kwargs: dict[str, Any] = {} if max_workers is None else {"max_workers": max_workers}
    sequences = [list(it) for it in iterables]
    if "total" not in kwargs and sequences:
        kwargs["total"] = min(len(s) for s in sequences)
    with pool_cls(**pool_kwargs) as pool:
        extra = {"chunksize": chunksize} if pool_cls is ProcessPoolExecutor else {}
        return list(tqdm_class(pool.map(fn, *sequences, **extra), **kwargs))


def thread_map(fn: Callable[..., Any], *iterables: Iterable[Any], **tqdm_kwargs: Any) -> list[Any]:
    """``map(fn, *iterables)`` on a thread pool with a progress bar; returns a list."""
    return _executor_map(ThreadPoolExecutor, fn, *iterables, **tqdm_kwargs)


def process_map(fn: Callable[..., Any], *iterables: Iterable[Any], **tqdm_kwargs: Any) -> list[Any]:
    """``map(fn, *iterables)`` on a process pool with a progress bar; returns a list."""
    return _executor_map(ProcessPoolExecutor, fn, *iterables, **tqdm_kwargs)


__all__ = ["process_map", "thread_map"]
