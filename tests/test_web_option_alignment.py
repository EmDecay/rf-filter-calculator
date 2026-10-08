"""The web form offers the CLI's options, defaults, and rules, and downloads match the result.

Covers the controls that cannot apply (disabled by the page from the shared rule, refused
by the server with the same reason), the ticked-by-default toroid-winding build box, the
pre-filled defaults, and downloads that post the inputs of the result shown.
"""

from __future__ import annotations

import html
import json
import re
from pathlib import Path

import pytest

pytest.importorskip("fastapi")

from markupsafe import escape  # noqa: E402

from filter_lib.design.option_applicability import (  # noqa: E402
    LOSS_Q,
    LOSS_Q_DISABLED_MESSAGE,
    OPTIONS,
    RAW_NEEDS_TABLE_MESSAGE,
    SUB_PF_RAW_MESSAGE,
    SUB_PF_VALUES_ONLY_MESSAGE,
    TEXT_PLOT_NEEDS_TABLE_MESSAGE,
    TOROID_DETAIL_NEEDS_TABLE_MESSAGE,
    OutputChoices,
    inapplicable_options,
)
from filter_lib.shared.build_types import BuildConfig  # noqa: E402
from filter_lib.web.form_parsing import form_defaults, parse_design_form  # noqa: E402
from filter_lib.web.option_states import PAGE_FORMATS, option_states, state_key  # noqa: E402
from filter_lib.wizard.state import FilterState  # noqa: E402
from tests.cli_parity_helpers import cli_stderr, cli_stdout  # noqa: E402
from tests.web_helpers import HTMX, output_text, web_client  # noqa: E402

LP = {"filter_type": "butterworth", "topology": "pi", "frequency": "10MHz"}
APP_JS = Path(__file__).resolve().parents[1] / "filter_lib" / "web" / "static" / "app.js"
STALE_NOTICE = "Inputs changed — select Design filter to update the result and downloads."
_STATES = re.compile(r'data-option-states="([^"]*)"')
_SNAPSHOT_FORM = re.compile(r'<form class="downloads__buttons" id="result-inputs".*?</form>', re.S)
_HIDDEN = re.compile(r'<input type="hidden" name="([^"]+)" value="([^"]*)">')


@pytest.fixture(scope="module")
def client():
    with web_client() as test_client:
        yield test_client


def _snapshot(fragment: str) -> dict[str, str]:
    """The inputs a result's download buttons post."""
    match = _SNAPSHOT_FORM.search(fragment)
    assert match, fragment[-1500:]
    return {name: html.unescape(value) for name, value in _HIDDEN.findall(match.group(0))}


# Options that cannot apply -----------------------------------------------------------


def test_the_form_carries_the_shared_rule_for_every_combination(client):
    page = client.get("/").text

    states = json.loads(html.unescape(_STATES.search(page).group(1)))

    assert states == option_states()
    assert len(states["states"]) == len(PAGE_FORMATS) * 2**4
    quiet = states["states"][state_key("quiet", False, False, False, False)]
    expected = inapplicable_options(OutputChoices(output_format="quiet"))
    assert {option: states["reasons"][i] for option, i in quiet.items()} == expected


def test_every_option_has_controls_and_a_reason_line(client):
    page = client.get("/?category=bandpass").text

    for option in OPTIONS:
        assert re.search(
            rf'data-option="{option}" aria-describedby="([^"]* )?reason-{option}"', page
        ), option
        assert (
            f'<p class="field__reason" id="reason-{option}" data-reason-for="{option}" hidden></p>'
            in page
        )


def test_resonator_q_fields_share_the_loss_q_reason(client):
    page = client.get("/?category=bandpass").text

    for name in ("qu", "ql", "qc"):
        assert re.search(rf'name="{name}"[^>]*data-option="loss_q"', page), name
    assert 'aria-describedby="f-qu-help reason-loss_q"' in page
    assert 'data-option="loss_q"' not in client.get("/?category=lowpass").text


def test_disabled_resonator_q_says_which_outputs_use_it_not_to_remove_it(client):
    """A disabled field cannot be cleared, so its reason never asks for that."""
    states = json.loads(html.unescape(_STATES.search(client.get("/?category=bandpass").text)[1]))

    for output_format in ("quiet", "csv"):
        entry = states["states"][state_key(output_format, False, False, False, False)]
        assert states["reasons"][entry[LOSS_Q]] == LOSS_Q_DISABLED_MESSAGE
    assert "remove" not in LOSS_Q_DISABLED_MESSAGE.lower()


def test_unavailable_options_are_announced_in_a_polite_live_region(client):
    """Disabled controls leave the tab order; their reasons are announced and described."""
    page = client.get("/").text
    script = APP_JS.read_text()

    assert re.search(
        r'<p class="visually-hidden" id="option-status" role="status" aria-live="polite" '
        r"data-option-status></p>",
        page,
    )
    assert 'querySelector("[data-option-status]")' in script
    assert "announceUnavailable(form, table, state);" in script
    # Each reason stays tied to its control (checked for every option above).
    assert 'aria-describedby="reason-eseries"' in page


def test_only_the_table_detail_toroid_choices_can_be_disabled(client):
    page = client.get("/").text

    for value in ("full", "compact"):
        assert f'name="toroids" value="{value}" data-option="toroid_detail"' in page
    for value in ("best", "none"):
        assert re.search(rf'name="toroids" value="{value}"( checked)?>', page)


def test_the_script_builds_the_same_state_key():
    """``app.js`` reads the five choices in ``state_key``'s order."""
    script = APP_JS.read_text()
    body = script[script.index("function stateKey") : script.index("function refreshOptions")]
    names = ["output_format", "eseries", "raw", "sim_build", "toroids"]

    positions = [body.index(f'"{name}"') for name in names]

    assert positions == sorted(positions)
    assert '=== "none"' in body


# The server refuses what the page disables, with the same reason, as the CLI does.
REFUSED = [
    ("plot-json", {"output_format": "json", "plot": "on"}, ("--plot", "--format", "json")),
    ("raw-csv", {"output_format": "csv", "raw": "on"}, ("--raw", "--format", "csv")),
    ("detail-quiet", {"output_format": "quiet", "toroids": "full"}, ("-q", "--toroid-full")),
    ("sub-pf-quiet", {"output_format": "quiet", "allow_sub_pf": "on"}, ("-q", "--allow-sub-pf")),
    ("sub-pf-raw", {"raw": "on", "allow_sub_pf": "on"}, ("--raw", "--allow-sub-pf")),
]
REFUSED_MESSAGES = {
    "plot-json": TEXT_PLOT_NEEDS_TABLE_MESSAGE,
    "raw-csv": RAW_NEEDS_TABLE_MESSAGE,
    "detail-quiet": TOROID_DETAIL_NEEDS_TABLE_MESSAGE,
    "sub-pf-quiet": SUB_PF_VALUES_ONLY_MESSAGE,
    "sub-pf-raw": SUB_PF_RAW_MESSAGE,
}


@pytest.mark.parametrize("case, extra, flags", REFUSED, ids=[c[0] for c in REFUSED])
def test_the_design_view_refuses_an_option_that_cannot_apply(
    monkeypatch, capsys, client, case, extra, flags
):
    response = client.post("/design/lowpass", data={**LP, **extra}, headers=HTMX)

    assert response.status_code == 400
    message = escape(REFUSED_MESSAGES[case])
    assert f'<p class="notice__message">{message}</p>' in response.text
    # The CLI refuses the same combination.
    assert "error:" in cli_stderr(monkeypatch, capsys, "lp", "bw", "pi", "10MHz", *flags)


@pytest.mark.parametrize(
    "extra, flags",
    [
        ({"output_format": "quiet", "raw": "on"}, ("-q", "--raw")),
        ({"output_format": "json", "toroids": "none"}, ("--format", "json", "--no-toroids")),
    ],
    ids=["raw-values-only", "no-toroids-json"],
)
def test_options_that_apply_are_still_accepted(monkeypatch, capsys, client, extra, flags):
    expected = cli_stdout(monkeypatch, capsys, "lp", "bw", "pi", "10MHz", *flags)

    response = client.post("/design/lowpass", data={**LP, **extra}, headers=HTMX)

    assert response.status_code == 200
    assert output_text(response.text) + "\n" == expected


def test_raw_units_with_the_build_still_choose_sub_pf_parts(monkeypatch, capsys, client):
    form = {**LP, "frequency": "5GHz", "raw": "on", "allow_sub_pf": "on", "sim_build": "on"}
    form["build_grid_points"] = "51"
    expected = cli_stdout(
        monkeypatch,
        capsys,
        *("lp", "bw", "pi", "5GHz", "--raw", "--allow-sub-pf", "--sim-build"),
        *("--analysis-points", "51"),
    )

    response = client.post("/design/lowpass", data=form, headers=HTMX)

    assert response.status_code == 200
    assert output_text(response.text) + "\n" == expected


# "Simulate inductors as the suggested toroid windings", ticked by default --------


def test_the_toroid_build_box_is_ticked_by_default_after_a_hidden_off(client):
    page = client.get("/").text

    hidden = '<input type="hidden" name="toroid_build" value="off" data-option="toroid_build">'
    box = '<input type="checkbox" name="toroid_build" checked data-option="toroid_build"'
    assert hidden in page and box in page
    assert page.index(hidden) < page.index(box)
    assert "Simulate inductors as the suggested toroid windings" in page
    assert "Use calculated inductances" not in page


@pytest.mark.parametrize(
    "toroid_build, simulated",
    [
        (None, True),  # a request without the field: the CLI default
        (["off", "on"], True),  # the page with the box ticked
        ("off", False),  # the page with the box unticked
    ],
    ids=["absent", "ticked", "unticked"],
)
def test_toroid_build_round_trips_through_a_form_post(client, toroid_build, simulated):
    form = {**LP, "sim_build": "on", "build_grid_points": "51", "output_format": "json"}
    if toroid_build is not None:
        form["toroid_build"] = toroid_build

    body = client.post("/api/design/lowpass", data=form).json()
    inductors = [part for part in body["nominal_build"]["substitutions"] if part["kind"] == "L"]

    assert inductors
    assert all((part["core_name"] is not None) is simulated for part in inductors), inductors


def test_unticked_toroid_build_is_the_cli_no_toroid_build(monkeypatch, capsys, client):
    form = {**LP, "sim_build": "on", "build_grid_points": "51", "toroid_build": "off"}
    expected = cli_stdout(
        monkeypatch,
        capsys,
        *("lp", "bw", "pi", "10MHz", "--sim-build", "--analysis-points", "51"),
        *("--no-toroid-build", "--format", "json"),
    )

    assert client.post("/api/design/lowpass", data=form).text == expected


def test_the_2_2_field_still_means_no_toroid_build():
    form = {**LP, "sim_build": "on", "no_toroid_build": "on"}

    assert parse_design_form("lowpass", form).request.build.use_toroid_candidates is False


@pytest.mark.parametrize("toroid_build, checked", [("off", False), ("on", True)])
def test_a_page_without_javascript_keeps_the_box_as_submitted(client, toroid_build, checked):
    form = {**LP, "sim_build": "on", "build_grid_points": "51", "toroid_build": toroid_build}

    page = client.post("/design/lowpass", data=form).text

    assert ('name="toroid_build" checked' in page) is checked


# Defaults ---------------------------------------------------------------------------


def test_build_fields_are_filled_with_the_cli_defaults(client):
    defaults = BuildConfig()
    page = client.get("/").text

    for name, value in (
        ("build_capacitor_tolerance_pct", f"{defaults.capacitor_tolerance_pct:g}"),
        ("build_inductor_tolerance_pct", f"{defaults.inductor_tolerance_pct:g}"),
        ("build_sample_count", str(defaults.sample_count)),
        ("build_seed", str(defaults.seed)),
        ("build_grid_points", str(defaults.grid_points)),
    ):
        assert re.search(rf'name="{name}" type="text".*?value="{value}"', page, re.S), name
    assert 'placeholder="601"' not in page


@pytest.mark.parametrize("category", ["lowpass", "highpass", "bandpass"])
def test_example_defaults_are_the_wizards(category):
    state = FilterState()
    defaults = form_defaults(category)

    assert defaults["filter_type"] == state.filter_type
    assert float(defaults["impedance"]) == state.impedance
    assert int(defaults.get("components", defaults.get("resonators"))) == state.order
    assert float(defaults["ripple"]) == state.ripple_db
    assert defaults["eseries"] == state.eseries
    expected = {
        "lowpass": {"topology": "pi", "frequency": "10MHz"},
        "highpass": {"topology": "t", "frequency": "10MHz"},
        "bandpass": {"frequency": "14.175MHz", "bandwidth": "350kHz"},
    }[category]
    assert expected.items() <= defaults.items()


@pytest.mark.parametrize(
    "category, argv",
    [
        ("lowpass", ("lp", "bw", "pi", "10MHz")),
        ("highpass", ("hp", "bw", "t", "10MHz")),
        ("bandpass", ("bp", "bw", "top", "-f", "14.175MHz", "-b", "350kHz")),
    ],
)
def test_the_fresh_form_shows_the_cli_default_output(monkeypatch, capsys, client, category, argv):
    """Toroid detail "Best, detailed" and every other default are the CLI's defaults."""
    expected = cli_stdout(monkeypatch, capsys, *argv)

    response = client.post(f"/design/{category}", data=form_defaults(category), headers=HTMX)

    assert response.status_code == 200
    assert output_text(response.text) + "\n" == expected


# Downloads post the inputs of the result shown ----------------------------------------


def test_the_result_carries_its_inputs_for_the_downloads(client):
    form = {**LP, "components": "5", "eseries": "E12", "toroid_build": "on"}

    fragment = client.post("/design/lowpass", data=form, headers=HTMX).text

    assert _snapshot(fragment) == form
    assert 'form="design-form"' not in fragment
    assert 'formaction="/export/lowpass/csv"' in _SNAPSHOT_FORM.search(fragment).group(0)
    assert "Downloads use the inputs of the result shown." in fragment
    assert f'id="stale-notice" role="status" hidden>{STALE_NOTICE}</p>' in fragment


def test_a_download_after_editing_the_form_is_the_result_shown(monkeypatch, capsys, client):
    """The live form changed after Design filter; the download still describes the result."""
    shown = {**LP, "filter_type": "chebyshev", "components": "5", "ripple": "0.25"}
    fragment = client.post("/design/lowpass", data=shown, headers=HTMX).text
    # The user now edits the page form (frequency, order); the buttons post the snapshot.
    snapshot = _snapshot(fragment)

    body = client.post("/export/lowpass/json", data=snapshot).text

    expected = cli_stdout(
        monkeypatch, capsys, "lp", "ch", "pi", "10MHz", "-n", "5", "-r", "0.25", "--format", "json"
    )
    assert body == expected
    edited = cli_stdout(monkeypatch, capsys, "lp", "ch", "pi", "7MHz", "-n", "7", "-r", "0.25")
    assert body != edited


def test_markup_in_a_submitted_value_survives_the_snapshot(client):
    # Ripple is ignored for Butterworth, so any text reaches the snapshot.
    form = {**LP, "ripple": '0.5" onfocus="x'}

    fragment = client.post("/design/lowpass", data=form, headers=HTMX).text

    assert 'onfocus="x"' not in fragment
    assert _snapshot(fragment)["ripple"] == form["ripple"]


def test_the_full_page_without_javascript_also_downloads_the_result_shown(client):
    form = {**LP, "components": "4"}

    page = client.post("/design/lowpass", data=form).text

    assert _snapshot(page) == form


# What a disabled control shows still reaches the downloads that use it --------------
# The page leaves a disabled control out of the request and sends its visible value as
# "visible.<name>"; these tests post what the page posts.

BP = {"filter_type": "butterworth", "frequency": "14.175MHz", "bandwidth": "350kHz"}
BP_ARGV = ("bp", "bw", "top", "-f", "14.175MHz", "-b", "350kHz")


@pytest.mark.parametrize(
    "kind, flags", [("json", ("--format", "json")), ("csv", ("--format", "csv"))]
)
def test_values_only_with_no_standard_values_downloads_no_match(
    monkeypatch, capsys, client, kind, flags
):
    """Values only + E-series None: the downloads are ``--no-match``, not E24."""
    sent = {**LP, "output_format": "quiet", "visible.eseries": "none"}
    fragment = client.post("/design/lowpass", data=sent, headers=HTMX).text
    assert output_text(fragment) + "\n" == cli_stdout(
        monkeypatch, capsys, "lp", "bw", "pi", "10MHz", "-q"
    )
    snapshot = _snapshot(fragment)
    assert snapshot["visible.eseries"] == "none"

    body = client.post(f"/export/lowpass/{kind}", data=snapshot).text

    expected = cli_stdout(monkeypatch, capsys, "lp", "bw", "pi", "10MHz", "--no-match", *flags)
    assert body == expected
    assert body != cli_stdout(monkeypatch, capsys, "lp", "bw", "pi", "10MHz", *flags)


def test_raw_units_keep_the_visible_eseries_for_downloads(monkeypatch, capsys, client):
    sent = {**LP, "raw": "on", "visible.eseries": "E96"}

    body = client.post("/export/lowpass/json", data=sent).text

    assert body == cli_stdout(
        monkeypatch, capsys, "lp", "bw", "pi", "10MHz", "-e", "E96", "--format", "json"
    )


def test_a_visible_option_that_does_not_apply_to_a_download_is_left_out(
    monkeypatch, capsys, client
):
    """Sub-pF with E-series None cannot apply anywhere, so it never breaks a download."""
    sent = {
        **LP,
        "output_format": "quiet",
        "visible.eseries": "none",
        "visible.allow_sub_pf": "on",
    }

    response = client.post("/export/lowpass/response-json", data=sent)
    json_body = client.post("/export/lowpass/json", data=sent).text

    assert response.status_code == 200
    assert json_body == cli_stdout(
        monkeypatch, capsys, "lp", "bw", "pi", "10MHz", "--no-match", "--format", "json"
    )


def test_visible_sub_pf_reaches_the_json_download(monkeypatch, capsys, client):
    sent = {**LP, "frequency": "5GHz", "output_format": "quiet", "visible.allow_sub_pf": "on"}

    body = client.post("/export/lowpass/json", data=sent).text

    assert body == cli_stdout(
        monkeypatch, capsys, "lp", "bw", "pi", "5GHz", "--allow-sub-pf", "--format", "json"
    )


def test_visible_resonator_q_reaches_only_downloads_that_show_it(monkeypatch, capsys, client):
    """CSV result: Qu is disabled; the JSON download uses it, the CSV download does not."""
    sent = {**BP, "output_format": "csv", "visible.qu": "200"}
    fragment = client.post("/design/bandpass", data=sent, headers=HTMX).text
    assert output_text(fragment) + "\n" == cli_stdout(
        monkeypatch, capsys, *BP_ARGV, "--format", "csv"
    )
    snapshot = _snapshot(fragment)

    json_body = client.post("/export/bandpass/json", data=snapshot).text
    csv_body = client.post("/export/bandpass/csv", data=snapshot).text

    assert json_body == cli_stdout(monkeypatch, capsys, *BP_ARGV, "--qu", "200", "--format", "json")
    assert csv_body == cli_stdout(monkeypatch, capsys, *BP_ARGV, "--format", "csv")


def test_visible_build_reaches_the_json_download(monkeypatch, capsys, client):
    sent = {
        **LP,
        "output_format": "quiet",
        "visible.sim_build": "on",
        "build_grid_points": "51",
    }

    body = client.post("/export/lowpass/json", data=sent).text

    assert body == cli_stdout(
        monkeypatch,
        capsys,
        *("lp", "bw", "pi", "10MHz", "--sim-build", "--analysis-points", "51"),
        *("--format", "json"),
    )


def test_display_only_choices_never_reach_a_download(client):
    plain = client.post("/export/lowpass/json", data=LP).text
    sent = {**LP, "output_format": "json", "visible.plot": "on", "visible.toroids": "full"}

    assert client.post("/export/lowpass/json", data=sent).text == plain


def test_the_design_view_ignores_visible_values(monkeypatch, capsys, client):
    sent = {**LP, "output_format": "quiet", "visible.eseries": "none", "visible.plot": "on"}

    fragment = client.post("/design/lowpass", data=sent, headers=HTMX).text

    assert output_text(fragment) + "\n" == cli_stdout(
        monkeypatch, capsys, "lp", "bw", "pi", "10MHz", "-q"
    )


def test_the_script_mirrors_disabled_values_as_visible_fields():
    script = APP_JS.read_text()

    assert '"visible." + control.name' in script
    assert "mirrorVisibleValues(form)" in script
