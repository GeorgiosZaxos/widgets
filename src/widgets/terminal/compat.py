"""Platform-specific terminal code behind small functions (FR-TERM-005, NFR-PORT-002). Layer L1.

POSIX: ``termios`` / ``select``. Windows: ``ctypes`` console modes and ``msvcrt``.
The Windows branches are not exercised by the Linux test run; they are covered by the CI matrix.
"""

from __future__ import annotations

import os
import sys
import time
from collections.abc import Callable, Mapping
from typing import Any, Protocol

COMPAT_IS_WINDOWS = sys.platform == "win32"


def _env_int(env: Mapping[str, str], name: str) -> int | None:
    try:
        value = int(env.get(name, ""))
    except ValueError:
        return None
    return value if value > 0 else None


def get_terminal_size(stream: Any = None, env: Mapping[str, str] | None = None) -> tuple[int, int]:
    """``(columns, lines)`` of the terminal behind ``stream`` (FR-TERM-004).

    Falls back to the ``COLUMNS`` / ``LINES`` environment variables and then to ``(80, 24)``.
    """
    environment = os.environ if env is None else env
    try:
        size = os.get_terminal_size(stream.fileno())
        if size.columns > 0 and size.lines > 0:
            return (size.columns, size.lines)
    except (AttributeError, OSError, ValueError):
        pass
    return (_env_int(environment, "COLUMNS") or 80, _env_int(environment, "LINES") or 24)


def enable_vt_processing(stream: object | None = None) -> tuple[bool, Callable[[], None] | None]:
    """Enable VT output processing on the Windows console behind ``stream`` (FR-TERM-010).

    Returns ``(ok, restore)``. On POSIX, ``(True, None)``. A stream without a file descriptor
    (in-memory or wrapped streams) has no console mode to change, so it is trusted as-is. For a
    real descriptor ``ok`` is False when it is not a console or the console refuses VT mode;
    ``restore`` puts the previous console mode back. Without ``stream`` the process stdout is used.
    """
    if sys.platform != "win32":
        return True, None
    import ctypes
    from ctypes import wintypes

    if stream is None:
        handle = None
    else:
        fileno = getattr(stream, "fileno", None)
        try:
            fd = fileno() if callable(fileno) else None
        except (OSError, ValueError):  # includes io.UnsupportedOperation
            fd = None
        if fd is None:
            return True, None
        import msvcrt

        try:
            handle = msvcrt.get_osfhandle(fd)
        except OSError:
            return False, None

    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel32.GetStdHandle.restype = wintypes.HANDLE
    kernel32.GetConsoleMode.argtypes = [wintypes.HANDLE, wintypes.LPDWORD]
    kernel32.SetConsoleMode.argtypes = [wintypes.HANDLE, wintypes.DWORD]
    if handle is None:
        handle = kernel32.GetStdHandle(-11)  # STD_OUTPUT_HANDLE
    mode = wintypes.DWORD()
    if not kernel32.GetConsoleMode(handle, ctypes.byref(mode)):
        return False, None
    previous = mode.value
    if not kernel32.SetConsoleMode(handle, previous | 0x0004):  # ENABLE_VIRTUAL_TERMINAL_PROCESSING
        return False, None

    def restore() -> None:
        kernel32.SetConsoleMode(handle, previous)

    return True, restore


def enter_raw_mode(fd: int) -> Callable[[], None]:
    """Put the terminal on ``fd`` into cbreak mode (no echo, unbuffered keys, signals kept).

    Returns a callable restoring the previous mode. ISIG stays enabled so Ctrl+C still raises
    ``KeyboardInterrupt`` and the session can restore the terminal.
    """
    if sys.platform == "win32":
        return lambda: None
    import termios
    import tty

    saved = termios.tcgetattr(fd)
    tty.setcbreak(fd)

    def restore() -> None:
        termios.tcsetattr(fd, termios.TCSADRAIN, saved)

    return restore


class InputSource(Protocol):
    """Byte-oriented keyboard input (the OS-specific half of the key reader, FR-INPUT-004)."""

    def read_bytes(self, timeout: float) -> bytes:
        """Bytes available within ``timeout`` seconds; ``b""`` when none."""
        ...

    def close(self) -> None: ...


class PosixInput:
    """Reads raw bytes from a file descriptor using ``select``."""

    def __init__(self, fd: int) -> None:
        self._fd = fd

    def read_bytes(self, timeout: float) -> bytes:
        import select

        try:
            ready, _, _ = select.select([self._fd], [], [], max(0.0, timeout))
            if not ready:
                return b""
            return os.read(self._fd, 4096)
        except (BlockingIOError, InterruptedError):
            return b""
        except OSError:
            return b""

    def close(self) -> None:
        return None


_WINDOWS_SPECIAL = {
    "H": b"\x1b[A",
    "P": b"\x1b[B",
    "M": b"\x1b[C",
    "K": b"\x1b[D",
    "G": b"\x1b[H",
    "O": b"\x1b[F",
    "I": b"\x1b[5~",
    "Q": b"\x1b[6~",
    "R": b"\x1b[2~",
    "S": b"\x1b[3~",
    ";": b"\x1bOP",
    "<": b"\x1bOQ",
    "=": b"\x1bOR",
    ">": b"\x1bOS",
    "?": b"\x1b[15~",
    "@": b"\x1b[17~",
    "A": b"\x1b[18~",
    "B": b"\x1b[19~",
    "C": b"\x1b[20~",
    "D": b"\x1b[21~",
}


class WindowsInput:
    """Reads console key presses with ``msvcrt`` and re-encodes special keys as ANSI sequences."""

    def read_bytes(self, timeout: float) -> bytes:
        if sys.platform != "win32":  # pragma: no cover
            return b""
        import msvcrt

        deadline = time.monotonic() + max(0.0, timeout)
        while True:
            chunks: list[bytes] = []
            while msvcrt.kbhit():
                char = msvcrt.getwch()
                if char in ("\x00", "\xe0"):
                    chunks.append(_WINDOWS_SPECIAL.get(msvcrt.getwch(), b""))
                else:
                    chunks.append(char.encode("utf-8", errors="replace"))
            if chunks:
                return b"".join(chunks)
            if time.monotonic() >= deadline:
                return b""
            time.sleep(0.005)

    def close(self) -> None:
        return None


def open_input_source(fd: int) -> InputSource:
    """The platform's :class:`InputSource` for the terminal input descriptor ``fd``."""
    if sys.platform == "win32":
        return WindowsInput()
    return PosixInput(fd)
