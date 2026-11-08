"""``tqdm.contrib.logging`` equivalents: log through the bars without garbling them."""

from __future__ import annotations

import logging
from collections.abc import Iterator, Sequence
from contextlib import contextmanager
from typing import Any

from widgets.progress.tqdm import tqdm as std_tqdm


class _TqdmLoggingHandler(logging.StreamHandler):  # type: ignore[type-arg]
    def __init__(self, tqdm_class: Any = std_tqdm) -> None:
        super().__init__()
        self.tqdm_class = tqdm_class

    def emit(self, record: logging.LogRecord) -> None:
        try:
            self.tqdm_class.write(self.format(record), file=self.stream, end=self.terminator)
        except (KeyboardInterrupt, SystemExit):
            raise
        except Exception:
            self.handleError(record)


@contextmanager
def logging_redirect_tqdm(
    loggers: Sequence[logging.Logger] | None = None, tqdm_class: Any = std_tqdm
) -> Iterator[None]:
    """Route console log handlers through ``tqdm.write`` inside the ``with`` block."""
    targets = list(loggers) if loggers is not None else [logging.root]
    original: list[tuple[logging.Logger, logging.Handler, _TqdmLoggingHandler]] = []
    try:
        for logger in targets:
            for handler in list(logger.handlers):
                if isinstance(handler, logging.StreamHandler) and not isinstance(
                    handler, logging.FileHandler
                ):
                    replacement: _TqdmLoggingHandler = _TqdmLoggingHandler(tqdm_class)
                    replacement.setFormatter(handler.formatter)
                    replacement.setLevel(handler.level)
                    replacement.stream = handler.stream
                    index = logger.handlers.index(handler)
                    logger.handlers[index] = replacement
                    original.append((logger, handler, replacement))
        yield
    finally:
        for logger, handler, replacement in original:
            if replacement in logger.handlers:
                logger.handlers[logger.handlers.index(replacement)] = handler


@contextmanager
def tqdm_logging_redirect(*args: Any, **kwargs: Any) -> Iterator[Any]:
    """``logging_redirect_tqdm`` plus a bar built from ``*args, **kwargs``."""
    loggers = kwargs.pop("loggers", None)
    tqdm_class = kwargs.pop("tqdm_class", std_tqdm)
    with tqdm_class(*args, **kwargs) as bar, logging_redirect_tqdm(loggers, tqdm_class):
        yield bar


__all__ = ["logging_redirect_tqdm", "tqdm_logging_redirect"]
