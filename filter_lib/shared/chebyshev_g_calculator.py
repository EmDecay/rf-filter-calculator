"""Chebyshev prototype g-value calculator.

Provides the mathematical foundation for Chebyshev filter synthesis.
These normalized element values are derived from:
- Zverev "Handbook of Filter Synthesis" (1967)
- Direct formula computation for arbitrary ripple values
"""
import math

# Conversion factor from dB to nepers for Chebyshev ripple calculation.
# Derivation: dB = 20 * log10(x), nepers = ln(x)
# Therefore: nepers = dB / (20 * log10(e)) = dB / 8.686
# The factor 17.37 = 2 * 8.686 accounts for the power ratio (squared amplitude)
# used in the epsilon calculation: epsilon = sqrt(10^(ripple_dB/10) - 1)
# Reference: Matthaei, Young, Jones "Microwave Filters" Ch. 4
CHEBYSHEV_DB_TO_NEPER_FACTOR = 17.37


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
    rr = ripple_db / CHEBYSHEV_DB_TO_NEPER_FACTOR
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
