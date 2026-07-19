"""Shared transfer function calculations for lowpass and highpass filters.

HPF response is derived from LPF response using frequency transformation:
- LP uses ratio = f/fc
- HP uses inverted ratio = fc/f
- HP returns 0.0 at DC (freq_hz=0), LP returns 1.0
"""

import math
import sys

from .numeric import is_finite_real, magnitude_from_log_gain, ripple_log_epsilon
from .transfer_functions import (
    BESSEL_COEFFS,
    BESSEL_SCALE,
    chebyshev_polynomial,
)


def _validate_response_inputs(freq_hz: float, cutoff_hz: float, order: int) -> None:
    """Validate the numeric contract shared by every LP/HP response."""
    if not is_finite_real(freq_hz) or freq_hz < 0:
        raise ValueError("Frequency must be non-negative and finite")
    if not is_finite_real(cutoff_hz) or cutoff_hz <= 0:
        raise ValueError("Cutoff frequency must be positive and finite")
    if isinstance(order, bool) or not isinstance(order, int) or order <= 0:
        raise ValueError("Order must be a positive integer")


def _butterworth_response_base(
    freq_hz: float, cutoff_hz: float, order: int, is_lowpass: bool
) -> float:
    """Calculate Butterworth filter magnitude response (0 to 1).

    Args:
        freq_hz: Frequency in Hz
        cutoff_hz: Cutoff frequency in Hz
        order: Filter order
        is_lowpass: True for lowpass, False for highpass

    Returns:
        Magnitude response (0 to 1)
    """
    _validate_response_inputs(freq_hz, cutoff_hz, order)
    if not is_lowpass and freq_hz == 0:
        return 0.0  # HPF blocks DC

    if is_lowpass:
        ratio = freq_hz / cutoff_hz
    else:
        ratio = cutoff_hz / freq_hz  # Inverted for HPF; freq_hz == 0 returned above

    # For |ratio| >> 1, ratio**(2n) may overflow double precision. The limit
    # of 1/sqrt(1 + ratio^(2n)) as that term overflows is 0, so clamp.
    try:
        powered_ratio = abs(ratio) ** order
    except OverflowError:
        return 0.0
    if powered_ratio > math.sqrt(sys.float_info.max):
        return 0.0
    return 1.0 / math.hypot(1.0, powered_ratio)


def _chebyshev_response_base(
    freq_hz: float, cutoff_hz: float, order: int, ripple_db: float, is_lowpass: bool
) -> float:
    """Calculate Chebyshev Type I filter magnitude response.

    ``cutoff_hz`` is the equal-ripple band edge: |H| there is
    1/sqrt(1 + epsilon^2), i.e. -ripple_db, NOT -3 dB. This matches the g-value
    synthesis convention in lp_hp_base_calculations, so plotted curves line
    up with the component tables.

    Args:
        freq_hz: Frequency in Hz
        cutoff_hz: Cutoff frequency in Hz (ripple band edge)
        order: Filter order
        ripple_db: Passband ripple in dB
        is_lowpass: True for lowpass, False for highpass

    Returns:
        Magnitude response (0 to 1)
    """
    _validate_response_inputs(freq_hz, cutoff_hz, order)
    if not is_finite_real(ripple_db) or ripple_db <= 0:
        raise ValueError("ripple_db must be positive and finite")
    if not is_lowpass and freq_hz == 0:
        return 0.0  # HPF blocks DC

    log_epsilon = ripple_log_epsilon(ripple_db)

    if is_lowpass:
        ratio = freq_hz / cutoff_hz
    else:
        ratio = cutoff_hz / freq_hz  # Inverted for HPF; freq_hz == 0 returned above

    tn = chebyshev_polynomial(order, ratio)
    if tn == 0:
        return 1.0
    log_polynomial = math.inf if math.isinf(tn) else math.log(abs(tn))
    return magnitude_from_log_gain(log_epsilon + log_polynomial)


def _bessel_response_base(freq_hz: float, cutoff_hz: float, order: int, is_lowpass: bool) -> float:
    """Calculate Bessel filter magnitude response.

    The frequency ratio is multiplied by BESSEL_SCALE[order] because the raw
    Bessel polynomial reaches -3 dB at w = scale, not w = 1; the scaling
    pins cutoff_hz to the -3 dB point so all three filter families share the
    same cutoff semantics.

    Args:
        freq_hz: Frequency in Hz
        cutoff_hz: Cutoff frequency in Hz (-3 dB point)
        order: Filter order (2-9, the range covered by the coefficient table)
        is_lowpass: True for lowpass, False for highpass

    Returns:
        Magnitude response (0 to 1)

    Raises:
        ValueError: If order is outside 2-9.
    """
    _validate_response_inputs(freq_hz, cutoff_hz, order)
    if not 2 <= order <= 9:
        raise ValueError("Order must be between 2 and 9")
    if not is_lowpass and freq_hz == 0:
        return 0.0  # HPF blocks DC

    if is_lowpass:
        w = (freq_hz / cutoff_hz) * BESSEL_SCALE[order]
    else:
        # Inverted for HPF; freq_hz == 0 returned above
        w = (cutoff_hz / freq_hz) * BESSEL_SCALE[order]

    coeffs = BESSEL_COEFFS[order]

    # |H(jw)|^2 = theta_n(0)^2 / |theta_n(jw)|^2, with theta_n the reverse
    # Bessel polynomial (coeffs in ascending powers of s). Substituting
    # s = jw makes term k carry j^k = (real for even k, imaginary for odd),
    # with sign (-1)^(k//2) — accumulate the two parts without complex math.
    real_part, imag_part = 0.0, 0.0
    w_power = 1.0

    for k, c in enumerate(coeffs):
        if not math.isfinite(w_power):
            return 0.0
        if k % 2 == 0:
            sign = (-1) ** (k // 2)
            real_part += sign * c * w_power
        else:
            sign = (-1) ** (k // 2)
            imag_part += sign * c * w_power
        if not math.isfinite(real_part) or not math.isfinite(imag_part):
            return 0.0
        w_power *= w

    denominator = math.hypot(real_part, imag_part)
    if denominator == 0:
        return 1.0 if is_lowpass else 0.0  # LP passes DC, HP blocks DC
    # |theta_n(jw)| >= theta_n(0) analytically, so clamp only guards float
    # rounding near w = 0 from pushing the magnitude a hair above unity.
    return min(coeffs[0] / denominator, 1.0)


# Lowpass public API
def lowpass_butterworth_response(freq_hz: float, cutoff_hz: float, order: int) -> float:
    """Calculate Butterworth lowpass filter magnitude response (0 to 1)."""
    return _butterworth_response_base(freq_hz, cutoff_hz, order, is_lowpass=True)


def lowpass_chebyshev_response(
    freq_hz: float, cutoff_hz: float, order: int, ripple_db: float
) -> float:
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


def highpass_chebyshev_response(
    freq_hz: float, cutoff_hz: float, order: int, ripple_db: float
) -> float:
    """Calculate Chebyshev Type I highpass filter magnitude response.

    HPF uses inverted frequency ratio: fc/f instead of f/fc
    """
    return _chebyshev_response_base(freq_hz, cutoff_hz, order, ripple_db, is_lowpass=False)


def highpass_bessel_response(freq_hz: float, cutoff_hz: float, order: int) -> float:
    """Calculate Bessel highpass filter magnitude response.

    HPF uses inverted frequency transformation: w_hp = fc/f * scale
    """
    return _bessel_response_base(freq_hz, cutoff_hz, order, is_lowpass=False)
