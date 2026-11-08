"""Multi-lane RSS ticker: each feed scrolls on its own line with its own direction/speed/colour.

    python examples/rss_ticker.py            offline demo feeds
    python examples/rss_ticker.py --live     real feeds (needs internet)

Keys: up/down pick a lane, + / - its speed, [ / ] all lanes, space pause, d reverse, r refresh, q quit.
"""

from __future__ import annotations

import argparse
from collections.abc import Mapping

from widgets.base_elements.events import Event, KeyEvent
from widgets.base_elements.layout import Screen
from widgets.net.http import HttpResponse, HttpTransport, UrllibTransport
from widgets.net.rss import FeedSource
from widgets.net.rss_ticker import RssTicker, TickerLane
from widgets.render.run import run_app

W = 100


class DemoTransport:
    def get(
        self,
        url: str,
        *,
        headers: Mapping[str, str] | None = None,
        timeout: float = 10.0,
        max_bytes: int = 1 << 20,
    ) -> HttpResponse:
        site = url.rsplit("/", 1)[-1].title()
        items = "".join(
            f"<item><title>{site}: headline number {i + 1} of the day</title></item>"
            for i in range(12)
        )
        body = f"<rss version='2.0'><channel><title>{site}</title>{items}</channel></rss>"
        return HttpResponse(200, body.encode(), {})


def lanes(live: bool) -> list[TickerLane]:
    if live:
        return [
            TickerLane(
                FeedSource("Python", "https://blog.python.org/feeds/posts/default"), "left", 9
            ),
            TickerLane(
                FeedSource("NASA", "https://www.nasa.gov/rss/dyn/breaking_news.rss"), "right", 14
            ),
        ]

    def mk(n: str) -> FeedSource:
        return FeedSource(n, f"https://demo.test/{n.lower()}")

    return [
        TickerLane(mk("World"), "left", 8),
        TickerLane(mk("Sport"), "right", 14, color="#5fd7ff"),
        TickerLane(mk("Tech"), "left", 22, gradient="rainbow"),
        TickerLane(mk("Science"), "right", 5, color="#ffd75f"),
    ]


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--live", action="store_true")
    ap.add_argument("--duration", type=float, default=None)
    args = ap.parse_args()
    transport: HttpTransport = UrllibTransport() if args.live else DemoTransport()
    ticker = RssTicker(
        0, 1, W, lanes=lanes(args.live), transport=transport, spacing=1, show_speed=True
    )
    screen = Screen(W, ticker.height + 3)
    screen.add(ticker)

    ticker.focus()

    def on_event(event: Event) -> None:
        if isinstance(event, KeyEvent):
            ticker.handle_key(event)

    run_app(
        screen,
        duration=args.duration,
        quit_keys=("q", "ctrl+q"),
        on_event=on_event,
        title="widgets RSS ticker",
    )


if __name__ == "__main__":
    main()
