"""Transfer function calculations for low-pass filter frequency response."""
import math

from ..shared.transfer_functions import (
    BESSEL_COEFFS, BESSEL_SCALE,
    generate_frequency_points, chebyshev_polynomial,
    magnitude_to_db, export_response_json, export_response_csv,
)


def butterworth_response(freq_hz: float, cutoff_hz: float, order: int) -> float:
    """Calculate Butterworth filter magnitude response (0 to 1)."""
    ratio = freq_hz / cutoff_hz
    h_squared = 1.0 / (1.0 + ratio ** (2 * order))
    return math.sqrt(h_squared)


def chebyshev_response(freq_hz: float, cutoff_hz: float, order: int,
                       ripple_db: float) -> float:
    """Calculate Chebyshev Type I filter magnitude response."""
    epsilon = math.sqrt(10 ** (ripple_db / 10) - 1)
    ratio = freq_hz / cutoff_hz
    tn = chebyshev_polynomial(order, ratio)
    h_squared = 1.0 / (1.0 + epsilon ** 2 * tn ** 2)
    return math.sqrt(h_squared)


def bessel_response(freq_hz: float, cutoff_hz: float, order: int) -> float:
    """Calculate Bessel filter magnitude response."""
    if order < 2 or order > 9:
        raise ValueError("Order must be between 2 and 9")

    w = (freq_hz / cutoff_hz) * BESSEL_SCALE[order]
    coeffs = BESSEL_COEFFS[order]

    real_part, imag_part = 0.0, 0.0
    w_power = 1.0

    for k, c in enumerate(coeffs):
        if k % 2 == 0:
            sign = (-1) ** (k // 2)
            real_part += sign * c * w_power
        else:
            sign = (-1) ** (k // 2)
            imag_part += sign * c * w_power
        w_power *= w

    dc_gain_squared = coeffs[0] ** 2
    denom_squared = real_part ** 2 + imag_part ** 2
    if denom_squared == 0:
        return 1.0
    h_squared = dc_gain_squared / denom_squared
    return math.sqrt(min(h_squared, 1.0))


def frequency_response(filter_type: str, freqs: list[float], cutoff_hz: float,
                       order: int, ripple_db: float = 0.5) -> list[float]:
    """Calculate frequency response in dB for a list of frequencies."""
    filter_type = filter_type.lower()

    if filter_type in ('butterworth', 'bw'):
        response_fn = lambda f: butterworth_response(f, cutoff_hz, order)
    elif filter_type in ('chebyshev', 'ch'):
        response_fn = lambda f: chebyshev_response(f, cutoff_hz, order, ripple_db)
    elif filter_type in ('bessel', 'bs'):
        response_fn = lambda f: bessel_response(f, cutoff_hz, order)
    else:
        raise ValueError(f"Unknown filter type: {filter_type}")

    return [magnitude_to_db(response_fn(f)) for f in freqs]
