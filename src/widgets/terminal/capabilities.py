"""Terminal capability detection (FR-TERM-009, FR-TERM-012, FR-COLOR-003). Layer L1."""

from __future__ import annotations

import os
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from widgets.base_elements.color_manager import ColorMode, detect_color_mode


@dataclass(frozen=True, slots=True)
class Capabilities:
    """What the output stream can do.

    ``ansi`` means cursor control and styling sequences may be written. It is False for non-TTY
    streams and ``TERM=dumb``; widgets then fall back to plain text (FR-TERM-009).
    ``unicode`` is False when the stream encoding is not UTF-based or ASCII-only output was
    requested; widgets then use their ASCII fallback glyphs (FR-ASSET-009).
    """

    is_tty: bool
    ansi: bool
    color_mode: ColorMode
    unicode: bool


def stream_is_tty(stream: Any) -> bool:
    """True when ``stream`` reports itself as an interactive terminal."""
    try:
        return bool(stream.isatty())
    except (AttributeError, ValueError, OSError):
        return False


def detect_capabilities(
    stream: Any,
    *,
    env: Mapping[str, str] | None = None,
    color_override: ColorMode | None = None,
    ascii_only: bool = False,
    force_ansi: bool | None = None,
) -> Capabilities:
    """Inspect ``stream`` and the environment.

    ``force_ansi`` overrides the ``ansi`` decision (useful for tests and for piping into a
    terminal-aware consumer).
    """
    environment = os.environ if env is None else env
    is_tty = stream_is_tty(stream)
    ansi = is_tty and environment.get("TERM", "") != "dumb"
    if force_ansi is not None:
        ansi = force_ansi
    color_mode = detect_color_mode(environment, isatty=is_tty, override=color_override)
    encoding = (
        str(getattr(stream, "encoding", None) or "").lower().replace("-", "").replace("_", "")
    )
    unicode = not ascii_only and "utf" in encoding
    return Capabilities(is_tty=is_tty, ansi=ansi, color_mode=color_mode, unicode=unicode)
