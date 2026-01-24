"""Chebyshev prototype g-value calculator.

Provides the mathematical foundation for Chebyshev filter synthesis.
These normalized element values are derived from:
- Zverev "Handbook of Filter Synthesis" (1967)
- Direct formula computation for arbitrary ripple values
"""
import math


def calculate_chebyshev_g_values(n: int, ripple_db: float) -> list[float]:
    """Calculate Chebyshev prototype g-values from ripple specification.

    This computes g-values directly from the ripple formula, supporting
    arbitrary ripple values (not just lookup table entries).

    Args:
        n: Filter order (number of elements)
        ripple_db: Passband ripple in dB (e.g., 0.1, 0.5, 1.0)

    Returns:
        List of g-values [g1, g2, ..., gn] (1-indexed values at indices 1..n)

    Note:
        Returns array where g[0] is unused (0.0), and g[1]..g[n] are the values.
        This matches the mathematical notation used in filter synthesis.
    """
    rr = ripple_db / 17.37
    e2x = math.exp(2 * rr)
    coth = (e2x + 1) / (e2x - 1)
    bt = math.log(coth)
    btn = bt / (2 * n)
    gn = math.sinh(btn)

    a = [0.0] * (n + 1)
    b = [0.0] * (n + 1)
    g = [0.0] * (n + 1)

    for i in range(1, n + 1):
        k = (2 * i - 1) * math.pi / (2 * n)
        a[i] = math.sin(k)
        k2 = math.pi * i / n
        b[i] = gn ** 2 + math.sin(k2) ** 2

    g[1] = 2 * a[1] / gn
    for i in range(2, n + 1):
        g[i] = (4 * a[i - 1] * a[i]) / (b[i - 1] * g[i - 1])

    return g
