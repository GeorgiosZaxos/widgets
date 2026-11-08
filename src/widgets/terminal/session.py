"""Terminal ownership, output gate and restoration (FR-TERM-001..012, FR-CLEAN-008). Layer L1.

A :class:`TerminalSession` owns one output stream for its lifetime (decision D-01). Two sessions on
the same stream raise :class:`~widgets.errors.TerminalBusyError`. Everything the session changes
(alternate screen, cursor visibility, autowrap, bracketed paste, title, input mode, console mode,
signal handlers) is restored in reverse order on normal exit, exceptions, ``KeyboardInterrupt``,
``SIGTERM`` / ``SIGHUP`` (POSIX), at interpreter exit, and around ``SIGTSTP`` / ``SIGCONT``.

All output flows through :class:`OutputGate`, which serialises writes from different threads.
"""

from __future__ import annotations

import atexit
import dataclasses
import enum
import logging
import os
import signal
import sys
import threading
from collections.abc import Callable, Iterator, Mapping
from contextlib import contextmanager
from types import FrameType
from typing import Any, TextIO

from widgets.base_elements.cleanup import CleanupManager
from widgets.base_elements.color_manager import ColorMode
from widgets.errors import LifecycleError, TerminalBusyError, TerminalCapabilityError
from widgets.render.width import WidthPolicy
from widgets.terminal import ansi
from widgets.terminal.capabilities import Capabilities, detect_capabilities, stream_is_tty
from widgets.terminal.compat import (
    InputSource,
    enable_vt_processing,
    enter_raw_mode,
    get_terminal_size,
    open_input_source,
)

logger = logging.getLogger(__name__)


class TerminalMode(enum.Enum):
    """``INLINE`` keeps output in scrollback; ``FULLSCREEN`` uses the alternate screen."""

    INLINE = "inline"
    FULLSCREEN = "fullscreen"


class OutputGate:
    """Serialises writes to one stream so sequences from different threads never interleave."""

    def __init__(self, stream: TextIO) -> None:
        self._stream = stream
        self._lock = threading.RLock()

    @property
    def stream(self) -> TextIO:
        return self._stream

    def write(self, data: str) -> None:
        with self._lock:
            self._stream.write(data)

    def flush(self) -> None:
        with self._lock:
            self._stream.flush()

    def write_flush(self, data: str) -> None:
        with self._lock:
            self._stream.write(data)
            self._stream.flush()

    @contextmanager
    def locked(self) -> Iterator[None]:
        """Hold the gate for several writes that must not be interleaved."""
        with self._lock:
            yield


_OWNERS: dict[int, TerminalSession] = {}
_OWNERS_LOCK = threading.Lock()

_SignalHandler = Callable[[int, FrameType | None], Any] | int | signal.Handlers | None


class TerminalSession:
    """Owns a terminal output stream (and optionally raw keyboard input)."""

    def __init__(
        self,
        mode: TerminalMode = TerminalMode.FULLSCREEN,
        *,
        stream: TextIO | None = None,
        input_stream: TextIO | None = None,
        raw_input: bool = False,
        env: Mapping[str, str] | None = None,
        color_mode: ColorMode | None = None,
        ascii_only: bool = False,
        force_ansi: bool | None = None,
        reduced_motion: bool | None = None,
        ambiguous_width: int = 1,
        use_wcwidth: bool = False,
        title: str | None = None,
        bracketed_paste: bool = False,
        handle_signals: bool = True,
        use_atexit: bool = True,
        strict_vt: bool = False,
    ) -> None:
        self.mode = mode
        self.cleanup = CleanupManager("terminal-session")
        self._stream: TextIO = sys.stdout if stream is None else stream
        self._input_stream: TextIO = sys.stdin if input_stream is None else input_stream
        self._raw_input = raw_input
        self._env: Mapping[str, str] = os.environ if env is None else env
        self._color_override = color_mode
        self._ascii_only = ascii_only
        self._force_ansi = force_ansi
        self._reduced_motion_override = reduced_motion
        self._width_policy = WidthPolicy(ambiguous=ambiguous_width, use_wcwidth=use_wcwidth)
        self._title = title
        self._bracketed_paste = bracketed_paste
        self._handle_signals = handle_signals
        self._use_atexit = use_atexit
        self._strict_vt = strict_vt

        self.output = OutputGate(self._stream)
        self._capabilities: Capabilities | None = None
        self._started = False
        self._closed = False
        self._interactive = False
        self._raw_fd: int | None = None
        self._raw_restore: Callable[[], None] | None = None
        self._applied: list[tuple[str, str]] = []
        self._terminal_active = False
        self._suspended = False
        self._saved_handlers: dict[int, _SignalHandler] = {}
        self._installed_signals: set[int] = set()
        self._resize_flag = False
        self._repaint_flag = False
        self._last_size: tuple[int, int] | None = None

    # -- properties -------------------------------------------------------------

    @property
    def stream(self) -> TextIO:
        return self._stream

    @property
    def started(self) -> bool:
        return self._started

    @property
    def closed(self) -> bool:
        return self._closed

    @property
    def capabilities(self) -> Capabilities:
        if self._capabilities is None:
            raise LifecycleError("terminal session has not been started")
        return self._capabilities

    @property
    def interactive(self) -> bool:
        """True once raw keyboard input is active."""
        return self._interactive

    @property
    def width_policy(self) -> WidthPolicy:
        return self._width_policy

    @property
    def autowrap_disabled(self) -> bool:
        """Whether the session turned autowrap off (so the last cell can be written safely)."""
        return self._terminal_active and self.mode is TerminalMode.FULLSCREEN

    @property
    def reduced_motion(self) -> bool:
        """Reduced-motion preference (FR-FX-006): explicit option or ``WIDGETS_REDUCED_MOTION=1``."""
        if self._reduced_motion_override is not None:
            return self._reduced_motion_override
        return self._env.get("WIDGETS_REDUCED_MOTION") == "1"

    @property
    def use_ascii(self) -> bool:
        """Whether widgets should pick ASCII fallback glyphs (FR-ASSET-009)."""
        return not self.capabilities.unicode

    # -- output helpers ---------------------------------------------------------------

    def write(self, data: str) -> None:
        self.output.write(data)

    def flush(self) -> None:
        self.output.flush()

    def get_size(self) -> tuple[int, int]:
        """``(columns, lines)``; falls back to ``COLUMNS``/``LINES`` then ``(80, 24)``."""
        return get_terminal_size(self._stream, self._env)

    def consume_resize(self) -> bool:
        """True if the terminal size changed since the last call (SIGWINCH or polling)."""
        changed = self._resize_flag
        self._resize_flag = False
        size = self.get_size()
        if size != self._last_size:
            self._last_size = size
            changed = True
        return changed

    def consume_repaint(self) -> bool:
        """True after the session was resumed from suspension (a full repaint is required)."""
        needed = self._repaint_flag
        self._repaint_flag = False
        return needed

    def open_input(self) -> InputSource:
        """Platform input source; raises when keyboard input is not available (FR-INPUT-011)."""
        if not self._interactive or self._raw_fd is None:
            raise TerminalCapabilityError(
                "keyboard input requires an interactive terminal "
                "(create the session with raw_input=True and run it on a TTY)"
            )
        return open_input_source(self._raw_fd)

    # -- lifecycle --------------------------------------------------------------------

    def start(self) -> TerminalSession:
        if self._closed:
            raise LifecycleError("terminal session is already closed")
        if self._started:
            return self
        self._acquire()
        self._started = True
        try:
            self._setup()
        except BaseException:
            self.close()
            raise
        if self._use_atexit:
            atexit.register(self.close)
        return self

    def close(self) -> None:
        """Restore the terminal and release the stream. Idempotent."""
        if self._closed:
            return
        self._closed = True
        try:
            self.cleanup.cleanup()
        finally:
            if self._use_atexit:
                atexit.unregister(self.close)

    def __enter__(self) -> TerminalSession:
        return self.start()

    def __exit__(self, *exc_info: object) -> None:
        self.close()

    # -- internals ----------------------------------------------------------------------

    def _acquire(self) -> None:
        key = id(self._stream)
        with _OWNERS_LOCK:
            owner = _OWNERS.get(key)
            if owner is not None and owner is not self:
                raise TerminalBusyError("the output stream is already owned by another session")
            _OWNERS[key] = self
        self.cleanup.register(self._release)  # registered first => runs last

    def _release(self) -> None:
        with _OWNERS_LOCK:
            if _OWNERS.get(id(self._stream)) is self:
                del _OWNERS[id(self._stream)]

    def _setup(self) -> None:
        caps = detect_capabilities(
            self._stream,
            env=self._env,
            color_override=self._color_override,
            ascii_only=self._ascii_only,
            force_ansi=self._force_ansi,
        )
        if sys.platform == "win32" and caps.is_tty:
            ok, restore = enable_vt_processing(self._stream)
            if restore is not None:
                self.cleanup.register(restore)
            if not ok:
                if self._strict_vt:
                    raise TerminalCapabilityError("the console does not support VT processing")
                caps = dataclasses.replace(caps, ansi=False, color_mode=ColorMode.NONE)
        self._capabilities = caps
        self._last_size = self.get_size()

        if self._handle_signals and caps.ansi:
            self._install_signals()
        if self._raw_input and stream_is_tty(self._input_stream):
            self._enter_raw()
        if caps.ansi:
            self._plan_terminal_state()
            self.cleanup.register(self._write_restore)

    def _plan_terminal_state(self) -> None:
        if self._title:
            self._applied.append((ansi.PUSH_TITLE + ansi.set_title(self._title), ansi.POP_TITLE))
        if self.mode is TerminalMode.FULLSCREEN:
            self._applied.append(
                (
                    ansi.ENTER_ALT_SCREEN
                    + ansi.HIDE_CURSOR
                    + ansi.AUTOWRAP_OFF
                    + ansi.CLEAR_SCREEN
                    + ansi.HOME,
                    ansi.AUTOWRAP_ON + ansi.SHOW_CURSOR + ansi.EXIT_ALT_SCREEN,
                )
            )
        if self._bracketed_paste and self._interactive:
            self._applied.append((ansi.BRACKETED_PASTE_ON, ansi.BRACKETED_PASTE_OFF))
        self._write_setup()

    def _write_setup(self) -> None:
        text = ansi.SGR_RESET + "".join(setup for setup, _ in self._applied)
        self._terminal_active = True
        self._safe_write(text)

    def _write_restore(self) -> None:
        if not self._terminal_active:
            return
        self._terminal_active = False
        text = "".join(restore for _, restore in reversed(self._applied))
        self._safe_write(text + ansi.SGR_RESET)

    def _safe_write(self, text: str) -> None:
        try:
            self.output.write_flush(text)
        except (OSError, ValueError):  # stream gone (closed pipe / file): nothing left to restore
            logger.debug("could not write terminal sequences", exc_info=True)

    def _enter_raw(self) -> None:
        fd = self._input_stream.fileno()
        self._raw_restore = enter_raw_mode(fd)
        self._raw_fd = fd
        self._interactive = True
        self.cleanup.register(self._leave_raw)

    def _leave_raw(self) -> None:
        restore, self._raw_restore = self._raw_restore, None
        if restore is not None:
            try:
                restore()
            except OSError:
                logger.debug("could not restore input mode", exc_info=True)
        self._interactive = False

    # -- signals ------------------------------------------------------------------------

    def _install_signals(self) -> None:
        if threading.current_thread() is not threading.main_thread():
            return
        wanted: tuple[tuple[str, Callable[[int, FrameType | None], None]], ...] = (
            ("SIGTERM", self._on_terminate),
            ("SIGHUP", self._on_terminate),
            ("SIGTSTP", self._on_stop),
            ("SIGCONT", self._on_continue),
            ("SIGWINCH", self._on_winch),
        )
        for name, handler in wanted:
            number = getattr(signal, name, None)
            if number is None:
                continue
            try:
                self._saved_handlers[number] = signal.signal(number, handler)
            except (ValueError, OSError):
                continue
            self._installed_signals.add(number)
        self.cleanup.register(self._uninstall_signals)

    def _uninstall_signals(self) -> None:
        for number in sorted(self._installed_signals):
            previous = self._saved_handlers.get(number)
            try:
                signal.signal(number, signal.SIG_DFL if previous is None else previous)
            except (ValueError, OSError):
                logger.debug("could not restore signal handler %s", number, exc_info=True)
        self._installed_signals.clear()

    def _on_terminate(self, signum: int, frame: FrameType | None) -> None:
        previous = self._saved_handlers.get(signum)
        self.close()  # restores the terminal and the previous handlers
        if callable(previous):
            previous(signum, frame)
        elif previous in (signal.SIG_DFL, None):
            os.kill(os.getpid(), signum)  # default action (terminate) now that we are restored

    def _on_stop(self, signum: int, frame: FrameType | None) -> None:
        self._suspend()
        signal.signal(signum, signal.SIG_DFL)
        os.kill(os.getpid(), signum)  # really stops; execution continues after SIGCONT
        signal.signal(signum, self._on_stop)
        self._resume()

    def _on_continue(self, signum: int, frame: FrameType | None) -> None:
        self._resume()

    def _on_winch(self, signum: int, frame: FrameType | None) -> None:
        self._resize_flag = True

    def _suspend(self) -> None:
        if self._suspended or self._closed:
            return
        self._suspended = True
        self._write_restore()
        if self._raw_restore is not None:
            self._raw_restore()

    def _resume(self) -> None:
        if not self._suspended or self._closed:
            return
        self._suspended = False
        if self._raw_fd is not None:
            self._raw_restore = enter_raw_mode(self._raw_fd)
        if self._applied:
            self._write_setup()
        self._repaint_flag = True
        self._resize_flag = True
