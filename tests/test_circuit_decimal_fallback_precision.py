"""Branch magnitudes in the high-precision nodal fallback keep binary64 relative accuracy.

The fallback stamps exp(log_magnitude - log_scale) for every branch. When an extreme port
sets the scale, a binary64 difference of the two logs loses up to 1e-13; the exact Decimal
difference must be used instead. References are 50-digit Decimal exponentials of the
exact difference of the two binary64 logs.
"""

import math
import random
from decimal import Context, Decimal
from fractions import Fraction

import pytest

from filter_lib.shared.decimal_nodal_solver import _difference_is_exact, _scaled_magnitude

REFERENCE = Context(prec=50)


def _reference_magnitude(log_magnitude: float, log_scale: float) -> Decimal:
    exponent = REFERENCE.subtract(Decimal(log_magnitude), Decimal(log_scale))
    return REFERENCE.exp(exponent)


@pytest.mark.parametrize(
    ("minuend", "subtrahend"),
    [
        (1.0, 0.5),
        (0.1, 690.123456789),
        (0.123456789012345, 63.456789012345),
        (-3.5, 2.25),
        (1e16, 1.0),
        (2.0**52, 1.0),
        (690.7755278982137, 690.7755278982137),
        (-45.678901234567, 99.123456789012),
        (5e-324, 1.0),
    ],
)
def test_difference_exactness_matches_rational_arithmetic(minuend, subtrahend):
    """The TwoSum error term is zero exactly when binary64 subtraction lost nothing."""
    difference = minuend - subtrahend
    exact = Fraction(minuend) - Fraction(subtrahend) == Fraction(difference)

    assert _difference_is_exact(minuend, subtrahend, difference) is exact


def test_difference_exactness_matches_rational_arithmetic_on_seeded_samples():
    """Logs of branch admittances span roughly -1500 to 1500; sample that range densely."""
    generator = random.Random(20260923)
    for _ in range(5000):
        minuend = generator.uniform(-1500.0, 1500.0) * 10 ** generator.randint(-6, 0)
        subtrahend = generator.uniform(-1500.0, 1500.0)
        difference = minuend - subtrahend
        exact = Fraction(minuend) - Fraction(subtrahend) == Fraction(difference)

        assert _difference_is_exact(minuend, subtrahend, difference) is exact


# The scale is the largest log in a matrix, so every pair has log_magnitude <= log_scale.
_SCALES = [0.0, 2.5, 63.456789012345, 99.123456789012, 690.7755278982137, 1400.5]
_LOGS = [0.123456789012345, -2.5, -45.678901234567, 0.5, -700.25]
_PAIRS = [(log, scale) for scale in _SCALES for log in _LOGS if log <= scale]


@pytest.mark.parametrize(("log_magnitude", "log_scale"), _PAIRS)
def test_scaled_magnitude_has_binary64_relative_accuracy(log_magnitude, log_scale):
    """Both the direct path (small exponent) and the decade split agree with the reference.

    With a binary64 difference, scales near 63 and 99 would leave errors of several parts
    in 1e15, and a scale near 690 about 1e-13.
    """
    actual = _scaled_magnitude(log_magnitude, log_scale)
    expected = _reference_magnitude(log_magnitude, log_scale)

    relative_error = abs(REFERENCE.divide(actual - expected, expected))
    assert relative_error < Decimal("1e-15"), (log_magnitude, log_scale, relative_error)


def test_magnitudes_far_below_the_binary64_range_keep_their_digits():
    """exp(-1400.75) is about 1e-609: no binary64 value holds it, but the Decimal stamp does."""
    actual = _scaled_magnitude(-700.25, 700.5)
    expected = _reference_magnitude(-700.25, 700.5)

    assert actual.adjusted() == expected.adjusted() == -609
    assert abs(REFERENCE.divide(actual - expected, expected)) < Decimal("1e-15")
    assert math.isfinite(float(REFERENCE.divide(actual, expected)))
