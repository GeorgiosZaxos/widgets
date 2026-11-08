"""The reusable frame loop and ``run_app`` helper (FR-RENDER-009..011, FR-LAYOUT-007, FR-INPUT-010).

Each frame: poll input -> deliver events -> resize check -> ``update(dt)`` -> render into a
buffer -> diff -> write. The loop honours ``fps`` and ``duration``, never busy-waits, clamps ``dt``
after stalls, and always closes the widget tree (and restores the terminal if it owns the session)
when anything raises (FR-RENDER-010).
"""

from __future__ import annotations

import contextlib
import logging
import threading
from collections.abc import Callable, Collection
from typing import Any, TextIO

from widgets.base_elements.base import Widget
from widgets.base_elements.effects import Clock, MonotonicClock
from widgets.base_elements.events import (
    CustomEvent,
    Event,
    EventQueue,
    KeyEvent,
    KeyReader,
    PasteEvent,
    ResizeEvent,
)
from widgets.base_elements.interactive import FocusManager
from widgets.base_elements.layout import Screen
from widgets.render.buffer import Buffer
from widgets.render.screen_renderer import ScreenRenderer
from widgets.render.width import DEFAULT_WIDTH_POLICY
from widgets.terminal.session import TerminalMode, TerminalSession

logger = logging.getLogger(__name__)

EventHandler = Callable[[Event], bool | None]


class FrameLoop:
    """Drives a widget tree against a renderer."""

    def __init__(
        self,
        root: Widget,
        *,
        renderer: ScreenRenderer | None = None,
        session: TerminalSession | None = None,
        key_reader: KeyReader | None = None,
        events: EventQueue | None = None,
        focus: FocusManager | None = None,
        size: tuple[int, int] | None = None,
        fps: float = 30.0,
        duration: float | None = None,
        max_dt: float = 0.25,
        clock: Clock | None = None,
        on_event: EventHandler | None = None,
        quit_keys: Collection[str] = (),
        raise_callback_errors: bool = False,
        close_session: bool = False,
    ) -> None:
        if isinstance(fps, bool) or not 1 <= fps <= 240:
            raise ValueError(f"fps must be in 1..240, got {fps!r}")
        if duration is not None and duration < 0:
            raise ValueError(f"duration must be >= 0 or None, got {duration!r}")
        if not max_dt > 0:
            raise ValueError(f"max_dt must be > 0, got {max_dt!r}")
        if renderer is None:
            if session is None:
                raise ValueError("FrameLoop needs a renderer or a session")
            renderer = ScreenRenderer.from_session(session)
        self.root = root
        self.renderer = renderer
        self.session = session
        self.key_reader = key_reader
        self.events = EventQueue() if events is None else events
        self.focus = FocusManager(root) if focus is None else focus
        self.fps = float(fps)
        self.duration = duration
        self.max_dt = max_dt
        self.clock: Clock = MonotonicClock() if clock is None else clock
        self.on_event = on_event
        self.quit_keys = frozenset(quit_keys)
        self.raise_callback_errors = raise_callback_errors
        self.close_session = close_session
        self.frames = 0
        """Number of frames rendered so far."""
        self._size = size
        self._stop = threading.Event()
        self._buffer: Buffer | None = None
        self._policy = DEFAULT_WIDTH_POLICY if session is None else session.width_policy

    # -- control ----------------------------------------------------------------------------

    def stop(self) -> None:
        """Ask the loop to finish after the current frame (safe from any thread)."""
        self._stop.set()

    @property
    def stopped(self) -> bool:
        return self._stop.is_set()

    @property
    def buffer(self) -> Buffer:
        if self._buffer is None:
            raise RuntimeError("the frame loop has not started")
        return self._buffer

    def run(self) -> None:
        """Run until :meth:`stop`, a quit key, or ``duration`` elapsed."""
        self._stop.clear()
        try:
            self._loop()
        except BaseException:
            self._shutdown(suppress=True)
            raise
        else:
            self._shutdown(suppress=False)

    # -- internals -----------------------------------------------------------------------------

    def _terminal_size(self) -> tuple[int, int]:
        if self.session is not None:
            return self.session.get_size()
        return self._size or (80, 24)

    def _loop(self) -> None:
        width, height = self._terminal_size()
        self._buffer = Buffer(width, height, policy=self._policy)
        if isinstance(self.root, Screen) and (self.root.width, self.root.height) != (width, height):
            self.root.resize(width, height)
        self.root.mount()
        self.root.start()
        interval = 1.0 / self.fps
        start = last = self.clock.now()
        while not self._stop.is_set():
            frame_start = self.clock.now()
            if self.duration is not None and frame_start - start >= self.duration:
                break
            dt = min(max(frame_start - last, 0.0), self.max_dt)
            last = frame_start
            self._process_input()
            self._check_resize()
            self.root.tick(dt)
            self._render_frame()
            self.frames += 1
            remaining = frame_start + interval - self.clock.now()
            if remaining > 0:
                self.clock.sleep(remaining)

    def _process_input(self) -> None:
        events: list[Event] = []
        if self.key_reader is not None:
            events.extend(self.key_reader.poll(0.0))
        events.extend(self.events.drain())
        for event in events:
            self._handle_event(event)

    def _handle_event(self, event: Event) -> None:
        if self.on_event is not None:
            try:
                if self.on_event(event):
                    return
            except Exception:
                if self.raise_callback_errors:
                    raise
                logger.exception("on_event callback raised")
        if isinstance(event, KeyEvent):
            if event.combo in self.quit_keys:
                self.stop()
                return
            self.focus.dispatch(event)
        elif isinstance(event, PasteEvent):
            self.focus.dispatch_paste(event.text)
        elif isinstance(event, ResizeEvent):
            self._apply_resize(event.width, event.height)
        elif isinstance(event, CustomEvent):
            pass  # delivered to on_event only

    def _check_resize(self) -> None:
        session = self.session
        if session is None:
            return
        if session.consume_repaint():
            self.renderer.invalidate(clear_screen=True)
        if session.consume_resize():
            width, height = session.get_size()
            self._apply_resize(width, height)

    def _apply_resize(self, width: int, height: int) -> None:
        buffer = self._buffer
        if buffer is not None and (buffer.width, buffer.height) == (width, height):
            return
        self._buffer = Buffer(width, height, policy=self._policy)
        if isinstance(self.root, Screen):
            self.root.resize(width, height)
        self.renderer.invalidate(clear_screen=True)

    def _render_frame(self) -> None:
        buffer = self.buffer
        buffer.clear()
        self.root.draw(buffer)
        self.renderer.render(buffer)

    def _shutdown(self, *, suppress: bool) -> None:
        errors: list[Exception] = []
        for step in (self.root.close, self.renderer.finish):
            try:
                step()
            except Exception as exc:
                logger.exception("error during frame loop shutdown")
                errors.append(exc)
        try:
            if self.key_reader is not None:
                self.key_reader.close()
            if self.close_session and self.session is not None:
                self.session.close()
        except Exception as exc:
            logger.exception("error during frame loop shutdown")
            errors.append(exc)
        if errors and not suppress:
            raise errors[0]


def run_app(
    root: Widget,
    *,
    fps: float = 30.0,
    duration: float | None = None,
    mode: TerminalMode = TerminalMode.FULLSCREEN,
    on_event: EventHandler | None = None,
    quit_keys: Collection[str] = (),
    interactive: bool = True,
    stream: TextIO | None = None,
    input_stream: TextIO | None = None,
    title: str | None = None,
) -> None:
    """Run ``root`` in a terminal session until it is stopped (Ctrl+C also ends the app).

    Terminal state is always restored; keyboard input is only used when stdin is a TTY.
    """
    with TerminalSession(
        mode,
        stream=stream,
        input_stream=input_stream,
        raw_input=interactive,
        title=title,
    ) as session:
        reader = KeyReader(session.open_input()) if session.interactive else None
        loop = FrameLoop(
            root,
            session=session,
            key_reader=reader,
            fps=fps,
            duration=duration,
            on_event=on_event,
            quit_keys=quit_keys,
        )
        with contextlib.suppress(KeyboardInterrupt):
            loop.run()


class WidgetRunner:
    """Convenience: collect widgets, then run them together in one terminal session."""

    def __init__(
        self,
        *,
        fps: float = 30.0,
        duration: float | None = None,
        mode: TerminalMode = TerminalMode.FULLSCREEN,
        quit_keys: Collection[str] = ("q",),
        title: str | None = None,
    ) -> None:
        self.fps, self.duration, self.mode = fps, duration, mode
        self.quit_keys, self.title = quit_keys, title
        self.widgets: list[Widget] = []

    def add(self, widget: Widget) -> Widget:
        """Register a widget (positioned by its own x/y); returns it for chaining."""
        self.widgets.append(widget)
        return widget

    def run(self, **overrides: Any) -> None:
        import shutil

        from widgets.base_elements.layout import Screen

        size = shutil.get_terminal_size((80, 24))
        root = Screen(size.columns, size.lines)
        for widget in self.widgets:
            root.add(widget)
        options: dict[str, Any] = {
            "fps": self.fps,
            "duration": self.duration,
            "mode": self.mode,
            "quit_keys": self.quit_keys,
            "title": self.title,
        }
        options.update(overrides)
        run_app(root, **options)
