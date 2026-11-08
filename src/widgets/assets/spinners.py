"""Named spinner frame sequences (FR-ASSET-006, FR-ASSET-009). Layer L1."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class SpinnerSpec:
    name: str
    frames: tuple[str, ...]
    interval: float
    ascii_safe: bool


def _spec(
    name: str, frames: str | tuple[str, ...], interval: float, ascii_safe: bool
) -> SpinnerSpec:
    return SpinnerSpec(name, tuple(frames), interval, ascii_safe)


_SPINNERS = {
    spec.name: spec
    for spec in (
        _spec("line", "-\\|/", 0.1, True),
        _spec("plus", "+x", 0.15, True),
        _spec("balloon", " .oO@*", 0.14, True),
        _spec("flip", "_-`'-", 0.14, True),
        _spec("bar", ("[=   ]", "[ =  ]", "[  = ]", "[   =]", "[  = ]", "[ =  ]"), 0.1, True),
        _spec("dots-ascii", (".  ", ".. ", "...", " ..", "  .", "   "), 0.2, True),
        _spec("pipe", "┤┘┴└├┌┬┐", 0.1, False),
        _spec("dots", "⠋⠙⠹⠸⠼⠴⠦⠧⠇⠏", 0.08, False),
        _spec("dots2", "⣾⣽⣻⢿⡿⣟⣯⣷", 0.08, False),
        _spec("dots3", "⠁⠂⠄⡀⢀⠠⠐⠈", 0.1, False),
        _spec("arc", "◜◠◝◞◡◟", 0.1, False),
        _spec("circle", "◐◓◑◒", 0.12, False),
        _spec("quarter", "◴◷◶◵", 0.12, False),
        _spec("star", "✶✸✹✺✹✷", 0.1, False),
        _spec("arrows", "←↖↑↗→↘↓↙", 0.1, False),
        _spec("grow-v", "▁▃▄▅▆▇▆▅▄▃", 0.1, False),
        _spec("grow-h", "▏▎▍▌▋▊▉▊▋▌▍▎", 0.1, False),
        _spec("bounce", "⠁⠂⠄⠂", 0.12, False),
        _spec("box", "▖▘▝▗", 0.12, False),
        _spec("triangle", "◢◣◤◥", 0.12, False),
        _spec("toggle", "⊶⊷", 0.25, False),
        _spec("hamburger", "☱☲☴", 0.15, False),
    )
}

FALLBACK_SPINNER = "line"


def _install_bundled() -> None:
    import widgets.assets._spinner_data as _spinner_data

    for name, frames in _spinner_data.SPINNERS.items():
        if name not in _SPINNERS:
            safe = all(ord(ch) < 128 for frame in frames for ch in frame)
            _SPINNERS[name] = SpinnerSpec(name, tuple(frames), 0.1, safe)


_install_bundled()


def list_spinners() -> list[str]:
    """Return the names of all registered spinner styles."""
    return sorted(_SPINNERS)


def get_spinner(name: str) -> SpinnerSpec:
    """The spinner called ``name``; unknown names raise ``KeyError`` listing the valid ones."""
    try:
        return _SPINNERS[name]
    except KeyError:
        raise KeyError(f"unknown spinner {name!r}; available: {sorted(_SPINNERS)}") from None


def spinner_frames(name: str, ascii_only: bool = False) -> tuple[str, ...]:
    """Frames of ``name``; non-ASCII-safe spinners fall back to the ``line`` frames when asked."""
    spec = get_spinner(name)
    if ascii_only and not spec.ascii_safe:
        return _SPINNERS[FALLBACK_SPINNER].frames
    return spec.frames
