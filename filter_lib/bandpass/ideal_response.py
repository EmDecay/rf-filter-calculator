"""Numerically stable ideal bandpass responses and frequency transformation."""

import math
import sys

from ..shared.lp_hp_base_transfer_functions import lowpass_bessel_response
from ..shared.numeric import (
    is_finite_real,
    positive_float_from_log,
)
from ..shared.numeric import (
    magnitude_from_log_gain as _magnitude_from_log_gain,
)
from ..shared.numeric import (
    ripple_log_epsilon as _ripple_log_epsilon,
)
from ..shared.transfer_functions import magnitude_to_db
from .numeric_validation import _validate_chebyshev_ripple, _validate_order

_LOG_MAX = math.log(sys.float_info.max)
_LOG_MIN_SUBNORMAL = math.log(float.fromhex("0x0.0000000000001p-1022"))
_LOG_TWO = math.log(2.0)


def chebyshev_3db_deviation(order: int, ripple_db: float) -> float:
    """Return normalized deviation where a supported Chebyshev response is -3 dB."""
    _validate_order(order)
    _validate_chebyshev_ripple(ripple_db)
    log_epsilon = _ripple_log_epsilon(ripple_db)
    inverse_epsilon = math.exp(-log_epsilon)
    numerator = math.acosh(inverse_epsilon)
    normalized = 0.0 if order.bit_length() > 1023 else numerator / order
    return math.cosh(normalized)


def _bandpass_deviation(f: float, f0: float, bw: float) -> float:
    """Return ``(f²-f0²)/(BW*f)`` without intermediate overflow or NaN."""
    from .numeric_validation import _is_positive_finite

    if not _is_positive_finite(f):
        raise ValueError("Frequency must be positive and finite")
    if not _is_positive_finite(f0):
        raise ValueError("Center frequency must be positive and finite")
    if not _is_positive_finite(bw):
        raise ValueError("Bandwidth must be positive and finite")
    if f == f0:
        return 0.0

    if f > f0:
        log_ratio = math.log1p((f - f0) / f0)
    else:
        log_ratio = -math.log1p((f0 - f) / f)
    if log_ratio == 0.0:
        return math.copysign(0.0, f - f0)
    absolute_log_ratio = abs(log_ratio)
    gap = -math.expm1(-2.0 * absolute_log_ratio)
    log_deviation = absolute_log_ratio + math.log(gap) + math.log(f0) - math.log(bw)
    if log_deviation > _LOG_MAX:
        return math.copysign(math.inf, log_ratio)
    if log_deviation < _LOG_MIN_SUBNORMAL:
        return math.copysign(0.0, log_ratio)
    return math.copysign(math.exp(log_deviation), log_ratio)


def frequency_from_deviation(delta: float, f0: float, bw: float) -> float:
    """Invert the bandpass deviation using cancellation-resistant roots."""
    from .numeric_validation import _is_positive_finite

    if not is_finite_real(delta):
        raise ValueError("delta must be finite")
    if not _is_positive_finite(f0):
        raise ValueError("f0 must be positive and finite")
    if not _is_positive_finite(bw):
        raise ValueError("bw must be positive and finite")
    if delta == 0:
        return f0

    log_f0 = math.log(f0)
    log_absolute_ratio = math.log(abs(delta)) + math.log(bw) - _LOG_TWO - log_f0
    if log_absolute_ratio <= _LOG_MAX:
        ratio = math.exp(log_absolute_ratio)
        signed_ratio = math.copysign(ratio, delta)
        log_frequency = log_f0 + math.asinh(signed_ratio)
    elif delta > 0:
        # For an unrepresentably large positive ratio, f ~= delta*bw.
        log_frequency = math.log(delta) + math.log(bw)
    else:
        # For an unrepresentably large negative ratio, f ~= f0^2/(|delta|*bw).
        log_frequency = 2 * log_f0 - math.log(-delta) - math.log(bw)
    try:
        return positive_float_from_log(log_frequency, "derived frequency")
    except ValueError as error:
        raise ValueError("delta, f0, and bw must produce a positive finite frequency") from error


def _order_times(value: float, order: int) -> float:
    """Multiply a finite float by any positive Python integer without leaking overflow."""
    if value == 0.0:
        return 0.0
    if order.bit_length() > 1023:
        return math.copysign(math.inf, value)
    product = value * order
    return product if math.isfinite(product) else math.copysign(math.inf, value)


def _cos_integer_multiple(angle: float, order: int) -> float:
    """Evaluate cos(order*angle) without converting an arbitrary-size int to float."""
    if order.bit_length() <= 50:
        return math.cos(order * angle)
    result = 0.0
    addend = angle % math.tau
    multiplier = order
    while multiplier:
        if multiplier & 1:
            result = (result + addend) % math.tau
        addend = (2.0 * addend) % math.tau
        multiplier >>= 1
    return math.cos(result)


def _log_cosh(value: float) -> float:
    """Return log(cosh(value)) without overflowing cosh."""
    absolute = abs(value)
    if math.isinf(absolute):
        return math.inf
    return absolute + math.log1p(math.exp(-2.0 * absolute)) - _LOG_TWO


def magnitude_butterworth(f: float, f0: float, bw: float, order: int) -> float:
    """Return ideal Butterworth bandpass magnitude."""
    _validate_order(order)
    deviation = abs(_bandpass_deviation(f, f0, bw))
    if deviation == 0.0:
        return 1.0
    if math.isinf(deviation):
        return 0.0
    return _magnitude_from_log_gain(_order_times(math.log(deviation), order))


def magnitude_chebyshev(f: float, f0: float, bw: float, order: int, ripple_db: float) -> float:
    """Return ideal Chebyshev Type I bandpass magnitude for true -3 dB ``bw``."""
    _validate_order(order)
    _validate_chebyshev_ripple(ripple_db)
    log_epsilon = _ripple_log_epsilon(ripple_db)
    deviation = abs(_bandpass_deviation(f, f0, bw))
    scaled = deviation * chebyshev_3db_deviation(order, ripple_db)
    if math.isinf(scaled):
        return 0.0
    if scaled <= 1.0:
        polynomial = _cos_integer_multiple(math.acos(scaled), order)
        if polynomial == 0.0:
            return 1.0
        log_polynomial = math.log(abs(polynomial))
    else:
        log_polynomial = _log_cosh(_order_times(math.acosh(scaled), order))
    return _magnitude_from_log_gain(log_epsilon + log_polynomial)


def magnitude_bessel(f: float, f0: float, bw: float, order: int) -> float:
    """Return ideal Bessel bandpass magnitude for supported orders 2-9."""
    _validate_order(order)
    if not 2 <= order <= 9:
        raise ValueError("Order must be between 2 and 9")
    deviation = abs(_bandpass_deviation(f, f0, bw))
    if math.isinf(deviation):
        return 0.0
    try:
        magnitude = lowpass_bessel_response(deviation, 1.0, order)
    except OverflowError:
        return 0.0
    return magnitude if math.isfinite(magnitude) else 0.0


def magnitude_db(
    f: float,
    f0: float,
    bw: float,
    order: int,
    filter_type: str,
    ripple_db: float = 0.5,
) -> float:
    """Return ideal magnitude in dB, floored at the shared -120 dB limit."""
    if filter_type == "butterworth":
        magnitude = magnitude_butterworth(f, f0, bw, order)
    elif filter_type == "chebyshev":
        magnitude = magnitude_chebyshev(f, f0, bw, order, ripple_db)
    elif filter_type == "bessel":
        magnitude = magnitude_bessel(f, f0, bw, order)
    else:
        raise ValueError(f"Unknown filter type: {filter_type}")
    return magnitude_to_db(magnitude)
