"""``tqdm.asyncio`` equivalent: ``async for`` support plus ``gather`` / ``as_completed``."""

from __future__ import annotations

from collections.abc import Iterator
from typing import Any

from widgets.progress.tqdm import asyncio_tools, tqdm
from widgets.progress.vertical import vtqdm


class tqdm_asyncio(tqdm):
    """:class:`tqdm` with ``gather`` and ``as_completed`` (``async for`` works on every tqdm)."""

    @classmethod
    async def gather(cls, *coros: Any, **kwargs: Any) -> list[Any]:
        """``asyncio.gather`` with a bar of this class; results keep their input order."""
        return await asyncio_tools.gather(*coros, tqdm_class=cls, **kwargs)

    @classmethod
    def as_completed(cls, coros: Any, **kwargs: Any) -> Iterator[Any]:
        """Like ``asyncio.as_completed`` with a bar that advances as results arrive."""
        return asyncio_tools.as_completed(coros, tqdm_class=cls, **kwargs)


class vtqdm_asyncio(vtqdm):
    """:class:`vtqdm` with ``gather`` and ``as_completed``."""

    gather = tqdm_asyncio.__dict__["gather"]
    as_completed = tqdm_asyncio.__dict__["as_completed"]


def tarange(*args: int, **kwargs: Any) -> tqdm_asyncio:
    """``tqdm_asyncio(range(*args))`` for ``async for`` loops."""
    return tqdm_asyncio(range(*args), **kwargs)


__all__ = ["tarange", "tqdm", "tqdm_asyncio", "vtqdm_asyncio"]
