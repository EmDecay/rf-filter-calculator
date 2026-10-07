"""Only the calculator's own page (or a script) can submit work to the local server."""

from __future__ import annotations

import pytest

from filter_lib.web.request_guard import CROSS_SITE_REFUSED, UNKNOWN_HOST_REFUSED, refusal

HOST = "127.0.0.1:8765"


def _headers(**values: str) -> dict[str, str]:
    return {"host": HOST, **{name.replace("_", "-"): value for name, value in values.items()}}


@pytest.mark.parametrize(
    "method, headers, expected",
    [
        ("POST", _headers(sec_fetch_site="same-origin"), None),
        ("POST", _headers(sec_fetch_site="none"), None),
        ("POST", _headers(sec_fetch_site="cross-site"), CROSS_SITE_REFUSED),
        ("POST", _headers(sec_fetch_site="same-site"), CROSS_SITE_REFUSED),
        # Sec-Fetch-Site wins over a matching Origin.
        (
            "POST",
            _headers(sec_fetch_site="cross-site", origin=f"http://{HOST}"),
            CROSS_SITE_REFUSED,
        ),
        ("POST", _headers(origin=f"http://{HOST}"), None),
        ("POST", _headers(origin="https://evil.example"), CROSS_SITE_REFUSED),
        ("POST", _headers(origin="http://127.0.0.1:9999"), CROSS_SITE_REFUSED),
        ("POST", _headers(origin="null"), CROSS_SITE_REFUSED),
        ("POST", _headers(), None),
        ("GET", _headers(sec_fetch_site="cross-site", origin="https://evil.example"), None),
    ],
    ids=[
        "same-origin",
        "typed-address",
        "cross-site",
        "same-site-other-port-or-subdomain",
        "fetch-site-wins",
        "matching-origin",
        "foreign-origin",
        "other-local-port",
        "opaque-origin",
        "script-without-headers",
        "navigation-get",
    ],
)
def test_submissions_must_come_from_the_page(method, headers, expected):
    assert refusal(method, headers, loopback_only=True) == expected


@pytest.mark.parametrize("host", ["127.0.0.1:8765", "localhost:8765", "[::1]:8765", "LOCALHOST"])
def test_loopback_hosts_are_accepted(host):
    assert refusal("GET", {"host": host}, loopback_only=True) is None


@pytest.mark.parametrize("host", ["evil.example:8765", "192.168.1.5:8765", "", "127.0.0.2"])
def test_other_hosts_are_refused_on_a_loopback_bind(host):
    assert refusal("GET", {"host": host}, loopback_only=True) == UNKNOWN_HOST_REFUSED


def test_a_non_loopback_bind_accepts_any_host_but_still_checks_origin():
    lan = {"host": "192.168.1.5:8765"}

    assert refusal("GET", lan, loopback_only=False) is None
    assert (
        refusal("POST", {**lan, "origin": "http://192.168.1.5:8765"}, loopback_only=False) is None
    )
    assert refusal("POST", {**lan, "origin": "https://evil.example"}, loopback_only=False) == (
        CROSS_SITE_REFUSED
    )


class TestRunningApp:
    @pytest.fixture(scope="class")
    def client(self):
        pytest.importorskip("fastapi")
        from tests.web_helpers import web_client

        with web_client() as test_client:
            yield test_client

    FORM = {"filter_type": "butterworth", "topology": "pi", "frequency": "10MHz"}

    @pytest.mark.parametrize(
        "path", ["/design/lowpass", "/api/design/lowpass", "/export/lowpass/json"]
    )
    def test_cross_site_posts_are_refused_before_any_work(self, monkeypatch, client, path):
        def never(*_args, **_kwargs):
            raise AssertionError("a refused request must not reach the calculator")

        monkeypatch.setattr("filter_lib.lowpass.calculate_butterworth", never)

        response = client.post(
            path, data=self.FORM, headers={"Origin": "https://evil.example", "HX-Request": "true"}
        )

        assert response.status_code == 403
        assert response.json() == {"error": CROSS_SITE_REFUSED}
        assert "script-src 'self'" in response.headers["content-security-policy"]

    def test_same_origin_posts_are_served(self, client):
        response = client.post(
            "/api/design/lowpass",
            data=self.FORM,
            headers={"Origin": "http://127.0.0.1:8765", "Sec-Fetch-Site": "same-origin"},
        )

        assert response.status_code == 200

    def test_a_rebound_host_name_is_refused(self, client):
        response = client.get("/", headers={"Host": "attacker.example:8765"})

        assert (response.status_code, response.json()) == (403, {"error": UNKNOWN_HOST_REFUSED})
