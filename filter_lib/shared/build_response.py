"""Sweep construction, port selection, and response measurement for build analysis."""

import math

from .build_types import BuildConfig, CircuitMeasurement
from .circuit_model import NamedCircuit
from .nodal_solver import solve_transducer_power_gain
from .numeric import is_finite_real
from .response_measurement import find_3db_edges


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
        if not math.isfinite(upper_ratio) or upper_ratio <= 1:
            raise ValueError("frequency span must be finite")
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
    """Measure edges and gain landmarks for one named circuit."""
    gains = solve_transducer_power_gain(
        circuit.n_nodes,
        circuit.branches(),
        source_resistance,
        load_resistance,
        circuit.in_node,
        circuit.out_node,
        freqs,
    )
    magnitudes = [math.sqrt(gain) for gain in gains]
    reference = result["f0"] if category == "bandpass" else None
    measured_low, measured_high = find_3db_edges(freqs, magnitudes, reference_frequency=reference)
    at_grid_edge = measured_low == freqs[0] or measured_high == freqs[-1]
    if category == "lowpass":
        at_grid_edge = measured_high == freqs[-1]
        f_low, f_high = None, measured_high
    elif category == "highpass":
        at_grid_edge = measured_low == freqs[0]
        f_low, f_high = measured_low, None
    else:
        f_low, f_high = measured_low, measured_high
    passband = _passband(result, category, freqs)
    in_band = [
        gain for frequency, gain in zip(freqs, gains) if passband[0] <= frequency <= passband[1]
    ]
    if not in_band:
        raise ValueError("simulation grid does not include the design passband")
    worst = min(10.0 * math.log10(gain) if gain > 0 else -math.inf for gain in in_band)
    peak = max(10.0 * math.log10(gain) if gain > 0 else -math.inf for gain in gains)
    return CircuitMeasurement(f_low, f_high, worst, at_grid_edge, peak)
