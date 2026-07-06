"""Transfer function magnitude calculations for bandpass filters.

Supports Butterworth, Chebyshev Type I, and Bessel responses via
lowpass-prototype frequency transformation.

Conventions: ``bw`` is always the user-facing true -3 dB bandwidth in Hz
(for Chebyshev the internal deviation is rescaled so this holds); returned
magnitudes are linear 0-1 unless a function says dB.
"""

import math

from ..shared.lp_hp_base_transfer_functions import lowpass_bessel_response
from ..shared.transfer_functions import chebyshev_polynomial, magnitude_to_db


def chebyshev_3db_deviation(order: int, ripple_db: float) -> float:
    """Normalized frequency deviation at which a Chebyshev Type I response is -3 dB.

    Chebyshev passband ends at |delta| = 1 with attenuation = ripple_db, NOT at
    -3 dB. The -3 dB point lies outside the ripple passband at:

        delta_3dB = cosh(acosh(1/eps) / n),   eps = sqrt(10^(ripple/10) - 1)

    For Butterworth and Bessel responses this scale is effectively 1 (their
    prototypes are already normalized so delta=1 lies at -3 dB).

    Raises:
        ValueError: If ripple_db <= 0 (ambiguous: no ripple, no eps).
    """
    if ripple_db <= 0:
        raise ValueError("ripple_db must be positive for Chebyshev")
    eps = math.sqrt(10 ** (ripple_db / 10) - 1)
    return math.cosh(math.acosh(1.0 / eps) / order)


def _bandpass_deviation(f: float, f0: float, bw: float) -> float:
    """Calculate normalized frequency deviation for bandpass.

    delta = (f^2 - f0^2) / (BW * f)

    This is the standard LP→BP prototype mapping: delta plays the role of
    the lowpass prototype's normalized frequency, with |delta| = 1 at the
    passband edges and geometric symmetry about f0.
    """
    if f <= 0:
        raise ValueError("Frequency must be positive")
    if bw <= 0:
        raise ValueError("Bandwidth must be positive")
    return (f * f - f0 * f0) / (bw * f)


def magnitude_butterworth(f: float, f0: float, bw: float, order: int) -> float:
    """Return |H(f)| for Butterworth bandpass filter.

    |H(f)| = 1 / sqrt(1 + delta^(2n))
    """
    delta = _bandpass_deviation(f, f0, bw)
    return 1.0 / math.sqrt(1.0 + delta ** (2 * order))


def magnitude_chebyshev(f: float, f0: float, bw: float, order: int, ripple_db: float) -> float:
    """Return |H(f)| for Chebyshev Type I bandpass filter.

    ``bw`` is the user-facing -3 dB bandwidth. Internally the normalized
    deviation is scaled by the Chebyshev 3-dB-point so that ``delta = ±1`` in
    user units maps onto the Chebyshev polynomial's -3 dB point, not the
    ripple edge.

    eps = sqrt(10^(ripple/10) - 1)
    scale = cosh(acosh(1/eps)/n)                   # >= 1 for ripple > 0
    |H(f)| = 1 / sqrt(1 + eps^2 * Cn^2(delta * scale))
    """
    eps = math.sqrt(10 ** (ripple_db / 10) - 1)
    scale = chebyshev_3db_deviation(order, ripple_db)
    delta = _bandpass_deviation(f, f0, bw) * scale
    cn = chebyshev_polynomial(order, delta)
    return 1.0 / math.sqrt(1.0 + eps * eps * cn * cn)


def magnitude_bessel(f: float, f0: float, bw: float, order: int) -> float:
    """Return |H(f)| for Bessel bandpass filter.

    The normalized bandpass deviation maps directly onto the corresponding
    lowpass prototype variable, so the Bessel magnitude can be evaluated by
    reusing the normalized lowpass Bessel response.

    Magnitude only: the LP→BP transformation does not preserve the Bessel
    prototype's maximally-flat group delay, so passband phase linearity is
    not guaranteed.
    """
    delta = abs(_bandpass_deviation(f, f0, bw))
    return lowpass_bessel_response(delta, 1.0, order)


def magnitude_db(
    f: float, f0: float, bw: float, order: int, filter_type: str, ripple_db: float = 0.5
) -> float:
    """Return magnitude in dB for any supported filter type.

    Floored at -120 dB (shared convention with LP/HP responses).

    Raises:
        ValueError: If filter_type is not butterworth/chebyshev/bessel
            (canonical names only — alias resolution happens in the CLI).
    """
    if filter_type == "butterworth":
        mag = magnitude_butterworth(f, f0, bw, order)
    elif filter_type == "chebyshev":
        mag = magnitude_chebyshev(f, f0, bw, order, ripple_db)
    elif filter_type == "bessel":
        mag = magnitude_bessel(f, f0, bw, order)
    else:
        raise ValueError(f"Unknown filter type: {filter_type}")

    return magnitude_to_db(mag)


def frequency_sweep(
    f0: float,
    bw: float,
    order: int,
    filter_type: str,
    ripple_db: float = 0.5,
    decades: float | None = None,
    points: int = 61,
) -> list[tuple[float, float]]:
    """Generate (frequency, magnitude_db) pairs for plotting.

    Adaptive range based on bandwidth to show meaningful filter shape.

    Args:
        f0: Center frequency in Hz
        bw: Bandwidth in Hz
        order: Filter order (number of resonators)
        filter_type: 'butterworth', 'chebyshev', or 'bessel'
        ripple_db: Chebyshev ripple in dB
        decades: Number of decades to span (auto-calculated if None)
        points: Number of points to generate

    Returns:
        List of (frequency_hz, magnitude_db) tuples
    """
    if points < 2:
        raise ValueError("points must be >= 2 for a log sweep")
    if decades is None:
        # Show 10x BW on each side of f0, converted to log scale. Clamp to
        # [0.1, 1.0] decades so ultra-narrow filters still get a visible span
        # and wide ones don't zoom out past the useful stopband detail.
        span = 10 * bw
        decades = math.log10((f0 + span) / f0)
        decades = max(0.1, min(1.0, decades))

    f_start = f0 / (10**decades)
    f_end = f0 * (10**decades)
    log_start = math.log10(f_start)
    log_end = math.log10(f_end)

    result = []
    for i in range(points):
        log_f = log_start + (log_end - log_start) * i / (points - 1)
        f = 10**log_f
        db = magnitude_db(f, f0, bw, order, filter_type, ripple_db)
        result.append((f, db))
    return result


def netlist_frequency_sweep(
    result: dict, decades: float | None = None, points: int = 61
) -> list[tuple[float, float]]:
    """Simulated (frequency, magnitude_db) pairs for the as-synthesized circuit.

    Unlike ``frequency_sweep`` (idealized symmetric prototype), this builds
    the exact prescribed network from the result dict's component values and
    solves it by nodal analysis, so the plotted response matches what a built
    filter measures — including the skew real Top-C circuits show at wider
    fractional bandwidths. Same adaptive log x-range as ``frequency_sweep``.
    """
    from ..shared.netlist_builders import build_bandpass_top_c_netlist
    from ..shared.netlist_simulation import solve_s21

    f0, bw = result["f0"], result["bw"]
    if points < 2:
        raise ValueError("points must be >= 2 for a log sweep")
    if decades is None:
        span = 10 * bw
        decades = math.log10((f0 + span) / f0)
        decades = max(0.1, min(1.0, decades))

    log_start = math.log10(f0 / (10**decades))
    log_end = math.log10(f0 * (10**decades))
    freqs = [10 ** (log_start + (log_end - log_start) * i / (points - 1)) for i in range(points)]

    n_nodes, branches, in_node, out_node = build_bandpass_top_c_netlist(result)
    z0 = result["z0"]
    mags = solve_s21(n_nodes, branches, z0, z0, in_node, out_node, freqs)
    return [(f, magnitude_to_db(m)) for f, m in zip(freqs, mags)]


def generate_frequency_points(f0: float, bw: float, points: int = 101) -> list[float]:
    """Generate frequency points for bandpass response plotting.

    Args:
        f0: Center frequency in Hz
        bw: Bandwidth in Hz
        points: Number of points to generate

    Returns:
        List of frequencies in Hz
    """
    if points < 2:
        raise ValueError("points must be >= 2 for a log sweep")
    span = 10 * bw
    decades = math.log10((f0 + span) / f0)
    decades = max(0.1, min(1.0, decades))

    f_start = f0 / (10**decades)
    f_end = f0 * (10**decades)
    log_start = math.log10(f_start)
    log_end = math.log10(f_end)

    return [10 ** (log_start + (log_end - log_start) * i / (points - 1)) for i in range(points)]


def frequency_response(result: dict, freqs: list[float]) -> list[float]:
    """Calculate frequency response for a bandpass filter result.

    Args:
        result: Filter calculation result dict with f0, bw, n_resonators,
                filter_type, ripple_db
        freqs: List of frequencies in Hz

    Returns:
        List of magnitudes in dB
    """
    f0 = result["f0"]
    bw = result["bw"]
    order = result["n_resonators"]
    filter_type = result["filter_type"]
    # ripple_db is None in non-Chebyshev results; that is safe because only
    # the Chebyshev branch of magnitude_db ever reads it.
    ripple_db = result.get("ripple_db", 0.5)

    return [magnitude_db(f, f0, bw, order, filter_type, ripple_db) for f in freqs]
