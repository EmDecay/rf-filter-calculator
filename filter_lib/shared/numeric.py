"""Overflow- and underflow-aware numeric primitives shared by calculators."""

import math
import sys

_LOG_MIN_SUBNORMAL = math.log(float.fromhex("0x0.0000000000001p-1022"))


def is_finite_real(value: object) -> bool:
    """Return whether ``value`` is a binary64-compatible finite real.

    ``math.isfinite`` converts Python integers to ``float`` and therefore
    raises ``OverflowError`` for sufficiently large integers.  Public API
    validators use this predicate so malformed numeric input is rejected
    consistently instead of leaking an implementation exception.
    """
    if not isinstance(value, (int, float)) or isinstance(value, bool):
        return False
    try:
        return math.isfinite(value)
    except (OverflowError, TypeError, ValueError):
        return False


def require_positive_finite(value: object, label: str) -> int | float:
    """Return a positive finite real or raise a stable public ``ValueError``."""
    if not is_finite_real(value) or value <= 0:
        raise ValueError(f"{label} must be positive and finite")
    return value


def require_nonnegative_finite(value: object, label: str) -> int | float:
    """Return a non-negative finite real or raise a stable public ``ValueError``."""
    if not is_finite_real(value) or value < 0:
        raise ValueError(f"{label} must be non-negative and finite")
    return value


def require_finite_real(value: object, label: str) -> int | float:
    """Return a finite real (of either sign) or raise a stable ``ValueError``."""
    if not is_finite_real(value):
        raise ValueError(f"{label} must be a finite real number")
    return value


def require_integer(value: object, label: str, *, minimum: int) -> int:
    """Return an exact Python integer at or above ``minimum``."""
    if isinstance(value, bool) or not isinstance(value, int) or value < minimum:
        qualifier = "non-negative" if minimum == 0 else "positive"
        raise ValueError(f"{label} must be a {qualifier} integer")
    return value


def positive_float_from_log(log_value: float, label: str) -> float:
    """Materialize a positive finite float from its logarithm.

    Keeping multiplicative calculations in log space lets callers accept an
    extreme input when the *result* is representable, while still returning a
    clear validation error when the requested result would overflow or round
    down to zero.
    """
    if not is_finite_real(log_value):
        raise ValueError(f"{label} logarithm must be finite")
    try:
        result = math.exp(log_value)
    except OverflowError as error:
        raise ValueError(f"{label} is outside the positive finite numeric range") from error
    if not math.isfinite(result) or result <= 0:
        raise ValueError(f"{label} is outside the positive finite numeric range")
    return result


def positive_geometric_mean(first: float, second: float) -> float:
    """Return ``sqrt(first * second)`` without forming the risky product."""
    for name, value in (("first", first), ("second", second)):
        if not is_finite_real(value) or value <= 0:
            raise ValueError(f"{name} must be positive and finite")
    result = math.sqrt(first) * math.sqrt(second)
    if not math.isfinite(result) or result <= 0:
        raise ValueError("geometric mean is outside the positive finite numeric range")
    return result


def ripple_log_epsilon(ripple_db: float) -> float:
    """Return log(sqrt(10**(ripple_db/10)-1)) without underflow."""
    log_scaled = math.log(ripple_db) + math.log(math.log(10.0) / 10.0)
    if log_scaled < math.log(1e-8):
        return 0.5 * log_scaled
    scaled = ripple_db * math.log(10.0) / 10.0
    if scaled > math.log(sys.float_info.max):
        return 0.5 * scaled
    return 0.5 * math.log(math.expm1(scaled))


def magnitude_from_log_gain(log_gain: float) -> float:
    """Return ``1/hypot(1, exp(log_gain))`` without overflowing."""
    if log_gain > 0:
        inverse_gain = math.exp(-log_gain) if log_gain < -_LOG_MIN_SUBNORMAL else 0.0
        return inverse_gain / math.hypot(inverse_gain, 1.0)
    gain = math.exp(log_gain) if log_gain > _LOG_MIN_SUBNORMAL else 0.0
    return 1.0 / math.hypot(1.0, gain)
