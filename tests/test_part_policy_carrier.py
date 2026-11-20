"""One carrier for the part policy: ``DesignRequest`` in, ``DesignResult`` out.

Only ``design()`` builds a ``DesignResult`` or resolves a ``MatchPolicy`` and the
``ResolvedParts`` (through ``design/part_resolution.py``); every output reads its parts
from the result. A chosen-parts SPICE deck uses the build settings but
never runs the tolerance cases, and the wizard reuses a result only for an equal request.
"""

from __future__ import annotations

import ast
import re
from pathlib import Path

import pytest

from filter_lib.wizard.calculation_handler import calculate_and_format
from filter_lib.wizard.state import CSV_DOCUMENT, JSON_DOCUMENT, FilterState
from tests.cli_parity_helpers import cli_stdout

PACKAGE = Path(__file__).resolve().parents[1] / "filter_lib"
# Where each constructor may be called: the result only in design(), the policy only where
# it is defined (its default) and in design()'s part resolution, and the resolved parts
# only there too.
ALLOWED_CALLERS = {
    "DesignResult": {"design/design_service.py"},
    "MatchPolicy": {"shared/eseries.py", "design/part_resolution.py"},
    "ResolvedParts": {"design/part_resolution.py"},
}


def _constructor_calls(name: str) -> set[str]:
    callers = set()
    for path in PACKAGE.rglob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            func = node.func
            called = func.id if isinstance(func, ast.Name) else getattr(func, "attr", None)
            replaced = (
                called == "replace"
                and node.args
                and isinstance(node.args[0], ast.Name)
                and node.args[0].id == "DEFAULT_MATCH_POLICY"
            )
            if called == name or (name == "MatchPolicy" and replaced):
                callers.add(path.relative_to(PACKAGE).as_posix())
    return callers


@pytest.mark.parametrize("name", sorted(ALLOWED_CALLERS))
def test_only_design_builds_results_and_policies(name):
    assert _constructor_calls(name) <= ALLOWED_CALLERS[name]


def _count_analyses(monkeypatch) -> list[int]:
    calls = [0]
    from filter_lib.shared import build_simulation

    real = build_simulation.analyze_build

    def counting(*args, **kwargs):
        calls[0] += 1
        return real(*args, **kwargs)

    monkeypatch.setattr("filter_lib.shared.build_simulation.analyze_build", counting)
    return calls


def test_cli_chosen_parts_deck_uses_its_ports_without_tolerance_cases(monkeypatch, capsys):
    calls = _count_analyses(monkeypatch)

    deck = cli_stdout(
        monkeypatch,
        capsys,
        *("lp", "bw", "pi", "10MHz", "-n", "3", "--format", "spice"),
        *("--source-resistance", "25", "--load-resistance", "100"),
    )

    assert calls == [0]
    assert re.search(r"^RSOURCE NSOURCE 1 25$", deck, re.M)
    assert re.search(r"^RLOAD 2 0 100$", deck, re.M)


def test_web_chosen_parts_download_uses_its_ports_without_tolerance_cases(monkeypatch):
    pytest.importorskip("fastapi")
    from tests.web_helpers import web_client

    calls = _count_analyses(monkeypatch)
    form = {
        "frequency": "10MHz",
        "components": "3",
        "topology": "pi",
        "sim_build": "on",
        "build_source_resistance": "25",
        "build_load_resistance": "100",
        "build_grid_points": "51",
    }

    with web_client() as client:
        deck = client.post("/export/lowpass/spice-nominal", data=form).text

    assert calls == [0]
    assert re.search(r"^RSOURCE NSOURCE 1 25$", deck, re.M)
    assert re.search(r"^RLOAD 2 0 100$", deck, re.M)


def _shown(**overrides) -> FilterState:
    """A wizard state after its result was calculated and published."""
    values = dict(category="lowpass", frequency_hz=10e6, order=3, show_plot=False, eseries="E24")
    values.update(overrides)
    state = FilterState(**values)
    outcome = calculate_and_format(state)
    assert outcome.succeeded, outcome.error
    revision = state.begin_calculation()
    assert state.publish_success(
        revision, outcome.output_text, outcome.result, outcome.build_analysis, outcome.design
    )
    return state


def test_wizard_reuses_the_result_only_for_an_equal_request():
    state = _shown()

    for document in (JSON_DOCUMENT, CSV_DOCUMENT, "response-json"):
        assert not state.needs_own_design(document)
        assert state.design_result(document) is state.design_outcome


def test_wizard_csv_shown_and_json_with_the_build_never_share_a_result():
    state = _shown(output_format="csv", build_analysis_enabled=True, build_grid_points=51)

    assert state.design_outcome.build_analysis is None
    assert not state.needs_own_design(CSV_DOCUMENT)
    assert state.needs_own_design(JSON_DOCUMENT)
    request = state.document_request(JSON_DOCUMENT)
    assert request.run_build_analysis is True
    assert request != state.design_outcome.request


def test_wizard_values_only_result_and_a_json_with_its_series_are_designed_apart():
    """Values only leaves the series out; the saved JSON uses the visible E96."""
    state = _shown(output_format="table", quiet=True, eseries="E96")

    assert state.design_outcome.eseries == "E24"
    assert state.needs_own_design(JSON_DOCUMENT)
    assert state.document_request(JSON_DOCUMENT).eseries == "E96"


def test_bandpass_usage_errors_come_before_the_build_starts(monkeypatch, capsys):
    """--q-safety needs JSON output; with a table the CLI refuses it before any analysis."""
    calls = _count_analyses(monkeypatch)
    argv = ("bp", "bw", "top", "-f", "10MHz", "-b", "500kHz", "--q-safety", "3", "--sim-build")
    monkeypatch.setattr("sys.argv", ["filter-calc", *argv])

    from filter_lib import cli

    with pytest.raises(SystemExit):
        cli.main()

    assert calls == [0]
    assert "--q-safety only changes q_min in JSON output" in capsys.readouterr().err


@pytest.mark.parametrize(("field", "value"), [("eseries", []), ("capacitor_grade", {})])
def test_malformed_part_policy_values_are_a_clear_value_error(field, value):
    from filter_lib.design import DesignRequest

    with pytest.raises(ValueError):
        DesignRequest("lowpass", "butterworth", "pi", 10e6, 50.0, 3, **{field: value})


def test_the_wizard_keeps_one_copy_of_the_result_and_its_build():
    state = _shown(build_analysis_enabled=True, build_grid_points=51)

    assert state.design_outcome.build_analysis is not None
    assert state.result is state.design_outcome.result
    assert state.build_analysis is state.design_outcome.build_analysis


def test_the_wizard_response_file_reuses_the_result_shown():
    """Response data is the ideal response: no capacitor option, Q or build changes it."""
    state = _shown(eseries="E96", output_format="csv", build_analysis_enabled=True)
    state.capacitor_input_error = "Capacitor tolerance must be a number"

    for document in ("response-json", "response-csv"):
        assert not state.needs_own_design(document)
        assert state.design_result(document) is state.design_outcome
