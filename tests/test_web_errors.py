"""Invalid web input fails with HTTP 400 and the CLI's own error message.

Where the CLI reports the problem as ``Error: <message>``, the web message is compared
with that live stderr line. Mode rules the CLI enforces as argparse usage errors (build
analysis with CSV or quiet output) have web-specific wording owned by ``RenderOptions``.
"""

from __future__ import annotations

import pytest

pytest.importorskip("fastapi")

from filter_lib.design.render_options import BUILD_NEEDS_ESERIES_MESSAGE  # noqa: E402
from filter_lib.shared.build_types import (  # noqa: E402
    RESONATOR_AND_COMPONENT_Q_MESSAGE,
    SEED_NEEDS_SAMPLES_MESSAGE,
)
from filter_lib.shared.cli_aliases import RIPPLE_RANGE_MESSAGE  # noqa: E402
from tests.cli_parity_helpers import cli_error_message, cli_stderr, cli_stdout  # noqa: E402
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
    # The range is reported before the Chebyshev odd-count rule, as the CLI does.
    (
        "even-chebyshev-bandpass-out-of-range",
        "bandpass",
        {**BP, "filter_type": "chebyshev", "resonators": "10"},
        ("bp", "ch", "top", "-f", "14MHz", "-b", "500kHz", "-n", "10"),
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
            BUILD_NEEDS_ESERIES_MESSAGE,
        ),
        (
            {**BP, "sim_build": "on", "qu": "200", "build_inductor_q": "100"},
            RESONATOR_AND_COMPONENT_Q_MESSAGE,
        ),
        ({**BP, "bandwidth": ""}, "Bandwidth is required"),
        ({**LP, "frequency": " "}, "Cutoff frequency is required"),
        ({**LP, "components": "three"}, "Number of components must be a whole number"),
        ({**LP, "filter_type": "chebyshev", "ripple": "lots"}, RIPPLE_RANGE_MESSAGE),
        ({**LP, "output_format": "spice"}, "Output format must be one of: table, quiet, json, csv"),
        ({**LP, "topology": "x"}, "Topology must be one of: pi, t"),
        ({**LP, "sim_build": "on", "build_seed": "1.5"}, "Random seed must be a whole number"),
        (
            {**LP, "sim_build": "on", "build_seed": "5", "build_sample_count": "0"},
            SEED_NEEDS_SAMPLES_MESSAGE,
        ),
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
        "seed-without-random-cases",
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
    assert response.json()["error"] == (
        '"SPICE – chosen parts" needs an E-series (E12, E24, or E96) to choose standard '
        'capacitor values; or download "SPICE – calculated values"'
    )


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
    assert "script-src 'self'" in response.headers["content-security-policy"]
    assert response.headers["x-content-type-options"] == "nosniff"


@pytest.mark.parametrize(
    "output_format, message",
    [
        ("csv", "Build simulation needs table or JSON output"),
        ("quiet", "Build simulation cannot be used with values-only output"),
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
    "{0} {1} no effect on this output. Resonator Q values are used only in table and JSON "
    "output and in the chosen-parts (nominal-build) SPICE deck; remove {0} or change the output"
)


@pytest.mark.parametrize("output_format", ["quiet", "csv"])
def test_design_view_refuses_loss_q_its_output_cannot_show(client, output_format):
    form = {**BP, "qu": "200", "ql": "150", "output_format": output_format}

    response = client.post("/design/bandpass", data=form, headers=HTMX)

    assert response.status_code == 400
    assert LOSS_Q_MESSAGE.format("Qu, QL", "have") in response.text


@pytest.mark.parametrize("kind", ["csv", "spice-exact"])
def test_downloads_refuse_loss_q_they_cannot_show(monkeypatch, capsys, client, kind):
    flags = {
        "csv": ("--format", "csv"),
        "spice-exact": ("--format", "spice", "--spice-realization", "exact"),
    }[kind]
    cli_err = cli_stderr(
        monkeypatch, capsys, "bp", "bw", "top", "-f", "14MHz", "-b", "500kHz", "--qc", "900", *flags
    )

    response = client.post(f"/export/bandpass/{kind}", data={**BP, "qc": "900"})

    assert response.status_code == 400
    assert response.json() == {"error": LOSS_Q_MESSAGE.format("QC", "has")}
    # The CLI refuses the same combination, naming its flag instead of the form label.
    assert LOSS_Q_MESSAGE.format("--qc", "has") in cli_err


@pytest.mark.parametrize("data_format", ["json", "csv"])
def test_response_downloads_leave_out_loss_q_like_the_wizard(
    monkeypatch, capsys, client, data_format
):
    # Qu/QL/QC never change the ideal response, so the download equals the CLI's
    # --plot-data output for the same design without them.
    cli_out = cli_stdout(
        monkeypatch,
        capsys,
        "bp",
        "bw",
        "top",
        "-f",
        "14MHz",
        "-b",
        "500kHz",
        "--plot-data",
        data_format,
    )

    response = client.post(f"/export/bandpass/response-{data_format}", data={**BP, "qu": "200"})

    assert response.status_code == 200
    assert response.text == cli_out


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


@pytest.mark.parametrize(
    "form, message",
    [
        (
            {**LP, "sim_build": "on", "build_capacitor_tolerance_pct": "100"},
            "Capacitor tolerance must be at least 0% and less than 100%",
        ),
        (
            {**LP, "sim_build": "on", "build_inductor_q": "0"},
            "Inductor Q must be between 0.01 and 1e9",
        ),
        (
            {**LP, "sim_build": "on", "build_sample_count": "10001"},
            "The number of extra random tolerance cases must be a whole number from 0 to 10000",
        ),
        (
            {**LP, "sim_build": "on", "build_grid_points": "50"},
            "Frequency points must be a whole number from 51 to 5001",
        ),
        (
            {**LP, "sim_build": "on", "build_reference_frequency": "abc"},
            "Invalid frequency at which the Q values apply: abc (use a number with an optional "
            "k, M, or G suffix, e.g. 14.2MHz)",
        ),
        (
            {**BP, "resonator_impedance": "75", "resonator_inductance": "1uH"},
            "Set either the resonator impedance or the resonator inductance, not both",
        ),
        ({**BP, "qu": "100", "ql": "200"}, "Give either Qu or QL/QC, not both"),
        ({**BP, "qu": "0"}, "Qu must be between 0.01 and 1e9"),
    ],
    ids=[
        "capacitor-tolerance",
        "inductor-q",
        "random-cases",
        "frequency-points",
        "q-frequency",
        "two-tank-settings",
        "qu-and-ql",
        "qu-range",
    ],
)
def test_field_rules_name_the_field_in_plain_words(client, form, message):
    """No internal field name (``capacitor_tolerance_pct``) or interval notation is shown."""
    category = "bandpass" if "bandwidth" in form else "lowpass"

    response = client.post(f"/api/design/{category}", data=form)

    assert (response.status_code, response.json()) == (400, {"error": message})
    assert "_" not in message


def test_loss_q_download_rules_come_from_the_shared_rule():
    """Refused for CSV and the calculated-values deck; left out of response data."""
    from filter_lib.web.routes_export import LOSS_Q_DROPPED, LOSS_Q_HIDDEN

    assert LOSS_Q_HIDDEN == {"csv", "spice-exact"}
    assert LOSS_Q_DROPPED == {"response-json", "response-csv"}


def test_a_json_download_refuses_a_seed_without_random_cases(client):
    """The visible build reaches the JSON download, with the CLI's --seed rule."""
    form = {**LP, "output_format": "csv", "visible.sim_build": "on", "build_seed": "4"}

    response = client.post("/export/lowpass/json", data=form)

    assert response.status_code == 400
    assert response.json() == {"error": SEED_NEEDS_SAMPLES_MESSAGE}
