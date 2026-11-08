"""``tqdm.contrib`` equivalents: ``tenumerate``, ``tzip``, ``tmap``, ``DummyTqdmFile``."""

from __future__ import annotations

from typing import Any, TextIO

from widgets.progress.tqdm import tenumerate, tmap, tqdm, tzip

builtin_iter = iter


class DummyTqdmFile:
    """File-like object that routes ``write`` through ``tqdm.write`` (to redirect ``print``)."""

    def __init__(self, file: TextIO | None = None) -> None:
        self.file = file

    def write(self, x: str) -> int:
        """Print ``x`` above the bars (blank writes are ignored, as ``print`` emits them)."""
        if len(x.rstrip()) > 0:
            tqdm.write(x, file=self.file, end="")
        return len(x)

    def __del__(self) -> None:
        return None

    def flush(self) -> None:
        """Flush the wrapped file when it has one."""
        getattr(self.file, "flush", lambda: None)()

    def isatty(self) -> bool:
        """Whether the wrapped file is a terminal."""
        return bool(getattr(self.file, "isatty", lambda: False)())

    def __getattr__(self, name: str) -> Any:
        return getattr(self.file, name)


__all__ = ["DummyTqdmFile", "builtin_iter", "tenumerate", "tmap", "tzip"]
