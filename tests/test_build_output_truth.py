"""Truthfulness contracts for realized-build machine output."""

from filter_lib.bandpass import calculate_bandpass_filter
from filter_lib.highpass.calculations import calculate_butterworth as calculate_highpass
from filter_lib.lowpass.calculations import calculate_butterworth
from filter_lib.shared.build_output import build_analysis_fields
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


def test_realization_summary_discloses_calculated_fallbacks() -> None:
    result = _lowpass_result()
    analysis = analyze_build(
        result,
        "lowpass",
        BuildConfig(grid_points=51, use_toroid_candidates=False),
    )

    fields = build_analysis_fields(result, analysis)
    nominal = fields["nominal_build"]
    model = fields["build_model"]

    assert nominal["realization"] == "selected_nominal_parts_and_calculated_exact_fallbacks"
    assert nominal["has_calculated_exact_fallbacks"] is True
    assert nominal["calculated_exact_fallback_elements"]
    assert model["toroid_candidate_screen_enabled"] is False
    assert model["verified_toroid_candidate_used"] is False
    assert model["uses_verified_toroid_candidates"] is False


def test_toroid_screen_toggle_is_separate_from_actual_candidate_use() -> None:
    result = _lowpass_result()
    analysis = analyze_build(result, "lowpass", BuildConfig(grid_points=51))

    model = build_analysis_fields(result, analysis)["build_model"]

    assert model["toroid_candidate_screen_enabled"] is True
    assert model["verified_toroid_candidate_used"] == bool(model["verified_toroid_elements"])
    assert model["uses_verified_toroid_candidates"] == model["verified_toroid_candidate_used"]


def test_bandpass_complete_resonator_q_is_in_effective_loss_model() -> None:
    result = calculate_bandpass_filter(10e6, 0.5e6, 50, 3, "butterworth", "top", qu=150)
    analysis = analyze_build(
        result,
        "bandpass",
        BuildConfig(grid_points=51, use_toroid_candidates=False),
    )

    model = build_analysis_fields(result, analysis)["build_model"]
    effective = model["effective_loss_model"]

    assert model["resonator_q"] is None
    assert model["q_fields_semantics"] == "explicit_build_config_overrides"
    assert effective["is_lossless"] is False
    assert effective["source"] == "bandpass_synthesis_q_model"
    assert effective["synthesis_q_model_applied"] is True
    assert effective["synthesis_q_model"]["resonator_qu"] == 150
    assert effective["physical_elements_with_series_loss"]


def test_bandpass_separate_component_q_preserves_tank_only_semantics() -> None:
    result = calculate_bandpass_filter(
        10e6,
        0.5e6,
        50,
        3,
        "butterworth",
        "top",
        ql=200,
        qc=400,
    )
    analysis = analyze_build(
        result,
        "bandpass",
        BuildConfig(grid_points=51, use_toroid_candidates=False),
    )

    effective = build_analysis_fields(result, analysis)["build_model"]["effective_loss_model"]
    lossy = effective["physical_elements_with_series_loss"]

    assert effective["synthesis_q_model"]["inductor_ql"] == 200
    assert effective["synthesis_q_model"]["capacitor_qc"] == 400
    assert all(item["quality_factor_at_reference"] == 200 for item in lossy if item["kind"] == "L")
    assert all(item["logical_name"].startswith("CT") for item in lossy if item["kind"] == "C")


def test_lowpass_measurement_does_not_invent_center_or_lower_skirt() -> None:
    result = _lowpass_result()
    analysis = analyze_build(
        result, "lowpass", BuildConfig(grid_points=51, use_toroid_candidates=False)
    )

    measurement = build_analysis_fields(result, analysis)["simulated"]["measurement"]

    assert measurement["cutoff_hz"] == measurement["f_high_hz"]
    assert measurement["f_low_hz"] is None
    assert measurement["f0_hz"] is None
    assert measurement["bandwidth_hz"] is None


def test_highpass_measurement_does_not_invent_center_or_upper_skirt() -> None:
    inductors, capacitors, order = calculate_highpass(10e6, 50.0, 3, "t")
    result = {
        "filter_type": "butterworth",
        "freq_hz": 10e6,
        "impedance": 50.0,
        "capacitors": capacitors,
        "inductors": inductors,
        "order": order,
        "ripple": None,
        "topology": "t",
    }
    analysis = analyze_build(
        result, "highpass", BuildConfig(grid_points=51, use_toroid_candidates=False)
    )

    measurement = build_analysis_fields(result, analysis)["simulated"]["measurement"]

    assert measurement["cutoff_hz"] == measurement["f_low_hz"]
    assert measurement["f_high_hz"] is None
    assert measurement["f0_hz"] is None
    assert measurement["bandwidth_hz"] is None
