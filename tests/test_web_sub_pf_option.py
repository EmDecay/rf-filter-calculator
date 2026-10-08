"""The web "Allow capacitors below 1 pF" option: parsing, page, result, and CLI parity.

The option maps onto ``DesignRequest.allow_sub_pf``; every document it changes must be
byte-identical to ``filter-calc ... --allow-sub-pf`` and every document it cannot change
must equal the CLI's output without it.
"""

from __future__ import annotations

import pytest

pytest.importorskip("fastapi")

from filter_lib.design.render_options import SUB_PF_NEEDS_ESERIES_MESSAGE  # noqa: E402
from filter_lib.shared.eseries import SUB_PF_OPTION_LABEL  # noqa: E402
from filter_lib.web.form_parsing import parse_design_form  # noqa: E402
from tests.cli_parity_helpers import cli_stdout  # noqa: E402
from tests.web_helpers import HTMX, output_text, web_client  # noqa: E402

# Designs whose capacitors fall below 1 pF (LP: 636.62 fF; BP: coupling and end caps).
LP = {"filter_type": "butterworth", "topology": "pi", "frequency": "5GHz", "components": "3"}
LP_ARGV = ("lp", "bw", "pi", "5GHz", "-n", "3")
BP = {"filter_type": "butterworth", "frequency": "500MHz", "bandwidth": "10MHz"}
BP_ARGV = ("bp", "bw", "top", "-f", "500MHz", "-b", "10MHz")
DESIGNS = [("lowpass", LP, LP_ARGV), ("bandpass", BP, BP_ARGV)]
DESIGN_IDS = ["lowpass", "bandpass"]
ON = {"allow_sub_pf": "on"}


@pytest.fixture(scope="module")
def client():
    with web_client() as test_client:
        yield test_client


@pytest.mark.parametrize("category, form, _argv", DESIGNS, ids=DESIGN_IDS)
def test_the_box_maps_onto_the_design_request(category, form, _argv):
    assert parse_design_form(category, form).request.allow_sub_pf is False
    assert parse_design_form(category, {**form, **ON}).request.allow_sub_pf is True


@pytest.mark.parametrize("category, form, _argv", DESIGNS, ids=DESIGN_IDS)
def test_without_standard_values_the_shared_message_is_raised(category, form, _argv):
    with pytest.raises(ValueError) as caught:
        parse_design_form(category, {**form, **ON, "eseries": "none"})

    assert str(caught.value) == SUB_PF_NEEDS_ESERIES_MESSAGE


@pytest.mark.parametrize("path", ["/api/design/lowpass", "/export/lowpass/response-json"])
def test_every_route_gives_the_same_answer_without_standard_values(client, path):
    response = client.post(path, data={**LP, **ON, "eseries": "none"})

    assert (response.status_code, response.json()) == (
        400,
        {"error": SUB_PF_NEEDS_ESERIES_MESSAGE},
    )


def test_the_design_view_shows_that_message(client):
    response = client.post("/design/lowpass", data={**LP, **ON, "eseries": "none"}, headers=HTMX)

    assert response.status_code == 400
    escaped = SUB_PF_NEEDS_ESERIES_MESSAGE.replace('"', "&#34;")
    assert f'<p class="notice__message">{escaped}</p>' in response.text


def test_the_form_offers_the_option_unticked_next_to_the_standard_values(client):
    page = client.get("/?category=lowpass").text

    assert f'<span class="check__label">{SUB_PF_OPTION_LABEL}</span>' in page
    assert 'name="allow_sub_pf" checked' not in page
    assert page.index("Standard capacitor values") < page.index(SUB_PF_OPTION_LABEL)


def test_the_result_shows_a_sub_pf_part_chosen(client):
    off = output_text(client.post("/design/lowpass", data=LP, headers=HTMX).text)
    on = output_text(client.post("/design/lowpass", data={**LP, **ON}, headers=HTMX).text)

    assert "Use:            none (below 1 pF; see warning)" in off
    assert "Use:            75.00 fF || 560.00 fF (-0.3%)" in on
    assert "below 1 pF" not in on.split("Toroid")[0]


@pytest.mark.parametrize("category, form, argv", DESIGNS, ids=DESIGN_IDS)
def test_table_is_the_cli_output(monkeypatch, capsys, client, category, form, argv):
    expected = cli_stdout(monkeypatch, capsys, *argv, "--allow-sub-pf")

    response = client.post(f"/design/{category}", data={**form, **ON}, headers=HTMX)

    assert response.status_code == 200
    assert output_text(response.text) + "\n" == expected


CHANGED_EXPORTS = {
    "json": ("--format", "json"),
    "csv": ("--format", "csv"),
    "spice-nominal": ("--format", "spice", "--spice-realization", "nominal-build"),
}
UNCHANGED_EXPORTS = {
    "spice-exact": ("--format", "spice", "--spice-realization", "exact"),
    "response-csv": ("--plot-data", "csv"),
}


@pytest.mark.parametrize("kind", list(CHANGED_EXPORTS))
@pytest.mark.parametrize("category, form, argv", DESIGNS, ids=DESIGN_IDS)
def test_downloads_it_changes_match_the_cli_flag(
    monkeypatch, capsys, client, category, form, argv, kind
):
    expected = cli_stdout(monkeypatch, capsys, *argv, *CHANGED_EXPORTS[kind], "--allow-sub-pf")
    without = cli_stdout(monkeypatch, capsys, *argv, *CHANGED_EXPORTS[kind])

    response = client.post(f"/export/{category}/{kind}", data={**form, **ON})

    assert response.status_code == 200
    assert response.content.decode() == expected
    assert expected != without


@pytest.mark.parametrize("kind", list(UNCHANGED_EXPORTS))
@pytest.mark.parametrize("category, form, argv", DESIGNS, ids=DESIGN_IDS)
def test_downloads_of_calculated_values_are_unchanged(
    monkeypatch, capsys, client, category, form, argv, kind
):
    """The CLI refuses the flag here; the web form is shared, so the box is ignored."""
    expected = cli_stdout(monkeypatch, capsys, *argv, *UNCHANGED_EXPORTS[kind])

    response = client.post(f"/export/{category}/{kind}", data={**form, **ON})

    assert response.status_code == 200
    assert response.content.decode() == expected


def test_build_simulation_json_matches_the_cli_flag(monkeypatch, capsys, client):
    flags = ("--sim-build", "--analysis-points", "101")
    expected = cli_stdout(
        monkeypatch, capsys, *LP_ARGV, *flags, "--format", "json", "--allow-sub-pf"
    )

    response = client.post(
        "/export/lowpass/json", data={**LP, **ON, "sim_build": "on", "build_grid_points": "101"}
    )

    assert response.status_code == 200
    assert response.content.decode() == expected
    assert '"allow_sub_pf": true' in expected
