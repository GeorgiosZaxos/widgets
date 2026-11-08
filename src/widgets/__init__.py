"""widgets - a terminal UI toolkit for Python 3.13.

Public names are loaded lazily (PEP 562): ``import widgets`` imports nothing but this module, so
no optional dependency, widget module or terminal machinery is touched until a name is used
(FR-API-003). Import paths like ``from widgets.render.buffer import Buffer`` work as well.
"""

from __future__ import annotations

import importlib
import logging
from typing import TYPE_CHECKING, Any

__version__ = "1.0.0rc1"

# Libraries must not configure logging; the application decides (ER-006, NFR-MAINT-003).
logging.getLogger(__name__).addHandler(logging.NullHandler())

_EXPORTS: dict[str, tuple[str, ...]] = {
    "widgets.errors": (
        "WidgetsError",
        "LifecycleError",
        "TerminalBusyError",
        "TerminalCapabilityError",
        "MissingDependencyError",
    ),
    "widgets.base_elements.widget_types": (
        "WidgetId",
        "Size",
        "Point",
        "Rect",
        "RGB",
        "Style",
        "Cell",
        "RenderOp",
        "DEFAULT_STYLE",
        "BLANK_CELL",
        "CONTINUATION",
    ),
    "widgets.base_elements.import_helper": ("optional_import", "require_import"),
    "widgets.base_elements.cleanup": ("CleanupManager", "CleanupToken"),
    "widgets.base_elements.color_manager": (
        "ColorMode",
        "Gradient",
        "parse_color",
        "detect_color_mode",
        "style_to_ansi",
        "apply_style",
        "register_palette",
        "get_palette",
        "register_gradient",
        "get_gradient",
    ),
    "widgets.base_elements.effects": (
        "Clock",
        "MonotonicClock",
        "ManualClock",
        "FlashLimiter",
        "ease",
        "make_rng",
        "reduced_motion_enabled",
    ),
    "widgets.base_elements.events": (
        "KeyEvent",
        "ResizeEvent",
        "PasteEvent",
        "CustomEvent",
        "Event",
        "KeyDecoder",
        "KeyReader",
        "EventQueue",
    ),
    "widgets.base_elements.lifecycle": ("LifecycleState",),
    "widgets.base_elements.base": ("Widget",),
    "widgets.base_elements.layout": ("Container", "Screen"),
    "widgets.base_elements.interactive": ("InteractiveWidget", "FocusManager"),
    "widgets.render.width": ("WidthPolicy", "display_width"),
    "widgets.render.sanitize": ("sanitize_text",),
    "widgets.render.buffer": ("Buffer", "BufferView", "Canvas"),
    "widgets.render.diff": ("diff_buffers",),
    "widgets.render.screen_renderer": ("ScreenRenderer",),
    "widgets.render.run": ("FrameLoop", "WidgetRunner", "run_app"),
    "widgets.display.box": ("Box",),
    "widgets.display.spinner": ("Spinner", "SpinnerGroup"),
    "widgets.display.marquee": ("Marquee", "AnimatedText"),
    "widgets.net.rss_ticker": ("RssTicker", "TickerLane"),
    "widgets.display.effects_widgets": ("Neon", "Sign", "MatrixRain"),
    "widgets.display.vprint": ("VerticalPrint",),
    "widgets.display.gauge": ("Gauge",),
    "widgets.display.notify": ("NotificationCenter", "NotificationType"),
    "widgets.display.calendar": ("CalendarWidget", "ClockWidget", "Countdown"),
    "widgets.display.tabs": ("Tabs", "SplitPane"),
    "widgets.display.stepper": ("Stepper", "Sparkline", "Heatmap"),
    "widgets.display.palette": ("CommandPalette", "TimerWidget"),
    "widgets.display.image": ("ImageView", "QrView"),
    "widgets.display.game": ("GridGame",),
    "widgets.data.logview": ("LogViewer",),
    "widgets.data.kanban": ("KanbanBoard", "MarkdownView"),
    "widgets.data.procmon": ("ProcessMonitor",),
    "widgets.audio.scope": ("Oscilloscope",),
    "widgets.assets.borders": ("BorderStyle", "list_border_styles", "get_border_style"),
    "widgets.assets.fonts": (
        "Font",
        "list_fonts",
        "get_font",
        "font_height",
        "render_text",
        "render_vertical",
    ),
    "widgets.assets.registry": ("list_asset_groups", "list_assets"),
    "widgets.assets.bars": ("BarStyle", "list_bar_styles", "get_bar_style"),
    "widgets.assets.spinners": ("SpinnerSpec", "list_spinners", "get_spinner", "spinner_frames"),
    "widgets.progress.state": ("ProgressState",),
    "widgets.progress.indicators": (
        "HorizontalBar",
        "VerticalBar",
        "CircularIndicator",
        "SpinnerIndicator",
    ),
    "widgets.progress.inline": ("ProgressManager",),
    "widgets.progress.tqdm": (
        "tqdm",
        "trange",
        "tqdm_pandas",
        "TqdmWarning",
        "TqdmKeyError",
        "TqdmTypeError",
        "TqdmDeprecationWarning",
        "TqdmExperimentalWarning",
    ),
    "widgets.progress.vertical": ("vtqdm", "vtrange"),
    "widgets.terminal.capabilities": ("Capabilities",),
    "widgets.terminal.session": ("TerminalSession", "TerminalMode", "OutputGate"),
}

_LAZY: dict[str, str] = {name: module for module, names in _EXPORTS.items() for name in names}

__all__ = ["__version__", *sorted(_LAZY)]


def __getattr__(name: str) -> Any:
    module_name = _LAZY.get(name)
    if module_name is None:
        raise AttributeError(f"module 'widgets' has no attribute {name!r}")
    value = getattr(importlib.import_module(module_name), name)
    globals()[name] = value  # cache for subsequent lookups
    return value


def __dir__() -> list[str]:
    return sorted({*globals(), *__all__})


if TYPE_CHECKING:  # static analysis / IDE completion only; never executed at runtime
    from widgets.assets.bars import BarStyle as BarStyle
    from widgets.assets.bars import get_bar_style as get_bar_style
    from widgets.assets.bars import list_bar_styles as list_bar_styles
    from widgets.assets.borders import BorderStyle as BorderStyle
    from widgets.assets.borders import get_border_style as get_border_style
    from widgets.assets.borders import list_border_styles as list_border_styles
    from widgets.assets.fonts import Font as Font
    from widgets.assets.fonts import font_height as font_height
    from widgets.assets.fonts import get_font as get_font
    from widgets.assets.fonts import list_fonts as list_fonts
    from widgets.assets.fonts import render_text as render_text
    from widgets.assets.fonts import render_vertical as render_vertical
    from widgets.assets.registry import list_asset_groups as list_asset_groups
    from widgets.assets.registry import list_assets as list_assets
    from widgets.assets.spinners import SpinnerSpec as SpinnerSpec
    from widgets.assets.spinners import get_spinner as get_spinner
    from widgets.assets.spinners import list_spinners as list_spinners
    from widgets.assets.spinners import spinner_frames as spinner_frames
    from widgets.audio.scope import Oscilloscope as Oscilloscope
    from widgets.base_elements.base import Widget as Widget
    from widgets.base_elements.cleanup import CleanupManager as CleanupManager
    from widgets.base_elements.cleanup import CleanupToken as CleanupToken
    from widgets.base_elements.color_manager import ColorMode as ColorMode
    from widgets.base_elements.color_manager import Gradient as Gradient
    from widgets.base_elements.color_manager import apply_style as apply_style
    from widgets.base_elements.color_manager import detect_color_mode as detect_color_mode
    from widgets.base_elements.color_manager import get_gradient as get_gradient
    from widgets.base_elements.color_manager import get_palette as get_palette
    from widgets.base_elements.color_manager import parse_color as parse_color
    from widgets.base_elements.color_manager import register_gradient as register_gradient
    from widgets.base_elements.color_manager import register_palette as register_palette
    from widgets.base_elements.color_manager import style_to_ansi as style_to_ansi
    from widgets.base_elements.effects import Clock as Clock
    from widgets.base_elements.effects import FlashLimiter as FlashLimiter
    from widgets.base_elements.effects import ManualClock as ManualClock
    from widgets.base_elements.effects import MonotonicClock as MonotonicClock
    from widgets.base_elements.effects import ease as ease
    from widgets.base_elements.effects import make_rng as make_rng
    from widgets.base_elements.effects import reduced_motion_enabled as reduced_motion_enabled
    from widgets.base_elements.events import CustomEvent as CustomEvent
    from widgets.base_elements.events import Event as Event
    from widgets.base_elements.events import EventQueue as EventQueue
    from widgets.base_elements.events import KeyDecoder as KeyDecoder
    from widgets.base_elements.events import KeyEvent as KeyEvent
    from widgets.base_elements.events import KeyReader as KeyReader
    from widgets.base_elements.events import PasteEvent as PasteEvent
    from widgets.base_elements.events import ResizeEvent as ResizeEvent
    from widgets.base_elements.import_helper import optional_import as optional_import
    from widgets.base_elements.import_helper import require_import as require_import
    from widgets.base_elements.interactive import FocusManager as FocusManager
    from widgets.base_elements.interactive import InteractiveWidget as InteractiveWidget
    from widgets.base_elements.layout import Container as Container
    from widgets.base_elements.layout import Screen as Screen
    from widgets.base_elements.lifecycle import LifecycleState as LifecycleState
    from widgets.base_elements.widget_types import BLANK_CELL as BLANK_CELL
    from widgets.base_elements.widget_types import CONTINUATION as CONTINUATION
    from widgets.base_elements.widget_types import DEFAULT_STYLE as DEFAULT_STYLE
    from widgets.base_elements.widget_types import RGB as RGB
    from widgets.base_elements.widget_types import Cell as Cell
    from widgets.base_elements.widget_types import Point as Point
    from widgets.base_elements.widget_types import Rect as Rect
    from widgets.base_elements.widget_types import RenderOp as RenderOp
    from widgets.base_elements.widget_types import Size as Size
    from widgets.base_elements.widget_types import Style as Style
    from widgets.base_elements.widget_types import WidgetId as WidgetId
    from widgets.data.kanban import KanbanBoard as KanbanBoard
    from widgets.data.kanban import MarkdownView as MarkdownView
    from widgets.data.logview import LogViewer as LogViewer
    from widgets.data.procmon import ProcessMonitor as ProcessMonitor
    from widgets.display.box import Box as Box
    from widgets.display.calendar import CalendarWidget as CalendarWidget
    from widgets.display.calendar import ClockWidget as ClockWidget
    from widgets.display.calendar import Countdown as Countdown
    from widgets.display.effects_widgets import MatrixRain as MatrixRain
    from widgets.display.effects_widgets import Neon as Neon
    from widgets.display.effects_widgets import Sign as Sign
    from widgets.display.game import GridGame as GridGame
    from widgets.display.gauge import Gauge as Gauge
    from widgets.display.image import ImageView as ImageView
    from widgets.display.image import QrView as QrView
    from widgets.display.marquee import AnimatedText as AnimatedText
    from widgets.display.marquee import Marquee as Marquee
    from widgets.display.notify import NotificationCenter as NotificationCenter
    from widgets.display.notify import NotificationType as NotificationType
    from widgets.display.palette import CommandPalette as CommandPalette
    from widgets.display.palette import TimerWidget as TimerWidget
    from widgets.display.spinner import Spinner as Spinner
    from widgets.display.spinner import SpinnerGroup as SpinnerGroup
    from widgets.display.stepper import Heatmap as Heatmap
    from widgets.display.stepper import Sparkline as Sparkline
    from widgets.display.stepper import Stepper as Stepper
    from widgets.display.tabs import SplitPane as SplitPane
    from widgets.display.tabs import Tabs as Tabs
    from widgets.display.vprint import VerticalPrint as VerticalPrint
    from widgets.errors import LifecycleError as LifecycleError
    from widgets.errors import MissingDependencyError as MissingDependencyError
    from widgets.errors import TerminalBusyError as TerminalBusyError
    from widgets.errors import TerminalCapabilityError as TerminalCapabilityError
    from widgets.errors import WidgetsError as WidgetsError
    from widgets.net.rss_ticker import RssTicker as RssTicker
    from widgets.net.rss_ticker import TickerLane as TickerLane
    from widgets.progress.indicators import CircularIndicator as CircularIndicator
    from widgets.progress.indicators import HorizontalBar as HorizontalBar
    from widgets.progress.indicators import SpinnerIndicator as SpinnerIndicator
    from widgets.progress.indicators import VerticalBar as VerticalBar
    from widgets.progress.inline import ProgressManager as ProgressManager
    from widgets.progress.state import ProgressState as ProgressState
    from widgets.progress.tqdm import TqdmDeprecationWarning as TqdmDeprecationWarning
    from widgets.progress.tqdm import TqdmExperimentalWarning as TqdmExperimentalWarning
    from widgets.progress.tqdm import TqdmKeyError as TqdmKeyError
    from widgets.progress.tqdm import TqdmTypeError as TqdmTypeError
    from widgets.progress.tqdm import TqdmWarning as TqdmWarning
    from widgets.progress.tqdm import tqdm as tqdm
    from widgets.progress.tqdm import tqdm_pandas as tqdm_pandas
    from widgets.progress.tqdm import trange as trange
    from widgets.progress.vertical import vtqdm as vtqdm
    from widgets.progress.vertical import vtrange as vtrange
    from widgets.render.buffer import Buffer as Buffer
    from widgets.render.buffer import BufferView as BufferView
    from widgets.render.buffer import Canvas as Canvas
    from widgets.render.diff import diff_buffers as diff_buffers
    from widgets.render.run import FrameLoop as FrameLoop
    from widgets.render.run import WidgetRunner as WidgetRunner
    from widgets.render.run import run_app as run_app
    from widgets.render.sanitize import sanitize_text as sanitize_text
    from widgets.render.screen_renderer import ScreenRenderer as ScreenRenderer
    from widgets.render.width import WidthPolicy as WidthPolicy
    from widgets.render.width import display_width as display_width
    from widgets.terminal.capabilities import Capabilities as Capabilities
    from widgets.terminal.session import OutputGate as OutputGate
    from widgets.terminal.session import TerminalMode as TerminalMode
    from widgets.terminal.session import TerminalSession as TerminalSession
