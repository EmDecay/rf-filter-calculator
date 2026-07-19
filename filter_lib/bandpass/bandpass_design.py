"""High-level orchestration for calibrated Top-C bandpass designs."""

from .design_constants import VALIDATION_POINTS
from .design_result import (
    _finalize_validation,
    _parameter_fields,
    _quality_fields,
    _validation_warnings,
)
from .g_values import get_g_values
from .ideal_response import chebyshev_3db_deviation
from .input_validation import _validate_inputs
from .numeric_validation import _is_positive_finite, _validate_chebyshev_ripple
from .resonator_math import (
    _resolve_resonator_components,
    combine_resonator_q,
    compute_bandpass_3db_edges,
)
from .response_verification import validate_netlist_shape
from .top_c_calibration import _calibrate_top_c
from .top_c_synthesis import BandpassResult


def _finish_result(
    result: BandpassResult,
    validation: BandpassResult,
    calibration_iterations: int,
    q_safety: float,
    qu: float | None,
    ql: float | None,
    qc: float | None,
    resonator_qu: float | None,
) -> None:
    """Attach validation, Q, and requested-versus-internal metadata."""
    _finalize_validation(validation, calibration_iterations)
    result.update(
        _quality_fields(
            f0=result["f0"],
            bw=result["bw"],
            q_safety=q_safety,
            qu=qu,
            ql=ql,
            qc=qc,
            resonator_qu=resonator_qu,
            g_values=result["g_values"],
            fbw_synth=result["fbw_synth"],
        )
    )
    result.update(
        _parameter_fields(
            result,
            f0=result["f0"],
            bw=result["bw"],
            f_low=result["f_low"],
            f_high=result["f_high"],
            fbw=result["fbw"],
            initial_fbw=result["fbw_synth_initial"],
        )
    )
    result.update(
        {
            "synthesis_validation": validation,
            "response_validation_status": (
                "validated" if validation["validated"] else "outside_validated_envelope"
            ),
            "warnings": _validation_warnings(result["fbw"], validation),
        }
    )


def calculate_bandpass_filter(
    f0: float,
    bw: float,
    z0: float,
    n_resonators: int,
    filter_type: str,
    coupling: str,
    ripple_db: float = 0.5,
    q_safety: float = 2.0,
    qu: float | None = None,
    ql: float | None = None,
    qc: float | None = None,
    resonator_impedance: float | None = None,
    resonator_inductance: float | None = None,
) -> BandpassResult:
    """Calculate a calibrated Top-C bandpass filter and response validation.

    ``bw`` is the true -3 dB bandwidth for every filter family. ``qu`` is the
    complete resonator unloaded Q; alternatively ``ql`` and ``qc`` combine by
    reciprocal loss. Tank impedance or inductance may be selected independently
    of the source/load impedance.

    Raises:
        ValueError: If inputs are invalid or the requested circuit is unrealizable.
    """
    _validate_inputs(f0, bw, z0, n_resonators, filter_type, coupling)
    if not _is_positive_finite(q_safety):
        raise ValueError("q_safety must be positive and finite")
    resonator_qu = combine_resonator_q(qu=qu, ql=ql, qc=qc)
    _resolve_resonator_components(f0, z0, resonator_impedance, resonator_inductance)
    if filter_type == "chebyshev":
        _validate_chebyshev_ripple(ripple_db)

    fbw = bw / f0
    f_low, f_high = compute_bandpass_3db_edges(f0, bw)
    g_values = get_g_values(filter_type, n_resonators, ripple_db)
    initial_fbw = fbw
    if filter_type == "chebyshev":
        initial_fbw = fbw / chebyshev_3db_deviation(n_resonators, ripple_db)

    result, calibration_iterations = _calibrate_top_c(
        f0,
        bw,
        f_low,
        f_high,
        initial_fbw,
        z0,
        n_resonators,
        g_values,
        resonator_impedance,
        resonator_inductance,
    )
    result.update(
        {
            "f0": f0,
            "f_low": f_low,
            "f_high": f_high,
            "bw": bw,
            "fbw": fbw,
            "fbw_synth_initial": initial_fbw,
            "f0_synth": result["f_tank_hz"],
            "filter_type": filter_type,
            "coupling": coupling,
            "ripple_db": ripple_db if filter_type == "chebyshev" else None,
        }
    )

    validation = validate_netlist_shape(result, f0, bw, points=VALIDATION_POINTS)
    _finish_result(
        result,
        validation,
        calibration_iterations,
        q_safety,
        qu,
        ql,
        qc,
        resonator_qu,
    )
    return result
