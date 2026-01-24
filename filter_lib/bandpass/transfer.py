"""Transfer function magnitude calculations for bandpass filters.

Supports Butterworth, Chebyshev Type I, and Bessel (approximated) responses.
"""
import math


def chebyshev_polynomial(n: int, x: float) -> float:
    """Evaluate Chebyshev polynomial Cn(x).

    |x| <= 1: Cn(x) = cos(n * arccos(x))
    |x| > 1:  Cn(x) = cosh(n * arccosh(x))
    """
    if abs(x) <= 1:
        return math.cos(n * math.acos(x))
    return math.cosh(n * math.acosh(abs(x)))


def _bandpass_deviation(f: float, f0: float, bw: float) -> float:
    """Calculate normalized frequency deviation for bandpass.

    delta = (f^2 - f0^2) / (BW * f)
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


def magnitude_chebyshev(f: float, f0: float, bw: float, order: int,
                        ripple_db: float) -> float:
    """Return |H(f)| for Chebyshev Type I bandpass filter.

    eps = sqrt(10^(ripple/10) - 1)
    |H(f)| = 1 / sqrt(1 + eps^2 * Cn^2(delta))
    """
    eps = math.sqrt(10 ** (ripple_db / 10) - 1)
    delta = _bandpass_deviation(f, f0, bw)
    cn = chebyshev_polynomial(order, delta)
    return 1.0 / math.sqrt(1.0 + eps * eps * cn * cn)


def magnitude_bessel(f: float, f0: float, bw: float, order: int) -> float:
    """Return |H(f)| for Bessel bandpass filter (Butterworth approximation).

    Note: Bessel has no simple closed-form for magnitude. Using Butterworth
    shape provides reasonable visual approximation for frequency plots.
    """
    return magnitude_butterworth(f, f0, bw, order)


def magnitude_db(f: float, f0: float, bw: float, order: int,
                 filter_type: str, ripple_db: float = 0.5) -> float:
    """Return magnitude in dB for any supported filter type.

    Clamps minimum to -100 dB to avoid log(0) issues.
    """
    if filter_type == 'butterworth':
        mag = magnitude_butterworth(f, f0, bw, order)
    elif filter_type == 'chebyshev':
        mag = magnitude_chebyshev(f, f0, bw, order, ripple_db)
    elif filter_type == 'bessel':
        mag = magnitude_bessel(f, f0, bw, order)
    else:
        raise ValueError(f"Unknown filter type: {filter_type}")

    if mag < 1e-5:
        return -100.0
    return 20.0 * math.log10(mag)


def frequency_sweep(f0: float, bw: float, order: int, filter_type: str,
                    ripple_db: float = 0.5, decades: float | None = None,
                    points: int = 61) -> list[tuple[float, float]]:
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
    if decades is None:
        # Show 10x BW on each side of f0, converted to log scale
        span = 10 * bw
        decades = math.log10((f0 + span) / f0)
        decades = max(0.1, min(1.0, decades))

    f_start = f0 / (10 ** decades)
    f_end = f0 * (10 ** decades)
    log_start = math.log10(f_start)
    log_end = math.log10(f_end)

    result = []
    for i in range(points):
        log_f = log_start + (log_end - log_start) * i / (points - 1)
        f = 10 ** log_f
        db = magnitude_db(f, f0, bw, order, filter_type, ripple_db)
        result.append((f, db))
    return result
