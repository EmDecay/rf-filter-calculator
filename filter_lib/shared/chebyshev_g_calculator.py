"""Chebyshev prototype g-value calculator.

Provides the mathematical foundation for Chebyshev filter synthesis.
These normalized element values are derived from:
- Zverev "Handbook of Filter Synthesis" (1967)
- Direct formula computation for arbitrary ripple values
"""

import math

# Conversion factor from dB to nepers for Chebyshev ripple calculation.
# Derivation: dB = 20 * log10(x), nepers = ln(x)
# Therefore: nepers = dB / (20 * log10(e)) = dB * ln(10) / 20
# The factor 40/ln(10) = 2 * 20/ln(10) ≈ 17.3718 accounts for the power ratio
# (squared amplitude) used in the epsilon calculation:
# epsilon = sqrt(10^(ripple_dB/10) - 1)
# Reference: Matthaei, Young, Jones "Microwave Filters" Ch. 4
CHEBYSHEV_DB_TO_NEPER_FACTOR = 40 / math.log(10)


def calculate_chebyshev_g_values(n: int, ripple_db: float) -> list[float]:
    """Calculate Chebyshev prototype g-values from ripple specification.

    This computes g-values directly from the ripple formula, supporting
    arbitrary ripple values (not just lookup table entries).

    Args:
        n: Filter order (number of elements)
        ripple_db: Passband ripple in dB (e.g., 0.1, 0.5, 1.0)

    Returns:
        List of length n+1 where g[0] is unused padding (0.0) and g[1]..g[n]
        are the prototype element values. The padding keeps indices aligned
        with the 1-indexed g_k of the filter-synthesis literature, so the
        recurrence below (and any caller doing g[i]) reads exactly like the
        textbook equations — shifting to 0-indexing would silently break
        every consumer that passes g[i] for element i.

    Note:
        g-values are normalized to the equal-ripple band edge (omega' = 1
        where the response last touches -ripple_db), NOT the -3 dB point.
        Callers that promise -3 dB semantics (e.g. bandpass) must apply
        their own edge correction.
    """
    # Matthaei, Young, Jones "Microwave Filters" Sec. 4.05, Eq. 4.13-4.16
    # (their beta/gamma/a_k/b_k recurrence for equal-ripple prototypes):
    #   beta  = ln(coth(L_Ar / 17.37)) with L_Ar the ripple in dB
    #   gamma = sinh(beta / 2n)                     -> `gn` below
    #   a_k   = sin((2k-1)·pi / 2n)                 -> `a[i]`
    #   b_k   = gamma^2 + sin^2(k·pi / n)           -> `b[i]`
    #   g_1   = 2·a_1 / gamma
    #   g_k   = 4·a_{k-1}·a_k / (b_{k-1}·g_{k-1})
    # 17.37 is Matthaei's rounding of 40/ln(10); we keep it exact.
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
        b[i] = gn**2 + math.sin(k2) ** 2

    g[1] = 2 * a[1] / gn
    for i in range(2, n + 1):
        g[i] = (4 * a[i - 1] * a[i]) / (b[i - 1] * g[i - 1])

    return g
