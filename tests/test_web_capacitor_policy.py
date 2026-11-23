"""The web capacitor grade, tolerance and stray fields, against the CLI.

Blank fields are the CLI with the flags left out; filled fields are the CLI flags. The
calculated-values SPICE download uses no standard capacitors, so it leaves them out, as
if their controls were disabled; the chosen-parts download uses them.
"""

from __future__ import annotations

import pytest

pytest.importorskip("fastapi")

from filter_lib.web.form_parsing import parse_design_form  # noqa: E402
from tests.cli_parity_helpers import cli_stdout  # noqa: E402
from tests.web_helpers import HTMX, output_text, web_client  # noqa: E402

LP = {"filter_type": "butterworth", "topology": "pi", "frequency": "146MHz", "components": "5"}
LP_ARGV = ("lp", "bw", "pi", "146MHz", "-n", "5")
POLICY_FIELDS = {
    "capacitor_grade": "tight",
    "capacitor_tolerance_pct": "3",
    "stray_capacitance": "0.1pF",
}
POLICY_FLAGS = (
    "--capacitor-grade",
    "tight",
    "--capacitor-tolerance",
    "3",
    "--stray-capacitance",
    "0.1pF",
)


@pytest.fixture(scope="module")
def client():
    with web_client() as test_client:
        yield test_client


def test_blank_fields_are_the_cli_defaults(monkeypatch, capsys, client):
    blank = {
        **LP,
        "capacitor_grade": "standard",
        "capacitor_tolerance_pct": "",
        "stray_capacitance": "",
    }
    expected = cli_stdout(monkeypatch, capsys, *LP_ARGV)

    response = client.post("/design/lowpass", data=blank, headers=HTMX)

    assert output_text(response.text) + "\n" == expected
    request = parse_design_form("lowpass", blank).request
    assert (request.capacitor_grade, request.capacitor_tolerance_pct) == ("standard", None)
    assert request.stray_capacitance_f == pytest.approx(0.2e-12, rel=1e-12, abs=0)


@pytest.mark.parametrize(
    ("kind", "flags"),
    [
        ("json", ("--format", "json")),
        ("csv", ("--format", "csv")),
        ("spice-nominal", ("--format", "spice", "--spice-realization", "nominal-build")),
    ],
)
def test_filled_fields_are_the_cli_flags_in_every_download(
    monkeypatch, capsys, client, kind, flags
):
    expected = cli_stdout(monkeypatch, capsys, *LP_ARGV, *POLICY_FLAGS, *flags)

    response = client.post(f"/export/lowpass/{kind}", data={**LP, **POLICY_FIELDS})

    assert response.status_code == 200
    assert response.content.decode() == expected


def test_the_calculated_values_deck_leaves_the_capacitor_options_out(monkeypatch, capsys, client):
    expected = cli_stdout(
        monkeypatch, capsys, *LP_ARGV, "--format", "spice", "--spice-realization", "exact"
    )

    response = client.post("/export/lowpass/spice-exact", data={**LP, **POLICY_FIELDS})

    assert response.status_code == 200
    assert response.content.decode() == expected


def test_the_page_offers_the_fields_outside_the_build_section(client):
    page = client.get("/").text
    build_start = page.index('class="group build"')

    for name in ("capacitor_grade", "capacitor_tolerance_pct", "stray_capacitance"):
        assert page.index(f'name="{name}"') < build_start, name
    assert 'data-option="capacitor_grade"' in page
    assert 'data-option="stray_capacitance"' in page
