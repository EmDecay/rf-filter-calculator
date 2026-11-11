"""Bound untrusted forms before decoding and synchronous numeric parsing."""

from __future__ import annotations

import asyncio
from urllib.parse import urlencode

import pytest

pytest.importorskip("fastapi")

from fastapi import HTTPException, Request  # noqa: E402

from filter_lib.web.form_parsing import form_defaults  # noqa: E402
from filter_lib.web.responses import (  # noqa: E402
    FORM_TOO_LARGE,
    MAX_FIELD_NAME_LENGTH,
    MAX_FIELD_VALUE_LENGTH,
    MAX_FORM_BODY_BYTES,
    MAX_FORM_FIELDS,
    form_fields,
)
from tests.web_helpers import web_client  # noqa: E402

PATHS = ["/design/lowpass", "/api/design/lowpass", "/export/lowpass/json"]


@pytest.fixture(scope="module")
def client():
    with web_client() as test_client:
        yield test_client


def never(*_args, **_kwargs):
    raise AssertionError("oversized input must be rejected before parsing")


@pytest.mark.parametrize("path", PATHS)
@pytest.mark.parametrize("streamed", [False, True])
def test_body_limit_precedes_form_decoding(monkeypatch, client, path, streamed):
    monkeypatch.setattr(Request, "form", never)
    body = b"frequency=" + b"1" * MAX_FORM_BODY_BYTES
    response = client.post(
        path,
        content=iter([body[:100], body[100:]]) if streamed else body,
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    assert response.status_code == 413
    assert response.json() == {"detail": FORM_TOO_LARGE}
    assert "content-security-policy" in response.headers
    if streamed:
        assert "content-length" not in response.request.headers


@pytest.mark.parametrize("path", PATHS)
@pytest.mark.parametrize("multipart", [False, True])
@pytest.mark.parametrize(
    "fields",
    [
        [("frequency", "1" * (MAX_FIELD_VALUE_LENGTH + 1))],
        [("x" * (MAX_FIELD_NAME_LENGTH + 1), "1")],
        [("frequency", "1")] * (MAX_FORM_FIELDS + 1),
        # A last-value-wins dictionary must not conceal an oversized earlier field.
        [("frequency", "1" * (MAX_FIELD_VALUE_LENGTH + 1)), ("frequency", "10MHz")],
    ],
    ids=["value", "name", "duplicate-count", "replaced-value"],
)
def test_field_limits_precede_design_parsing(monkeypatch, client, path, multipart, fields):
    monkeypatch.setattr("filter_lib.web.routes_design.parse_design_form", never)
    monkeypatch.setattr("filter_lib.web.routes_export.parse_design_form", never)
    if multipart:
        response = client.post(path, files=[(name, (None, value)) for name, value in fields])
    else:
        response = client.post(
            path,
            content=urlencode(fields),
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )
    assert response.status_code == 413
    assert response.json() == {"detail": FORM_TOO_LARGE}


def request_from_chunks(chunks):
    messages = iter(chunks)

    async def receive():
        return next(messages)

    return Request(
        {"type": "http", "headers": [(b"content-type", b"application/x-www-form-urlencoded")]},
        receive,
    )


def test_stream_stops_at_overflow_without_reading_the_remainder(monkeypatch):
    monkeypatch.setattr(Request, "form", never)
    request = request_from_chunks(
        [
            {"type": "http.request", "body": b"x" * MAX_FORM_BODY_BYTES, "more_body": True},
            {"type": "http.request", "body": b"x", "more_body": True},
            # No final chunk: continuing to consume the stream fails the test.
        ]
    )
    with pytest.raises(HTTPException) as exc:
        asyncio.run(form_fields(request))
    assert exc.value.status_code == 413


def test_exact_limits_and_last_value_wins_are_accepted():
    fields = [
        ("x" * MAX_FIELD_NAME_LENGTH, "v" * MAX_FIELD_VALUE_LENGTH),
        ("toroid_build", "off"),
        ("toroid_build", "on"),
        *[("extra", "v")] * (MAX_FORM_FIELDS - 3),
    ]
    body = urlencode(fields).encode()
    # Empty URL-encoded segments pad the body without adding fields.
    body += b"&" * (MAX_FORM_BODY_BYTES - len(body))
    request = request_from_chunks([{"type": "http.request", "body": body}])
    result = asyncio.run(form_fields(request))
    assert result == {
        "x" * MAX_FIELD_NAME_LENGTH: "v" * MAX_FIELD_VALUE_LENGTH,
        "toroid_build": "on",
        "extra": "v",
    }


@pytest.mark.parametrize("category", ["lowpass", "highpass", "bandpass"])
def test_complete_forms_and_export_snapshots_remain_accepted(client, category):
    fields = form_defaults(category)
    # Exports include both submitted values and visible controls for option handling.
    fields.update({f"visible.{name}": value for name, value in list(fields.items())})
    response = client.post(f"/export/{category}/json", data=fields)
    assert response.status_code == 200
    assert response.json()
