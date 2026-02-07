"""Shared transfer function calculations for lowpass and highpass filters.

HPF response is derived from LPF response using frequency transformation:
- LP uses ratio = f/fc
- HP uses inverted ratio = fc/f
- HP returns 0.0 at DC (freq_hz=0), LP returns 1.0
"""
import math
from typing import Callable

from .transfer_functions import (
    BESSEL_COEFFS, BESSEL_SCALE,
    chebyshev_polynomial,
    magnitude_to_db,
)


def _butterworth_response_base(freq_hz: float, cutoff_hz: float, order: int,
                                is_lowpass: bool) -> float:
    """Calculate Butterworth filter magnitude response (0 to 1).

    Args:
        freq_hz: Frequency in Hz
        cutoff_hz: Cutoff frequency in Hz
        order: Filter order
        is_lowpass: True for lowpass, False for highpass

    Returns:
        Magnitude response (0 to 1)
    """
    if not is_lowpass and freq_hz == 0:
        return 0.0  # HPF blocks DC

    if is_lowpass:
        ratio = freq_hz / cutoff_hz
    else:
        if freq_hz == 0:
            return 0.0
        ratio = cutoff_hz / freq_hz  # Inverted for HPF

    h_squared = 1.0 / (1.0 + ratio ** (2 * order))
    return math.sqrt(h_squared)


def _chebyshev_response_base(freq_hz: float, cutoff_hz: float, order: int,
                              ripple_db: float, is_lowpass: bool) -> float:
    """Calculate Chebyshev Type I filter magnitude response.

    Args:
        freq_hz: Frequency in Hz
        cutoff_hz: Cutoff frequency in Hz
        order: Filter order
        ripple_db: Passband ripple in dB
        is_lowpass: True for lowpass, False for highpass

    Returns:
        Magnitude response (0 to 1)
    """
    if not is_lowpass and freq_hz == 0:
        return 0.0  # HPF blocks DC

    epsilon = math.sqrt(10 ** (ripple_db / 10) - 1)

    if is_lowpass:
        ratio = freq_hz / cutoff_hz
    else:
        if freq_hz == 0:
            return 0.0
        ratio = cutoff_hz / freq_hz  # Inverted for HPF

    tn = chebyshev_polynomial(order, ratio)
    h_squared = 1.0 / (1.0 + epsilon ** 2 * tn ** 2)
    return math.sqrt(h_squared)


def _bessel_response_base(freq_hz: float, cutoff_hz: float, order: int,
                           is_lowpass: bool) -> float:
    """Calculate Bessel filter magnitude response.

    Args:
        freq_hz: Frequency in Hz
        cutoff_hz: Cutoff frequency in Hz
        order: Filter order
        is_lowpass: True for lowpass, False for highpass

    Returns:
        Magnitude response (0 to 1)
    """
    if order < 2 or order > 9:
        raise ValueError("Order must be between 2 and 9")

    if not is_lowpass and freq_hz == 0:
        return 0.0  # HPF blocks DC

    if is_lowpass:
        w = (freq_hz / cutoff_hz) * BESSEL_SCALE[order]
    else:
        if freq_hz == 0:
            return 0.0
        w = (cutoff_hz / freq_hz) * BESSEL_SCALE[order]  # Inverted for HPF

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
        return 1.0 if is_lowpass else 0.0  # LP passes DC, HP blocks DC
    h_squared = dc_gain_squared / denom_squared
    return math.sqrt(min(h_squared, 1.0))


# Lowpass public API
def lowpass_butterworth_response(freq_hz: float, cutoff_hz: float, order: int) -> float:
    """Calculate Butterworth lowpass filter magnitude response (0 to 1)."""
    return _butterworth_response_base(freq_hz, cutoff_hz, order, is_lowpass=True)


def lowpass_chebyshev_response(freq_hz: float, cutoff_hz: float, order: int,
                                ripple_db: float) -> float:
    """Calculate Chebyshev Type I lowpass filter magnitude response."""
    return _chebyshev_response_base(freq_hz, cutoff_hz, order, ripple_db, is_lowpass=True)


def lowpass_bessel_response(freq_hz: float, cutoff_hz: float, order: int) -> float:
    """Calculate Bessel lowpass filter magnitude response."""
    return _bessel_response_base(freq_hz, cutoff_hz, order, is_lowpass=True)


# Highpass public API
def highpass_butterworth_response(freq_hz: float, cutoff_hz: float, order: int) -> float:
    """Calculate Butterworth highpass filter magnitude response (0 to 1).

    HPF response: H(f) = 1 / sqrt(1 + (fc/f)^(2n))
    """
    return _butterworth_response_base(freq_hz, cutoff_hz, order, is_lowpass=False)


def highpass_chebyshev_response(freq_hz: float, cutoff_hz: float, order: int,
                                 ripple_db: float) -> float:
    """Calculate Chebyshev Type I highpass filter magnitude response.

    HPF uses inverted frequency ratio: fc/f instead of f/fc
    """
    return _chebyshev_response_base(freq_hz, cutoff_hz, order, ripple_db, is_lowpass=False)


def highpass_bessel_response(freq_hz: float, cutoff_hz: float, order: int) -> float:
    """Calculate Bessel highpass filter magnitude response.

    HPF uses inverted frequency transformation: w_hp = fc/f * scale
    """
    return _bessel_response_base(freq_hz, cutoff_hz, order, is_lowpass=False)
