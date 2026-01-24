"""Shared filter design constants.

References:
- Zverev "Handbook of Filter Synthesis" (1967)
- Matthaei, Young, Jones "Microwave Filters, Impedance-Matching Networks..."
"""

# Bessel filter g-values (normalized element values)
# Keys are filter order, values are g-values for each element
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

# Chebyshev g-values for equal-termination bandpass filters
# Outer dict key: ripple in dB (0.1, 0.5, 1.0)
# Inner dict key: number of resonators (odd only: 3, 5, 7, 9)
# Note: Chebyshev requires odd resonator count for equal source/load impedance
CHEBYSHEV_G_VALUES: dict[float, dict[int, list[float]]] = {
    0.1: {  # 0.1 dB ripple
        3: [1.03159, 1.14740, 1.03159],
        5: [1.14684, 1.37121, 1.97503, 1.37121, 1.14684],
        7: [1.18120, 1.42280, 2.09669, 1.57339, 2.09669, 1.42280, 1.18120],
        9: [1.19570, 1.44260, 2.13457, 1.61671, 2.20539, 1.61671, 2.13457, 1.44260, 1.19570],
    },
    0.5: {  # 0.5 dB ripple
        3: [1.59633, 1.09668, 1.59633],
        5: [1.70582, 1.22961, 2.54088, 1.22961, 1.70582],
        7: [1.73734, 1.25822, 2.63834, 1.34431, 2.63834, 1.25822, 1.73734],
        9: [1.75049, 1.26902, 2.66783, 1.36730, 2.72396, 1.36730, 2.66783, 1.26902, 1.75049],
    },
    1.0: {  # 1.0 dB ripple
        3: [2.02367, 0.99408, 2.02367],
        5: [2.13496, 1.09108, 3.00101, 1.09108, 2.13496],
        7: [2.16664, 1.11148, 3.09373, 1.17349, 3.09373, 1.11148, 2.16664],
        9: [2.17980, 1.11915, 3.12152, 1.18964, 3.17472, 1.18964, 3.12152, 1.11915, 2.17980],
    },
}
