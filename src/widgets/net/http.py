"""HTTP transport seam (D-11, FR-RSS-008/009). Layer L3.

``HttpTransport`` is a Protocol so tests and applications can substitute their own; the default
``UrllibTransport`` verifies TLS, accepts only http/https, limits redirects (5), never downgrades
https to http, can be confined to an allow-list of hosts, and caps the response size.
"""

from __future__ import annotations

import socket
import urllib.error
import urllib.request
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from typing import Protocol
from urllib.parse import urlparse

from widgets.errors import FeedConnectionError, FeedError, FeedHttpError, FeedTimeoutError

DEFAULT_MAX_BYTES = 1 << 20
MAX_REDIRECTS = 5
USER_AGENT = "widgets/0.1 (+terminal widgets library)"


@dataclass(frozen=True, slots=True)
class HttpResponse:
    status: int
    body: bytes
    headers: Mapping[str, str] = field(default_factory=dict)
    url: str = ""


class HttpTransport(Protocol):
    """Protocol for HTTP GET transports; inject one to fetch offline or in tests."""

    def get(
        self,
        url: str,
        *,
        headers: Mapping[str, str] | None = None,
        timeout: float = 10.0,
        max_bytes: int = DEFAULT_MAX_BYTES,
    ) -> HttpResponse:
        """Fetch ``url``. 304 is returned as a normal response; other errors raise ``FeedError``."""
        ...


def validate_url(url: str, schemes: Sequence[str] = ("http", "https")) -> str:
    """Return ``url`` if its scheme is in ``schemes`` and it has a host, else raise ``ValueError``."""
    parts = urlparse(url)
    if parts.scheme.lower() not in schemes or not parts.netloc:
        raise ValueError(
            f"unsupported or malformed URL {url!r}; allowed schemes: {', '.join(schemes)}"
        )
    return url


class _RedirectPolicy(urllib.request.HTTPRedirectHandler):
    def __init__(self, allowed_hosts: Sequence[str] | None) -> None:
        self.allowed = {h.lower() for h in allowed_hosts} if allowed_hosts else None
        self.count = 0

    def redirect_request(self, req, fp, code, msg, headers, newurl):  # type: ignore[no-untyped-def]
        old, new = urlparse(req.full_url), urlparse(newurl)
        self.count += 1
        if self.count > MAX_REDIRECTS:
            raise FeedConnectionError(f"more than {MAX_REDIRECTS} redirects")
        if new.scheme.lower() not in ("http", "https"):
            raise FeedConnectionError(f"redirect to unsupported scheme {new.scheme!r}")
        if old.scheme.lower() == "https" and new.scheme.lower() == "http":
            raise FeedConnectionError("redirect would downgrade https to http")
        if self.allowed is not None and (new.hostname or "").lower() not in self.allowed:
            raise FeedConnectionError(f"redirect to host outside the allowed list: {new.hostname}")
        return super().redirect_request(req, fp, code, msg, headers, newurl)


class UrllibTransport:
    """Default ``HttpTransport`` built on ``urllib`` (TLS verified, redirect and size limits)."""

    def __init__(
        self, *, allowed_hosts: Sequence[str] | None = None, user_agent: str = USER_AGENT
    ) -> None:
        self.allowed_hosts = allowed_hosts
        self.user_agent = user_agent

    def get(
        self,
        url: str,
        *,
        headers: Mapping[str, str] | None = None,
        timeout: float = 10.0,
        max_bytes: int = DEFAULT_MAX_BYTES,
    ) -> HttpResponse:
        validate_url(url)
        request = urllib.request.Request(
            url, headers={"User-Agent": self.user_agent, **(headers or {})}
        )
        opener = urllib.request.build_opener(_RedirectPolicy(self.allowed_hosts))
        try:
            with opener.open(request, timeout=timeout) as resp:
                body = resp.read(max_bytes + 1)
                if len(body) > max_bytes:
                    raise FeedConnectionError(f"response larger than {max_bytes} bytes")
                return HttpResponse(
                    resp.status, body, {k.lower(): v for k, v in resp.headers.items()}, resp.url
                )
        except urllib.error.HTTPError as exc:
            if exc.code == 304:
                return HttpResponse(304, b"", {k.lower(): v for k, v in exc.headers.items()}, url)
            if 300 <= exc.code < 400:
                raise FeedConnectionError(
                    f"too many redirects or redirect loop (HTTP {exc.code})"
                ) from exc
            raise FeedHttpError(exc.code, f"HTTP {exc.code} {exc.reason}") from exc
        except FeedError:
            raise
        except urllib.error.URLError as exc:
            if isinstance(exc.reason, socket.timeout | TimeoutError):
                raise FeedTimeoutError(f"timed out after {timeout:g}s") from exc
            raise FeedConnectionError(str(exc.reason)) from exc
        except TimeoutError as exc:
            raise FeedTimeoutError(f"timed out after {timeout:g}s") from exc
        except OSError as exc:
            raise FeedConnectionError(str(exc)) from exc
