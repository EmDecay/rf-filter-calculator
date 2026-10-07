"""Shared helpers for the web UI tests (import after ``pytest.importorskip("fastapi")``).

``web_client`` runs the app's lifespan, so the calculation pool exists during the test
and is shut down, with its threads joined, when the ``with`` block ends.
"""

from __future__ import annotations

import html
import re
import threading
from collections.abc import Iterator
from contextlib import contextmanager

from fastapi.testclient import TestClient

from filter_lib.web import WebSettings, create_app

HTMX = {"HX-Request": "true"}
# The app only answers requests addressed to this computer, as a browser's would be.
BASE_URL = "http://127.0.0.1:8765"
POOL_THREAD_PREFIX = "filter-calc-web"
_PRE = re.compile(r'<pre class="output" id="output-text"[^>]*>(.*?)</pre>', re.S)


@contextmanager
def web_client(**settings) -> Iterator[TestClient]:
    """A test client whose app runs with ``WebSettings(**settings)``."""
    with TestClient(create_app(WebSettings(**settings)), base_url=BASE_URL) as client:
        yield client


def output_text(fragment: str) -> str:
    """Return the calculator text a browser shows for a result fragment.

    HTML parsing drops one newline that directly follows ``<pre>``, so this does too;
    the result is what the page displays and what its Copy button copies.
    """
    match = _PRE.search(fragment)
    assert match, fragment[:500]
    text = html.unescape(match.group(1))
    return text[1:] if text.startswith("\n") else text


def pool_threads() -> list[threading.Thread]:
    return [t for t in threading.enumerate() if t.name.startswith(POOL_THREAD_PREFIX)]
