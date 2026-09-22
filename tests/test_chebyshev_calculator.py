"""Chebyshev prototype g-value calculator: published tables and input contract.

The response-level proof that arbitrary ripple and order produce an equiripple
prototype lives in ``test_prototype_ladder_responses.py``.
"""

import math

import pytest

from filter_lib.shared.chebyshev_g_calculator import (
    MAX_PROTOTYPE_ORDER,
    calculate_chebyshev_g_values,
)

# Published Zverev/Matthaei prototype values (rounded to 5 decimals), kept as
# reference fixtures to pin the calculator against the literature.
PUBLISHED_G_VALUES: dict[float, dict[int, list[float]]] = {
    0.1: {
        3: [1.03159, 1.14740, 1.03159],
        5: [1.14684, 1.37121, 1.97503, 1.37121, 1.14684],
        7: [1.18120, 1.42280, 2.09669, 1.57339, 2.09669, 1.42280, 1.18120],
        9: [1.19570, 1.44260, 2.13457, 1.61671, 2.20539, 1.61671, 2.13457, 1.44260, 1.19570],
    },
    0.5: {
        3: [1.59633, 1.09668, 1.59633],
        5: [1.70582, 1.22961, 2.54088, 1.22961, 1.70582],
        7: [1.73734, 1.25822, 2.63834, 1.34431, 2.63834, 1.25822, 1.73734],
        9: [1.75049, 1.26902, 2.66783, 1.36730, 2.72396, 1.36730, 2.66783, 1.26902, 1.75049],
    },
    1.0: {
        3: [2.02367, 0.99408, 2.02367],
        5: [2.13496, 1.09108, 3.00101, 1.09108, 2.13496],
        7: [2.16664, 1.11148, 3.09373, 1.17349, 3.09373, 1.11148, 2.16664],
        9: [2.17980, 1.11915, 3.12152, 1.18964, 3.17472, 1.18964, 3.12152, 1.11915, 2.17980],
    },
}


@pytest.mark.parametrize("ripple_db", [0.1, 0.5, 1.0])
@pytest.mark.parametrize("n", [3, 5, 7, 9])
def test_agreement_with_published_values(ripple_db, n):
    expected = PUBLISHED_G_VALUES[ripple_db][n]
    computed = calculate_chebyshev_g_values(n, ripple_db)[1:]
    assert len(computed) == len(expected)
    for i, (got, want) in enumerate(zip(computed, expected), start=1):
        # Published values are rounded to 5 decimals -> 1e-4 agreement
        assert got == pytest.approx(want, abs=1e-4), f"g[{i}] mismatch at n={n}"


@pytest.mark.parametrize("n", [1, 2, 9])
def test_g_list_is_one_indexed_with_zero_padding(n):
    """g[0] is unused padding so g[k] is the literature's 1-indexed element g_k."""
    g = calculate_chebyshev_g_values(n, 0.5)

    assert len(g) == n + 1
    assert g[0] == 0.0
    assert all(value > 0 for value in g[1:])


def test_order_limit_is_inclusive():
    assert len(calculate_chebyshev_g_values(MAX_PROTOTYPE_ORDER, 0.5)) == MAX_PROTOTYPE_ORDER + 1
    with pytest.raises(ValueError, match="positive integer no greater than 10,000"):
        calculate_chebyshev_g_values(MAX_PROTOTYPE_ORDER + 1, 0.5)


@pytest.mark.parametrize("order", [0, -1, True, 3.0, "3", None])
def test_invalid_order_is_rejected(order):
    with pytest.raises(ValueError, match="positive integer"):
        calculate_chebyshev_g_values(order, 0.5)


@pytest.mark.parametrize(
    "ripple_db",
    [0.0, -0.1, float("nan"), float("inf"), True, "0.5", None],
)
def test_invalid_ripple_is_rejected(ripple_db):
    with pytest.raises(ValueError, match="ripple_db must be positive and finite"):
        calculate_chebyshev_g_values(3, ripple_db)


def test_ripple_beyond_finite_prototype_range_is_rejected_instead_of_dividing_by_zero():
    """tanh(ripple/17.37) rounds to 1 above about 331 dB, which would make gamma zero."""
    g = calculate_chebyshev_g_values(3, 300.0)
    assert all(math.isfinite(value) and value > 0 for value in g[1:])

    with pytest.raises(ValueError, match="too large for finite prototype"):
        calculate_chebyshev_g_values(3, 400.0)
