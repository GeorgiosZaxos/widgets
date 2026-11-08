"""``tqdm.std`` equivalent: the standard terminal implementation."""

from __future__ import annotations

from widgets.progress.tqdm import (
    TqdmDeprecationWarning,
    TqdmExperimentalWarning,
    TqdmKeyError,
    TqdmMonitorWarning,
    TqdmSynchronisationWarning,
    TqdmTypeError,
    TqdmWarning,
    tqdm,
    tqdm_pandas,
    trange,
)

__all__ = [
    "TqdmDeprecationWarning",
    "TqdmExperimentalWarning",
    "TqdmKeyError",
    "TqdmMonitorWarning",
    "TqdmSynchronisationWarning",
    "TqdmTypeError",
    "TqdmWarning",
    "tqdm",
    "tqdm_pandas",
    "trange",
]
