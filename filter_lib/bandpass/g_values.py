"""Prototype g-value functions for filter design.

Provides g-value calculations for Butterworth, Chebyshev, and Bessel filters.
These normalized element values are the foundation of filter synthesis.

References:
- Zverev "Handbook of Filter Synthesis" (1967)
- Matthaei, Young, Jones "Microwave Filters, Impedance-Matching Networks..."
"""

import math

from ..shared.chebyshev_g_calculator import calculate_chebyshev_g_values
from ..shared.constants import BESSEL_G_VALUES


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
    """Calculate Chebyshev prototype g-values for an arbitrary ripple.

    Note: Chebyshev with equal terminations requires ODD resonator counts.

    Args:
        n: Number of resonators (odd only)
        ripple_db: Passband ripple in dB, in (0, 3.0]

    Returns:
        List of g-values [g1, g2, ..., gn]

    Raises:
        ValueError: If n is even or ripple_db is outside (0, 3.0]
    """
    if not math.isfinite(ripple_db) or ripple_db <= 0:
        raise ValueError("ripple_db must be positive and finite")
    if ripple_db > 3.0:
        raise ValueError(f"Ripple {ripple_db} dB not supported. Must be at most 3.0 dB")
    if n < 1 or n % 2 == 0:
        raise ValueError(
            f"Chebyshev requires an odd resonator count for equal terminations. "
            f"Got {n}. Use Butterworth for even counts."
        )
    # The calculator returns [0.0, g1, ..., gn]; strip the unused g[0].
    return calculate_chebyshev_g_values(n, ripple_db)[1:]


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
    if filter_type == "butterworth":
        return calculate_butterworth_g_values(n)
    elif filter_type == "chebyshev":
        return get_chebyshev_g_values(n, ripple_db)
    elif filter_type == "bessel":
        return get_bessel_g_values(n)
    else:
        raise ValueError(f"Unknown filter type: {filter_type}")
