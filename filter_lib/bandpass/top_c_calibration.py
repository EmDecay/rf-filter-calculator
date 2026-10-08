"""Bounded two-variable calibration for raw Top-C component designs."""

import math
from collections.abc import Callable

from .design_constants import (
    CALIBRATION_MAX_ITERATIONS,
    CALIBRATION_POINTS,
    CALIBRATION_TOLERANCE,
)
from .passband_measurement import measure_netlist_passband
from .top_c_synthesis import BandpassResult, _synthesize_top_c_raw

_Residual = tuple[float, float]
_Evaluator = Callable[[float, float], tuple[BandpassResult, _Residual]]


class TopCCalibrationError(ValueError):
    """The solver could not place both -3 dB edges; the message names the solver reason.

    ``calculate_bandpass_filter`` replaces it with :func:`calibration_failure_message`
    and chains this error as ``__cause__``, so developers keep the specific reason
    while users see one plain message.
    """


def calibration_failure_message(filter_type: str) -> str:
    """User message for a design whose -3 dB edges could not be placed.

    In the maintained matrix and a wider scan (0.5% to 40% fractional bandwidth), this
    happens only for Chebyshev with ripple of 2.9 dB or more, and a smaller ripple
    fixed every such case; fewer resonators or a wider bandwidth did not reliably help.
    """
    if filter_type == "chebyshev":
        return (
            "Could not place both -3 dB edges where requested for this ripple, resonator "
            "count and bandwidth. Try a smaller ripple: with ripple near 3 dB the passband "
            "dips almost to -3 dB, so the edges are hard to place."
        )
    return (
        "Could not place both -3 dB edges where requested for this response type, "
        "resonator count and bandwidth. Try a different bandwidth or number of resonators."
    )


def _jacobian_columns(
    evaluate: _Evaluator,
    coordinates: list[float],
    residual: _Residual,
    finite_step: float = 1e-3,
) -> list[_Residual]:
    """Estimate bounded-solver Jacobian columns with a feasible one-sided step."""
    columns: list[_Residual] = []
    for axis in range(2):
        perturbed = coordinates.copy()
        perturbed[axis] += finite_step
        try:
            _candidate, trial_residual = evaluate(*perturbed)
            derivative = tuple(
                (trial - base) / finite_step for trial, base in zip(trial_residual, residual)
            )
        except ValueError:
            perturbed[axis] = coordinates[axis] - finite_step
            _candidate, trial_residual = evaluate(*perturbed)
            derivative = tuple(
                (base - trial) / finite_step for trial, base in zip(trial_residual, residual)
            )
        columns.append(derivative)
    return columns


def _newton_step(columns: list[_Residual], residual: _Residual) -> list[float]:
    """Solve the two-by-two Newton system and clamp both log-coordinate steps."""
    a, c = columns[0]
    b, d = columns[1]
    determinant = a * d - b * c
    if not math.isfinite(determinant) or abs(determinant) < 1e-8:
        raise TopCCalibrationError("Top-C calibration Jacobian is singular")
    step = [
        (-d * residual[0] + b * residual[1]) / determinant,
        (c * residual[0] - a * residual[1]) / determinant,
    ]
    return [max(-0.25, min(0.25, value)) for value in step]


def _reducing_step(
    evaluate: _Evaluator,
    coordinates: list[float],
    residual: _Residual,
    step: list[float],
) -> tuple[list[float], BandpassResult, _Residual]:
    """Backtrack until the maximum edge residual decreases."""
    base_norm = max(abs(value) for value in residual)
    scale = 1.0
    for _attempt in range(9):
        trial_coordinates = [
            coordinate + scale * delta for coordinate, delta in zip(coordinates, step)
        ]
        try:
            candidate, trial_residual = evaluate(*trial_coordinates)
        except ValueError:
            scale /= 2.0
            continue
        if max(abs(value) for value in trial_residual) < base_norm:
            return trial_coordinates, candidate, trial_residual
        scale /= 2.0
    raise TopCCalibrationError("Top-C calibration could not find a reducing bounded step")


def _calibrate_top_c(
    target_f0: float,
    target_bw: float,
    target_f_low: float,
    target_f_high: float,
    initial_fbw_synth: float,
    z0: float,
    n_resonators: int,
    g_values: list[float],
    resonator_impedance: float | None,
    resonator_inductance: float | None,
) -> tuple[BandpassResult, int]:
    """Calibrate tank frequency and prototype FBW to both requested skirts."""

    def evaluate(log_f_tank: float, log_fbw: float) -> tuple[BandpassResult, _Residual]:
        candidate = _synthesize_top_c_raw(
            math.exp(log_f_tank),
            math.exp(log_fbw),
            z0,
            n_resonators,
            g_values,
            resonator_impedance,
            resonator_inductance,
        )
        measurement = measure_netlist_passband(
            candidate, target_f0, target_bw, points=CALIBRATION_POINTS
        )
        residual = (
            math.log(measurement["f_low"] / target_f_low),
            math.log(measurement["f_high"] / target_f_high),
        )
        return candidate, residual

    coordinates = [math.log(target_f0), math.log(initial_fbw_synth)]
    candidate, residual = evaluate(*coordinates)
    iterations = 0
    while max(abs(value) for value in residual) > CALIBRATION_TOLERANCE:
        if iterations >= CALIBRATION_MAX_ITERATIONS:
            raise TopCCalibrationError(
                "Top-C calibration did not converge on both requested -3 dB edges"
            )
        step = _newton_step(_jacobian_columns(evaluate, coordinates, residual), residual)
        coordinates, candidate, residual = _reducing_step(evaluate, coordinates, residual, step)
        iterations += 1
    return candidate, iterations
