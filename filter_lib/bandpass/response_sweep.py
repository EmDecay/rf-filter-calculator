"""Frequency-grid and ideal/netlist response sweep helpers for bandpass filters."""

import math
from collections.abc import Mapping

from ..shared.netlist_builders import build_bandpass_top_c_netlist
from ..shared.netlist_simulation import solve_s21
from ..shared.numeric import is_finite_real
from ..shared.transfer_functions import (
    MAX_FREQUENCY_POINTS,
    magnitude_to_db,
    validate_frequency_sequence,
)
from .ideal_response import magnitude_db
from .numeric_validation import _is_positive_finite


def _log_sweep_frequencies(
    f0: float,
    bw: float,
    points: int,
    decades: float | None,
) -> list[float]:
    """Build a finite log grid shared by ideal and netlist bandpass sweeps."""
    if not _is_positive_finite(f0):
        raise ValueError("f0 must be positive and finite")
    if not _is_positive_finite(bw):
        raise ValueError("bw must be positive and finite")
    if (
        isinstance(points, bool)
        or not isinstance(points, int)
        or not 2 <= points <= MAX_FREQUENCY_POINTS
    ):
        raise ValueError(
            f"points must be an integer >= 2 and <= {MAX_FREQUENCY_POINTS:,} for a log sweep"
        )
    if decades is None:
        relative_span = 10.0 * (bw / f0)
        auto_decades = (
            math.inf
            if not math.isfinite(relative_span)
            else math.log1p(relative_span) / math.log(10.0)
        )
        decades = max(0.1, min(1.0, auto_decades))
    elif not is_finite_real(decades) or decades <= 0:
        raise ValueError("decades must be positive and finite")

    log_center = math.log10(f0)
    log_start = log_center - decades
    log_end = log_center + decades
    try:
        frequencies = [
            10 ** (log_start + (log_end - log_start) * index / (points - 1))
            for index in range(points)
        ]
    except OverflowError as exc:
        raise ValueError("Requested sweep frequencies must remain positive and finite") from exc
    if any(not _is_positive_finite(frequency) for frequency in frequencies):
        raise ValueError("Requested sweep frequencies must remain positive and finite")
    return frequencies


def frequency_sweep(
    f0: float,
    bw: float,
    order: int,
    filter_type: str,
    ripple_db: float = 0.5,
    decades: float | None = None,
    points: int = 61,
) -> list[tuple[float, float]]:
    """Return ideal ``(frequency, magnitude_db)`` pairs on an adaptive log grid."""
    frequencies = _log_sweep_frequencies(f0, bw, points, decades)
    return [
        (frequency, magnitude_db(frequency, f0, bw, order, filter_type, ripple_db))
        for frequency in frequencies
    ]


def netlist_frequency_sweep(
    result: dict, decades: float | None = None, points: int = 61
) -> list[tuple[float, float]]:
    """Simulate the synthesized ideal-component circuit on a log grid.

    This nodal-analysis model uses the result's exact ideal L/C values and
    source/load resistance. It is not a measurement and does not include
    component parasitics, finite Q, coupling from layout, or PCB/transmission-line effects.
    """
    if not isinstance(result, Mapping):
        raise ValueError("result must be a mapping")
    f0, bw = result.get("f0"), result.get("bw")
    frequencies = _log_sweep_frequencies(f0, bw, points, decades)
    n_nodes, branches, in_node, out_node = build_bandpass_top_c_netlist(result)
    z0 = result.get("z0")
    magnitudes = solve_s21(n_nodes, branches, z0, z0, in_node, out_node, frequencies)
    return [
        (frequency, magnitude_to_db(magnitude))
        for frequency, magnitude in zip(frequencies, magnitudes)
    ]


def generate_frequency_points(f0: float, bw: float, points: int = 101) -> list[float]:
    """Return adaptive logarithmic frequency points for bandpass plotting."""
    return _log_sweep_frequencies(f0, bw, points, None)


def frequency_response(result: dict, freqs: list[float]) -> list[float]:
    """Return ideal response dB values for a bandpass result and frequency list."""
    if not isinstance(result, Mapping):
        raise ValueError("result must be a mapping")
    freqs = validate_frequency_sequence(freqs)
    f0 = result.get("f0")
    bw = result.get("bw")
    order = result.get("n_resonators")
    filter_type = result.get("filter_type")
    ripple_db = result.get("ripple_db", 0.5)
    # Validate the response definition even for an empty caller-supplied grid.
    magnitude_db(f0, f0, bw, order, filter_type, ripple_db)
    return [magnitude_db(frequency, f0, bw, order, filter_type, ripple_db) for frequency in freqs]
