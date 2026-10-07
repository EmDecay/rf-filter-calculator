"""The page, the tab fragments, static assets, and response headers."""

from __future__ import annotations

import pytest

pytest.importorskip("fastapi")

from filter_lib import __version__  # noqa: E402
from filter_lib.shared.cli_aliases import DEFAULT_COMPONENTS, DEFAULT_RESONATORS  # noqa: E402
from tests.web_helpers import HTMX, output_text, web_client  # noqa: E402


@pytest.fixture(scope="module")
def client():
    with web_client() as test_client:
        yield test_client


@pytest.mark.parametrize(
    "category, action, order_field, order",
    [
        ("lowpass", "/design/lowpass", "components", DEFAULT_COMPONENTS),
        ("highpass", "/design/highpass", "components", DEFAULT_COMPONENTS),
        ("bandpass", "/design/bandpass", "resonators", DEFAULT_RESONATORS),
    ],
)
def test_each_category_page_has_its_form_and_cli_defaults(
    client, category, action, order_field, order
):
    response = client.get(f"/?category={category}")

    assert response.status_code == 200
    page = response.text
    assert f'action="{action}"' in page and f'hx-post="{action}"' in page
    assert f'name="{order_field}" type="text" inputmode="numeric"' in page
    assert f'id="f-{order_field}" name="{order_field}"' in page
    assert f'value="{order}"' in page
    assert 'name="svg_plot" checked' in page
    assert "No design yet" in page
    assert f"filter-calc {__version__}" in page


def test_default_page_is_lowpass(client):
    page = client.get("/").text

    assert 'aria-current="page">Low-pass</a>' in page


def test_tab_fragment_swaps_the_form_and_resets_the_result(client):
    fragment = client.get("/form/bandpass", headers=HTMX).text

    assert "<html" not in fragment
    assert 'action="/design/bandpass"' in fragment
    assert 'aria-current="page">Band-pass</a>' in fragment
    assert 'id="result"' in fragment and 'hx-swap-oob="true"' in fragment


def test_full_page_fallback_shows_the_result_and_keeps_inputs(client):
    form = {"filter_type": "bessel", "topology": "t", "frequency": "21MHz", "components": "6"}

    response = client.post("/design/highpass", data=form)

    assert response.status_code == 200
    assert "<!doctype html>" in response.text
    assert "Bessel T High Pass Filter" in output_text(response.text)
    assert 'value="21MHz"' in response.text
    assert 'value="t" checked' in response.text
    assert 'formaction="/export/highpass/json"' in response.text


def test_bandpass_warnings_are_listed_above_the_output(client):
    form = {"filter_type": "butterworth", "frequency": "14MHz", "bandwidth": "4MHz"}

    fragment = client.post("/design/bandpass", data=form, headers=HTMX).text

    assert "Design warnings" in fragment
    assert fragment.index("Design warnings") < fragment.index('id="output-text"')


def test_health_check(client):
    assert client.get("/healthz").json() == {"status": "ok"}


@pytest.mark.parametrize(
    "path, media_type",
    [
        ("/static/htmx.min.js", "javascript"),
        ("/static/app.js", "javascript"),
        ("/static/app.css", "text/css"),
        ("/static/tokens.css", "text/css"),
        ("/static/favicon.svg", "image/svg+xml"),
    ],
)
def test_static_assets_are_served_locally(client, path, media_type):
    response = client.get(path)

    assert response.status_code == 200
    assert media_type in response.headers["content-type"]


def test_every_response_carries_the_security_headers(client):
    for response in (
        client.get("/"),
        client.post("/api/design/notch"),
        client.get("/static/app.css"),
    ):
        assert "script-src 'self'" in response.headers["content-security-policy"]
        assert response.headers["x-content-type-options"] == "nosniff"
        assert response.headers["referrer-policy"] == "no-referrer"


def test_page_loads_nothing_from_other_origins(client):
    page = client.get("/").text

    assert "http://" not in page and "https://" not in page
    assert "<script>" not in page and "style=" not in page


def test_api_docs_are_not_exposed(client):
    assert client.get("/docs").status_code == 404
    assert client.get("/openapi.json").status_code == 404


def test_output_keeps_its_leading_blank_line_in_the_browser(client):
    form = {"filter_type": "butterworth", "topology": "pi", "frequency": "10MHz"}

    fragment = client.post("/design/lowpass", data=form, headers=HTMX).text

    # The parser drops the first newline after <pre>; the CLI text itself starts with one.
    assert 'aria-label="Calculator output">\n\n' in fragment


def test_vendored_htmx_matches_its_recorded_hash():
    import hashlib
    from pathlib import Path

    import filter_lib.web

    static = Path(filter_lib.web.__file__).parent / "static"
    recorded = next(
        line.split(":", 1)[1].strip()
        for line in (static / "LICENSE-htmx.txt").read_text(encoding="utf-8").splitlines()
        if line.startswith("htmx.min.js SHA-256:")
    )

    assert hashlib.sha256((static / "htmx.min.js").read_bytes()).hexdigest() == recorded


def test_htmx_may_not_evaluate_code_or_run_swapped_scripts(client):
    import html
    import json
    import re

    page = client.get("/").text
    config = json.loads(
        html.unescape(re.search(r'name="htmx-config" content=\'([^\']+)\'', page).group(1))
    )

    assert config["allowEval"] is False
    assert config["allowScriptTags"] is False
    assert config["selfRequestsOnly"] is True
