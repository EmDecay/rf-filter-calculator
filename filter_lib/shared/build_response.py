"""Sweep construction, port selection, and response measurement for build analysis."""

import math

from .build_types import BuildConfig, CircuitMeasurement
from .circuit_model import NamedCircuit
from .nodal_solver import make_transducer_gain_evaluator
from .numeric import is_finite_real
from .response_refinement import refine_response


def _is_finite_number(value: object) -> bool:
    return is_finite_real(value)


def build_frequency_grid(result: dict, category: str, points: int) -> list[float]:
    """Build the stable logarithmic sweep used by build analysis and SPICE."""
    if category == "bandpass":
        center = result.get("f0")
        bandwidth = result.get("bw")
        if (
            center is None
            or bandwidth is None
            or not _is_finite_number(center)
            or not _is_finite_number(bandwidth)
            or center <= 0
            or bandwidth <= 0
        ):
            raise ValueError("bandpass f0 and bw must be positive and finite")
        upper_ratio = (center + 10.0 * bandwidth) / center
        if not math.isfinite(upper_ratio):
            raise ValueError("frequency span must be finite")
        if upper_ratio <= 1:
            # 10 * bw is below the binary64 resolution of f0, so the sweep has zero width.
            raise ValueError("bandpass bandwidth is too small relative to f0 to form a sweep span")
        decades = min(1.0, math.log10(upper_ratio))
    else:
        center = result.get("freq_hz")
        if not _is_finite_number(center) or center <= 0:
            raise ValueError("freq_hz must be positive and finite")
        decades = 1.0
    start = center / (10.0**decades)
    stop = center * (10.0**decades)
    if not all(math.isfinite(value) and value > 0 for value in (start, stop)):
        raise ValueError("frequency span must be positive and finite")
    step = (math.log10(stop) - math.log10(start)) / (points - 1)
    return [10 ** (math.log10(start) + index * step) for index in range(points)]


def evaluation_ports(result: dict, category: str, config: BuildConfig) -> tuple[float, float]:
    """Return explicit source/load resistances without changing synthesis."""
    key = "z0" if category == "bandpass" else "impedance"
    synthesized = result.get(key)
    if not _is_finite_number(synthesized) or synthesized <= 0:
        raise ValueError(f"{key} must be positive and finite")
    source = config.source_resistance_ohm or synthesized
    load = config.load_resistance_ohm or synthesized
    return source, load


def _passband(result: dict, category: str, freqs: list[float]) -> tuple[float, float]:
    if category == "lowpass":
        return freqs[0], result["freq_hz"]
    if category == "highpass":
        return result["freq_hz"], freqs[-1]
    return result["f_low"], result["f_high"]


def measure_circuit(
    circuit: NamedCircuit,
    result: dict,
    category: str,
    freqs: list[float],
    source_resistance: float,
    load_resistance: float,
) -> CircuitMeasurement:
    """Measure evaluated extrema and crossings, checking mesh convergence."""
    transducer_gain = make_transducer_gain_evaluator(
        circuit.n_nodes,
        circuit.branches(),
        source_resistance,
        load_resistance,
        circuit.in_node,
        circuit.out_node,
    )

    def response(frequency: float) -> float:
        gain = transducer_gain(frequency)
        return 10 * math.log10(gain) if gain > 0 else -math.inf

    reference = result["f0"] if category == "bandpass" else None
    passband = _passband(result, category, freqs)
    grid = (
        freqs
        if len(freqs) >= 257
        else sorted(set(freqs + build_frequency_grid(result, category, 257)))
    )
    if category == "bandpass":
        intervals = 16 * result["n_resonators"]
        grid = sorted(
            set(grid + [passband[0] + result["bw"] * i / intervals for i in range(intervals + 1)])
        )
    refined = refine_response(
        response,
        grid,
        passband,
        reference_frequency=reference,
        frequency_scale=result["bw"] if category == "bandpass" else result["freq_hz"],
    )
    measured_low, measured_high = refined.regions[refined.selected_region]
    at_grid_edge = measured_low is None or measured_high is None
    if category == "lowpass":
        at_grid_edge = measured_high is None
        f_low, f_high = None, measured_high
    elif category == "highpass":
        at_grid_edge = measured_low is None
        f_low, f_high = measured_low, None
    else:
        f_low, f_high = measured_low, measured_high
    return CircuitMeasurement(
        f_low,
        f_high,
        refined.worst_db,
        at_grid_edge,
        refined.peak_db,
        reference_peak_frequency_hz=refined.reference_frequency,
        reference_peak_gain_db=refined.reference_db,
        threshold_db=refined.reference_db - 10 * math.log10(2),
        threshold_regions=refined.regions,
        selected_region_index=refined.selected_region,
        center_in_selected_region=(
            (measured_low is None or measured_low <= reference)
            and (measured_high is None or reference <= measured_high)
        )
        if reference is not None
        else None,
        measurement_converged=refined.converged,
        response_evaluations=refined.evaluations,
    )
