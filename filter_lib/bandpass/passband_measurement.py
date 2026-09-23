"""Ideal-component netlist measurement of the center-connected bandpass region."""

import math
from typing import Any

from ..shared.netlist_builders import build_bandpass_top_c_netlist
from ..shared.netlist_simulation import find_3db_edges, solve_s21
from ..shared.numeric import is_finite_real
from ..shared.plot_threshold_analysis import find_threshold_regions
from ..shared.transfer_functions import MAX_FREQUENCY_POINTS, magnitude_to_db
from .design_constants import THREE_DB_DOWN, VALIDATION_POINTS
from .ideal_response import frequency_from_deviation


def _deviation_grid(f0: float, bw: float, points: int, span: float = 4.0) -> list[float]:
    """Return a frequency grid uniform in normalized bandpass deviation."""
    if (
        isinstance(points, bool)
        or not isinstance(points, int)
        or not 3 <= points <= MAX_FREQUENCY_POINTS
    ):
        raise ValueError(f"points must be an integer between 3 and {MAX_FREQUENCY_POINTS:,}")
    if not is_finite_real(span) or span <= 0:
        raise ValueError("span must be positive and finite")
    step = 2.0 * span / (points - 1)
    return [frequency_from_deviation(-span + index * step, f0, bw) for index in range(points)]


def require_resolvable_bandwidth(f0: float, bw: float) -> None:
    """Reject a bandwidth too narrow for the verification sweep to resolve around ``f0``.

    Synthesis is calibrated and verified on grids uniform in bandpass deviation, the
    finest with ``VALIDATION_POINTS`` samples. Adjacent samples sit
    ``span * (bw / f0) / (points - 1)`` apart in ``ln(f)``, and computed frequencies
    are quantized to the binary64 spacing of ``ln(f0)``, so a sufficiently narrow
    band collapses the grid onto repeated frequencies.
    """
    grid = _deviation_grid(f0, bw, VALIDATION_POINTS)
    if all(low < high for low, high in zip(grid, grid[1:])):
        return
    minimum_fbw = _minimum_resolvable_fbw(f0)
    raise ValueError(
        f"Bandwidth {bw:.3g} Hz is too narrow relative to the {f0:.3g} Hz center frequency "
        f"to synthesize at double precision; use a fractional bandwidth of at least "
        f"{minimum_fbw:.2g} (a bandwidth of at least {_round_up(minimum_fbw * f0):.2g} Hz)"
    )


def _minimum_resolvable_fbw(f0: float, span: float = 4.0) -> float:
    """Fractional bandwidth whose grid spacing is twice the binary64 resolution of ``ln(f)``.

    Twice the spacing keeps samples distinct when ``ln(f)`` crosses a power of two, where
    its spacing doubles, and absorbs the rounding of ``exp``; one spacing, 2**-52, is the
    floor near 1 Hz where ``ln(f0)`` is small.
    """
    resolution = max(math.ulp(abs(math.log(f0))), math.ulp(1.0))
    return _round_up(2.0 * resolution * (VALIDATION_POINTS - 1) / span)


def _round_up(value: float) -> float:
    """Round up to two significant digits so a stated minimum is never understated."""
    exponent = math.floor(math.log10(value)) - 1
    return math.ceil(value / 10.0**exponent) * 10.0**exponent


def measure_netlist_passband(
    result: dict[str, Any],
    target_f0: float,
    target_bw: float,
    *,
    points: int = 401,
) -> dict[str, Any]:
    """Measure the center-connected, peak-relative -3.0103 dB passband."""
    freqs = _deviation_grid(target_f0, target_bw, points)
    n_nodes, branches, in_node, out_node = build_bandpass_top_c_netlist(result)
    z0 = result["z0"]
    mags = solve_s21(n_nodes, branches, z0, z0, in_node, out_node, freqs)
    local_maxima = [
        index
        for index, value in enumerate(mags)
        if (index == 0 or value >= mags[index - 1])
        and (index == len(mags) - 1 or value >= mags[index + 1])
    ]
    log_reference = math.log(target_f0)
    peak_index = min(
        local_maxima,
        key=lambda index: (
            abs(math.log(freqs[index]) - log_reference),
            -mags[index],
        ),
    )
    peak = mags[peak_index]
    if peak <= 0 or not math.isfinite(peak):
        raise ValueError("Synthesized circuit has no finite passband peak")
    response_db = [magnitude_to_db(magnitude) for magnitude in mags]
    peak_db = magnitude_to_db(peak)
    regions = find_threshold_regions(freqs, response_db, peak_db - THREE_DB_DOWN)
    f_low, f_high = find_3db_edges(freqs, mags, reference_frequency=target_f0)
    if f_low is None or f_high is None or f_low == freqs[0] or f_high == freqs[-1]:
        raise ValueError("Synthesized passband skirts are outside the calibration grid")

    outer_f_low = regions[0].f_low if regions else None
    outer_f_high = regions[-1].f_high if regions else None
    if outer_f_low is None and regions:
        outer_f_low = freqs[0]
    if outer_f_high is None and regions:
        outer_f_high = freqs[-1]
    return {
        "f_low": f_low,
        "f_high": f_high,
        "outer_f_low": outer_f_low,
        "outer_f_high": outer_f_high,
        "peak_db": peak_db,
        "connected_region_count": len(regions),
        "freqs": freqs,
        "mags": mags,
        "response_db": response_db,
    }
