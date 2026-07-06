"""Shared transfer function utilities for frequency response calculations.

Holds the Bessel polynomial data plus the small numeric helpers (frequency
grids, Chebyshev polynomial, dB conversion) used by every idealized
response function. Magnitudes are unitless 0-1; frequencies are Hz.
"""

import math

# Reverse Bessel polynomial theta_n(s) coefficients for orders 2-9, listed
# in ascending powers of s (coeffs[0] = theta_n(0) = the DC gain the
# response functions normalize by). Integer-exact by construction from the
# recurrence theta_n = (2n-1)·theta_{n-1} + s^2·theta_{n-2}.
BESSEL_COEFFS = {
    2: [3, 3, 1],
    3: [15, 15, 6, 1],
    4: [105, 105, 45, 10, 1],
    5: [945, 945, 420, 105, 15, 1],
    6: [10395, 10395, 4725, 1260, 210, 21, 1],
    7: [135135, 135135, 62370, 17325, 3150, 378, 28, 1],
    8: [2027025, 2027025, 945945, 270270, 51975, 6930, 630, 36, 1],
    9: [34459425, 34459425, 16216200, 4729725, 945945, 135135, 13860, 990, 45, 1],
}

# Bessel -3 dB normalization: the raw polynomial |theta_n(jw)| reaches
# -3 dB at w equal to these factors (they grow with order), so response
# functions multiply the f/fc ratio by BESSEL_SCALE[order] to place the
# user's cutoff exactly at -3 dB. Standard tabulated values (Zverev).
BESSEL_SCALE = {
    2: 1.3617,
    3: 1.7557,
    4: 2.1139,
    5: 2.4274,
    6: 2.7034,
    7: 2.9517,
    8: 3.1796,
    9: 3.3917,
}


def generate_frequency_points(
    f0: float, num_points: int | None = None, decades: float = 2.0, points_per_decade: int = 25
) -> list[float]:
    """Generate logarithmically-spaced frequency points around f0.

    Two calling conventions supported:
    - num_points specified: fixed 2-decade span (0.1*f0 to 10*f0)
    - num_points=None: use decades and points_per_decade for flexible ranging

    Args:
        f0: Center/cutoff frequency in Hz
        num_points: Exact point count (legacy mode, spans 0.1fc to 10fc)
        decades: Number of decades to span (default 2.0)
        points_per_decade: Points per decade when num_points not specified

    Returns:
        List of frequencies in Hz

    Raises:
        ValueError: If f0 is not positive and finite, or num_points < 2.
    """
    if not math.isfinite(f0) or f0 <= 0:
        raise ValueError("Cutoff frequency must be positive and finite")

    if num_points is not None:
        if num_points < 2:
            raise ValueError("num_points must be >= 2 for a log sweep")
        # Legacy mode: fixed 2-decade span from 0.1*f0 to 10*f0
        points = []
        for i in range(num_points):
            exp = -1 + (2 * i / (num_points - 1))
            points.append(f0 * (10**exp))
        return points

    # Flexible mode: configurable decades centered on f0
    total_points = int(decades * points_per_decade)
    start_exp = math.log10(f0) - decades / 2
    return [10 ** (start_exp + i * decades / total_points) for i in range(total_points + 1)]


def chebyshev_polynomial(n: int, x: float) -> float:
    """Evaluate a magnitude-form Chebyshev polynomial Cn(x).

    |x| <= 1: Cn(x) = cos(n * arccos(x))
    |x| > 1:  Cn(x) = cosh(n * arccosh(|x|))

    Equals Tn(x) for x >= 0 and |Tn(x)| for x < -1; response functions only
    use Cn squared, so the magnitude form is interchangeable with the
    recurrence while staying numerically stable far outside the passband.
    """
    if abs(x) <= 1:
        return math.cos(n * math.acos(x))
    return math.cosh(n * math.acosh(abs(x)))


def magnitude_to_db(magnitude: float) -> float:
    """Convert magnitude to dB, floored at -120 dB.

    The floor keeps deep-stopband and zero-magnitude points plottable
    (no -inf) without visibly affecting any real filter curve.
    """
    if magnitude <= 0:
        return -120.0
    return max(20 * math.log10(magnitude), -120.0)
