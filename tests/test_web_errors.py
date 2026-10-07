"""Invalid web input fails with HTTP 400 and the CLI's own error message.

Where the CLI reports the problem as ``Error: <message>``, the web message is compared
with that live stderr line. Mode rules the CLI enforces as argparse usage errors (build
analysis with CSV or quiet output) have web-specific wording owned by ``RenderOptions``.
"""

from __future__ import annotations

import pytest

pytest.importorskip("fastapi")

from tests.cli_parity_helpers import cli_error_message, cli_stderr  # noqa: E402
from tests.web_helpers import BASE_URL, HTMX, web_client  # noqa: E402

LP = {"filter_type": "butterworth", "topology": "pi", "frequency": "10MHz"}
BP = {"filter_type": "butterworth", "frequency": "14MHz", "bandwidth": "500kHz"}


@pytest.fixture(scope="module")
def client():
    with web_client() as test_client:
        yield test_client


CLI_MATCHED_CASES = [
    ("invalid-frequency", "lowpass", {**LP, "frequency": "abc"}, ("lp", "bw", "pi", "abc")),
    (
        "invalid-impedance",
        "lowpass",
        {**LP, "impedance": "abc"},
        ("lp", "bw", "pi", "10MHz", "-z", "abc"),
    ),
    (
        "components-range",
        "highpass",
        {**LP, "components": "12"},
        ("hp", "bw", "pi", "10MHz", "-n", "12"),
    ),
    (
        "ripple-over-3-db",
        "lowpass",
        {**LP, "filter_type": "chebyshev", "ripple": "3.5"},
        ("lp", "ch", "pi", "10MHz", "-r", "3.5"),
    ),
    (
        "ripple-not-positive",
        "highpass",
        {**LP, "filter_type": "chebyshev", "ripple": "0"},
        ("hp", "ch", "pi", "10MHz", "-r", "0"),
    ),
    (
        "even-chebyshev-bandpass",
        "bandpass",
        {**BP, "filter_type": "chebyshev", "resonators": "4"},
        ("bp", "ch", "top", "-f", "14MHz", "-b", "500kHz", "-n", "4"),
    ),
    (
        "bandwidth-too-wide",
        "bandpass",
        {**BP, "bandwidth": "20MHz"},
        ("bp", "bw", "top", "-f", "14MHz", "-b", "20MHz"),
    ),
    (
        "edges-reversed",
        "bandpass",
        {**BP, "band_spec": "edges", "f_low": "14.3MHz", "f_high": "14MHz"},
        ("bp", "bw", "top", "--fl", "14.3MHz", "--fh", "14MHz"),
    ),
    (
        "bad-tank-inductance",
        "bandpass",
        {**BP, "resonator_inductance": "1.2 furlongs"},
        (
            "bp",
            "bw",
            "top",
            "-f",
            "14MHz",
            "-b",
            "500kHz",
            "--resonator-inductance",
            "1.2 furlongs",
        ),
    ),
    (
        "bad-source-resistance",
        "lowpass",
        {**LP, "sim_build": "on", "build_source_resistance": "-5"},
        ("lp", "bw", "pi", "10MHz", "--sim-build", "--source-resistance", "-5"),
    ),
]


@pytest.mark.parametrize(
    "category, form, argv",
    [c[1:] for c in CLI_MATCHED_CASES],
    ids=[c[0] for c in CLI_MATCHED_CASES],
)
def test_api_errors_carry_the_cli_message(monkeypatch, capsys, client, category, form, argv):
    expected = cli_error_message(monkeypatch, capsys, *argv)

    response = client.post(f"/api/design/{category}", data=form)

    assert response.status_code == 400
    assert response.json() == {"error": expected}


@pytest.mark.parametrize(
    "category, form, argv",
    [c[1:] for c in CLI_MATCHED_CASES],
    ids=[c[0] for c in CLI_MATCHED_CASES],
)
def test_design_view_shows_the_cli_message(monkeypatch, capsys, client, category, form, argv):
    expected = cli_error_message(monkeypatch, capsys, *argv)

    response = client.post(f"/design/{category}", data=form, headers=HTMX)

    assert response.status_code == 400
    assert 'role="alert"' in response.text
    assert f'<p class="notice__message">{expected}</p>' in response.text


@pytest.mark.parametrize(
    "form, message",
    [
        (
            {**LP, "sim_build": "on", "eseries": "none"},
            "Realized-build analysis requires an E-series",
        ),
        (
            {**BP, "sim_build": "on", "qu": "200", "build_inductor_q": "100"},
            "Use either resonator Q (Qu, QL, QC) or component Q (inductor, capacitor), "
            "not both loss models",
        ),
        ({**BP, "bandwidth": ""}, "Bandwidth is required"),
        ({**LP, "frequency": " "}, "Frequency is required"),
        ({**LP, "components": "three"}, "Components must be a whole number"),
        ({**LP, "filter_type": "chebyshev", "ripple": "lots"}, "Ripple must be a number"),
        ({**LP, "output_format": "spice"}, "Output format must be one of: table, quiet, json, csv"),
        ({**LP, "topology": "x"}, "Topology must be one of: pi, t"),
        ({**LP, "sim_build": "on", "build_seed": "1.5"}, "Seed must be a whole number"),
    ],
    ids=[
        "build-without-eseries",
        "two-loss-models",
        "missing-bandwidth",
        "blank-frequency",
        "non-integer-components",
        "non-numeric-ripple",
        "unknown-format",
        "unknown-topology",
        "non-integer-seed",
    ],
)
def test_web_only_rules_are_reported_as_bad_requests(client, form, message):
    category = "bandpass" if "bandwidth" in form else "lowpass"

    response = client.post(f"/api/design/{category}", data=form)

    assert response.status_code == 400
    assert response.json() == {"error": message}


def test_markup_in_an_error_message_is_escaped(client):
    response = client.post(
        "/design/lowpass", data={**LP, "frequency": "<b>10MHz</b>"}, headers=HTMX
    )

    assert response.status_code == 400
    assert "Invalid frequency: &lt;b&gt;10MHz&lt;/b&gt;" in response.text
    assert "<b>10MHz" not in response.text


@pytest.mark.parametrize("path", ["/design/notch", "/api/design/notch", "/export/notch/json"])
def test_unknown_category_is_a_bad_request(client, path):
    response = client.post(path, data=LP, headers=HTMX)

    assert response.status_code == 400
    assert "Unknown filter category" in response.text


def test_unknown_category_tab_is_a_bad_request(client):
    assert client.get("/form/notch").json() == {"error": "Unknown filter category"}
    assert client.get("/?category=notch").status_code == 400


def test_unknown_export_is_a_bad_request(client):
    response = client.post("/export/lowpass/pdf", data=LP)

    assert (response.status_code, response.json()) == (400, {"error": "Unknown export: pdf"})


def test_nominal_spice_needs_an_eseries(client):
    response = client.post("/export/lowpass/spice-nominal", data={**LP, "eseries": "none"})

    assert response.status_code == 400
    assert response.json()["error"].startswith("Nominal-build SPICE requires selected capacitor")


def test_failed_submission_without_javascript_keeps_the_inputs(client):
    form = {**LP, "frequency": "-5MHz", "components": "7", "impedance": "75"}

    response = client.post("/design/lowpass", data=form)

    assert response.status_code == 400
    assert "<!doctype html>" in response.text
    assert 'role="alert"' in response.text
    assert 'value="-5MHz"' in response.text
    assert 'value="7"' in response.text
    assert 'value="75"' in response.text


def test_an_error_without_a_message_is_named_by_its_type(monkeypatch, client):
    def fail(*_args, **_kwargs):
        raise ValueError("   ")

    monkeypatch.setattr("filter_lib.lowpass.calculate_butterworth", fail)

    response = client.post("/api/design/lowpass", data=LP)

    assert (response.status_code, response.json()) == (400, {"error": "ValueError"})


def test_unexpected_failures_are_not_reported_as_input_errors(monkeypatch):
    def crash(*_args, **_kwargs):
        raise RuntimeError("bug")

    monkeypatch.setattr("filter_lib.lowpass.calculate_butterworth", crash)
    from fastapi.testclient import TestClient

    from filter_lib.web import create_app

    with TestClient(create_app(), base_url=BASE_URL, raise_server_exceptions=False) as test_client:
        response = test_client.post("/design/lowpass", data=LP, headers=HTMX)

    assert response.status_code == 500
    assert "bug" not in response.text


@pytest.mark.parametrize(
    "output_format, message",
    [
        ("csv", "Realized-build analysis is supported only with table or JSON component output"),
        ("quiet", "Realized-build analysis cannot be combined with quiet output"),
    ],
)
def test_design_view_rejects_a_build_its_output_cannot_show(client, output_format, message):
    form = {**LP, "sim_build": "on", "output_format": output_format}

    response = client.post("/design/lowpass", data=form, headers=HTMX)

    assert response.status_code == 400
    assert f'<p class="notice__message">{message}</p>' in response.text


@pytest.mark.parametrize(
    "path",
    [
        "/api/design/lowpass",
        "/export/lowpass/json",
        "/export/lowpass/csv",
        "/export/lowpass/spice-nominal",
    ],
)
def test_downloads_do_not_depend_on_the_page_format(client, path):
    form = {**LP, "sim_build": "on", "build_grid_points": "51", "output_format": "csv"}

    assert client.post(path, data=form).status_code == 200


def test_hidden_ripple_is_ignored_for_non_chebyshev_types(client):
    response = client.post("/api/design/lowpass", data={**LP, "ripple": "left over text"})

    assert response.status_code == 200


LOSS_Q_MESSAGE = (
    "Loss-Q input {} is not represented by this output mode; "
    "use table, JSON, or nominal-build SPICE"
)


@pytest.mark.parametrize("output_format", ["quiet", "csv"])
def test_design_view_refuses_loss_q_its_output_cannot_show(client, output_format):
    form = {**BP, "qu": "200", "ql": "150", "output_format": output_format}

    response = client.post("/design/bandpass", data=form, headers=HTMX)

    assert response.status_code == 400
    assert LOSS_Q_MESSAGE.format("Qu, QL") in response.text


@pytest.mark.parametrize("kind", ["csv", "spice-exact", "response-json", "response-csv"])
def test_downloads_refuse_loss_q_they_cannot_show(monkeypatch, capsys, client, kind):
    flags = {
        "csv": ("--format", "csv"),
        "spice-exact": ("--format", "spice", "--spice-realization", "exact"),
        "response-json": ("--plot-data", "json"),
        "response-csv": ("--plot-data", "csv"),
    }[kind]
    cli_err = cli_stderr(
        monkeypatch, capsys, "bp", "bw", "top", "-f", "14MHz", "-b", "500kHz", "--qc", "900", *flags
    )

    response = client.post(f"/export/bandpass/{kind}", data={**BP, "qc": "900"})

    assert response.status_code == 400
    assert response.json() == {"error": LOSS_Q_MESSAGE.format("QC")}
    # The CLI refuses the same combination, naming its flag instead of the form label.
    assert LOSS_Q_MESSAGE.format("--qc") in cli_err


@pytest.mark.parametrize(
    "path, extra",
    [
        ("/design/bandpass", {"output_format": "table"}),
        ("/design/bandpass", {"output_format": "json"}),
        ("/api/design/bandpass", {}),
        ("/export/bandpass/json", {}),
        ("/export/bandpass/spice-nominal", {}),
    ],
)
def test_outputs_that_show_the_loss_model_accept_loss_q(client, path, extra):
    response = client.post(path, data={**BP, "qu": "200", **extra}, headers=HTMX)

    assert response.status_code == 200
