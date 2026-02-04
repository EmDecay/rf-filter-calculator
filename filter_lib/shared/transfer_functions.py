"""Shared transfer function utilities for frequency response calculations."""
import math
import json

# Bessel polynomial coefficients for orders 2-9
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

# Bessel -3dB normalization scale factors
BESSEL_SCALE = {
    2: 1.3617, 3: 1.7557, 4: 2.1139, 5: 2.4274,
    6: 2.7034, 7: 2.9517, 8: 3.1796, 9: 3.3917
}


def generate_frequency_points(
    f0: float,
    num_points: int | None = None,
    decades: float = 2.0,
    points_per_decade: int = 25
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
    """
    if f0 <= 0:
        raise ValueError("Cutoff frequency must be positive")

    if num_points is not None:
        # Legacy mode: fixed 2-decade span from 0.1*f0 to 10*f0
        points = []
        for i in range(num_points):
            exp = -1 + (2 * i / (num_points - 1))
            points.append(f0 * (10 ** exp))
        return points

    # Flexible mode: configurable decades centered on f0
    total_points = int(decades * points_per_decade)
    start_exp = math.log10(f0) - decades / 2
    return [10 ** (start_exp + i * decades / total_points)
            for i in range(total_points + 1)]


def chebyshev_polynomial(n: int, x: float) -> float:
    """Calculate Chebyshev polynomial Tn(x) using recurrence."""
    if n == 0:
        return 1.0
    if n == 1:
        return x
    t_prev2, t_prev1 = 1.0, x
    for _ in range(2, n + 1):
        t_curr = 2 * x * t_prev1 - t_prev2
        t_prev2, t_prev1 = t_prev1, t_curr
    return t_prev1


def magnitude_to_db(magnitude: float) -> float:
    """Convert magnitude to dB (floored at -120 dB)."""
    if magnitude <= 0:
        return -120.0
    return max(20 * math.log10(magnitude), -120.0)


def export_response_json(freqs: list[float], response_db: list[float],
                         filter_info: dict) -> str:
    """Export frequency response as JSON."""
    output = {
        'filter_type': filter_info.get('filter_type', 'unknown'),
        'cutoff_hz': filter_info.get('cutoff_hz') or filter_info.get('freq_hz', 0),
        'order': filter_info.get('order', 0),
        'data': [{'frequency_hz': f, 'magnitude_db': round(db, 2)}
                 for f, db in zip(freqs, response_db)]
    }
    if filter_info.get('ripple') is not None:
        output['ripple_db'] = filter_info['ripple']
    return json.dumps(output, indent=2)


def export_response_csv(freqs: list[float], response_db: list[float]) -> str:
    """Export frequency response as CSV."""
    lines = ['frequency_hz,magnitude_db']
    for f, db in zip(freqs, response_db):
        lines.append(f'{f:.6g},{db:.2f}')
    return '\n'.join(lines)
