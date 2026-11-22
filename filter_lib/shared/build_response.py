"""Sweep construction, port selection, and response measurement for build analysis."""

import math
from collections.abc import Mapping

from .build_types import BuildConfig, CircuitMeasurement
from .circuit_model import NamedCircuit
from .formatting import format_frequency
from .nodal_solver import make_transducer_gain_evaluator
from .numeric import is_finite_real, require_positive_finite
from .physical_input_limits import require_port_resistance
from .response_refinement import refine_response
from .srf_screen import HIGHPASS_CHECK_MULTIPLE
from .transfer_functions import MAX_FREQUENCY_POINTS

_CATEGORIES = ("lowpass", "highpass", "bandpass")


def build_frequency_grid(result: dict, category: str, points: int) -> list[float]:
    """Build the stable logarithmic sweep used by build analysis and SPICE."""
    if not isinstance(result, Mapping):
        raise ValueError("result must be a mapping")
    if not isinstance(category, str) or category not in _CATEGORIES:
        raise ValueError("category must be 'lowpass', 'highpass', or 'bandpass'")
    if (
        isinstance(points, bool)
        or not isinstance(points, int)
        or not 2 <= points <= MAX_FREQUENCY_POINTS
    ):
        raise ValueError(f"points must be an integer between 2 and {MAX_FREQUENCY_POINTS:,}")
    if category == "bandpass":
        center = result.get("f0")
        bandwidth = result.get("bw")
        if (
            center is None
            or bandwidth is None
            or not is_finite_real(center)
            or not is_finite_real(bandwidth)
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
        require_positive_finite(center, "freq_hz")
        decades = 1.0
    start = center / (10.0**decades)
    stop = center * (10.0**decades)
    if not all(math.isfinite(value) and value > 0 for value in (start, stop)):
        raise ValueError("frequency span must be positive and finite")
    step = (math.log10(stop) - math.log10(start)) / (points - 1)
    try:
        # The last grid point can round past the float maximum even when ``stop`` is finite.
        return [10 ** (math.log10(start) + index * step) for index in range(points)]
    except OverflowError as error:
        raise ValueError("frequency span must be positive and finite") from error


def evaluation_ports(result: dict, category: str, config: BuildConfig) -> tuple[float, float]:
    """Return explicit source/load resistances without changing synthesis.

    An explicit port must lie within the accepted ratio of the design impedance; see
    ``physical_input_limits``.
    """
    key = "z0" if category == "bandpass" else "impedance"
    synthesized = result.get(key)
    if not is_finite_real(synthesized) or synthesized <= 0:
        raise ValueError(f"{key} must be positive and finite")
    source = config.source_resistance_ohm or synthesized
    load = config.load_resistance_ohm or synthesized
    require_port_resistance(source, synthesized, "Simulation source resistance")
    require_port_resistance(load, synthesized, "Simulation load resistance")
    return source, load


def highpass_passband_top(
    result: dict, category: str, freqs: list[float], qualified_range: tuple[float, float] | None
) -> float | None:
    """Where a high-pass build's passband figures stop, or ``None`` for the whole sweep.

    With a part whose SRF is checked, the passband, the reference peak, the half-power
    threshold and the cutoff are found only up to the top of the qualified range, clamped
    to at least twice the cutoff (the checked window) and at most the sweep's end. Without
    one (toroid windings, calculated values) the figures use the whole sweep, as before.
    """
    if category != "highpass" or qualified_range is None:
        return None
    if qualified_range[1] >= freqs[-1]:
        return None
    return max(qualified_range[1], HIGHPASS_CHECK_MULTIPLE * result["freq_hz"])


def highpass_peak_range(
    result: dict, category: str, freqs: list[float], qualified_range: tuple[float, float] | None
) -> tuple[float, float] | None:
    """Where a high-pass build takes its peak and half-power threshold, or ``None``.

    The qualified range within the sweep (its top as ``highpass_passband_top``); ``None``
    when that is the whole sweep, so a build without a checked part is unchanged. A cutoff
    crossing below the range is still found, and reported as outside it.
    """
    top = highpass_passband_top(result, category, freqs, qualified_range)
    if category != "highpass" or qualified_range is None:
        return None
    low = qualified_range[0]
    if top is None and low <= freqs[0]:
        return None
    return max(low, freqs[0]), freqs[-1] if top is None else top


def _passband(
    result: dict, category: str, freqs: list[float], top: float | None
) -> tuple[float, float]:
    if category == "lowpass":
        return freqs[0], result["freq_hz"]
    if category == "highpass":
        return result["freq_hz"], (freqs[-1] if top is None else top)
    return result["f_low"], result["f_high"]


def _up_to(freqs: list[float], top: float | None) -> list[float]:
    """The sweep cut at ``top`` (kept as its last point); unchanged when ``top`` is None."""
    if top is None:
        return freqs
    return [frequency for frequency in freqs if frequency < top] + [top]


def _underflow_message(
    circuit: NamedCircuit, frequency: float, source_resistance: float, load_resistance: float
) -> str:
    """Name the simulation inputs behind a transducer gain below the binary64 range."""
    inputs = [f"source resistance {source_resistance:.3g} \u03a9"]
    inputs.append(f"load resistance {load_resistance:.3g} \u03a9")
    for kind, label in (("L", "inductor"), ("C", "capacitor")):
        factors = [
            element.quality_factor
            for element in circuit.elements
            if element.kind == kind and element.quality_factor is not None
        ]
        if factors:
            inputs.append(f"lowest {label} Q {min(factors):.3g}")
    return (
        f"The simulated transducer gain at {format_frequency(frequency)} underflows binary64 "
        f"(below about 4.9e-324, or -3233 dB), so the response cannot be measured. Simulation "
        f"inputs: {', '.join(inputs)}; use less extreme component Q or port resistances"
    )


def measure_circuit(
    circuit: NamedCircuit,
    result: dict,
    category: str,
    freqs: list[float],
    source_resistance: float,
    load_resistance: float,
    passband_top_hz: float | None = None,
    peak_range_hz: tuple[float, float] | None = None,
) -> CircuitMeasurement:
    """Measure evaluated extrema and crossings, checking mesh convergence.

    ``passband_top_hz`` (high-pass only, ``highpass_passband_top``) limits every figure
    to the sweep up to it, and ``peak_range_hz`` (``highpass_peak_range``) where the peak
    and the half-power threshold are taken.
    """
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
        if gain > 0:
            return 10 * math.log10(gain)
        # The built ladders connect source to load through finite nonzero parts, so a zero
        # gain means the transmitted power fell below the binary64 range; its dB value
        # would be -inf, which no response landmark can be measured against.
        raise ValueError(_underflow_message(circuit, frequency, source_resistance, load_resistance))

    reference = result["f0"] if category == "bandpass" else None
    passband = _passband(result, category, freqs, passband_top_hz)
    grid = (
        freqs
        if len(freqs) >= 257
        else sorted(set(freqs + build_frequency_grid(result, category, 257)))
    )
    grid = _up_to(grid, passband_top_hz)
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
        peak_range=peak_range_hz,
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
        peak_frequency_hz=refined.peak_frequency,
        sweep_hz=(refined.frequencies[0], refined.frequencies[-1]),
    )
