"""Shared filter design constants.

References:
- Zverev "Handbook of Filter Synthesis" (1967)
- Matthaei, Young, Jones "Microwave Filters, Impedance-Matching Networks..."
"""

# Bessel filter g-values (normalized element values) from Zverev's tables.
# Keys are filter order; values are g1..gn listed in ladder order starting
# from the source end, normalized to -3 dB at omega = 1 with equal 1-ohm
# terminations. Unlike Butterworth/odd-Chebyshev prototypes, Bessel
# prototypes are asymmetric, so element order matters — reversing a row
# yields the (electrically equivalent but differently valued) dual ladder,
# and would change every component table this tool prints.
# Bessel g-values have no closed form, hence a lookup table rather than a
# calculator module like Chebyshev's.
BESSEL_G_VALUES: dict[int, list[float]] = {
    2: [0.5755, 2.1478],
    3: [0.3374, 0.9705, 2.2034],
    4: [0.2334, 0.6725, 1.0815, 2.2404],
    5: [0.1743, 0.5072, 0.8040, 1.1110, 2.2582],
    6: [0.1365, 0.4002, 0.6392, 0.8538, 1.1126, 2.2645],
    7: [0.1106, 0.3259, 0.5249, 0.7020, 0.8690, 1.1052, 2.2659],
    8: [0.0919, 0.2719, 0.4409, 0.5936, 0.7303, 0.8695, 1.0956, 2.2656],
    9: [0.0780, 0.2313, 0.3770, 0.5108, 0.6306, 0.7407, 0.8639, 1.0863, 2.2649],
}
