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
    lines = _format_measurement("bandpass", measurement)
    payload = _measurement_payload(measurement, "bandpass")
    assert "did not converge; values approximate" in lines
    assert (
        "above -3 dB in 2 separate ranges; edges taken from the range around the peak "
        "nearest the center"
    ) in lines
    # The reference peak (-2 dB) differs from the overall peak (-1 dB), so it is named.
    assert "-3 dB measured from the -2.00 dB peak at 10 Hz" in lines
    assert payload["measurement_converged"] is False
    assert payload["selected_region_index"] == 1
    assert payload["half_power_regions"][0] == {"f_low_hz": 5, "f_high_hz": 6}


@pytest.mark.parametrize(
    "category, measurement, text_claim, missing_keys",
    [
        (
            "bandpass",
            CircuitMeasurement(9e6, None, -60, True),
            "no complete -3 dB passband within the simulated frequency range",
            ("f_high_hz", "f0_hz", "bandwidth_hz"),
        ),
        (
            "lowpass",
            CircuitMeasurement(None, None, -60, True),
            "no -3 dB cutoff within the simulated frequency range",
            ("cutoff_hz", "f0_hz", "bandwidth_hz"),
        ),
        (
            "highpass",
            CircuitMeasurement(None, None, -60, True),
            "no -3 dB cutoff within the simulated frequency range",
            ("cutoff_hz", "f0_hz", "bandwidth_hz"),
        ),
    ],
)
def test_missing_skirt_is_reported_instead_of_invented(
    category, measurement, text_claim, missing_keys
):
    lines = _format_measurement(category, measurement)
    payload = _measurement_payload(measurement, category)

    assert lines[0] == text_claim
    # The missing landmark already says the range was exceeded; it is not repeated.
    assert sum("simulated frequency range" in line for line in lines) == 1
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
            f"{substitution.turns} turns of AWG {substitution.wire_awg} on "
            f"{substitution.core_name} ({substitution.wire_length_mm:.0f} mm wire)"
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

    assert "Build Simulation (chosen parts; simulated, not measured)" in text
    assert "Simulated with a 25 \u03a9 source and a 100 \u03a9 load" in text
    assert "Ideal values:" in text
    assert "Chosen parts:" in text
    assert "The tolerance cases do not guarantee the true worst case." in text
    # Bullets wrap, so compare the limitation with whitespace folded.
    assert "the different source and load resistances apply only to this simulation" in " ".join(
        text.split()
    )


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
        f"{cutoff.included_cases} of {len(analysis.cases)} cases; "
        f"{cutoff.grid_censored_cases} outside the simulated frequency range"
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
        if line.startswith("  ") and " cases; " in line
    ]
    payload = build_analysis_fields(result, unresolved)["tolerance_analysis"]

    assert len(summary_lines) == len(analysis.metric_summaries) == 3
    assert all(line.endswith("; 2 did not converge") for line in summary_lines)
    assert [item["unresolved_cases"] for item in payload["metric_summaries"]] == [2, 2, 2]


def _bandpass_analysis(**config):
    result = calculate_bandpass_filter(10e6, 0.5e6, 50.0, 3, "butterworth", "top")
    return result, analyze_build(result, "bandpass", BuildConfig(grid_points=51, **config))


def test_bandpass_block_uses_component_table_names():
    _result, analysis = _bandpass_analysis()

    text = "\n".join(format_build_analysis_block(analysis))

    for name in ("Cp1", "L1", "Cs12", "Cs23", "Ce_in", "Ce_out"):
        assert f"  {name}:" in text
    for circuit_name in ("CT1", "LT1", "CK1", "CIN", "COUT"):
        assert circuit_name not in text


def test_repeated_inductor_caveat_prints_once_but_json_keeps_every_entry():
    result, analysis = _bandpass_analysis()

    lines = format_build_analysis_block(analysis)
    warnings = build_analysis_fields(result, analysis)["nominal_build"]["warnings"]

    caveat = "Not checked: RF Q, core loss, SRF, saturation, heating, power handling."
    folded = " ".join(" ".join(lines).split())
    assert folded.count(caveat) == 1
    assert f"- L1–L3: {caveat} Measure before use." in folded
    assert [item for item in warnings if caveat in item] == [
        f"L{index}: {caveat} Measure before use." for index in (1, 2, 3)
    ]


def test_caveats_print_only_for_features_the_run_used():
    from filter_lib.shared.build_analysis import RANDOM_CASES_LIMITATION
    from filter_lib.shared.nominal_realization import TOROID_LIMITATION

    result = _lowpass_result()
    plain = analyze_build(
        result, "lowpass", BuildConfig(grid_points=51, use_toroid_candidates=False)
    )
    sampled = analyze_build(result, "lowpass", BuildConfig(grid_points=51, sample_count=2, seed=4))

    plain_text = " ".join(" ".join(format_build_analysis_block(plain)).split())
    sampled_text = " ".join(" ".join(format_build_analysis_block(sampled)).split())

    # No toroid and no random cases: neither caveat nor the unused seed is printed ...
    assert TOROID_LIMITATION not in plain_text
    assert RANDOM_CASES_LIMITATION not in plain_text
    assert "seed" not in plain_text
    # ... while JSON keeps both entries in the same list.
    plain_limits = build_analysis_fields(result, plain)["tolerance_analysis"]["limitations"]
    assert {TOROID_LIMITATION, RANDOM_CASES_LIMITATION} <= set(plain_limits)
    assert TOROID_LIMITATION in sampled_text
    assert RANDOM_CASES_LIMITATION in sampled_text
    assert "and 2 extra random tolerance cases (seed 4)." in sampled_text


def test_chosen_parts_row_says_when_calculated_values_were_used():
    analysis = analyze_build(
        _lowpass_result(), "lowpass", BuildConfig(grid_points=51, use_toroid_candidates=False)
    )

    lines = format_build_analysis_block(analysis)

    chosen = lines.index(next(line for line in lines if line.startswith("Chosen parts:")))
    assert lines[chosen + 2] == " " * 15 + "calculated value used for 1 of 3 parts (see Parts used)"
    assert "  L1: 1.59 µH, calculated value used (toroid windings off)" in lines


def test_block_states_part_losses_and_metric_labels_not_json_keys():
    lossless = analyze_build(
        _lowpass_result(), "lowpass", BuildConfig(grid_points=51, use_toroid_candidates=False)
    )
    lossy = analyze_build(
        _lowpass_result(),
        "lowpass",
        BuildConfig(grid_points=51, inductor_q=120, capacitor_q=900, use_toroid_candidates=False),
    )

    lossless_text = "\n".join(format_build_analysis_block(lossless))
    lossy_text = "\n".join(format_build_analysis_block(lossy))

    assert "Part losses (Q): none; all parts are lossless." in lossless_text
    assert "Part losses (Q at 10 MHz): inductors 120, capacitors 900." in lossy_text
    for label in ("  Peak gain:", "  Lowest gain in passband:", "  -3 dB cutoff:"):
        assert label in lossless_text
    for key in ("peak_transducer_gain_db", "worst_passband_db", "cutoff_hz", "ohm"):
        assert key not in lossless_text
