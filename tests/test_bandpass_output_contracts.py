"""Machine-readable bandpass output contract regressions."""

import copy
import csv
import io
import json

import pytest

from filter_lib.bandpass.calculations import calculate_bandpass_filter
from filter_lib.bandpass.formatters import format_csv, format_json
from tests.parts_helpers import parts_for


@pytest.fixture(scope="module")
def _reference_result() -> dict:
    return calculate_bandpass_filter(
        f0=14.2e6,
        bw=500e3,
        z0=50.0,
        n_resonators=3,
        filter_type="butterworth",
        coupling="top",
        ql=180.0,
        qc=500.0,
    )


@pytest.fixture
def result(_reference_result) -> dict:
    """Fresh copy of a 3.5% FBW Butterworth design with separate component Q values."""
    return copy.deepcopy(_reference_result)


def test_json_exposes_validation_q_and_suggestion_semantics(result) -> None:
    data = json.loads(
        format_json(result, parts_for(result, "bandpass")),
        parse_constant=lambda value: (_ for _ in ()).throw(ValueError(value)),
    )

    assert data["response_validation_status"] == "validated"
    assert data["synthesis_validation"]["edge_validated"] is True
    assert data["q_model"]["definition"] == "complete_resonator_unloaded_q"
    assert data["q_model"]["combination"] == "reciprocal_component_loss_sum"
    assert data["q_min_is_heuristic"] is True
    assert data["q_safety_compatibility_only"] is True
    # Suggestions sit on each inductor; equal resonator inductances share the same ones.
    assert "resonator_toroid_candidates" not in data
    assert "resonator_toroid_recommendations" not in data
    suggestions = [item["inductor_suggestions"] for item in data["components"]["inductors"]]
    assert len(suggestions) == 3
    assert all(item == suggestions[0] for item in suggestions)
    assert [group["kind"] for group in suggestions[0]["kinds"]] == ["toroid", "air-coil", "chip"]

    for group in (
        "tank_capacitors",
        "coupling_capacitors",
        "end_coupling_capacitors",
    ):
        for component in data["components"][group]:
            match = component["standard_match"]
            assert match["status"] in {"recommended", "expert_override_required"}
            assert "policy" in match
            if match["selected"] is not None:
                assert match["selected"]["kind"] in {"single", "parallel"}


@pytest.mark.parametrize(
    "field, json_path",
    [("f0", "center_frequency_hz"), ("bw", "bandwidth_hz"), ("z0", "impedance_ohms")],
)
def test_json_rejects_non_finite_numeric_fields(result, field: str, json_path: str) -> None:
    parts = parts_for(result, "bandpass", eseries=None, inductor_detail="none")
    result[field] = float("nan")

    with pytest.raises(ValueError, match=rf"\$\.{json_path} must be finite"):
        format_json(result, parts)


def test_csv_is_rectangular_and_emits_only_selected_parallel_pairs(result) -> None:
    rows = list(csv.reader(io.StringIO(format_csv(result, parts_for(result, "bandpass")))))
    header = rows[0]
    assert all(len(row) == len(header) for row in rows)

    kind_index = header.index("RecommendedStdKind")
    parallel_index = header.index("ParallelStdValues")
    selected_index = header.index("RecommendedStdValues")
    policy_index = header.index("RecommendationPolicy")
    for row in rows[1:]:
        if not row[0].startswith("C"):
            continue
        assert row[policy_index]
        if row[kind_index] == "parallel":
            assert row[parallel_index]
            assert row[selected_index] == row[parallel_index]
        else:
            assert row[kind_index] == "single"
            assert row[parallel_index] == ""
            assert row[selected_index]


def test_json_carries_the_tank_trimmers_and_the_coupling_advice() -> None:
    from filter_lib.design import DesignRequest, design
    from filter_lib.design.render import render_lines
    from filter_lib.design.render_options import RenderOptions

    outcome = design(
        DesignRequest(
            "bandpass", "chebyshev", "top", 146e6, 50.0, 3, ripple_db=0.5, bandwidth_hz=4e6
        )
    )
    data = json.loads(render_lines(outcome, RenderOptions(output_format="json"))[0])

    trimmers = data["tank_trimmers"]
    assert [tank["circuit_name"] for tank in trimmers["tanks"]] == ["CT1", "CT2", "CT3"]
    for tank in trimmers["tanks"]:
        low, high = tank["need_f"]
        assert 0 < low < high
        assert tank["need_basis"] in {"sourced", "conditional"}
        assert tank["fits"] == bool(tank["splits"])
        for split in tank["splits"]:
            assert split["trimmer"]["source"]["sha256"]
            assert split["series_inductance_basis"] in {"assumed", "bound_from_minimum_srf"}
    advice = data["coupling_advice"]
    assert advice["advised"]["setting"] == "21nH"
    assert advice["short_coupling_capacitors"] == ["Cs12", "Cs23"]


def test_csv_tank_rows_carry_the_trimmer_columns(result) -> None:
    rows = list(csv.reader(io.StringIO(format_csv(result, parts_for(result, "bandpass")))))
    header = rows[0]

    assert header[-13:] == [
        "TankFixedParts",
        "TrimmerPart",
        "TrimmerRequiredMinPF",
        "TrimmerRequiredMaxPF",
        "TrimmerRangeMinPF",
        "TrimmerRangeMaxPF",
        "TrimmerSeriesInductanceNH",
        "TrimmerSeriesInductanceBasis",
        "TrimmerFit",
        "TankNeedMinPF",
        "TankNeedMaxPF",
        "TankNeedBasis",
        "TankNeedAssumptions",
    ]
    assert all(len(row) == len(header) for row in rows)
    by_name = {row[0]: dict(zip(header, row)) for row in rows[1:]}
    # Every tank states its need; the other rows leave the columns blank.
    assert all(by_name[f"Cp{i}"]["TankNeedBasis"] for i in (1, 2, 3))
    assert {by_name[f"Cp{i}"]["TrimmerFit"] for i in (1, 2, 3)} <= {
        "conditional_on_series_inductance",
        "no_fit",
    }
    assert by_name["Cs12"]["TankNeedBasis"] == "" and by_name["L1"]["TankNeedBasis"] == ""
