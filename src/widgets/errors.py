"""Exception hierarchy of the package (ER-001).

Programming errors use the built-in ``ValueError`` / ``TypeError`` / ``KeyError`` /
``IndexError`` exactly as the individual requirements specify; everything else derives
from :class:`WidgetsError`.
"""

from __future__ import annotations


class WidgetsError(Exception):
    """Base class of all package-specific errors."""


class LifecycleError(WidgetsError):
    """A lifecycle operation is illegal for the widget's current state (FR-LIFE-003)."""


class TerminalBusyError(WidgetsError):
    """The output stream is already owned by another terminal session (FR-TERM-007)."""


class TerminalCapabilityError(WidgetsError):
    """The terminal lacks a capability that the operation requires (FR-TERM-010, FR-INPUT-011)."""


class MissingDependencyError(WidgetsError, ImportError):
    """An optional dependency required by a feature is not installed (ER-002)."""

    def __init__(
        self, module: str, *, feature: str | None = None, extra: str | None = None
    ) -> None:
        self.module = module
        self.feature = feature
        self.extra = extra
        message = f"optional dependency {module!r} is not installed"
        if feature:
            message += f" (required by {feature})"
        if extra:
            message += f"; install it with: pip install 'termwidgets[{extra}]'"
        ImportError.__init__(self, message, name=module)


class TableDataError(WidgetsError, ValueError):
    """Malformed, empty or ragged tabular input (FR-TABLE-005); ``row`` is 1-based."""

    def __init__(self, message: str, *, row: int | None = None) -> None:
        self.row = row
        super().__init__(f"{message} (row {row})" if row is not None else message)


class FeedError(WidgetsError):
    """Base class for feed retrieval/parse failures (FR-RSS-006)."""


class FeedTimeoutError(FeedError):
    """The request timed out."""


class FeedConnectionError(FeedError):
    """DNS, TLS, connection, redirect-policy or size-limit failure."""


class FeedHttpError(FeedError):
    """The server answered with an HTTP error status."""

    def __init__(self, status: int, message: str = "") -> None:
        self.status = status
        super().__init__(message or f"HTTP {status}")


class FeedParseError(FeedError):
    """The response was not a well-formed, acceptable RSS/Atom document."""


class LocationNotFoundError(WidgetsError, LookupError):
    """The weather geocoder found no match (FR-WEATHER-001)."""


class WeatherError(WidgetsError):
    """Provider/transport failure while fetching weather."""


class AudioBackendError(WidgetsError):
    """Base class for audio backend failures (FR-AUDIO-006)."""


class AudioUnavailableError(AudioBackendError):
    """No usable audio device/player, or the backend failed to initialise or was closed."""


class UnsupportedFormatError(AudioBackendError):
    """The backend cannot play this file format."""
