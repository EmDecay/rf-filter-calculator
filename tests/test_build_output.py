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
from filter_lib.shared.build_output_formatting import _format_measurement
from filter_lib.shared.build_output_payloads import _measurement_payload
from filter_lib.shared.build_simulation import BuildConfig, CircuitMeasurement, analyze_build
from filter_lib.shared.toroid_selection import recommend_cores


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
    measurement = fields["simulated"]["measurement"]
    assert measurement["measurement_converged"] is True
    assert measurement["half_power_threshold_db"] == pytest.approx(
        measurement["reference_peak_gain_db"] - 3.01029995664
    )
    assert measurement["connected_region_count"] == len(measurement["half_power_regions"])
    assert fields["tolerance_analysis"]["measurement_policy"]["grid_points_are_initial"] is True


def test_unresolved_and_disconnected_measurements_remain_explicit_in_text_and_json():
    measurement = CircuitMeasurement(
        9,
        11,
        -40,
        False,
        -1,
        reference_peak_frequency_hz=10,
        reference_peak_gain_db=-2,
        threshold_db=-5.0103,
        threshold_regions=((5, 6), (9, 11)),
        selected_region_index=1,
        center_in_selected_region=True,
        measurement_converged=False,
    )
    text = _format_measurement("bandpass", measurement)
    payload = _measurement_payload(measurement, "bandpass")
    assert "UNRESOLVED" in text and "2 disconnected regions, selected region 2" in text
    assert "half-power reference -2.000 dB at 10 Hz" in text
    assert payload["measurement_converged"] is False
    assert payload["selected_region_index"] == 1
    assert payload["half_power_regions"][0] == {"f_low_hz": 5, "f_high_hz": 6}


@pytest.mark.parametrize(
    "category, measurement, text_claim, missing_keys",
    [
        (
            "bandpass",
            CircuitMeasurement(9e6, None, -60, True),
            "no complete -3 dB passband on the simulation grid",
            ("f_high_hz", "f0_hz", "bandwidth_hz"),
        ),
        (
            "lowpass",
            CircuitMeasurement(None, None, -60, True),
            "no -3 dB cutoff on the simulation grid",
            ("cutoff_hz", "f0_hz", "bandwidth_hz"),
        ),
        (
            "highpass",
            CircuitMeasurement(None, None, -60, True),
            "no -3 dB cutoff on the simulation grid",
            ("cutoff_hz", "f0_hz", "bandwidth_hz"),
        ),
    ],
)
def test_missing_skirt_is_reported_instead_of_invented(
    category, measurement, text_claim, missing_keys
):
    text = _format_measurement(category, measurement)
    payload = _measurement_payload(measurement, category)

    assert text.startswith(text_claim)
    assert "skirt outside simulation window" in text
    assert payload["edge_at_simulation_grid_boundary"] is True
    assert all(payload[key] is None for key in missing_keys)


def test_bandpass_target_carries_per_design_validation_status():
    result = calculate_bandpass_filter(10e6, 0.5e6, 50.0, 2, "butterworth", "top")
    analysis = analyze_build(
        result,
        "bandpass",
        BuildConfig(grid_points=51, use_toroid_candidates=False),
    )

    target = build_analysis_fields(result, analysis)["target"]

    assert result["response_validation_status"] == "validated"
    assert target == {
        "category": "bandpass",
        "response_type": "butterworth",
        "order": 2,
        "frequency_specification": "center_and_bandwidth",
        "center_frequency_hz": 10e6,
        "bandwidth_hz": 0.5e6,
        "f_low_hz": result["f_low"],
        "f_high_hz": result["f_high"],
        "design_impedance_ohm": 50.0,
        "equal_termination_synthesis": True,
        "response_validation_status": "validated",
    }


def test_toroid_substitutions_report_winding_wire_in_text_and_json():
    result = _lowpass_result()
    analysis = analyze_build(result, "lowpass", BuildConfig(grid_points=101))
    toroid_substitutions = [
        item
        for item in analysis.nominal_realization.substitutions
        if item.method == "verified_toroid_integer_turns"
    ]
    assert toroid_substitutions

    text = "\n".join(format_build_analysis_block(analysis))
    payloads = {
        item["logical_name"]: item
        for item in build_analysis_fields(result, analysis)["nominal_build"]["substitutions"]
    }
    for substitution in toroid_substitutions:
        best = recommend_cores(substitution.calculated_value, result["freq_hz"], top_n=1)[0]
        assert substitution.wire_awg == best.mechanical.awg
        assert substitution.wire_length_mm == best.mechanical.wire_length_mm
        assert (
            f"on {substitution.core_name}, {substitution.turns} turns of "
            f"AWG {substitution.wire_awg} ({substitution.wire_length_mm:.0f} mm)"
        ) in text
        payload = payloads[substitution.logical_name]
        assert payload["wire_awg"] == substitution.wire_awg
        assert payload["wire_length_mm"] == substitution.wire_length_mm


def test_exact_fallback_inductors_carry_no_winding_wire():
    result = _lowpass_result()
    analysis = analyze_build(
        result, "lowpass", BuildConfig(grid_points=101, use_toroid_candidates=False)
    )

    inductors = [item for item in analysis.nominal_realization.substitutions if item.kind == "L"]
    assert inductors
    assert all(item.wire_awg is None and item.wire_length_mm is None for item in inductors)
    payloads = build_analysis_fields(result, analysis)["nominal_build"]["substitutions"]
    for payload in (item for item in payloads if item["kind"] == "L"):
        assert payload["wire_awg"] is None
        assert payload["wire_length_mm"] is None
    assert "AWG" not in "\n".join(format_build_analysis_block(analysis))


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


def test_unresolved_case_counts_are_disclosed_in_text_and_json():
    result = _lowpass_result()
    analysis = analyze_build(
        result, "lowpass", BuildConfig(grid_points=51, use_toroid_candidates=False)
    )
    unresolved = replace(
        analysis,
        metric_summaries=tuple(
            replace(item, unresolved_cases=2) for item in analysis.metric_summaries
        ),
    )

    summary_lines = [
        line
        for line in format_build_analysis_block(unresolved)
        if line.startswith("  ") and "cases included" in line
    ]
    payload = build_analysis_fields(result, unresolved)["tolerance_analysis"]

    assert len(summary_lines) == len(analysis.metric_summaries) == 3
    assert all(line.endswith("(2 unresolved)") for line in summary_lines)
    assert [item["unresolved_cases"] for item in payload["metric_summaries"]] == [2, 2, 2]
