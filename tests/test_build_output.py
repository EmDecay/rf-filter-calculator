"""Output contracts for realized-build analysis."""

import json
from dataclasses import replace

import pytest

from filter_lib.bandpass import calculate_bandpass_filter
from filter_lib.lowpass.calculations import calculate_butterworth
from filter_lib.shared.build_output import (
    build_analysis_fields,
    format_build_analysis_block,
)
from filter_lib.shared.build_simulation import BuildConfig, analyze_build


def _lowpass_result() -> dict:
    capacitors, inductors, order = calculate_butterworth(10e6, 50.0, 3, "pi")
    return {
        "filter_type": "butterworth",
        "freq_hz": 10e6,
        "impedance": 50.0,
        "capacitors": capacitors,
        "inductors": inductors,
        "order": order,
        "ripple": None,
        "topology": "pi",
    }


def test_json_fields_keep_target_ideal_nominal_and_tolerance_results_separate():
    result = _lowpass_result()
    analysis = analyze_build(
        result,
        "lowpass",
        BuildConfig(sample_count=1, seed=17, grid_points=101, use_toroid_candidates=False),
    )

    fields = build_analysis_fields(result, analysis)

    assert {"target", "simulated", "nominal_build", "tolerance_analysis"} <= fields.keys()
    assert fields["target"]["cutoff_frequency_hz"] == 10e6
    assert fields["simulated"]["realization"] == "calculated_exact_values"
    assert (
        fields["nominal_build"]["realization"]
        == "selected_nominal_parts_and_calculated_exact_fallbacks"
    )
    assert fields["nominal_build"]["substitutions"]
    assert fields["nominal_build"]["circuit_elements"]
    assert fields["tolerance_analysis"]["sample_count"] == 1
    assert fields["tolerance_analysis"]["seed"] == 17
    factors = fields["tolerance_analysis"]["cases"][0]["component_factors"]
    assert factors
    assert "physical_element_name" in factors[0]
    assert "logical_name" not in factors[0]
    assert fields["evaluation"] == {
        "source_resistance_ohm": 50.0,
        "load_resistance_ohm": 50.0,
        "gain_metric": "transducer_power_gain_db",
        "unequal_loads_change_evaluation_not_synthesis": True,
    }
    # Standard json must not need allow_nan=True for this public payload.
    assert json.loads(json.dumps(fields, allow_nan=False)) == fields


def test_bandpass_target_carries_per_design_validation_status():
    result = calculate_bandpass_filter(10e6, 0.5e6, 50.0, 3, "butterworth", "top")
    analysis = analyze_build(
        result,
        "bandpass",
        BuildConfig(grid_points=101, use_toroid_candidates=False),
    )

    target = build_analysis_fields(result, analysis)["target"]

    assert target["center_frequency_hz"] == 10e6
    assert target["bandwidth_hz"] == 0.5e6
    assert target["frequency_specification"] == "center_and_bandwidth"
    assert target["response_validation_status"] == result["response_validation_status"]


def test_text_block_states_metric_and_model_limits_without_measurement_claim():
    analysis = analyze_build(
        _lowpass_result(),
        "lowpass",
        BuildConfig(
            source_resistance_ohm=25,
            load_resistance_ohm=100,
            grid_points=101,
            use_toroid_candidates=False,
        ),
    )

    text = "\n".join(format_build_analysis_block(analysis))

    assert "simulation, not a measurement" in text
    assert "Rs=25 ohm, Rl=100 ohm" in text
    assert "Calculated exact values" in text
    assert "Selected nominal build" in text
    assert "not guaranteed worst case or probability" in text
    assert "does not imply unequal-termination synthesis" in text


def test_nonfinite_measurement_cannot_enter_machine_output():
    result = _lowpass_result()
    analysis = analyze_build(
        result,
        "lowpass",
        BuildConfig(grid_points=101, use_toroid_candidates=False),
    )
    invalid = replace(
        analysis,
        calculated=replace(analysis.calculated, peak_transducer_gain_db=float("inf")),
    )

    with pytest.raises(ValueError, match="must be finite"):
        build_analysis_fields(result, invalid)


def test_metric_outputs_expose_included_omitted_and_grid_censored_counts():
    result = _lowpass_result()
    analysis = analyze_build(
        result,
        "lowpass",
        BuildConfig(
            capacitor_tolerance_pct=99,
            inductor_tolerance_pct=99,
            grid_points=101,
            use_toroid_candidates=False,
        ),
    )
    cutoff = next(item for item in analysis.metric_summaries if item.metric == "cutoff_hz")
    payload = build_analysis_fields(result, analysis)
    cutoff_payload = next(
        item
        for item in payload["tolerance_analysis"]["metric_summaries"]
        if item["metric"] == "cutoff_hz"
    )

    assert cutoff.grid_censored_cases > 0
    assert cutoff_payload["included_cases"] == cutoff.included_cases
    assert cutoff_payload["omitted_cases"] == cutoff.omitted_cases
    assert cutoff_payload["grid_censored_cases"] == cutoff.grid_censored_cases
    assert cutoff.included_cases + cutoff.omitted_cases == len(analysis.cases)

    text = "\n".join(format_build_analysis_block(analysis))
    assert (
        f"cases included {cutoff.included_cases}, omitted {cutoff.omitted_cases} "
        f"({cutoff.grid_censored_cases} grid-boundary-censored)"
    ) in text
