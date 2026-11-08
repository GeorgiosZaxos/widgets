"""Input events, key decoder, key reader and event queue (FR-INPUT-004, 006, 007, 009, 010). Layer L2.

``KeyDecoder`` turns terminal bytes into :class:`KeyEvent` / :class:`PasteEvent` objects and never
raises: unknown sequences become ``KeyEvent(key="unknown", raw=...)``. ``KeyReader`` combines an
OS-specific :class:`~widgets.terminal.compat.InputSource` with the decoder without ever blocking
longer than the timeout it is given (a lone ESC is resolved by a time-out, not by waiting).
"""

from __future__ import annotations

import queue
from dataclasses import dataclass
from typing import TypeAlias

from widgets.base_elements.effects import Clock, MonotonicClock
from widgets.terminal.compat import InputSource

# ---------------------------------------------------------------------------
# Event types
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class KeyEvent:
    """A normalised key press (FR-INPUT-006).

    ``key`` is a name (``up``, ``enter``, ``f5``, ``space``, ...) or the character itself for
    printable keys. ``char`` is the typed text for printable keys, else ``None``.
    """

    key: str
    char: str | None = None
    ctrl: bool = False
    alt: bool = False
    shift: bool = False
    raw: bytes = b""

    @property
    def combo(self) -> str:
        """Human readable form such as ``"ctrl+x"`` or ``"alt+f"``."""
        parts = [
            name
            for name, on in (("ctrl", self.ctrl), ("alt", self.alt), ("shift", self.shift))
            if on
        ]
        parts.append(self.key)
        return "+".join(parts)


@dataclass(frozen=True, slots=True)
class ResizeEvent:
    width: int
    height: int


@dataclass(frozen=True, slots=True)
class PasteEvent:
    """Text delivered through bracketed paste."""

    text: str


@dataclass(frozen=True, slots=True)
class CustomEvent:
    """Application-defined event posted from any thread through the :class:`EventQueue`."""

    name: str
    payload: object = None


Event: TypeAlias = KeyEvent | ResizeEvent | PasteEvent | CustomEvent


# ---------------------------------------------------------------------------
# Decoder
# ---------------------------------------------------------------------------

_CSI_FINALS = {
    "A": "up",
    "B": "down",
    "C": "right",
    "D": "left",
    "H": "home",
    "F": "end",
    "Z": "backtab",
    "P": "f1",
    "Q": "f2",
    "R": "f3",
    "S": "f4",
}
_SS3_FINALS = {
    "A": "up",
    "B": "down",
    "C": "right",
    "D": "left",
    "H": "home",
    "F": "end",
    "P": "f1",
    "Q": "f2",
    "R": "f3",
    "S": "f4",
}
_TILDE_KEYS = {
    1: "home",
    2: "insert",
    3: "delete",
    4: "end",
    5: "pageup",
    6: "pagedown",
    7: "home",
    8: "end",
    11: "f1",
    12: "f2",
    13: "f3",
    14: "f4",
    15: "f5",
    17: "f6",
    18: "f7",
    19: "f8",
    20: "f9",
    21: "f10",
    23: "f11",
    24: "f12",
}
_PASTE_END = b"\x1b[201~"
_MAX_SEQUENCE = 64


def _unknown(raw: bytes) -> KeyEvent:
    return KeyEvent(key="unknown", raw=raw)


def _ascii_event(byte: int) -> KeyEvent:
    raw = bytes([byte])
    if byte in (0x0D, 0x0A):
        return KeyEvent("enter", raw=raw)
    if byte == 0x09:
        return KeyEvent("tab", raw=raw)
    if byte in (0x7F, 0x08):
        return KeyEvent("backspace", raw=raw)
    if byte == 0x00:
        return KeyEvent("space", ctrl=True, raw=raw)
    if byte == 0x20:
        return KeyEvent("space", char=" ", raw=raw)
    if 0x01 <= byte <= 0x1A:
        return KeyEvent(chr(byte + 96), ctrl=True, raw=raw)
    if 0x1C <= byte <= 0x1F:
        return KeyEvent(chr(byte + 64), ctrl=True, raw=raw)
    if byte == 0x1B:  # pragma: no cover - handled by the escape parser
        return KeyEvent("escape", raw=raw)
    char = chr(byte)
    return KeyEvent(char, char=char, raw=raw)


def _modifiers(code: int | None) -> tuple[bool, bool, bool]:
    """(ctrl, alt, shift) from an xterm modifier parameter (1 + bitmask)."""
    if code is None or code < 1:
        return False, False, False
    bits = code - 1
    return bool(bits & 4), bool(bits & 2), bool(bits & 1)


class KeyDecoder:
    """Incremental decoder from terminal bytes to events."""

    def __init__(self) -> None:
        self._buffer = bytearray()
        self._paste: bytearray | None = None

    @property
    def pending(self) -> bool:
        """True while a partial sequence (or an unfinished paste) is buffered."""
        return bool(self._buffer) or self._paste is not None

    def feed(self, data: bytes) -> list[Event]:
        self._buffer.extend(data)
        return self._drain()

    def flush(self) -> list[Event]:
        """Resolve buffered partial input after a time-out (lone ESC becomes ``escape``)."""
        events: list[Event] = []
        if self._paste is not None:
            self._paste.extend(self._buffer)
            events.append(PasteEvent(self._paste.decode("utf-8", errors="replace")))
            self._paste = None
        elif self._buffer:
            raw = bytes(self._buffer)
            events.append(KeyEvent("escape", raw=raw) if raw == b"\x1b" else _unknown(raw))
        self._buffer.clear()
        return events

    # -- internals ---------------------------------------------------------------------

    def _drain(self) -> list[Event]:
        events: list[Event] = []
        buf = self._buffer
        n = len(buf)
        i = 0
        while i < n:
            if self._paste is not None:
                end = buf.find(_PASTE_END, i)
                if end >= 0:
                    self._paste.extend(buf[i:end])
                    events.append(PasteEvent(self._paste.decode("utf-8", errors="replace")))
                    self._paste = None
                    i = end + len(_PASTE_END)
                    continue
                keep = 0
                for k in range(min(len(_PASTE_END) - 1, n - i), 0, -1):
                    if buf[n - k : n] == _PASTE_END[:k]:
                        keep = k
                        break
                self._paste.extend(buf[i : n - keep])
                i = n - keep
                break
            byte = buf[i]
            if byte == 0x1B:
                parsed = self._parse_escape(buf, i)
                if parsed is None:
                    break
                used, found = parsed
                events.extend(found)
                i += used
            elif byte < 0x80:
                events.append(_ascii_event(byte))
                i += 1
            else:
                need = (
                    2
                    if 0xC2 <= byte <= 0xDF
                    else 3
                    if 0xE0 <= byte <= 0xEF
                    else 4
                    if 0xF0 <= byte <= 0xF4
                    else 0
                )
                if need == 0:
                    events.append(_unknown(bytes([byte])))
                    i += 1
                    continue
                if i + need > n:
                    break
                chunk = bytes(buf[i : i + need])
                try:
                    text = chunk.decode("utf-8")
                except UnicodeDecodeError:
                    events.append(_unknown(bytes([byte])))
                    i += 1
                else:
                    events.append(KeyEvent(text, char=text, raw=chunk))
                    i += need
        del buf[:i]
        return events

    def _parse_escape(self, buf: bytearray, i: int) -> tuple[int, list[Event]] | None:
        n = len(buf)
        if i + 1 >= n:
            return None  # lone ESC: wait for more bytes or a flush
        second = buf[i + 1]
        if second == 0x5B:  # CSI
            j = i + 2
            while j < n and 0x30 <= buf[j] <= 0x3F:
                j += 1
            while j < n and 0x20 <= buf[j] <= 0x2F:
                j += 1
            if j >= n:
                if n - i > _MAX_SEQUENCE:
                    return n - i, [_unknown(bytes(buf[i:n]))]
                return None
            if not 0x40 <= buf[j] <= 0x7E:
                return j - i, [_unknown(bytes(buf[i:j]))]
            return j + 1 - i, self._decode_csi(bytes(buf[i : j + 1]))
        if second == 0x4F:  # SS3
            if i + 2 >= n:
                return None
            raw = bytes(buf[i : i + 3])
            name = _SS3_FINALS.get(chr(buf[i + 2]))
            return 3, [KeyEvent(name, raw=raw) if name else _unknown(raw)]
        if second == 0x1B:
            return 1, [KeyEvent("escape", raw=b"\x1b")]
        if 0x20 <= second <= 0x7E:
            char = chr(second)
            key = "space" if second == 0x20 else char
            return 2, [KeyEvent(key, char=char, alt=True, raw=bytes(buf[i : i + 2]))]
        return 1, [KeyEvent("escape", raw=b"\x1b")]

    def _decode_csi(self, seq: bytes) -> list[Event]:
        final = chr(seq[-1])
        body = seq[2:-1].decode("ascii", errors="replace")
        if final == "~" and body == "200":
            self._paste = bytearray()
            return []
        if final == "~" and body == "201":
            return []
        numbers: list[int | None] = []
        for part in body.split(";"):
            if part == "":
                numbers.append(None)
            elif part.isdigit():
                numbers.append(int(part))
            else:
                return [_unknown(seq)]
        key: str | None
        modifier: int | None = numbers[1] if len(numbers) > 1 else None
        if final == "~":
            key = _TILDE_KEYS.get(numbers[0]) if numbers and numbers[0] is not None else None
        else:
            key = _CSI_FINALS.get(final)
        if key is None:
            return [_unknown(seq)]
        ctrl, alt, shift = _modifiers(modifier)
        return [KeyEvent(key, ctrl=ctrl, alt=alt, shift=shift or key == "backtab", raw=seq)]


# ---------------------------------------------------------------------------
# Reader and queue
# ---------------------------------------------------------------------------


class KeyReader:
    """Non-blocking key reader over an OS-specific input source (FR-INPUT-004/010).

    ``poll`` waits at most ``timeout`` seconds for input. A pending partial sequence is resolved
    on a later poll once ``esc_timeout`` (default 50 ms) elapsed without more bytes.
    """

    def __init__(
        self,
        source: InputSource,
        *,
        esc_timeout: float = 0.05,
        clock: Clock | None = None,
    ) -> None:
        if esc_timeout < 0:
            raise ValueError("esc_timeout must be >= 0")
        self._source = source
        self._esc_timeout = esc_timeout
        self._clock: Clock = MonotonicClock() if clock is None else clock
        self._decoder = KeyDecoder()
        self._pending_since: float | None = None

    def poll(self, timeout: float = 0.0) -> list[Event]:
        data = self._source.read_bytes(timeout)
        events: list[Event] = []
        now = self._clock.now()
        if data:
            events.extend(self._decoder.feed(data))
            self._pending_since = now if self._decoder.pending else None
        elif self._decoder.pending:
            if self._pending_since is None:
                self._pending_since = now
            elif now - self._pending_since >= self._esc_timeout:
                events.extend(self._decoder.flush())
                self._pending_since = None
        return events

    def close(self) -> None:
        self._source.close()


class ScriptedInput:
    """Input source returning pre-recorded chunks (for tests and replays)."""

    def __init__(self, chunks: list[bytes] | None = None) -> None:
        self._chunks = list(chunks or [])
        self.closed = False

    def push(self, chunk: bytes) -> None:
        self._chunks.append(chunk)

    def read_bytes(self, timeout: float) -> bytes:
        return self._chunks.pop(0) if self._chunks else b""

    def close(self) -> None:
        self.closed = True


class EventQueue:
    """Thread-safe bounded queue through which worker threads reach the UI thread (D-04)."""

    def __init__(self, maxsize: int = 10_000) -> None:
        self._queue: queue.Queue[Event] = queue.Queue(maxsize)

    def put(self, event: Event) -> bool:
        """Queue ``event``; returns False (and drops it) when the queue is full."""
        try:
            self._queue.put_nowait(event)
        except queue.Full:
            return False
        return True

    def drain(self, limit: int | None = None) -> list[Event]:
        events: list[Event] = []
        while limit is None or len(events) < limit:
            try:
                events.append(self._queue.get_nowait())
            except queue.Empty:
                break
        return events

    def empty(self) -> bool:
        return self._queue.empty()

    def qsize(self) -> int:
        return self._queue.qsize()
