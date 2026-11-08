"""RSS 2.0 / Atom reader (FR-RSS-001..010). Layer L3."""

from __future__ import annotations

import datetime as dt
import email.utils
import functools
import html
import re
import xml.etree.ElementTree as ET
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field

from widgets.base_elements.events import KeyEvent
from widgets.base_elements.interactive import InteractiveWidget
from widgets.base_elements.widget_types import DEFAULT_STYLE, RGB, Rect, Style, WidgetId
from widgets.display._common import clip_cells
from widgets.display.box import Box
from widgets.display.marquee import Marquee
from widgets.errors import FeedConnectionError, FeedError, FeedParseError
from widgets.net._jobs import Jobs
from widgets.net.http import DEFAULT_MAX_BYTES, HttpTransport, UrllibTransport, validate_url
from widgets.render.buffer import Canvas
from widgets.render.sanitize import sanitize_text

_TAG = re.compile(r"<[^>]*>")
_ATOM = "{http://www.w3.org/2005/Atom}"


def clean_text(raw: str | None) -> str:
    """Untrusted feed text -> plain, control-free single line (FR-RSS-010, FR-SAN-001)."""
    if not raw:
        return ""
    text = html.unescape(_TAG.sub(" ", raw))
    text = html.unescape(text)  # double-encoded entities
    return " ".join(sanitize_text(text, newlines="space").split())


@dataclass(frozen=True, slots=True)
class FeedItem:
    title: str
    link: str = ""
    summary: str = ""
    published: dt.datetime | None = None


@dataclass(frozen=True, slots=True)
class FeedSource:
    name: str
    url: str
    category: str = "General"


@dataclass(slots=True)
class FeedState:
    source: FeedSource
    items: list[FeedItem] = field(default_factory=list)
    error: FeedError | None = None
    stale: bool = False
    loading: bool = False
    etag: str | None = None
    last_modified: str | None = None
    last_fetch: float | None = None
    title: str = ""


def _parse_date(text: str | None) -> dt.datetime | None:
    if not text:
        return None
    try:
        return email.utils.parsedate_to_datetime(text.strip())
    except (TypeError, ValueError):
        pass
    try:
        return dt.datetime.fromisoformat(text.strip().replace("Z", "+00:00"))
    except ValueError:
        return None


def parse_feed(body: bytes, *, max_items: int = 100) -> tuple[str, list[FeedItem]]:
    """Parse RSS 2.0 or Atom. DOCTYPE/ENTITY declarations are rejected before parsing."""
    head = body.lower()
    if b"<!doctype" in head or b"<!entity" in head:
        raise FeedParseError("feed contains a DOCTYPE or ENTITY declaration")
    try:
        root = ET.fromstring(body)
    except ET.ParseError as exc:
        raise FeedParseError(f"malformed XML: {exc}") from exc
    items: list[FeedItem] = []
    if root.tag == "rss" or root.find("channel") is not None:
        channel = root.find("channel")
        if channel is None:
            raise FeedParseError("RSS document without <channel>")
        title = clean_text(channel.findtext("title"))
        for el in channel.findall("item")[:max_items]:
            items.append(
                FeedItem(
                    clean_text(el.findtext("title")) or "(untitled)",
                    clean_text(el.findtext("link")),
                    clean_text(el.findtext("description")),
                    _parse_date(el.findtext("pubDate")),
                )
            )
    elif root.tag == f"{_ATOM}feed":
        title = clean_text(root.findtext(f"{_ATOM}title"))
        for el in root.findall(f"{_ATOM}entry")[:max_items]:
            link = ""
            for ln in el.findall(f"{_ATOM}link"):
                if ln.get("rel", "alternate") == "alternate":
                    link = ln.get("href", "")
                    break
            summary = el.findtext(f"{_ATOM}summary") or el.findtext(f"{_ATOM}content")
            items.append(
                FeedItem(
                    clean_text(el.findtext(f"{_ATOM}title")) or "(untitled)",
                    clean_text(link),
                    clean_text(summary),
                    _parse_date(el.findtext(f"{_ATOM}published") or el.findtext(f"{_ATOM}updated")),
                )
            )
    else:
        raise FeedParseError(f"not an RSS or Atom document (root element {root.tag!r})")
    return title, items


class RssReader(InteractiveWidget):
    """Feeds grouped by category; list, marquee or box presentation."""

    def __init__(
        self,
        x: int = 0,
        y: int = 0,
        width: int = 70,
        height: int = 16,
        *,
        sources: Sequence[FeedSource] = (),
        transport: HttpTransport | None = None,
        view: str = "list",
        max_response_bytes: int = DEFAULT_MAX_BYTES,
        max_items_per_feed: int = 100,
        min_refresh_interval: float = 60.0,
        timeout: float = 10.0,
        allowed_schemes: Sequence[str] = ("http", "https"),
        clock: Callable[[], float] | None = None,
        on_update: Callable[[FeedSource, list[FeedItem]], object] | None = None,
        on_error: Callable[[FeedSource, FeedError], object] | None = None,
        on_select: Callable[[FeedItem], object] | None = None,
        ascii_only: bool = False,
        name: WidgetId | None = None,
    ) -> None:
        super().__init__(x, y, width, height, name=name)
        if view not in ("list", "marquee", "box"):
            raise ValueError("view must be list, marquee or box")
        if min_refresh_interval < 0 or max_items_per_feed < 1 or max_response_bytes < 1:
            raise ValueError("invalid limits")
        import time

        self._clock = clock or time.monotonic
        self.transport = transport or UrllibTransport()
        self.view, self.timeout, self.ascii_only = view, timeout, ascii_only
        self.max_response_bytes, self.max_items_per_feed = max_response_bytes, max_items_per_feed
        self.min_refresh_interval, self.allowed_schemes = (
            min_refresh_interval,
            tuple(allowed_schemes),
        )
        self.on_update, self.on_error, self.on_select = on_update, on_error, on_select
        self.feeds: list[FeedState] = []
        self.feed_index = 0
        self.item_index = 0
        self.top = 0
        self._jobs = Jobs()
        self._marquee = Marquee(0, 0, width, 1, speed=10.0)
        self._box = Box(0, 0, width, height, border="single", overflow="wrap")
        for s in sources:
            self.add_source(s)

    # -- sources ---------------------------------------------------------------------------
    def add_source(self, source: FeedSource) -> None:
        self.feeds.append(FeedState(source))
        self.feeds.sort(key=lambda f: (f.source.category.casefold(), f.source.name.casefold()))

    @property
    def categories(self) -> list[str]:
        return sorted({f.source.category for f in self.feeds}, key=str.casefold)

    @property
    def current(self) -> FeedState | None:
        return self.feeds[self.feed_index] if self.feeds else None

    @property
    def items(self) -> list[FeedItem]:
        return self.current.items if self.current else []

    # -- refresh (off the UI thread) ---------------------------------------------------------------------------
    def refresh(self, *, force: bool = False) -> int:
        """Start fetching every feed that is due; returns how many fetches were started."""
        started = 0
        now = self._clock()
        for state in self.feeds:
            if state.loading:
                continue
            if (
                not force
                and state.last_fetch is not None
                and now - state.last_fetch < self.min_refresh_interval
            ):
                continue
            state.loading = True
            state.last_fetch = now
            headers = {}
            if state.etag:
                headers["If-None-Match"] = state.etag
            if state.last_modified:
                headers["If-Modified-Since"] = state.last_modified
            self._jobs.submit(
                functools.partial(self._fetch, state, headers),
                functools.partial(self._finish_for, state),
            )
            started += 1
        return started

    def _fetch(self, state: FeedState, headers: dict[str, str]) -> object:
        try:
            validate_url(state.source.url, self.allowed_schemes)
        except ValueError as exc:
            raise FeedConnectionError(str(exc)) from exc
        resp = self.transport.get(
            state.source.url,
            headers=headers,
            timeout=self.timeout,
            max_bytes=self.max_response_bytes,
        )
        if resp.status == 304:
            return None
        if len(resp.body) > self.max_response_bytes:
            raise FeedConnectionError(f"response larger than {self.max_response_bytes} bytes")
        title, items = parse_feed(resp.body, max_items=self.max_items_per_feed)
        return title, items, resp.headers.get("etag"), resp.headers.get("last-modified")

    def _finish_for(self, state: FeedState, value: object, error: BaseException | None) -> None:
        self._finish(state, value, error)

    def _finish(self, state: FeedState, value: object, error: BaseException | None) -> None:
        state.loading = False
        if error is not None:
            err = error if isinstance(error, FeedError) else FeedConnectionError(str(error))
            state.error, state.stale = err, bool(state.items)
            self.invoke_callback(self.on_error, state.source, err)
            return
        state.error, state.stale = None, False
        if value is not None:
            parsed: tuple[str, list[FeedItem], str | None, str | None] = value  # type: ignore[assignment]
            state.title, state.items, state.etag, state.last_modified = parsed
            self.invoke_callback(self.on_update, state.source, list(state.items))

    def update(self, dt_: float) -> None:
        self._jobs.drain()
        if self.view == "marquee":
            self._marquee.update(dt_)

    def on_close(self) -> None:
        self._jobs.close()

    # -- presentation control (FR-RSS-004) ---------------------------------------------------------------------------
    def set_speed(self, speed: float) -> None:
        self._marquee.set_speed(speed)

    def set_direction(self, direction: str) -> None:
        if direction not in ("left", "right"):
            raise ValueError("direction must be left or right")
        self._marquee.direction = direction

    def _clamp(self) -> None:
        self.item_index = max(0, min(len(self.items) - 1, self.item_index)) if self.items else 0
        body = max(1, self.height - 2)
        if self.item_index < self.top:
            self.top = self.item_index
        elif self.item_index >= self.top + body:
            self.top = self.item_index - body + 1

    def page(self, delta: int) -> None:
        self.item_index += delta * max(1, self.height - 3)
        self._clamp()

    def handle_key(self, event: KeyEvent) -> bool:
        if not self.effective_enabled:
            return False
        key = event.key
        if key == "up":
            self.item_index -= 1
        elif key == "down":
            self.item_index += 1
        elif key == "pageup":
            self.page(-1)
        elif key == "pagedown":
            self.page(1)
        elif key == "tab" or key == "]":
            self.feed_index = (self.feed_index + 1) % max(1, len(self.feeds))
            self.item_index = self.top = 0
        elif key == "backtab" or key == "[":
            self.feed_index = (self.feed_index - 1) % max(1, len(self.feeds))
            self.item_index = self.top = 0
        elif key == "enter" and self.items:
            self.invoke_callback(self.on_select, self.items[self.item_index])
        elif key == "r":
            self.refresh(force=True)
        else:
            return False
        self._clamp()
        return True

    def status_text(self) -> str:
        state = self.current
        if state is None:
            return "no feeds"
        if state.loading:
            return "loading…"
        if state.error is not None:
            return f"error: {state.error}" + (" (showing stale items)" if state.stale else "")
        return f"{len(state.items)} items"

    def render(self, canvas: Canvas) -> None:
        self._clamp()
        state = self.current
        w, h = canvas.width, canvas.height
        if state is None:
            canvas.write_text(0, 0, "No feeds configured", Style(dim=True))
            return
        head = f"{state.source.category} / {state.source.name}"
        if state.stale:
            head += "  [stale]"
        canvas.write_text(0, 0, clip_cells(head, w).ljust(w), Style(bold=True))
        canvas.write_text(
            h - 1,
            0,
            clip_cells(self.status_text(), w),
            Style(fg=RGB(230, 70, 70)) if state.error else Style(dim=True),
        )
        items = state.items
        if self.view == "marquee" and items:
            self._marquee.text = "   ***   ".join(i.title for i in items)
            self._marquee.resize(w, 1)
            self._marquee.draw(canvas.view(Rect(0, 1, w, 1)))
            return
        if self.view == "box" and items:
            it = items[min(self.item_index, len(items) - 1)]
            self._box.resize(w, max(3, h - 2))
            self._box.text = f"{it.title}\n{it.published.isoformat() if it.published else ''}\n{it.summary}\n{it.link}"
            self._box.draw(canvas.view(Rect(0, 1, w, max(3, h - 2))))
            return
        for r, item in enumerate(items[self.top : self.top + h - 2]):
            sel = self.top + r == self.item_index
            when = item.published.strftime("%m-%d %H:%M ") if item.published else ""
            line = clip_cells(f"{'>' if sel else ' '} {when}{item.title}", w)
            canvas.write_text(
                1 + r,
                0,
                line.ljust(w) if sel else line,
                Style(reverse=sel and self.focused, bold=sel) if sel else DEFAULT_STYLE,
            )

    def describe(self) -> str:
        s = self.current
        return f"RssReader({len(self.feeds)} feeds, current={s.source.name if s else None!r}, {self.status_text()})"
