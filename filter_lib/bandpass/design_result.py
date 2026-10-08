"""Assembly of validation, Q-model, and parameter metadata for bandpass results."""

from typing import Any

from .design_constants import (
    CALIBRATION_MAX_ITERATIONS,
    CALIBRATION_POINTS,
    CALIBRATION_TOLERANCE,
    VALIDATION_POINTS,
)
from .input_validation import _get_fbw_warnings
from .resonator_math import STANDARD_QU_VALUES, calculate_min_q, estimate_insertion_loss
from .top_c_calibration import TopCCalibrationError


def _finalize_validation(validation: dict[str, Any], iterations: int) -> None:
    """Record calibration provenance and enforce independent edge verification."""
    validation.update(
        {
            "iterations": iterations,
            "calibration_converged": True,
            "calibration_method": "bounded_log_newton",
            "calibration_tolerance": CALIBRATION_TOLERANCE,
            "calibration_max_iterations": CALIBRATION_MAX_ITERATIONS,
            "calibration_points": CALIBRATION_POINTS,
            "validation_points": VALIDATION_POINTS,
            "scope": "requested_half_power_edges_passband_shape_and_near_stopband_samples",
            "far_stopband_validated": False,
            "near_stopband_normalized_deviations": [-2.0, -1.5, 1.5, 2.0],
        }
    )
    if not validation["edge_validated"]:
        raise TopCCalibrationError(
            "Top-C calibration failed independent verification of both requested -3 dB edges"
        )


def _validation_warnings(fbw: float, validation: dict[str, Any], filter_type: str) -> list[str]:
    """Return design-range and independently measured response warnings."""
    warnings = _get_fbw_warnings(fbw)
    if not validation["shape_validated"]:
        # The shape check covers the passband, Chebyshev ripple, and the near-stopband
        # samples, so the text must not blame the passband alone.
        checked = (
            "passband shape, ripple, or the points just outside the passband differ"
            if filter_type == "chebyshev"
            else "passband shape or the points just outside the passband differ"
        )
        warnings.append(
            f"The -3 dB edges match your request, but the simulated {checked} from the ideal "
            f"{filter_type.title()} response shape by more than this tool's limits. Check the "
            "response plot before building."
        )
    if validation["connected_region_count"] != 1:
        warnings.append(
            "The simulated response crosses -3 dB more than twice, so it is above -3 dB in "
            "separate ranges (for example, a ripple dip inside the band). Only the edges of "
            "the range around the center were matched to your request. Check the response "
            "plot before building."
        )
    return warnings


def _insertion_loss_estimates(
    g_values: list[float], fbw_synth: float, resonator_qu: float | None
) -> dict[str, float]:
    """Return standard and optional user-Q insertion-loss estimates."""
    estimates = {
        f"{q:g}": estimate_insertion_loss(g_values, fbw_synth, q) for q in STANDARD_QU_VALUES
    }
    if resonator_qu is not None:
        key = f"{resonator_qu:g}"
        # Keep historical compact keys when they round-trip, but do not merge
        # a distinct user Q with a standard example through display rounding.
        if float(key) != resonator_qu:
            key = repr(resonator_qu)
        if key not in estimates:
            estimates[key] = estimate_insertion_loss(g_values, fbw_synth, resonator_qu)
    return estimates


def _quality_fields(
    *,
    f0: float,
    bw: float,
    q_safety: float,
    qu: float | None,
    ql: float | None,
    qc: float | None,
    resonator_qu: float | None,
    g_values: list[float],
    fbw_synth: float,
) -> dict[str, Any]:
    """Build compatibility Q fields and the explicit resonator-loss model."""
    q_min = calculate_min_q(f0, bw, q_safety)
    combination = "not_supplied"
    if qu is not None:
        combination = "direct_resonator_q"
    elif ql is not None or qc is not None:
        combination = "reciprocal_component_loss_sum"
    return {
        "q_safety": q_safety,
        "q_safety_compatibility_only": True,
        "q_min": q_min,
        "q_min_resonator": q_min,
        "q_min_is_heuristic": True,
        "q_model": {
            "definition": "complete_resonator_unloaded_q",
            "combination": combination,
            "resonator_qu": resonator_qu,
            "inductor_ql": ql,
            "capacitor_qc": qc,
            "reference_frequency_hz": f0,
        },
        "il_estimates": _insertion_loss_estimates(g_values, fbw_synth, resonator_qu),
    }


def _parameter_fields(
    result: dict[str, Any],
    *,
    f0: float,
    bw: float,
    f_low: float,
    f_high: float,
    fbw: float,
    initial_fbw: float,
) -> dict[str, Any]:
    """Build requested-versus-internal synthesis parameter records."""
    return {
        "requested_parameters": {
            "frequency_specification": "center_and_bandwidth",
            "f0_hz": f0,
            "bandwidth_hz": bw,
            "f_low_hz": f_low,
            "f_high_hz": f_high,
            "fractional_bandwidth": fbw,
        },
        "internal_synthesis_parameters": {
            "tank_frequency_hz": result["f_tank_hz"],
            "initial_prototype_fbw": initial_fbw,
            "calibrated_prototype_fbw": result["fbw_synth"],
            "resonator_impedance_ohms": result["resonator_impedance"],
            "resonator_selection": result["resonator_selection"],
        },
    }
