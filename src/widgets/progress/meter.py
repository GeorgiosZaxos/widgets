"""tqdm-compatible text formatting: ``format_meter``, ``format_interval``, ``format_sizeof``.

These reproduce the documented output layout of ``tqdm.tqdm.format_meter`` so code that formats
meters itself (or inspects ``format_dict``) keeps working. Layer L3.
"""

from __future__ import annotations

import re
from typing import Any

_ANSI = re.compile(r"\x1b\[[0-9;]*[A-Za-z]")
_ASCII_CHARS = " 123456789#"
_UNICODE_CHARS = " ▏▎▍▌▋▊▉█"


def format_interval(t: float) -> str:
    """``MM:SS`` or ``H:MM:SS`` for ``t`` seconds."""
    mins, secs = divmod(int(t), 60)
    hours, mins = divmod(mins, 60)
    return f"{hours:d}:{mins:02d}:{secs:02d}" if hours else f"{mins:02d}:{secs:02d}"


def format_sizeof(num: float, suffix: str = "", divisor: float = 1000) -> str:
    """Human-readable number with an SI prefix (``1.50k``, ``12.3M``)."""
    for unit in ("", "k", "M", "G", "T", "P", "E", "Z"):
        if abs(num) < 999.5:
            if abs(num) < 99.95:
                if abs(num) < 9.995:
                    return f"{num:1.2f}{unit}{suffix}"
                return f"{num:2.1f}{unit}{suffix}"
            return f"{num:3.0f}{unit}{suffix}"
        num /= divisor
    return f"{num:3.1f}Y{suffix}"


def format_num(n: float) -> str:
    """Compact number in ``.3g`` notation (``1.23e+8``) when that is shorter than ``str(n)``."""
    shortest = f"{n:.3g}".replace("e+0", "e+").replace("e-0", "e-")
    text = str(n)
    return shortest if len(shortest) < len(text) else text


def display_length(text: str) -> int:
    """Length of ``text`` without ANSI escapes."""
    return len(_ANSI.sub("", text))


class Bar:
    """Renders a bar of ``length`` cells; ``format(bar, "20")`` overrides the width."""

    def __init__(self, frac: float, default_len: int = 10, ascii_chars: bool | str = False) -> None:
        self.frac = max(0.0, min(1.0, frac))
        self.default_len = default_len
        if isinstance(ascii_chars, str) and ascii_chars:
            self.charset = ascii_chars if len(ascii_chars) > 1 else " " + ascii_chars
        else:
            self.charset = _ASCII_CHARS if ascii_chars else _UNICODE_CHARS

    def __format__(self, spec: str) -> str:
        length = int(spec.strip("a")) if spec.strip("a") else self.default_len
        symbols = len(self.charset) - 1
        full, part = divmod(int(self.frac * length * symbols), symbols)
        text = self.charset[-1] * full
        if full < length:
            text += self.charset[part] + self.charset[0] * (length - full - 1)
        return text

    __str__ = lambda self: self.__format__("")  # noqa: E731


def format_meter(
    n: float,
    total: float | None,
    elapsed: float,
    ncols: int | None = None,
    prefix: str = "",
    ascii: bool | str = False,
    unit: str = "it",
    unit_scale: bool | float = False,
    rate: float | None = None,
    bar_format: str | None = None,
    postfix: Any = None,
    unit_divisor: float = 1000,
    initial: float = 0,
    colour: str | None = None,
    **extra_kwargs: Any,
) -> str:
    """Return the progress line ``tqdm`` would print for these numbers."""
    if total and n >= total + 0.5:  # tqdm: past the total means the total is unknown
        total = None
    if unit_scale and unit_scale not in (True, 1) and isinstance(unit_scale, int | float):
        if total:
            total *= unit_scale
        n *= unit_scale
        if rate:
            rate *= unit_scale
        unit_scale = False
    elapsed_str = format_interval(elapsed)
    if rate is None and elapsed:
        rate = (n - initial) / elapsed
    inv_rate = 1 / rate if rate else None
    rate_noinv_fmt = ((format_sizeof(rate) if unit_scale else f"{rate:5.2f}") if rate else "?") + (
        unit + "/s"
    )
    rate_inv_fmt = (
        (format_sizeof(inv_rate) if unit_scale else f"{inv_rate:5.2f}") if inv_rate else "?"
    ) + ("s/" + unit)
    rate_fmt = rate_inv_fmt if inv_rate and inv_rate > 1 else rate_noinv_fmt
    if unit_scale:
        n_fmt = format_sizeof(n, divisor=unit_divisor)
        total_fmt = format_sizeof(total, divisor=unit_divisor) if total is not None else "?"
    else:
        n_fmt = str(n)
        total_fmt = str(total) if total is not None else "?"
    post = ""
    if postfix:
        post = ", " + postfix if isinstance(postfix, str) else ", " + str(postfix)
    remaining = (total - n) / rate if rate and total else 0
    remaining_str = format_interval(remaining) if rate else "?"
    l_bar = ""
    if prefix:
        l_bar = prefix if prefix[-2:] == ": " else prefix + ": "
    fields: dict[str, Any] = {
        "n": n,
        "n_fmt": n_fmt,
        "total": total,
        "total_fmt": total_fmt,
        "elapsed": elapsed_str,
        "elapsed_s": elapsed,
        "ncols": ncols,
        "desc": prefix or "",
        "unit": unit,
        "rate": inv_rate if inv_rate and inv_rate > 1 else rate,
        "rate_fmt": rate_fmt,
        "rate_noinv": rate,
        "rate_noinv_fmt": rate_noinv_fmt,
        "rate_inv": inv_rate,
        "rate_inv_fmt": rate_inv_fmt,
        "postfix": post,
        "unit_divisor": unit_divisor,
        "remaining": remaining_str,
        "remaining_s": remaining,
        "percentage": (n / total * 100) if total else None,
        **extra_kwargs,
    }
    r_bar = f"| {n_fmt}/{total_fmt} [{elapsed_str}<{remaining_str}, {rate_fmt}{post}]"
    if total:
        frac = n / total
        l_bar += f"{frac * 100:3.0f}%|"
        if ncols == 0:
            return l_bar[:-1] + r_bar[1:]
        fields.update(l_bar=l_bar, r_bar=r_bar)
        if bar_format:
            if "{bar" in bar_format:
                nobar = bar_format.format(bar="", **fields)
                width = max(1, ncols - display_length(nobar)) if ncols else 10
                return bar_format.format(bar=Bar(frac, width, ascii), **fields)
            return bar_format.format(**fields)
        width = max(1, ncols - display_length(l_bar + r_bar)) if ncols else 10
        return l_bar + format(Bar(frac, width, ascii)) + r_bar
    fields.update(l_bar=l_bar, r_bar=r_bar, bar="")
    if bar_format:
        fields["percentage"] = 0.0
        return bar_format.format(**fields)
    lead = f"{prefix}: " if prefix else ""
    return f"{lead}{n_fmt}{unit} [{elapsed_str}, {rate_fmt}{post}]"
