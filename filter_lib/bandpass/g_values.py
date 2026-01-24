"""Prototype g-value functions for filter design.

Provides g-value calculations for Butterworth, Chebyshev, and Bessel filters.
These normalized element values are the foundation of filter synthesis.

References:
- Zverev "Handbook of Filter Synthesis" (1967)
- Matthaei, Young, Jones "Microwave Filters, Impedance-Matching Networks..."
"""

import math

from ..shared.constants import BESSEL_G_VALUES, CHEBYSHEV_G_VALUES


def calculate_butterworth_g_values(n: int) -> list[float]:
    """Calculate Butterworth prototype g-values.

    Formula: g[i] = 2 * sin((2*i - 1) * pi / (2*n))

    Args:
        n: Filter order (number of resonators)

    Returns:
        List of g-values [g1, g2, ..., gn]
    """
    return [2 * math.sin((2 * i - 1) * math.pi / (2 * n)) for i in range(1, n + 1)]


def get_chebyshev_g_values(n: int, ripple_db: float) -> list[float]:
    """Get Chebyshev prototype g-values from lookup table.

    Note: Chebyshev with equal terminations requires ODD resonator counts.

    Args:
        n: Number of resonators (3, 5, 7, or 9 - odd only)
        ripple_db: Passband ripple (0.1, 0.5, or 1.0 dB)

    Returns:
        List of g-values [g1, g2, ..., gn]

    Raises:
        ValueError: If n or ripple_db not in table
    """
    if ripple_db not in CHEBYSHEV_G_VALUES:
        raise ValueError(f"Ripple {ripple_db} dB not supported. Use 0.1, 0.5, or 1.0")
    if n not in CHEBYSHEV_G_VALUES[ripple_db]:
        raise ValueError(
            f"Chebyshev requires odd resonator count (3, 5, 7, 9) for equal terminations. "
            f"Got {n}. Use Butterworth for even counts."
        )
    return CHEBYSHEV_G_VALUES[ripple_db][n].copy()


def get_bessel_g_values(n: int) -> list[float]:
    """Get Bessel (Thomson) prototype g-values from lookup table.

    Args:
        n: Number of resonators (2-9)

    Returns:
        List of g-values [g1, g2, ..., gn]

    Raises:
        ValueError: If n not in table (2-9)
    """
    if n not in BESSEL_G_VALUES:
        raise ValueError(f"Bessel g-values only available for 2-9 resonators, got {n}")
    return BESSEL_G_VALUES[n].copy()


def get_g_values(filter_type: str, n: int, ripple_db: float = 0.5) -> list[float]:
    """Get g-values for any supported filter type.

    Args:
        filter_type: 'butterworth', 'chebyshev', or 'bessel'
        n: Number of resonators
        ripple_db: Chebyshev ripple (ignored for other types)

    Returns:
        List of g-values [g1, g2, ..., gn]

    Raises:
        ValueError: If filter_type unknown or parameters invalid
    """
    if filter_type == 'butterworth':
        return calculate_butterworth_g_values(n)
    elif filter_type == 'chebyshev':
        return get_chebyshev_g_values(n, ripple_db)
    elif filter_type == 'bessel':
        return get_bessel_g_values(n)
    else:
        raise ValueError(f"Unknown filter type: {filter_type}")
