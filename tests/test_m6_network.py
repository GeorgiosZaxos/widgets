"""M6 network widgets: RSS reader and weather widget (fake transport, no real internet)."""

from __future__ import annotations

import http.server
import threading
import time

import pytest
from tests.conftest import text_rows

from widgets.base_elements.events import KeyEvent
from widgets.errors import (
    FeedConnectionError,
    FeedError,
    FeedHttpError,
    FeedParseError,
    FeedTimeoutError,
    LocationNotFoundError,
    WeatherError,
)
from widgets.net.http import HttpResponse, UrllibTransport, validate_url
from widgets.net.rss import FeedSource, RssReader, clean_text, parse_feed
from widgets.net.weather import (
    Current,
    Day,
    Location,
    OpenMeteoProvider,
    Weather,
    WeatherWidget,
    compass,
    describe_code,
    fmt,
    symbol,
)
from widgets.render.buffer import Buffer

RSS = b"""<?xml version="1.0"?><rss version="2.0"><channel><title>News</title>
<item><title>One &amp; only</title><link>http://x/1</link><description>&lt;b&gt;bold&lt;/b&gt; text</description>
<pubDate>Mon, 02 Jan 2023 10:00:00 GMT</pubDate></item>
<item><title>Two</title><link>http://x/2</link></item>
<item><title>Three</title><link>http://x/3</link></item></channel></rss>"""
ATOM = b"""<feed xmlns="http://www.w3.org/2005/Atom"><title>A</title>
<entry><title>E1</title><link rel="alternate" href="http://a/1"/><summary>sum</summary><updated>2023-01-02T10:00:00Z</updated></entry></feed>"""


class FakeTransport:
    def __init__(self, responses=None):
        self.responses = responses or {}
        self.calls: list[tuple[str, dict]] = []

    def get(self, url, *, headers=None, timeout=10.0, max_bytes=1 << 20):
        self.calls.append((url, dict(headers or {})))
        r = self.responses.get(url)
        if isinstance(r, BaseException):
            raise r
        if callable(r):
            r = r()
        if r is None:
            raise FeedConnectionError("no route")
        return r


def settle(widget, timeout=3.0):
    end = time.monotonic() + timeout
    while time.monotonic() < end:
        widget.update(0.0)
        if not widget._jobs.busy:
            widget.update(0.0)
            return
        time.sleep(0.005)
    raise AssertionError("jobs did not finish")


def make_reader(responses, **kw):
    t = FakeTransport(responses)
    clock = kw.pop("clock", None)
    r = RssReader(
        0,
        0,
        60,
        12,
        transport=t,
        clock=clock,
        sources=kw.pop(
            "sources",
            [FeedSource("N", "http://n/rss", "News"), FeedSource("A", "http://a/atom", "Tech")],
        ),
        **kw,
    )
    r.mount()
    return r, t


def draw(w, width=60, height=12):
    buf = Buffer(width, height)
    w.draw(buf)
    return text_rows(buf)


# ------------------------------------------------------------------ RSS
@pytest.mark.req("FR-RSS-001")
def test_sources_grouped_by_category_and_selection():
    r, _ = make_reader({})
    assert r.categories == ["News", "Tech"]
    assert r.current.source.name == "N"
    r.handle_key(KeyEvent("tab", None))
    assert r.current.source.name == "A"
    r.handle_key(KeyEvent("[", "["))
    assert r.current.source.name == "N"


@pytest.mark.req("FR-RSS-002", "FR-RSS-010")
def test_parse_rss_and_atom_and_sanitise():
    title, items = parse_feed(RSS)
    assert title == "News" and [i.title for i in items] == ["One & only", "Two", "Three"]
    assert items[0].summary == "bold text"
    assert items[0].published is not None
    assert "\x1b" not in clean_text("a\x1b[31mb\x07")
    assert items[0].link == "http://x/1"
    t2, i2 = parse_feed(ATOM)
    assert t2 == "A" and i2[0].link == "http://a/1" and i2[0].summary == "sum"
    assert clean_text(None) == ""


@pytest.mark.req("FR-RSS-002")
def test_refresh_is_asynchronous_and_updates_items():
    gate = threading.Event()

    def slow():
        gate.wait(2)
        return HttpResponse(200, RSS)

    r, _ = make_reader({"http://n/rss": slow, "http://a/atom": HttpResponse(200, ATOM)})
    assert r.refresh() == 2
    assert r.current.loading and r.items == []  # UI thread not blocked
    gate.set()
    settle(r)
    assert len(r.items) == 3 and not r.current.loading
    rows = "\n".join(draw(r))
    assert "One & only" in rows


@pytest.mark.req("FR-RSS-003")
@pytest.mark.parametrize("view", ["list", "marquee", "box"])
def test_three_presentations(view):
    r, _ = make_reader({"http://n/rss": HttpResponse(200, RSS)}, view=view)
    r.refresh()
    settle(r)
    r.update(0.5)
    assert "One & only" in "\n".join(draw(r)) or view == "marquee"


@pytest.mark.req("FR-RSS-004")
def test_scroll_page_speed_direction():
    big = (
        b"<rss><channel><title>t</title>"
        + b"".join(b"<item><title>I%d</title></item>" % i for i in range(30))
        + b"</channel></rss>"
    )
    r, _ = make_reader(
        {"http://n/rss": HttpResponse(200, big)}, sources=[FeedSource("N", "http://n/rss")]
    )
    r.refresh()
    settle(r)
    r.handle_key(KeyEvent("down", None))
    assert r.item_index == 1
    r.handle_key(KeyEvent("pagedown", None))
    assert r.item_index > 1
    r.handle_key(KeyEvent("up", None))
    for _ in range(100):
        r.handle_key(KeyEvent("down", None))
    assert r.item_index == 29
    r.set_speed(5.0)
    r.set_direction("right")
    r.start()
    r.pause()
    r.resume()
    with pytest.raises(ValueError):
        r.set_direction("sideways")


@pytest.mark.req("FR-RSS-005")
def test_callbacks():
    got: dict[str, object] = {}
    r, _ = make_reader(
        {"http://n/rss": HttpResponse(200, RSS), "http://a/atom": FeedHttpError(500, "boom")},
        on_update=lambda s, items: got.setdefault("update", (s.name, len(items))),
        on_error=lambda s, e: got.setdefault("error", (s.name, type(e).__name__)),
        on_select=lambda item: got.setdefault("select", item.title),
    )
    r.refresh()
    settle(r)
    assert got["update"] == ("N", 3) and got["error"] == ("A", "FeedHttpError")
    r.handle_key(KeyEvent("enter", None))
    assert got["select"] == "One & only"


@pytest.mark.req("FR-RSS-006", "NFR-SEC-002")
@pytest.mark.parametrize(
    ("resp", "exc"),
    [
        (FeedTimeoutError("t"), FeedTimeoutError),
        (FeedConnectionError("c"), FeedConnectionError),
        (FeedHttpError(404, "nf"), FeedHttpError),
        (HttpResponse(200, b"<rss><channel>"), FeedParseError),
        (HttpResponse(200, b"<html/>"), FeedParseError),
        (ValueError("bad url"), FeedError),
    ],
)
def test_errors_are_typed_and_isolated(resp, exc):
    r, _ = make_reader({"http://n/rss": resp, "http://a/atom": HttpResponse(200, ATOM)})
    r.refresh()
    settle(r)
    bad, good = r.feeds
    assert isinstance(bad.error, exc) and good.error is None and len(good.items) == 1
    assert "error" in r.status_text()


@pytest.mark.req("FR-RSS-006")
def test_stale_items_kept_after_failure():
    state = {"ok": True}

    def fn():
        if state["ok"]:
            return HttpResponse(200, RSS)
        raise FeedTimeoutError("t")

    now = [0.0]
    r, _ = make_reader(
        {"http://n/rss": fn}, sources=[FeedSource("N", "http://n/rss")], clock=lambda: now[0]
    )
    r.refresh()
    settle(r)
    state["ok"] = False
    now[0] = 1000
    r.refresh()
    settle(r)
    assert len(r.items) == 3 and r.current.stale and "stale" in r.status_text()


@pytest.mark.req("FR-RSS-007")
def test_limits_and_refresh_interval():
    now = [0.0]
    r, t = make_reader(
        {"http://n/rss": HttpResponse(200, RSS)},
        sources=[FeedSource("N", "http://n/rss")],
        clock=lambda: now[0],
        max_items_per_feed=2,
    )
    assert r.min_refresh_interval == 60.0
    assert r.refresh() == 1
    settle(r)
    assert len(r.items) == 2
    now[0] = 30
    assert r.refresh() == 0  # too soon
    now[0] = 61
    assert r.refresh() == 1
    settle(r)
    assert len(t.calls) == 2
    # oversized responses are rejected
    r2, _ = make_reader(
        {"http://n/rss": HttpResponse(200, b"x" * 100)},
        sources=[FeedSource("N", "http://n/rss")],
        max_response_bytes=10,
    )
    r2.refresh()
    settle(r2)
    assert isinstance(r2.current.error, FeedError)
    with pytest.raises(ValueError):
        RssReader(max_items_per_feed=0)


@pytest.mark.req("FR-RSS-008", "NFR-SEC-002")
def test_scheme_policy():
    assert validate_url("https://a/b") == "https://a/b"
    for bad in ("file:///etc/passwd", "ftp://x/y", "javascript:alert(1)", "http://", "nonsense"):
        with pytest.raises(ValueError):
            validate_url(bad)
    with pytest.raises(ValueError):
        UrllibTransport().get("file:///etc/passwd")
    r, _ = make_reader({}, sources=[FeedSource("B", "file:///etc/passwd")])
    r.transport = UrllibTransport()
    r.refresh()
    settle(r)
    assert isinstance(r.current.error, FeedError)


class _Handler(http.server.BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def do_GET(self):
        if self.path == "/loop":
            self.send_response(302)
            self.send_header("Location", "/loop")
            self.end_headers()
        elif self.path == "/off":
            self.send_response(302)
            self.send_header("Location", "http://other.invalid/x")
            self.end_headers()
        elif self.path == "/etag":
            if self.headers.get("If-None-Match") == '"v1"':
                self.send_response(304)
                self.end_headers()
            else:
                self.send_response(200)
                self.send_header("ETag", '"v1"')
                self.end_headers()
                self.wfile.write(RSS)
        elif self.path == "/big":
            self.send_response(200)
            self.end_headers()
            self.wfile.write(b"x" * 5000)
        else:
            self.send_response(200)
            self.end_headers()
            self.wfile.write(RSS)


@pytest.fixture
def server():
    srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), _Handler)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{srv.server_port}"
    srv.shutdown()
    srv.server_close()


@pytest.mark.req("FR-RSS-008", "FR-RSS-009", "NFR-SEC-002")
def test_real_transport_redirects_size_and_etag(server):
    t = UrllibTransport()
    assert t.get(server + "/ok").status == 200
    with pytest.raises(FeedConnectionError, match="redirect"):
        t.get(server + "/loop")
    with pytest.raises(FeedConnectionError, match="allowed"):
        UrllibTransport(allowed_hosts=["127.0.0.1"]).get(server + "/off")
    with pytest.raises(FeedConnectionError, match="larger"):
        t.get(server + "/big", max_bytes=100)
    first = t.get(server + "/etag")
    assert first.headers["etag"] == '"v1"'
    assert t.get(server + "/etag", headers={"If-None-Match": '"v1"'}).status == 304


@pytest.mark.req("FR-RSS-008")
def test_https_downgrade_refused():
    import urllib.request

    from widgets.net.http import _RedirectPolicy

    pol = _RedirectPolicy(None)
    req = urllib.request.Request("https://a/x")
    with pytest.raises(FeedConnectionError, match="downgrade"):
        pol.redirect_request(req, None, 302, "Found", {}, "http://a/y")
    with pytest.raises(FeedConnectionError, match="scheme"):
        _RedirectPolicy(None).redirect_request(req, None, 302, "Found", {}, "file:///x")


@pytest.mark.req("FR-RSS-009")
def test_conditional_get_headers_and_304():
    calls = []

    def fn():
        calls.append(1)
        if len(calls) == 1:
            return HttpResponse(
                200, RSS, {"etag": '"e1"', "last-modified": "Mon, 01 Jan 2023 00:00:00 GMT"}
            )
        return HttpResponse(304, b"")

    now = [0.0]
    r, t = make_reader(
        {"http://n/rss": fn}, sources=[FeedSource("N", "http://n/rss")], clock=lambda: now[0]
    )
    r.refresh()
    settle(r)
    now[0] = 100
    r.refresh()
    settle(r)
    assert t.calls[0][1] == {}
    assert t.calls[1][1] == {
        "If-None-Match": '"e1"',
        "If-Modified-Since": "Mon, 01 Jan 2023 00:00:00 GMT",
    }
    assert len(r.items) == 3 and r.current.error is None


@pytest.mark.req("FR-RSS-002", "FR-RSS-006", "NFR-SEC-002")
def test_xml_hardening():
    bomb = b'<?xml version="1.0"?><!DOCTYPE l [<!ENTITY a "aaaa"><!ENTITY b "&a;&a;">]><rss><channel><title>&b;</title></channel></rss>'
    with pytest.raises(FeedParseError):
        parse_feed(bomb)


@pytest.mark.req("FR-RSS-010")
def test_html_stripped_from_titles_and_summaries():
    body = b"<rss><channel><title>t</title><item><title>&lt;img src=x onerror=1&gt;Hi</title><description>&lt;p&gt;a&lt;/p&gt;&amp;amp;</description></item></channel></rss>"
    _, items = parse_feed(body)
    assert items[0].title == "Hi" and "<" not in items[0].summary


# -------------------------------------------------------------- weather
GEO = (
    b'{"results":[{"name":"Paris","latitude":48.85,"longitude":2.35,"country":"France","admin1":"Ile-de-France"},'
    b'{"name":"Paris","latitude":33.6,"longitude":-95.5,"country":"United States","admin1":"Texas"}]}'
)
FORECAST = (
    b'{"current":{"temperature_2m":12.5,"apparent_temperature":11.0,"relative_humidity_2m":70,'
    b'"wind_speed_10m":15,"wind_direction_10m":200,"precipitation":0.2,"weather_code":61},'
    b'"daily":{"time":["2024-05-01","2024-05-02","2024-05-03"],"weather_code":[61,3,0],'
    b'"temperature_2m_max":[15,16,null],"temperature_2m_min":[8,9,10],"precipitation_sum":[1.0,0,0]}}'
)


def wx_transport(geo=GEO, fc=FORECAST):
    class T:
        def __init__(self):
            self.urls: list[str] = []
            self.fail: BaseException | None = None

        def get(self, url, *, headers=None, timeout=10.0, max_bytes=1 << 20):
            self.urls.append(url)
            if self.fail:
                raise self.fail
            return HttpResponse(200, geo if "geocoding" in url else fc)

    return T()


def make_wx(**kw):
    t = kw.pop("transport", None) or wx_transport()
    clock = kw.pop("clock", time.monotonic)
    w = WeatherWidget(
        0, 0, 70, 14, location=kw.pop("location", "Paris"), transport=t, clock=clock, **kw
    )
    w.mount()
    return w, t


@pytest.mark.req("FR-WEATHER-001")
def test_geocode_top_match_and_candidates():
    w, _ = make_wx()
    w.refresh()
    settle(w)
    assert w.location.country == "France" and len(w.candidates) == 2
    assert w.candidates[1].admin == "Texas"
    assert "matches" in "\n".join(draw(w, 70, 14))


@pytest.mark.req("FR-WEATHER-001")
def test_no_match_raises_location_not_found():
    p = OpenMeteoProvider(wx_transport(geo=b"{}"))
    assert p.geocode("zzzz") == []
    w, _ = make_wx(transport=wx_transport(geo=b"{}"), location="zzzz")
    w.refresh()
    settle(w)
    assert "no location found" in (w.error or "") and w.weather is None
    assert issubclass(LocationNotFoundError, LookupError)


@pytest.mark.req("FR-WEATHER-002")
def test_forecast_default_days_and_range():
    w, t = make_wx()
    assert w.days == 5
    w.refresh()
    settle(w)
    assert any("forecast_days=5" in u for u in t.urls) and len(w.weather.days) == 3
    for bad in (0, 17):
        with pytest.raises(ValueError):
            WeatherWidget(location="x", days=bad)
    WeatherWidget(location="x", days=16)


@pytest.mark.req("FR-WEATHER-003")
def test_data_model_na_and_units():
    w, t = make_wx()
    w.refresh()
    settle(w)
    c = w.weather.current
    assert (c.temperature, c.apparent, c.humidity, c.wind_direction, c.code) == (
        12.5,
        11.0,
        70,
        200,
        61,
    )
    assert w.weather.days[2].t_max is None
    text = "\n".join(draw(w, 70, 14))
    assert "n/a" in text and "Light rain" in text
    assert fmt(None) == "n/a" and compass(None) == "n/a" and describe_code(None) == "n/a"
    assert compass(200) == "S" and describe_code(9999) == "Unknown"
    w.handle_key(KeyEvent("u", "u"))
    settle(w)
    assert w.units == "imperial" and any("temperature_unit=fahrenheit" in u for u in t.urls)
    with pytest.raises(ValueError):
        w.set_units("kelvin")
    sparse = OpenMeteoProvider(wx_transport(fc=b'{"current":{},"daily":{}}'))
    out = sparse.forecast(Location("x", 0, 0), 3, "metric")
    assert out.current == Current() and out.days == ()


@pytest.mark.req("FR-WEATHER-004")
def test_cache_ttl_force_and_stale():
    now = [0.0]
    t = wx_transport()
    w, _ = make_wx(transport=t, clock=lambda: now[0], cache_ttl=600)
    w.refresh()
    settle(w)
    n = len(t.urls)
    now[0] = 100
    w.refresh()
    settle(w)
    assert len(t.urls) == n  # cache hit
    w.refresh(force=True)
    settle(w)
    assert len(t.urls) > n
    now[0] = 2000
    t.fail = FeedTimeoutError("down")
    w.refresh()
    settle(w)
    assert w.stale and w.weather is not None and "[stale]" in "\n".join(draw(w, 70, 14))
    assert w.error and "unavailable" in w.error
    t.fail = None
    w.refresh(force=True)
    settle(w)
    assert not w.stale and w.error is None
    assert WeatherWidget(location="x").cache_ttl == 600.0


@pytest.mark.req("FR-WEATHER-005")
def test_symbols_and_ascii_fallback_and_multi_day():
    w, _ = make_wx(ascii_only=True)
    w.refresh()
    settle(w)
    text = "\n".join(draw(w, 70, 14))
    assert all(ord(ch) < 128 for ch in text)
    assert "2024-05-03" in text and "2024-05-01" in text
    assert symbol(0) != symbol(0, True) and symbol(None) == "?"
    w2, _ = make_wx()
    w2.refresh()
    settle(w2)
    assert "🌧" in "\n".join(draw(w2, 70, 14)) or "☀" in "\n".join(draw(w2, 70, 14))


@pytest.mark.req("FR-WEATHER-006")
def test_set_location_async_and_supersede():
    gate = threading.Event()
    base = wx_transport()
    orig = base.get

    def slow(url, **kw):
        if "geocoding" in url and "Rome" in url:
            gate.wait(2)
        return orig(url, **kw)

    base.get = slow
    w, _ = make_wx(transport=base)
    w.set_location("Rome")
    assert w.loading and w.weather is None  # returns immediately
    w.set_location("Paris")  # supersedes Rome
    gate.set()
    settle(w)
    assert w.location_name == "Paris"


@pytest.mark.req("FR-WEATHER-007")
def test_keyboard_controls():
    w, _ = make_wx()
    w.refresh()
    settle(w)
    w.handle_key(KeyEvent("right", None))
    assert w.day_index == 1
    w.handle_key(KeyEvent("left", None))
    w.handle_key(KeyEvent("left", None))
    assert w.day_index == 2
    assert w.handle_key(KeyEvent("r", "r"))
    settle(w)
    w.handle_key(KeyEvent("l", "l"))
    assert w.editing and "Location:" in draw(w, 70, 14)[0]
    for ch in "Oslo":
        w.handle_key(KeyEvent(ch, ch))
    w.handle_key(KeyEvent("backspace", None))
    assert w.edit_text == "Osl"
    w.handle_key(KeyEvent("escape", None))
    assert not w.editing and w.location_name == "Paris"
    w.handle_key(KeyEvent("l", "l"))
    for ch in "Oslo":
        w.handle_key(KeyEvent(ch, ch))
    w.handle_key(KeyEvent("enter", None))
    assert w.location_name == "Oslo"
    settle(w)
    assert not w.handle_key(KeyEvent("z", "z"))


@pytest.mark.req("FR-WEATHER-008")
def test_provider_protocol_and_injectable_transport():
    class Fake:
        def geocode(self, name):
            return [Location(name, 1.0, 2.0, "Nowhere")]

        def forecast(self, location, days, units):
            return Weather(
                location, Current(temperature=1.0, code=0), (Day("d1", 0, 2.0, 0.0, 0.0),), units
            )

    w = WeatherWidget(0, 0, 60, 10, location="Zed", provider=Fake())
    w.mount()
    w.refresh()
    settle(w)
    assert w.location.label == "Zed, Nowhere" and "Zed, Nowhere" in "\n".join(draw(w, 60, 10))
    with pytest.raises(WeatherError):
        OpenMeteoProvider(wx_transport(geo=b"not json")).geocode("x")
    with pytest.raises(WeatherError):
        OpenMeteoProvider(wx_transport(geo=b"[1]")).geocode("x")


@pytest.mark.req("FR-WEATHER-009")
def test_privacy_notice_documented():
    import widgets.net.weather as mod

    assert "third-party" in (mod.__doc__ or "")
    w, _ = make_wx()
    w.handle_key(KeyEvent("l", "l"))
    assert "third-party" in "\n".join(draw(w, 70, 14))
