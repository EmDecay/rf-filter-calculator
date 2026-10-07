"""Accept work only from the calculator's own page.

The web UI has no login, so without this check any site the user visits could make
their browser submit designs here (cross-site request forgery): the page could not
read the answers, but it could keep the calculation workers busy. Browsers label each
request with where it came from: ``Sec-Fetch-Site`` in current browsers, ``Origin``
on cross-origin and form submissions in older ones. A submission is accepted only when
that label says it came from this origin. Scripts such as curl send neither header and
are accepted, because they are not a browser acting on someone else's behalf.

The ``Host`` header must also name this server: a loopback name, or the specific
address it was bound to. That stops a DNS-rebinding page, whose own domain resolves to
this server's address, from passing as same-origin. A wildcard bind (``0.0.0.0``) cannot
know its names and skips this check; ``filter-calc web`` warns about such binds.
"""

from __future__ import annotations

from collections.abc import Mapping
from urllib.parse import urlsplit

SAFE_METHODS = frozenset({"GET", "HEAD", "OPTIONS"})
SAME_SITE_FETCH = frozenset({"same-origin", "none"})
CROSS_SITE_REFUSED = (
    "Cross-site request refused: designs can be submitted only from the calculator's own page"
)
UNKNOWN_HOST_REFUSED = "Request refused: the Host header does not name this server"


def _host_name(host: str) -> str:
    """Return the host part of a ``Host`` header value, without port or brackets."""
    if host.startswith("["):
        return host[1 : host.find("]")]
    if host.count(":") == 1:
        return host.rsplit(":", 1)[0]
    return host


def refusal(
    method: str, headers: Mapping[str, str], *, allowed_hosts: frozenset[str] | None
) -> str | None:
    """Return why the request must be refused, or ``None`` to let it through.

    ``allowed_hosts`` comes from ``WebSettings.allowed_hosts`` (``None`` skips the Host
    check). ``headers`` must look names up case-insensitively, as Starlette's do.
    """
    host = headers.get("host", "")
    if allowed_hosts is not None and _host_name(host).lower() not in allowed_hosts:
        return UNKNOWN_HOST_REFUSED
    if method.upper() in SAFE_METHODS:
        return None
    fetch_site = headers.get("sec-fetch-site")
    if fetch_site is not None:
        return None if fetch_site.lower() in SAME_SITE_FETCH else CROSS_SITE_REFUSED
    origin = headers.get("origin")
    if origin is None:
        return None
    # An opaque origin ("null", from sandboxed frames or files) has no host and fails.
    if urlsplit(origin).netloc.lower() != host.lower():
        return CROSS_SITE_REFUSED
    return None
