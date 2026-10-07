"""Accept work only from the calculator's own page.

The web UI has no login, so without this check any site the user visits could make
their browser submit designs here (cross-site request forgery): the page could not
read the answers, but it could keep the calculation workers busy. Browsers label each
request with where it came from: ``Sec-Fetch-Site`` in current browsers, ``Origin``
on cross-origin and form submissions in older ones. A submission is accepted only when
that label says it came from this origin. Scripts such as curl send neither header and
are accepted, because they are not a browser acting on someone else's behalf.

On the default loopback bind, the ``Host`` header must also name this computer. That
stops a DNS-rebinding page, whose own address resolves to 127.0.0.1, from passing as
same-origin.
"""

from __future__ import annotations

from collections.abc import Mapping
from urllib.parse import urlsplit

from .settings import LOOPBACK_HOSTS

SAFE_METHODS = frozenset({"GET", "HEAD", "OPTIONS"})
SAME_SITE_FETCH = frozenset({"same-origin", "none"})
CROSS_SITE_REFUSED = (
    "Cross-site request refused: designs can be submitted only from the calculator's own page"
)
UNKNOWN_HOST_REFUSED = "Request refused: the Host header does not name this computer"


def _host_name(host: str) -> str:
    """Return the host part of a ``Host`` header value, without port or brackets."""
    if host.startswith("["):
        return host[1 : host.find("]")]
    if host.count(":") == 1:
        return host.rsplit(":", 1)[0]
    return host


def refusal(method: str, headers: Mapping[str, str], *, loopback_only: bool) -> str | None:
    """Return why the request must be refused, or ``None`` to let it through.

    ``headers`` must look names up case-insensitively, as Starlette's headers do.
    """
    host = headers.get("host", "")
    if loopback_only and _host_name(host).lower() not in LOOPBACK_HOSTS:
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
