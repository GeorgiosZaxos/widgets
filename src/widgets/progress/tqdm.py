"""``tqdm``-style subset (FR-PROG-013, D-18, FR-PROG-014/015). Layer L3.

Supported: ``tqdm(iterable=None, desc, total, leave, file, ncols, mininterval, miniters, disable,
unit, unit_scale, dynamic_ncols, smoothing, initial, position, postfix)``; ``update``, ``close``,
``refresh``, ``reset``, ``clear``, ``set_description``, ``set_postfix``, ``set_postfix_str``,
``tqdm.write``, iteration, context manager, and ``trange``. Output defaults to ``sys.stderr``.

Also supported: ``bar_format`` (placeholders ``{desc} {percentage} {bar} {n_fmt} {total_fmt}
{elapsed} {remaining} {rate_fmt} {postfix} {unit} {l_bar} {r_bar}``), ``delay``, ``unit_divisor``,
``write_bytes`` and ``tqdm.pandas()`` (``progress_apply``/``progress_map``; needs pandas).

Documented limitations: ``dynamic_ncols`` is accepted - the width always follows the
terminal unless ``ncols`` is given. Unknown arguments raise ``TypeError``. Bars writing to the
same stream share one :class:`ProgressManager`, so they never overlap.
"""

from __future__ import annotations

import contextlib
import sys
import threading
import time
import weakref
from collections.abc import AsyncIterator, Iterable, Iterator, Mapping, Sequence
from typing import Any, TextIO

from widgets.base_elements.color_manager import Gradient, parse_color
from widgets.base_elements.widget_types import Style
from widgets.progress import meter
from widgets.progress.indicators import HorizontalBar, ProgressIndicator, custom_bar_style
from widgets.progress.inline import ProgressManager
from widgets.progress.state import ProgressState

_LOCK: Any = threading.RLock()
_INSTANCES: weakref.WeakSet[tqdm] = weakref.WeakSet()


class TqdmWarning(Warning):
    """Base class of this library's tqdm-compatible warnings."""


class TqdmExperimentalWarning(TqdmWarning, FutureWarning):
    """Warning for experimental features (tqdm-compatible name)."""


class TqdmDeprecationWarning(TqdmWarning, DeprecationWarning):
    """Warning for deprecated arguments (tqdm-compatible name)."""


class TqdmMonitorWarning(TqdmWarning, RuntimeWarning):
    """Warning from the (unused) monitor thread; present for compatibility."""


class TqdmSynchronisationWarning(TqdmWarning, RuntimeWarning):
    """Warning about unsynchronised bars; present for compatibility."""


class TqdmKeyError(KeyError, TypeError):
    """Unknown ``tqdm`` argument (also a ``TypeError`` for callers that expect one)."""


class TqdmTypeError(TypeError):
    """Wrong ``tqdm`` argument type (tqdm-compatible name)."""


_MANAGERS: dict[int, ProgressManager] = {}


def _manager_for(stream: TextIO, mininterval: float) -> ProgressManager:
    manager = _MANAGERS.get(id(stream))
    if manager is None or manager.closed:
        manager = ProgressManager(stream, mininterval=mininterval)
        _MANAGERS[id(stream)] = manager
    else:
        manager.mininterval = min(manager.mininterval, mininterval)
    return manager


class _BytesWriter:
    """Text-to-bytes adapter for ``write_bytes=True`` (streams that expect ``bytes``)."""

    def __init__(self, raw: Any) -> None:
        self.raw = raw
        self.encoding = "utf-8"

    def write(self, text: str) -> int:
        self.raw.write(text.encode("utf-8"))
        return len(text)

    def flush(self) -> None:
        self.raw.flush()

    def isatty(self) -> bool:
        return bool(getattr(self.raw, "isatty", lambda: False)())


_BYTE_WRITERS: dict[int, _BytesWriter] = {}


def _look(
    ascii_: bool | str | None,
    style: str | None,
    fill: str | None,
    empty: str | None,
    colour: str | None,
    empty_colour: str | None,
    gradient: Sequence[object] | Gradient | None,
    spinner: str | None,
) -> dict[str, Any]:
    """Appearance options (widgets extensions to tqdm's API) as keyword arguments for the bar."""
    look: dict[str, Any] = {}
    charset = ascii_ if isinstance(ascii_, str) and ascii_ else None
    if fill or empty or charset:
        look["style"] = custom_bar_style(charset, fill, empty, frame=True)
    elif style is not None:
        look["style"] = style
    if colour:
        look["fill_style"] = Style(fg=parse_color(colour))
    if empty_colour:
        look["empty_style"] = Style(fg=parse_color(empty_colour))
    if gradient is not None:
        look["gradient"] = (
            gradient if isinstance(gradient, Gradient) else Gradient.from_colors(gradient)
        )
    if spinner is not None:
        look["spinner"] = spinner
    return look


class tqdm:
    """tqdm-compatible progress iterator rendered by this library.

    Widgets extensions (keyword only, ignored by code written for tqdm): ``style`` (bar style
    name), ``fill`` / ``empty`` (glyphs; ``ascii="  ▏▎▍█"`` charsets work too), ``colour`` and
    ``empty_colour``, ``gradient`` (list of colours) and ``spinner`` (spinner name).
    """

    def __init__(
        self,
        iterable: Iterable[Any] | None = None,
        desc: str | None = None,
        total: float | None = None,
        leave: bool = True,
        file: TextIO | None = None,
        ncols: int | None = None,
        mininterval: float = 0.1,
        miniters: int | None = None,
        disable: bool = False,
        unit: str = "it",
        unit_scale: bool = False,
        dynamic_ncols: bool = False,
        smoothing: float = 0.3,
        initial: float = 0,
        position: int | None = None,
        postfix: Mapping[str, object] | str | None = None,
        bar_format: str | None = None,
        unit_divisor: float = 1000,
        delay: float = 0,
        write_bytes: bool = False,
        manager: ProgressManager | None = None,
        maxinterval: float = 10.0,
        ascii: bool | str | None = None,
        lock_args: tuple[Any, ...] | None = None,
        nrows: int | None = None,
        colour: str | None = None,
        gui: bool = False,
        style: str | None = None,
        fill: str | None = None,
        empty: str | None = None,
        gradient: Sequence[object] | Gradient | None = None,
        spinner: str | None = None,
        empty_colour: str | None = None,
        **kwargs: Any,
    ) -> None:
        if kwargs:
            self.disable = True
            if "nested" in kwargs:
                raise TqdmDeprecationWarning("`nested` is deprecated and automated; use `position`")
            raise TqdmKeyError("Unknown argument(s): " + str(kwargs))
        if delay < 0:
            raise ValueError("delay must be >= 0")
        if leave is None:
            leave = not position
        self.iterable = iterable
        if total is None and iterable is not None:
            try:
                total = len(iterable)  # type: ignore[arg-type]
            except TypeError:
                total = None
        if total is not None and total == float("inf"):
            total = None
        self.disable = disable
        self.leave = leave
        self.unit, self.unit_scale = unit, unit_scale
        self.miniters = miniters
        self.mininterval, self.maxinterval, self.smoothing = mininterval, maxinterval, smoothing
        self.ncols, self.nrows, self.colour, self.gui = ncols, nrows, colour, gui
        self.ascii: bool | str = False if ascii is None else ascii
        self.bar_format, self.unit_divisor, self.initial = bar_format, unit_divisor, initial
        self.start_t = time.time()
        self.last_print_t = self.start_t
        self._closed = False
        self._cleared = False
        self._last_refresh_n = initial
        self._position = position
        self._file: Any = sys.stderr if file is None else file
        if write_bytes:
            self._file = _BYTE_WRITERS.setdefault(id(self._file), _BytesWriter(self._file))
        self._delay_until = time.monotonic() + delay if delay > 0 else None
        self._attached = False
        self._owned_manager = manager is None
        self._manager: ProgressManager | None = None
        self.state = ProgressState(
            total,
            n=initial,
            description=desc or "",
            smoothing=smoothing,
            clock=None if manager is None else manager.clock,
        )
        if postfix is not None:
            self.set_postfix(postfix, refresh=False)
        self.bar: ProgressIndicator | None = None
        if disable:
            return
        with _LOCK:
            self._manager = manager or _manager_for(self._file, mininterval)
            self.bar = self._make_bar(
                ncols,
                unit=unit,
                unit_scale=unit_scale,
                unit_divisor=unit_divisor,
                bar_format=bar_format,
                ascii_only=bool(ascii) if ascii is not None else self._manager.ascii_only,
                **_look(ascii, style, fill, empty, colour, empty_colour, gradient, spinner),
            )
            _INSTANCES.add(self)
            if self._delay_until is None:
                self._manager.add(self.bar, position, leave=leave)
                self._attached = True

    def _make_bar(self, ncols: int | None, **options: Any) -> ProgressIndicator:
        """Create the indicator drawn for this task (``vtqdm`` overrides this)."""
        return HorizontalBar(self.state, ncols, **options)

    def _attach_if_due(self) -> bool:
        """Show a ``delay``-ed bar once the delay has passed; True when the bar is visible."""
        if self._attached:
            return True
        if (
            self._delay_until is None
            or time.monotonic() < self._delay_until
            or self._manager is None
            or self.bar is None
        ):
            return False
        with _LOCK:
            self._manager.add(self.bar, self._position, leave=self.leave)
            self._attached = True
        return True

    # -- state --------------------------------------------------------------------------------

    @property
    def n(self) -> float:
        """Current count (assignable, like ``tqdm.n``)."""
        return self.state.n

    @n.setter
    def n(self, value: float) -> None:
        self.state.set(value)

    @property
    def total(self) -> float | None:
        """Expected count (assignable, like ``tqdm.total``)."""
        return self.state.total

    @total.setter
    def total(self, value: float | None) -> None:
        self.state.total = value

    @property
    def postfix(self) -> str:
        """The postfix text currently shown."""
        return self.state.postfix

    @property
    def pos(self) -> int:
        """Row of this bar (0 when not given)."""
        return self._position or 0

    @property
    def last_print_n(self) -> float:
        """Value of ``n`` at the last repaint."""
        return self._last_refresh_n

    @property
    def format_dict(self) -> dict[str, Any]:
        """The arguments :meth:`format_meter` needs to render the current state."""
        return {
            "n": self.state.n,
            "total": self.state.total,
            "elapsed": self.state.elapsed,
            "ncols": self.ncols,
            "nrows": self.nrows,
            "prefix": self.state.description,
            "ascii": self.ascii,
            "unit": self.unit,
            "unit_scale": self.unit_scale,
            "rate": None,
            "bar_format": self.bar_format,
            "postfix": self.state.postfix,
            "unit_divisor": self.unit_divisor,
            "initial": self.initial,
            "colour": self.colour,
        }

    @property
    def desc(self) -> str:
        return self.state.description

    # -- progress ---------------------------------------------------------------------------------

    def update(self, n: float = 1) -> None:
        """Advance by ``n`` and repaint if due. Thread-safe."""
        self.state.update(n)
        if self.disable or self._closed:
            return
        if not self._attach_if_due():
            return
        if self.miniters and self.state.n - self._last_refresh_n < self.miniters:
            return
        self._last_refresh_n = self.state.n
        if self._manager is not None:
            self._manager.refresh()

    def refresh(self) -> None:
        """Repaint now (re-showing the bar after :meth:`clear`)."""
        if self.disable or self._closed or self._manager is None or self.bar is None:
            return
        if not self._attach_if_due():
            return
        with _LOCK:
            if self._cleared:
                self._manager.add(self.bar, self._position, leave=self.leave)
                self._cleared = False
            else:
                self._manager.refresh(force=True)

    def clear(self) -> None:
        """Erase the bar from the display (it is shown again by :meth:`refresh`)."""
        if (
            self.disable
            or self._closed
            or self._cleared
            or self._manager is None
            or self.bar is None
        ):
            return
        with _LOCK:
            self._manager.remove(self.bar, leave=False, close=False)
            self._cleared = True

    def reset(self, total: float | None = None) -> None:
        self.state.reset(total)
        self._last_refresh_n = 0
        self.refresh()

    def set_description(self, desc: str | None = None, refresh: bool = True) -> None:
        self.state.description = desc or ""
        if refresh:
            self.refresh()

    def set_postfix(
        self,
        ordered_dict: Mapping[str, object] | str | None = None,
        refresh: bool = True,
        **kwargs: object,
    ) -> None:
        if isinstance(ordered_dict, str):
            self.state.set_postfix(ordered_dict, **kwargs)
        else:
            self.state.set_postfix(None, **{**(ordered_dict or {}), **kwargs})
        if refresh:
            self.refresh()

    def set_postfix_str(self, s: str = "", refresh: bool = True) -> None:
        self.set_postfix(s, refresh=refresh)

    def set_description_str(self, desc: str | None = None, refresh: bool = True) -> None:
        """Same as :meth:`set_description` (tqdm keeps a separate raw-string variant)."""
        self.set_description(desc, refresh)

    def display(self, msg: str | None = None, pos: int | None = None) -> None:
        """Repaint the bar (``msg`` and ``pos`` are accepted for compatibility)."""
        self.refresh()

    def moveto(self, n: int) -> None:
        """Compatibility no-op: rows are laid out by the shared progress manager."""

    def unpause(self) -> None:
        """Compatibility: repaint after a pause."""
        self.refresh()

    # -- tqdm's static helpers and class-level hooks -------------------------------------------

    monitor: Any = None
    monitor_interval: float = 10

    format_meter = staticmethod(meter.format_meter)
    format_interval = staticmethod(meter.format_interval)
    format_sizeof = staticmethod(meter.format_sizeof)
    format_num = staticmethod(meter.format_num)

    @staticmethod
    def status_printer(file: TextIO) -> Any:
        """Return ``print_status(s)`` that rewrites one line of ``file`` in place."""
        last = [0]

        def print_status(s: str) -> None:
            file.write("\r" + s + " " * max(last[0] - meter.display_length(s), 0))
            getattr(file, "flush", lambda: None)()
            last[0] = meter.display_length(s)

        return print_status

    @classmethod
    def get_lock(cls) -> Any:
        """The re-entrant lock that serialises drawing."""
        return _LOCK

    @classmethod
    def set_lock(cls, lock: Any) -> None:
        """Replace the drawing lock (e.g. with a multiprocessing lock)."""
        global _LOCK
        _LOCK = lock

    @classmethod
    @contextlib.contextmanager
    def external_write_mode(
        cls, file: TextIO | None = None, nolock: bool = False
    ) -> Iterator[None]:
        """Temporarily hide this stream's bars so other code can print, then redraw them."""
        stream = sys.stderr if file is None else file
        hidden = [b for b in list(_INSTANCES) if b._file is stream and b._attached]
        for bar in hidden:
            bar.clear()
        try:
            yield
        finally:
            for bar in hidden:
                bar.refresh()

    @classmethod
    @contextlib.contextmanager
    def wrapattr(
        cls,
        stream: Any,
        method: str,
        total: float | None = None,
        bytes: bool = True,
        **tqdm_kwargs: Any,
    ) -> Iterator[Any]:
        """Context manager wrapping ``stream.read`` / ``stream.write`` so each call advances a bar."""
        if bytes:
            tqdm_kwargs.setdefault("unit", "B")
            tqdm_kwargs.setdefault("unit_scale", True)
            tqdm_kwargs.setdefault("unit_divisor", 1024)
            if total is None:
                with contextlib.suppress(Exception):
                    import os

                    total = os.fstat(stream.fileno()).st_size
        with cls(total=total, **tqdm_kwargs) as bar:
            yield _Wrapped(stream, method, bar)

    def close(self) -> None:
        """Finish the bar (idempotent); the line stays in scrollback if ``leave``."""
        if self._closed:
            return
        self._closed = True
        self.state.close()
        if self.disable or self._manager is None or self.bar is None:
            return
        with _LOCK:
            manager = self._manager
            if not self._cleared and self._attached:
                manager.remove(self.bar, leave=self.leave)
            if not self._owned_manager:
                return
            if not manager.indicators and manager.retained:
                manager.park()
                return
            if not manager.indicators:
                manager.close()
                if _MANAGERS.get(id(self._file)) is manager:
                    del _MANAGERS[id(self._file)]

    # -- protocols ------------------------------------------------------------------------------------

    def __iter__(self) -> Iterator[Any]:
        if self.iterable is None:
            raise TypeError("tqdm object has no iterable; use update() instead")
        try:
            for item in self.iterable:
                yield item
                self.update(1)
        finally:  # exhaustion, break (generator close) and exceptions all end up here
            self.close()

    def __len__(self) -> int:
        if self.state.total is not None:
            return int(self.state.total)
        try:
            return len(self.iterable)  # type: ignore[arg-type]
        except TypeError:
            raise TypeError(f"object of type {type(self).__name__!r} has no len()") from None

    def __bool__(self) -> bool:
        if self.state.total is not None:
            return bool(self.state.total)
        if self.iterable is None:
            return True
        try:
            return bool(self.iterable)
        except TypeError:
            return True

    def __reversed__(self) -> Iterator[Any]:
        try:
            original = self.iterable
            self.iterable = reversed(original)  # type: ignore[call-overload]
        except TypeError:
            raise TypeError("'tqdm' wraps an object that is not reversible") from None
        return iter(self)

    def __contains__(self, item: object) -> bool:
        return item in self.iterable  # type: ignore[operator]

    def __str__(self) -> str:
        return self.format_meter(**{**self.format_dict, "rate": None})

    def __repr__(self) -> str:
        return self.__str__()

    def __hash__(self) -> int:
        return id(self)

    def __del__(self) -> None:
        with contextlib.suppress(Exception):
            self.close()

    def __aiter__(self) -> AsyncIterator[Any]:
        return self._aiter()

    async def _aiter(self) -> AsyncIterator[Any]:
        if self.iterable is None:
            raise TypeError("tqdm object has no iterable; use update() instead")
        try:
            if hasattr(self.iterable, "__aiter__"):
                async for item in self.iterable:
                    yield item
                    self.update(1)
            else:
                for item in self.iterable:
                    yield item
                    self.update(1)
        finally:
            self.close()

    def __enter__(self) -> tqdm:
        return self

    def __exit__(self, *exc_info: object) -> None:
        self.close()

    @classmethod
    def pandas(cls, **tqdm_kwargs: Any) -> None:
        """Register ``progress_apply`` / ``progress_map`` on pandas objects (needs pandas)."""
        from widgets.base_elements.import_helper import require_import

        pd = require_import("pandas", feature="tqdm.pandas()", extra="data")

        def wrap(total: int | None, func: Any) -> tuple[tqdm, Any]:
            bar = cls(total=total, **tqdm_kwargs)

            def inner(*a: Any, **k: Any) -> Any:
                try:
                    return func(*a, **k)
                finally:
                    bar.update(1)

            return bar, inner

        def frame_apply(self: Any, func: Any, axis: int = 0, *args: Any, **kwargs: Any) -> Any:
            total = self.shape[1] if axis in (0, "index") else self.shape[0]
            bar, inner = wrap(total, func)
            with bar:
                return self.apply(inner, axis, *args, **kwargs)

        def series_apply(self: Any, func: Any, *args: Any, **kwargs: Any) -> Any:
            bar, inner = wrap(len(self), func)
            with bar:
                return self.apply(inner, *args, **kwargs)

        def series_map(self: Any, arg: Any, *args: Any, **kwargs: Any) -> Any:
            if not callable(arg):
                return self.map(arg, *args, **kwargs)
            bar, inner = wrap(len(self), arg)
            with bar:
                return self.map(inner, *args, **kwargs)

        def group_apply(self: Any, func: Any, *args: Any, **kwargs: Any) -> Any:
            bar, inner = wrap(self.ngroups, func)
            with bar:
                return self.apply(inner, *args, **kwargs)

        pd.DataFrame.progress_apply = frame_apply
        pd.Series.progress_apply = series_apply
        pd.Series.progress_map = series_map
        pd.api.typing.DataFrameGroupBy.progress_apply = group_apply
        pd.api.typing.SeriesGroupBy.progress_apply = group_apply

    @classmethod
    def write(cls, s: str, file: TextIO | None = None, end: str = "\n") -> None:
        """Print ``s`` above the active bars of ``file`` (stderr by default) without garbling."""
        stream = sys.stderr if file is None else file
        text = s[: -len(end)] if end and s.endswith(end) else s
        with _LOCK:
            manager = _MANAGERS.get(id(stream))
            if manager is not None and not manager.closed:
                manager.write(text if end == "\n" else text + end.rstrip("\n"))
                return
        stream.write(s + end if not s.endswith(end) else s)
        stream.flush()


def trange(*args: int, **kwargs: Any) -> tqdm:
    """``tqdm(range(*args), **kwargs)``."""
    return tqdm(range(*args), **kwargs)


def tenumerate(iterable: Iterable[Any], start: int = 0, **kwargs: Any) -> Iterator[tuple[int, Any]]:
    """``enumerate`` with a progress bar (``tqdm.contrib.tenumerate``)."""
    if "total" not in kwargs:
        with contextlib.suppress(TypeError):
            kwargs["total"] = len(iterable)  # type: ignore[arg-type]
    yield from enumerate(tqdm(iterable, **kwargs), start)


def tzip(*iterables: Iterable[Any], **kwargs: Any) -> Iterator[tuple[Any, ...]]:
    """``zip`` with a progress bar over the shortest iterable."""
    if "total" not in kwargs:
        with contextlib.suppress(TypeError):
            kwargs["total"] = min(len(i) for i in iterables)  # type: ignore[arg-type]
    yield from tqdm(zip(*iterables, strict=False), **kwargs)


def tmap(function: Any, *sequences: Iterable[Any], **kwargs: Any) -> Iterator[Any]:
    """``map`` with a progress bar."""
    for args in tzip(*sequences, **kwargs):
        yield function(*args)


class _Wrapped:
    """File-like proxy that advances a bar by the number of bytes read/written."""

    def __init__(self, stream: Any, method: str, bar: tqdm) -> None:
        self._stream, self._method, self._bar = stream, method, bar

    def __getattr__(self, name: str) -> Any:
        return getattr(self._stream, name)

    def __enter__(self) -> _Wrapped:
        return self

    def __exit__(self, *exc: object) -> None:
        self._bar.close()

    def _wrap(self, *args: Any, **kwargs: Any) -> Any:
        data = getattr(self._stream, self._method)(*args, **kwargs)
        self._bar.update(len(data) if self._method != "write" else len(args[0]))
        return data

    def read(self, *args: Any, **kwargs: Any) -> Any:
        return (
            self._wrap(*args, **kwargs)
            if self._method == "read"
            else self._stream.read(*args, **kwargs)
        )

    def write(self, *args: Any, **kwargs: Any) -> Any:
        return (
            self._wrap(*args, **kwargs)
            if self._method == "write"
            else self._stream.write(*args, **kwargs)
        )


def wrapattr(
    stream: Any, method: str = "read", total: float | None = None, **kwargs: Any
) -> _Wrapped:
    """Wrap a file so ``read``/``write`` calls advance a byte-oriented bar (``tqdm.wrapattr``)."""
    if method not in ("read", "write"):
        raise ValueError("method must be 'read' or 'write'")
    kwargs.setdefault("unit", "B")
    kwargs.setdefault("unit_scale", True)
    return _Wrapped(stream, method, tqdm(total=total, **kwargs))


async def _agather(*coros: Any, **kwargs: Any) -> list[Any]:
    import asyncio

    bar = tqdm(total=len(coros), **kwargs)
    try:

        async def one(i: int, c: Any) -> tuple[int, Any]:
            result = await c
            bar.update(1)
            return i, result

        done = await asyncio.gather(*(one(i, c) for i, c in enumerate(coros)))
        return [r for _, r in sorted(done, key=lambda t: t[0])]
    finally:
        bar.close()


class asyncio_tools:
    """Namespace: ``await asyncio_tools.gather(*coros)`` / ``as_completed`` with a bar."""

    gather = staticmethod(_agather)

    @staticmethod
    def as_completed(coros: Iterable[Any], **kwargs: Any) -> Iterator[Any]:
        import asyncio

        coros = list(coros)
        bar = tqdm(total=len(coros), **kwargs)
        try:
            for fut in asyncio.as_completed(coros):
                yield _Tracked(fut, bar)
        finally:
            bar.close()


class _Tracked:
    def __init__(self, awaitable: Any, bar: tqdm) -> None:
        self._aw, self._bar = awaitable, bar

    def __await__(self) -> Any:
        result = yield from self._aw.__await__()
        self._bar.update(1)
        return result


# -- tqdm module-level names ------------------------------------------------------------------

tgrange = trange
tqdm_gui = tqdm
tqdm_gui.__doc__ = "Alias of :class:`tqdm` (there is no GUI window; ``gui=True`` is accepted)."


def tqdm_pandas(tclass: Any, **tqdm_kwargs: Any) -> None:
    """Deprecated tqdm entry point: register pandas ``progress_apply`` using ``tclass``."""
    target: Any = tclass if isinstance(tclass, type) else type(tclass)
    if not isinstance(tclass, type):
        tqdm_kwargs = {**getattr(tclass, "_kwargs", {}), **tqdm_kwargs}
    target.pandas(**tqdm_kwargs)
