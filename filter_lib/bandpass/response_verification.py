"""Independent edge, ripple, and prototype-shape checks for calibrated Top-C designs."""

import math
from typing import Any

from ..shared.netlist_builders import build_bandpass_top_c_netlist
from ..shared.netlist_simulation import solve_s21
from ..shared.numeric import positive_geometric_mean
from ..shared.transfer_functions import magnitude_to_db
from .design_constants import (
    BANDPASS_EDGE_CALIBRATION_FBW_MAX,
    CHEBYSHEV_RIPPLE_ALLOWANCE_DB,
    EDGE_ERROR_LIMIT_REL,
    PASSBAND_SHAPE_ERROR_LIMIT_DB,
    STOPBAND_SAMPLE_ERROR_LIMIT_DB,
)
from .ideal_response import (
    _bandpass_deviation,
    chebyshev_3db_deviation,
    frequency_from_deviation,
    magnitude_db,
)
from .passband_measurement import measure_netlist_passband


def _sample_prototype_errors(
    result: dict[str, Any], measurement: dict[str, Any], target_f0: float, target_bw: float
) -> tuple[list[float], list[float], dict[str, dict[str, float]]]:
    """Collect passband, ripple-band, and representative stopband errors."""
    peak_db = measurement["peak_db"]
    ripple_db = result.get("ripple_db") or 0.5
    ripple_limit = 1.0
    if result["filter_type"] == "chebyshev":
        ripple_limit = 1.0 / chebyshev_3db_deviation(result["n_resonators"], ripple_db)

    passband_errors: list[float] = []
    ripple_samples: list[float] = []
    for frequency, actual_db in zip(measurement["freqs"], measurement["response_db"]):
        delta = _bandpass_deviation(frequency, target_f0, target_bw)
        normalized_actual = actual_db - peak_db
        if abs(delta) <= 1.0 + 1e-12:
            ideal_db = magnitude_db(
                frequency,
                target_f0,
                target_bw,
                result["n_resonators"],
                result["filter_type"],
                ripple_db,
            )
            passband_errors.append(abs(normalized_actual - ideal_db))
        if abs(delta) <= ripple_limit + 1e-12:
            ripple_samples.append(normalized_actual)

    n_nodes, branches, in_node, out_node = build_bandpass_top_c_netlist(result)
    stopband_samples: dict[str, dict[str, float]] = {}
    for delta in (-2.0, -1.5, 1.5, 2.0):
        frequency = frequency_from_deviation(delta, target_f0, target_bw)
        (magnitude,) = solve_s21(
            n_nodes, branches, result["z0"], result["z0"], in_node, out_node, [frequency]
        )
        stopband_samples[f"{delta:+g}"] = {
            "frequency_hz": frequency,
            "actual_db": magnitude_to_db(magnitude) - peak_db,
            "ideal_db": magnitude_db(
                frequency,
                target_f0,
                target_bw,
                result["n_resonators"],
                result["filter_type"],
                ripple_db,
            ),
        }
    return passband_errors, ripple_samples, stopband_samples


def validate_netlist_shape(
    result: dict[str, Any],
    target_f0: float,
    target_bw: float,
    *,
    points: int = 2001,
) -> dict[str, Any]:
    """Verify calibrated edges and ideal-prototype shape independently."""
    measurement = measure_netlist_passband(result, target_f0, target_bw, points=points)
    f_low_target, f_high_target = result["f_low"], result["f_high"]
    lower_error = measurement["f_low"] / f_low_target - 1.0
    upper_error = measurement["f_high"] / f_high_target - 1.0
    outer_lower_error = (
        measurement["outer_f_low"] / f_low_target - 1.0
        if measurement["outer_f_low"] is not None
        else math.inf
    )
    outer_upper_error = (
        measurement["outer_f_high"] / f_high_target - 1.0
        if measurement["outer_f_high"] is not None
        else math.inf
    )
    passband_errors, ripple_samples, stopband_samples = _sample_prototype_errors(
        result, measurement, target_f0, target_bw
    )
    measured_passband_variation = max(ripple_samples) - min(ripple_samples)
    max_shape_error = max(passband_errors)
    max_stopband_error = max(
        abs(sample["actual_db"] - sample["ideal_db"]) for sample in stopband_samples.values()
    )
    measured_center = positive_geometric_mean(measurement["f_low"], measurement["f_high"])
    measured_bandwidth = measurement["f_high"] - measurement["f_low"]
    edge_ok = max(abs(lower_error), abs(upper_error)) <= EDGE_ERROR_LIMIT_REL
    outer_edge_ok = (
        measurement["connected_region_count"] == 1
        and max(abs(outer_lower_error), abs(outer_upper_error)) <= EDGE_ERROR_LIMIT_REL
    )
    stopband_ok = max_stopband_error <= STOPBAND_SAMPLE_ERROR_LIMIT_DB
    shape_ok = max_shape_error <= PASSBAND_SHAPE_ERROR_LIMIT_DB and stopband_ok
    ripple_db = result.get("ripple_db") or 0.5
    if result["filter_type"] == "chebyshev":
        shape_ok = (
            shape_ok and measured_passband_variation <= ripple_db + CHEBYSHEV_RIPPLE_ALLOWANCE_DB
        )
    validated = (
        edge_ok
        and outer_edge_ok
        and shape_ok
        and result["fbw"] <= BANDPASS_EDGE_CALIBRATION_FBW_MAX
    )
    validation = {
        "measured_f_low_hz": measurement["f_low"],
        "measured_f_high_hz": measurement["f_high"],
        "measured_outer_f_low_hz": measurement["outer_f_low"],
        "measured_outer_f_high_hz": measurement["outer_f_high"],
        "measured_center_hz": measured_center,
        "measured_bandwidth_hz": measured_bandwidth,
        "lower_edge_error_rel": lower_error,
        "upper_edge_error_rel": upper_error,
        "outer_lower_edge_error_rel": outer_lower_error,
        "outer_upper_edge_error_rel": outer_upper_error,
        "center_error_rel": measured_center / target_f0 - 1.0,
        "bandwidth_error_rel": measured_bandwidth / target_bw - 1.0,
        "peak_db": measurement["peak_db"],
        "connected_region_count": measurement["connected_region_count"],
        "internal_hole_count": max(0, measurement["connected_region_count"] - 1),
        "max_passband_shape_error_db": max_shape_error,
        "max_stopband_sample_error_db": max_stopband_error,
        "measured_passband_variation_db": measured_passband_variation,
        "stopband_samples": stopband_samples,
        "validation_limits": {
            "edge_error_rel": EDGE_ERROR_LIMIT_REL,
            "passband_shape_error_db": PASSBAND_SHAPE_ERROR_LIMIT_DB,
            "chebyshev_ripple_allowance_db": CHEBYSHEV_RIPPLE_ALLOWANCE_DB,
            "representative_stopband_sample_error_db": STOPBAND_SAMPLE_ERROR_LIMIT_DB,
        },
        "edge_validated": edge_ok,
        "outer_skirt_edge_validated": outer_edge_ok,
        "shape_validated": shape_ok,
        "stopband_samples_validated": stopband_ok,
        "validated": validated,
    }
    if result["filter_type"] == "chebyshev":
        validation["measured_ripple_db"] = measured_passband_variation
    return validation
