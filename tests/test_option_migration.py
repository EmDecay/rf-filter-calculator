"""The toroid-only names gave way to generic inductor options; each old behaviour survives.

For every row of the 3.0.0 migration table there is a test that the new name keeps the
old behaviour and a test that the old name is gone (removed, not aliased). A last test
guards that no removed spelling reappears anywhere in the package.
"""

from __future__ import annotations

import dataclasses
import importlib.util
import json
import re
from pathlib import Path

import pytest

from filter_lib.design import DesignRequest, RenderOptions, design, render_lines
from filter_lib.design import option_applicability as applicability
from filter_lib.design.option_applicability import (
    BUILD_INDUCTORS,
    BUILD_INDUCTORS_NEEDS_SUGGESTIONS_MESSAGE,
    INDUCTOR_DETAIL,
    INDUCTOR_DETAIL_NEEDS_TABLE_MESSAGE,
    OutputChoices,
    inapplicable_options,
)
from filter_lib.shared.build_types import BuildConfig
from filter_lib.shared.inductor_display import SECTION_NAME
from filter_lib.shared.inductor_suggestion import SUGGESTIONS_NOT_USED
from filter_lib.shared.toroid_selection import find_core_candidates
from filter_lib.wizard.state import FilterState
from tests.cli_parity_helpers import cli_stdout

PACKAGE = Path(__file__).resolve().parents[1] / "filter_lib"
LOWPASS = ("lp", "bw", "pi", "10MHz", "-n", "5")
BANDPASS = ("bp", "bw", "top", "-f", "14.2MHz", "-b", "500kHz")
FAST_BUILD = ("--sim-build", "--analysis-points", "51")


def _cli_error(monkeypatch, capsys, *argv: str) -> tuple[int, str]:
    from filter_lib import cli

    monkeypatch.setattr("sys.argv", ["filter-calc", *argv])
    capsys.readouterr()
    with pytest.raises(SystemExit) as stop:
        cli.main()
    return stop.value.code, capsys.readouterr().err


def _assert_unrecognized(monkeypatch, capsys, flag: str) -> None:
    code, err = _cli_error(monkeypatch, capsys, *LOWPASS, flag)
    assert code == 2
    assert f"unrecognized arguments: {flag}" in err


def _keys(document) -> set[str]:
    """Every key anywhere in a JSON document."""
    if isinstance(document, dict):
        return set(document).union(*(_keys(value) for value in document.values()))
    if isinstance(document, list):
        return set().union(*(_keys(value) for value in document))
    return set()


def _substitution(document: dict, name: str) -> dict:
    [item] = [
        part for part in document["nominal_build"]["substitutions"] if part["logical_name"] == name
    ]
    return item


def _deck_value(deck: str, element: str) -> float:
    [line] = [line for line in deck.splitlines() if line.startswith(f"{element} ")]
    return float(line.split()[3])


# -- --no-toroids -> --inductor-suggestions none -----------------------------------------


def test_suggestions_none_hides_them_everywhere_and_builds_calculated(monkeypatch, capsys):
    none = ("--inductor-suggestions", "none")
    table = cli_stdout(monkeypatch, capsys, *LOWPASS, *none)
    document = json.loads(cli_stdout(monkeypatch, capsys, *LOWPASS, "--format", "json", *none))
    csv_text = cli_stdout(monkeypatch, capsys, *LOWPASS, "--format", "csv", *none)
    build = json.loads(
        cli_stdout(monkeypatch, capsys, *LOWPASS, "--format", "json", *FAST_BUILD, *none)
    )
    deck = cli_stdout(monkeypatch, capsys, *LOWPASS, "--format", "spice", *none)

    assert SECTION_NAME not in table
    assert "inductor_suggestions" not in _keys(document)
    assert "InductorKind" not in csv_text.splitlines()[0]
    calculated = build["components"]["inductors"][0]["value_henries"]
    assert _substitution(build, "L1")["status"] == SUGGESTIONS_NOT_USED
    assert _substitution(build, "L1")["nominal_value_si"] == calculated
    assert _deck_value(deck, "L1") == pytest.approx(calculated, rel=1e-11, abs=0)


def test_no_toroids_is_gone(monkeypatch, capsys):
    _assert_unrecognized(monkeypatch, capsys, "--no-toroids")


# -- --no-toroid-build -> --build-inductors calculated -------------------------------------


def test_build_inductors_calculated_keeps_suggestions_and_builds_calculated(monkeypatch, capsys):
    calculated = ("--build-inductors", "calculated")
    table = cli_stdout(monkeypatch, capsys, *LOWPASS, *FAST_BUILD, *calculated)
    build = json.loads(
        cli_stdout(monkeypatch, capsys, *LOWPASS, "--format", "json", *FAST_BUILD, *calculated)
    )
    deck = cli_stdout(monkeypatch, capsys, *LOWPASS, "--format", "spice", *calculated)

    assert SECTION_NAME in table
    assert build["components"]["inductors"][0]["inductor_suggestions"]["best"] is not None
    value = build["components"]["inductors"][0]["value_henries"]
    assert _substitution(build, "L1")["status"] == SUGGESTIONS_NOT_USED
    assert _deck_value(deck, "L1") == pytest.approx(value, rel=1e-11, abs=0)


def test_no_toroid_build_is_gone(monkeypatch, capsys):
    _assert_unrecognized(monkeypatch, capsys, "--no-toroid-build")


# -- --toroid-full / --toroid-compact -> --inductor-suggestions full / compact -------------


def test_full_detail_lists_the_same_three_windings_the_old_full_view_did(monkeypatch, capsys):
    table = cli_stdout(monkeypatch, capsys, *LOWPASS, "--inductor-suggestions", "full")
    result = design(DesignRequest("lowpass", "butterworth", "pi", 10e6, 50.0, 5)).result
    screened = find_core_candidates(result["inductors"][0], 10e6, top_n=3)

    block = table.split("  L1 target:")[1].split("  L2 target:")[0]
    assert len(screened) == 3
    for rank, candidate in enumerate(screened, start=1):
        assert f"  {rank}. Toroid winding {candidate.core.name} " in block
        assert f"     {candidate.winding.n_turns} turns of AWG {candidate.mechanical.awg} " in block


def test_compact_detail_shows_the_best_on_one_line(monkeypatch, capsys):
    table = cli_stdout(monkeypatch, capsys, *LOWPASS, "--inductor-suggestions", "compact")
    block = table.split("  L1 target:")[1].split("\n\n")[0]

    assert block.count("\n  1. Toroid ") == 1
    assert "\n  2. " not in block
    assert "Error budget" not in block


@pytest.mark.parametrize("detail", ["full", "compact"])
@pytest.mark.parametrize("output", ["json", "csv"])
def test_table_details_leave_json_and_csv_unchanged(monkeypatch, capsys, detail, output):
    shown = cli_stdout(monkeypatch, capsys, *LOWPASS, "--format", output)
    code, err = _cli_error(
        monkeypatch, capsys, *LOWPASS, "--format", output, "--inductor-suggestions", detail
    )

    assert "inductor_suggestions" in shown or "InductorKind" in shown
    assert code == 2
    assert f"--inductor-suggestions {detail} cannot be used with --format {output}" in err
    # The same document as the best detail, which JSON and CSV always use.
    request = DesignRequest(
        "lowpass", "butterworth", "pi", 10e6, 50.0, 5, inductor_suggestions=detail
    )
    rendered = render_lines(design(request), RenderOptions(output_format=output))
    assert "\n".join(rendered) + "\n" == shown


@pytest.mark.parametrize("flag", ["--toroid-full", "--toroid-compact"])
def test_toroid_detail_flags_are_gone(monkeypatch, capsys, flag):
    _assert_unrecognized(monkeypatch, capsys, flag)


# -- --sim-matched and shared/matched_simulation.py -> --sim-build ---------------------------


def test_sim_build_compares_the_calculated_and_chosen_part_responses(monkeypatch, capsys):
    table = cli_stdout(monkeypatch, capsys, *LOWPASS, *FAST_BUILD)
    document = json.loads(
        cli_stdout(monkeypatch, capsys, *LOWPASS, "--format", "json", *FAST_BUILD)
    )

    assert "Ideal values:" in table
    assert "Chosen parts:" in table
    assert {"simulated", "nominal_build", "tolerance_analysis"} <= set(document)


def test_sim_matched_and_its_module_are_gone(monkeypatch, capsys):
    _assert_unrecognized(monkeypatch, capsys, "--sim-matched")
    assert importlib.util.find_spec("filter_lib.shared.matched_simulation") is None


def test_the_toroid_flag_module_is_gone():
    assert importlib.util.find_spec("filter_lib.cli.toroid_flags") is None


def test_the_print_functions_are_gone():
    """``design()`` + ``render_lines`` replace them; they selected parts themselves."""
    from filter_lib import bandpass, highpass, lowpass
    from filter_lib.bandpass import display as bandpass_display
    from filter_lib.shared import lp_hp_display

    assert not hasattr(lp_hp_display, "display_results_for_config")
    for module in (lowpass, highpass, bandpass, bandpass_display):
        assert not hasattr(module, "display_results")


# -- BuildConfig.use_toroid_candidates -> DesignRequest.build_inductors ----------------------


def test_the_request_chooses_the_build_inductors():
    request = DesignRequest(
        "lowpass",
        "butterworth",
        "pi",
        10e6,
        50.0,
        5,
        build_inductors="calculated",
        realization=BuildConfig(grid_points=51),
        run_build_analysis=True,
    )
    substitutions = design(request).build_analysis.nominal_realization.substitutions

    inductors = [item for item in substitutions if item.kind == "L"]
    assert {item.status for item in inductors} == {SUGGESTIONS_NOT_USED}
    assert all(item.nominal_value == item.calculated_value for item in inductors)


def test_build_config_has_no_toroid_switch():
    assert "use_toroid_candidates" not in {field.name for field in dataclasses.fields(BuildConfig)}
    with pytest.raises(TypeError):
        BuildConfig(use_toroid_candidates=False)  # type: ignore[call-arg]


# -- RenderOptions / OutputChoices toroid fields -> the inductor detail value ----------------


def test_the_request_s_detail_sets_the_table():
    full = DesignRequest("lowpass", "butterworth", "pi", 10e6, 50.0, 5, inductor_suggestions="full")
    lines = render_lines(design(full), RenderOptions())

    assert any(line.startswith("  3. Toroid winding ") for line in lines)


@pytest.mark.parametrize(
    "cls, names",
    [
        (RenderOptions, {"include_toroids", "toroid_full", "toroid_compact"}),
        (OutputChoices, {"include_toroids"}),
    ],
)
def test_presentation_toroid_fields_are_gone(cls, names):
    assert names.isdisjoint(field.name for field in dataclasses.fields(cls))


# -- option_applicability TOROID_DETAIL / TOROID_BUILD -> INDUCTOR_DETAIL / BUILD_INDUCTORS ---


def test_inductor_options_follow_the_old_rules():
    json_reasons = inapplicable_options(OutputChoices(output_format="json"))
    none_reasons = inapplicable_options(OutputChoices(inductor_detail="none"))

    assert json_reasons[INDUCTOR_DETAIL] == INDUCTOR_DETAIL_NEEDS_TABLE_MESSAGE
    assert BUILD_INDUCTORS not in json_reasons
    assert none_reasons[BUILD_INDUCTORS] == BUILD_INDUCTORS_NEEDS_SUGGESTIONS_MESSAGE
    assert INDUCTOR_DETAIL not in inapplicable_options(OutputChoices())


def test_toroid_option_names_are_gone():
    assert not hasattr(applicability, "TOROID_DETAIL")
    assert not hasattr(applicability, "TOROID_BUILD")
    assert {"toroid_detail", "toroid_build"}.isdisjoint(applicability.OPTIONS)


# -- Web fields ------------------------------------------------------------------------------


def _web_form(**fields) -> dict[str, str]:
    form = {
        "filter_type": "butterworth",
        "topology": "pi",
        "frequency": "10MHz",
        "components": "5",
        "impedance": "50",
        "eseries": "E24",
        "output_format": "table",
    }
    form.update(fields)
    return form


def test_web_inductor_fields_give_the_cli_output(monkeypatch, capsys):
    pytest.importorskip("fastapi")
    from tests.web_helpers import HTMX, output_text, web_client

    hidden = cli_stdout(monkeypatch, capsys, *LOWPASS, "--inductor-suggestions", "none")
    built = cli_stdout(
        monkeypatch, capsys, *LOWPASS, *FAST_BUILD, "--build-inductors", "calculated"
    )
    with web_client() as client:
        none_page = client.post(
            "/design/lowpass", data=_web_form(inductor_suggestions="none"), headers=HTMX
        )
        build_page = client.post(
            "/design/lowpass",
            data=_web_form(sim_build="on", build_grid_points="51", build_inductors="calculated"),
            headers=HTMX,
        )

    assert output_text(none_page.text) + "\n" == hidden
    assert output_text(build_page.text) + "\n" == built


def test_old_web_fields_are_gone(monkeypatch, capsys):
    pytest.importorskip("fastapi")
    from filter_lib.web import build_form_parsing
    from filter_lib.web.form_parsing import form_defaults
    from tests.web_helpers import HTMX, output_text, web_client

    default = cli_stdout(monkeypatch, capsys, *LOWPASS, *FAST_BUILD)
    with web_client() as client:
        page = client.post(
            "/design/lowpass",
            data=_web_form(
                sim_build="on",
                build_grid_points="51",
                toroids="none",
                toroid_build="off",
                no_toroid_build="on",
            ),
            headers=HTMX,
        )

    # The old fields mean nothing now: the result is the default design.
    assert output_text(page.text) + "\n" == default
    assert {"toroids", "toroid_build"}.isdisjoint(form_defaults("lowpass"))
    assert not hasattr(build_form_parsing, "simulate_toroid_windings")


# -- Wizard state ----------------------------------------------------------------------------


def test_wizard_inductor_choices_reach_the_request():
    state = FilterState(
        category="lowpass",
        filter_type="butterworth",
        topology="pi",
        frequency_hz=10e6,
        order=5,
        inductor_detail="full",
        build_analysis_enabled=True,
        build_inductors="calculated",
    )
    hidden = FilterState(category="lowpass", frequency_hz=10e6, inductor_detail="none")

    request = state.to_design_request()
    assert request.inductor_suggestions == "full"
    assert request.build_inductors == "calculated"
    assert hidden.to_design_request().inductor_suggestions == "none"


def test_wizard_toroid_fields_are_gone():
    names = {field.name for field in dataclasses.fields(FilterState)}

    assert {"toroid_detail", "build_use_toroid_candidates"}.isdisjoint(names)


# -- JSON keys -------------------------------------------------------------------------------

_OLD_JSON_KEYS = {
    "toroid_recommendations",
    "resonator_toroid_recommendations",
    "resonator_toroid_candidates",
    "toroid_candidate_screen_enabled",
    "verified_toroid_candidate_used",
    "verified_toroid_elements",
    "uses_verified_toroid_candidates",
    "q_dc_upper_bound",
    "matched_sim",
}


@pytest.mark.parametrize("argv", [LOWPASS, BANDPASS], ids=["lowpass", "bandpass"])
def test_every_inductor_carries_its_suggestions(monkeypatch, capsys, argv):
    document = json.loads(cli_stdout(monkeypatch, capsys, *argv, "--format", "json"))

    for inductor in document["components"]["inductors"]:
        suggestions = inductor["inductor_suggestions"]
        assert [group["kind"] for group in suggestions["kinds"]] == ["toroid", "air-coil", "chip"]
        assert suggestions["kinds"][0]["suggestions"]
        assert suggestions["best"] == {"kind": "toroid", "rank": 1}


@pytest.mark.parametrize("argv", [LOWPASS, BANDPASS], ids=["lowpass", "bandpass"])
def test_old_json_keys_are_gone(monkeypatch, capsys, argv):
    plain = json.loads(cli_stdout(monkeypatch, capsys, *argv, "--format", "json"))
    built = json.loads(cli_stdout(monkeypatch, capsys, *argv, "--format", "json", *FAST_BUILD))

    assert _OLD_JSON_KEYS.isdisjoint(_keys(plain) | _keys(built))


def test_build_json_names_the_inductor_choice_and_the_suggested_parts(monkeypatch, capsys):
    document = json.loads(
        cli_stdout(monkeypatch, capsys, *LOWPASS, "--format", "json", *FAST_BUILD)
    )
    model = document["build_model"]

    assert model["build_inductor_choice"] == "auto"
    assert model["suggested_inductors_used"] is True
    assert model["suggested_inductor_elements"] == ["L1", "L2"]
    part = _substitution(document, "L1")
    assert (part["method"], part["inductor_kind"]) == ("suggested_inductor", "toroid")
    assert part["part_name"] == part["core_name"]


# -- Method and status values ----------------------------------------------------------------

_OLD_VALUES = (
    "verified_toroid_integer_turns",
    "candidate_screen_disabled",
    "calculated_exact_value_toroid_selection_disabled",
)


@pytest.mark.parametrize("choice", ["auto", "calculated"])
def test_old_method_and_status_values_are_gone(monkeypatch, capsys, choice):
    flags = ("--build-inductors", choice)
    text = cli_stdout(monkeypatch, capsys, *LOWPASS, "--format", "json", *FAST_BUILD, *flags)
    text += cli_stdout(monkeypatch, capsys, *LOWPASS, "--format", "spice", *flags)

    assert not any(value in text for value in _OLD_VALUES)


# -- No removed spelling anywhere in the package ----------------------------------------------

_REMOVED = re.compile(
    r"--no-toroids\b|--toroid-full\b|--toroid-compact\b|--no-toroid-build\b|--sim-matched\b"
    r"|\bsim_matched\b|\bmatched_sim\b|\bmatched_simulation\b|\btoroid_flags\b|\btoroid_recommendations\b|\bresonator_toroid_"
    r"|\buse_toroid_candidates\b|\binclude_toroids\b|\btoroid_build\b|\bno_toroid_build\b"
    r"|\bno_toroids\b|\btoroid_full\b|\btoroid_compact\b|\btoroid_detail\b|\bTOROID_DETAIL\b"
    r"|\bTOROID_BUILD\b|\bsimulate_toroid_windings\b|\bverified_toroid_|\bcandidate_screen_"
    r"|\bdisplay_results(_for_config)?\b"
)


def test_no_removed_spelling_is_reachable_in_the_package():
    found = []
    for path in sorted(PACKAGE.rglob("*")):
        if path.suffix not in {".py", ".html", ".js", ".json", ".tcss"}:
            continue
        for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
            if _REMOVED.search(line):
                found.append(f"{path.relative_to(PACKAGE)}:{number}: {line.strip()}")

    assert found == []
