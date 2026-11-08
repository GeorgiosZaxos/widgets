"""Optional / required import helpers (FR-IMPORT-001..003). Layer L0."""

from __future__ import annotations

import importlib
import logging
from types import ModuleType

from widgets.errors import MissingDependencyError

logger = logging.getLogger(__name__)


def optional_import(name: str, *, feature: str | None = None) -> ModuleType | None:
    """Import ``name`` and return it, or ``None`` if it is unavailable.

    Never raises for a missing module and never logs above DEBUG level.
    """
    try:
        return importlib.import_module(name)
    except ImportError:
        logger.debug(
            "optional dependency %r unavailable%s",
            name,
            f" (needed for {feature})" if feature else "",
        )
        return None


def require_import(
    name: str, *, feature: str | None = None, extra: str | None = None
) -> ModuleType:
    """Import ``name`` or raise :class:`MissingDependencyError` naming module, feature and extra."""
    try:
        return importlib.import_module(name)
    except ImportError as exc:
        raise MissingDependencyError(name, feature=feature, extra=extra) from exc
