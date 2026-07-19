"""Shared transfer function utilities for frequency response calculations.

Holds the Bessel polynomial data plus the small numeric helpers (frequency
grids, Chebyshev polynomial, dB conversion) used by every idealized
response function. Magnitudes are unitless 0-1; frequencies are Hz.
"""

import math
from collections.abc import Sequence

from .numeric import is_finite_real

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

# A plotting/export grid beyond this size is not practical for this calculator
# and can otherwise turn malformed public-API input into an attempted enormous
# allocation.  Fixed-count legacy grids retain their existing explicit count.
MAX_FLEXIBLE_FREQUENCY_INTERVALS = 1_000_000
MAX_FREQUENCY_POINTS = MAX_FLEXIBLE_FREQUENCY_INTERVALS + 1


def validate_frequency_sequence(freqs: object) -> Sequence:
    """Return a non-text frequency sequence or raise a stable ``ValueError``."""
    if not isinstance(freqs, Sequence) or isinstance(freqs, (str, bytes, bytearray)):
        raise ValueError("freqs must be a sequence of positive finite frequencies")
    return freqs


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
    if not is_finite_real(f0) or f0 <= 0:
        raise ValueError("Cutoff frequency must be positive and finite")

    if num_points is not None:
        if (
            isinstance(num_points, bool)
            or not isinstance(num_points, int)
            or not 2 <= num_points <= MAX_FREQUENCY_POINTS
        ):
            raise ValueError(
                "num_points must be an integer >= 2 and <= "
                f"{MAX_FREQUENCY_POINTS:,} for a log sweep"
            )
        # Legacy mode: fixed 2-decade span from 0.1*f0 to 10*f0
        points = []
        for i in range(num_points):
            exp = -1 + (2 * i / (num_points - 1))
            points.append(f0 * (10**exp))
        if any(not math.isfinite(point) or point <= 0 for point in points):
            raise ValueError("Requested frequency span must remain positive and finite")
        return points

    # Flexible mode: configurable decades centered on f0
    if not is_finite_real(decades) or decades <= 0:
        raise ValueError("decades must be positive and finite")
    if (
        isinstance(points_per_decade, bool)
        or not isinstance(points_per_decade, int)
        or points_per_decade <= 0
    ):
        raise ValueError("points_per_decade must be a positive integer")
    try:
        interval_count = decades * points_per_decade
    except OverflowError as exc:
        raise ValueError("decades * points_per_decade is too large") from exc
    if not math.isfinite(interval_count) or interval_count > MAX_FLEXIBLE_FREQUENCY_INTERVALS:
        raise ValueError(
            "decades * points_per_decade must not exceed "
            f"{MAX_FLEXIBLE_FREQUENCY_INTERVALS:,} intervals"
        )
    total_points = int(interval_count)
    if total_points < 1:
        raise ValueError("decades * points_per_decade must produce at least one interval")
    start_exp = math.log10(f0) - decades / 2
    try:
        points = [10 ** (start_exp + i * decades / total_points) for i in range(total_points + 1)]
    except OverflowError as exc:
        raise ValueError("Requested frequency span must remain positive and finite") from exc
    if any(not math.isfinite(point) or point <= 0 for point in points):
        raise ValueError("Requested frequency span must remain positive and finite")
    return points


def chebyshev_polynomial(n: int, x: float) -> float:
    """Evaluate a magnitude-form Chebyshev polynomial Cn(x).

    |x| <= 1: Cn(x) = cos(n * arccos(x))
    |x| > 1:  Cn(x) = cosh(n * arccosh(|x|))

    Equals Tn(x) for x >= 0 and |Tn(x)| for x < -1; response functions only
    use Cn squared, so the magnitude form is interchangeable with the
    recurrence while staying numerically stable far outside the passband.
    """
    if isinstance(n, bool) or not isinstance(n, int) or n < 0:
        raise ValueError("n must be a non-negative integer")
    if isinstance(x, bool) or not isinstance(x, (int, float)):
        raise ValueError("x must be a real number that is not NaN")
    if n == 0:
        return 1.0
    try:
        x = float(x)
    except OverflowError:
        return math.inf
    if math.isnan(x):
        raise ValueError("x must be a real number that is not NaN")
    if math.isinf(x):
        return math.inf
    if abs(x) <= 1:
        angle = math.acos(x)
        if n.bit_length() <= 50:
            return math.cos(n * angle)
        # Avoid converting an arbitrary-size integer to float.  Binary modular
        # multiplication keeps the phase bounded while preserving parity and
        # periodicity for orders far beyond the CLI-supported synthesis range.
        phase = 0.0
        addend = angle % math.tau
        multiplier = n
        while multiplier:
            if multiplier & 1:
                phase = (phase + addend) % math.tau
            addend = (2.0 * addend) % math.tau
            multiplier >>= 1
        return math.cos(phase)
    growth = math.acosh(abs(x))
    if n.bit_length() > 1023:
        return math.inf
    argument = n * growth
    try:
        return math.cosh(argument)
    except OverflowError:
        return math.inf


def magnitude_to_db(magnitude: float) -> float:
    """Convert magnitude to dB, floored at -120 dB.

    The floor keeps deep-stopband and zero-magnitude points plottable
    (no -inf) without visibly affecting any real filter curve.
    """
    if not is_finite_real(magnitude):
        raise ValueError("Magnitude must be finite")
    if magnitude <= 0:
        return -120.0
    return max(20 * math.log10(magnitude), -120.0)
