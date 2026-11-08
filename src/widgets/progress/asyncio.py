"""``tqdm.asyncio`` equivalent: ``async for`` support plus ``gather`` / ``as_completed``."""

from __future__ import annotations

from collections.abc import Iterator
from typing import Any

from widgets.progress.tqdm import asyncio_tools, tqdm


class tqdm_asyncio(tqdm):
    """:class:`tqdm` with ``gather`` and ``as_completed`` (``async for`` works on every tqdm)."""

    gather = staticmethod(asyncio_tools.gather)

    @staticmethod
    def as_completed(coros: Any, **kwargs: Any) -> Iterator[Any]:
        """Like ``asyncio.as_completed`` with a bar that advances as results arrive."""
        return asyncio_tools.as_completed(coros, **kwargs)


def tarange(*args: int, **kwargs: Any) -> tqdm_asyncio:
    """``tqdm_asyncio(range(*args))`` for ``async for`` loops."""
    return tqdm_asyncio(range(*args), **kwargs)


__all__ = ["tarange", "tqdm", "tqdm_asyncio"]
