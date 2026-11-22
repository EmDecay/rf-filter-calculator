"""Truthfulness contracts for realized-build machine output."""

import pytest

from filter_lib.bandpass import calculate_bandpass_filter
from filter_lib.highpass.calculations import calculate_butterworth as calculate_highpass
from filter_lib.lowpass.calculations import calculate_butterworth
from filter_lib.shared.build_output import build_analysis_fields
from filter_lib.shared.build_simulation import BuildConfig, analyze_build
from tests.parts_helpers import parts_for


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


def _highpass_result() -> dict:
    inductors, capacitors, order = calculate_highpass(10e6, 50.0, 3, "t")
    return {
        "filter_type": "butterworth",
        "freq_hz": 10e6,
        "impedance": 50.0,
        "capacitors": capacitors,
        "inductors": inductors,
        "order": order,
        "ripple": None,
        "topology": "t",
    }


def _calculated_inductor_parts(result: dict, category: str):
    """E24 capacitors with every inductor built at its calculated value."""
    return parts_for(result, category, build_inductors="calculated")


@pytest.mark.parametrize(
    "inductance_override, build_inductors, used, fallbacks",
    [
        (None, "auto", True, []),
        # 3 nH has no acceptable integer-turn winding on the qualified cores and is below
        # the chip catalog (10 nH to 100 nH).
        (3e-9, "auto", False, ["L1"]),
        (None, "calculated", False, ["L1"]),
    ],
    ids=["suggestion-used", "no-qualifying-suggestion", "suggestions-not-used"],
)
def test_realization_summary_separates_build_inductor_choice_from_actual_use(
    inductance_override, build_inductors, used, fallbacks
) -> None:
    result = _lowpass_result()
    if inductance_override is not None:
        result["inductors"] = [inductance_override]
    analysis = analyze_build(
        result,
        "lowpass",
        BuildConfig(grid_points=51),
        parts=parts_for(result, "lowpass", build_inductors=build_inductors),
    )

    fields = build_analysis_fields(result, analysis)
    nominal = fields["nominal_build"]
    model = fields["build_model"]

    assert model["build_inductor_choice"] == build_inductors
    assert model["suggested_inductors_used"] is used
    assert model["suggested_inductor_elements"] == (["L1"] if used else [])
    assert nominal["has_calculated_exact_fallbacks"] is bool(fallbacks)
    assert nominal["calculated_exact_fallback_elements"] == fallbacks
    assert nominal["realization"] == (
        "selected_nominal_parts_and_calculated_exact_fallbacks"
        if fallbacks
        else "selected_nominal_physical_parts"
    )


def test_bandpass_complete_resonator_q_is_in_effective_loss_model() -> None:
    result = calculate_bandpass_filter(10e6, 0.5e6, 50, 2, "butterworth", "top", qu=150)
    analysis = analyze_build(
        result,
        "bandpass",
        BuildConfig(grid_points=51),
        parts=_calculated_inductor_parts(result, "bandpass"),
    )

    model = build_analysis_fields(result, analysis)["build_model"]
    effective = model["effective_loss_model"]

    assert model["resonator_q"] is None
    assert model["q_fields_semantics"] == "explicit_build_config_overrides"
    assert effective["is_lossless"] is False
    assert effective["source"] == "bandpass_synthesis_q_model"
    assert effective["synthesis_q_model_applied"] is True
    assert effective["synthesis_q_model"]["resonator_qu"] == 150
    assert [
        item["physical_element_name"] for item in effective["physical_elements_with_series_loss"]
    ] == ["LT1", "LT2"]


def test_bandpass_separate_component_q_preserves_tank_only_semantics() -> None:
    result = calculate_bandpass_filter(
        10e6,
        0.5e6,
        50,
        2,
        "butterworth",
        "top",
        ql=200,
        qc=400,
    )
    analysis = analyze_build(
        result,
        "bandpass",
        BuildConfig(grid_points=51),
        parts=_calculated_inductor_parts(result, "bandpass"),
    )

    effective = build_analysis_fields(result, analysis)["build_model"]["effective_loss_model"]
    lossy = effective["physical_elements_with_series_loss"]

    assert effective["synthesis_q_model"]["inductor_ql"] == 200
    assert effective["synthesis_q_model"]["capacitor_qc"] == 400
    assert {item["logical_name"] for item in lossy} == {"CT1", "CT2", "LT1", "LT2"}
    assert all(item["quality_factor_at_reference"] == 200 for item in lossy if item["kind"] == "L")
    assert all(item["quality_factor_at_reference"] == 400 for item in lossy if item["kind"] == "C")


@pytest.mark.parametrize(
    "category, make_result, cutoff_key, absent_skirt_key",
    [
        ("lowpass", _lowpass_result, "f_high_hz", "f_low_hz"),
        ("highpass", _highpass_result, "f_low_hz", "f_high_hz"),
    ],
    ids=["lowpass", "highpass"],
)
def test_ladder_measurement_does_not_invent_center_or_opposite_skirt(
    category, make_result, cutoff_key, absent_skirt_key
) -> None:
    result = make_result()
    analysis = analyze_build(
        result,
        category,
        BuildConfig(grid_points=51),
        parts=_calculated_inductor_parts(result, category),
    )

    measurement = build_analysis_fields(result, analysis)["simulated"]["measurement"]

    assert measurement["cutoff_hz"] == measurement[cutoff_key]
    assert measurement["cutoff_hz"] == pytest.approx(10e6, rel=0.01)
    assert measurement[absent_skirt_key] is None
    assert measurement["f0_hz"] is None
    assert measurement["bandwidth_hz"] is None
