"""``tqdm.contrib.itertools`` equivalent: ``product`` with a progress bar."""

from __future__ import annotations

import itertools
from collections.abc import Iterable, Iterator
from typing import Any

from widgets.progress.tqdm import tqdm


def product(*iterables: Iterable[Any], **tqdm_kwargs: Any) -> Iterator[tuple[Any, ...]]:
    """``itertools.product`` whose total is the product of the input lengths (when known)."""
    kwargs = dict(tqdm_kwargs)
    if "total" not in kwargs:
        try:
            total = 1
            for it in iterables:
                total *= len(it)  # type: ignore[arg-type]
            kwargs["total"] = total
        except TypeError:
            pass
    return iter(tqdm(itertools.product(*iterables), **kwargs))


__all__ = ["product"]
