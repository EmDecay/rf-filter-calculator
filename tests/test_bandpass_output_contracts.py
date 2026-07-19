"""Machine-readable bandpass output contract regressions."""

import csv
import io
import json

import pytest

from filter_lib.bandpass.calculations import calculate_bandpass_filter
from filter_lib.bandpass.formatters import format_csv, format_json


def _result() -> dict:
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


def test_json_exposes_validation_q_and_candidate_semantics() -> None:
    data = json.loads(
        format_json(_result(), eseries="E24"),
        parse_constant=lambda value: (_ for _ in ()).throw(ValueError(value)),
    )

    assert data["response_validation_status"] in {
        "validated",
        "outside_validated_envelope",
    }
    assert data["synthesis_validation"]["edge_validated"] is True
    assert data["q_model"]["definition"] == "complete_resonator_unloaded_q"
    assert data["q_model"]["combination"] == "reciprocal_component_loss_sum"
    assert data["q_min_is_heuristic"] is True
    assert data["q_safety_compatibility_only"] is True
    assert data["resonator_toroid_candidates"] == data["resonator_toroid_recommendations"]

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


@pytest.mark.parametrize("field", ["f0", "bw", "z0"])
def test_json_rejects_non_finite_numeric_fields(field: str) -> None:
    result = _result()
    result[field] = float("nan")

    with pytest.raises(ValueError, match="finite"):
        format_json(result, include_toroids=False)


def test_csv_is_rectangular_and_emits_only_selected_parallel_pairs() -> None:
    rows = list(csv.reader(io.StringIO(format_csv(_result(), eseries="E24"))))
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
