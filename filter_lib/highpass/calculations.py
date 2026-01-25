"""T-topology LC high-pass filter calculations.

Provides Butterworth, Chebyshev, and Bessel filter coefficient calculations.
T-topology: series inductors (odd positions), shunt capacitors (even positions).
"""
import math
from ..shared.constants import BESSEL_G_VALUES
from ..shared.chebyshev_g_calculator import calculate_chebyshev_g_values


def calculate_butterworth(cutoff_hz: float, impedance: float,
                          num_components: int) -> tuple[list[float], list[float], int]:
    """Calculate Butterworth T high-pass filter component values.

    T-topology: L1 - C1 - L2 - C2 - L3 (series inductors, shunt capacitors)

    Args:
        cutoff_hz: Cutoff frequency in Hz
        impedance: Characteristic impedance in Ohms
        num_components: Number of filter elements (2-9)

    Returns:
        Tuple of (inductors, capacitors, order)
    """
    n = num_components
    omega = 2 * math.pi * cutoff_hz

    inductors = []
    capacitors = []

    for i in range(1, n + 1):
        k = (2 * i - 1) * math.pi / (2 * n)
        g = 2 * math.sin(k)

        # HPF formulas (dual of LPF Pi topology)
        # Series inductor: L = Z0 / (omega * g)
        # Shunt capacitor: C = g / (omega * Z0)

        if i % 2 == 1:  # Odd position: series inductor
            ind_value = impedance / (omega * g)
            inductors.append(ind_value)
        else:  # Even position: shunt capacitor
            cap_value = g / (omega * impedance)
            capacitors.append(cap_value)

    return inductors, capacitors, n


def calculate_chebyshev(cutoff_hz: float, impedance: float, ripple_db: float,
                        num_components: int) -> tuple[list[float], list[float], int]:
    """Calculate Chebyshev T high-pass filter component values.

    Args:
        cutoff_hz: Cutoff frequency in Hz
        impedance: Characteristic impedance in Ohms
        ripple_db: Passband ripple in dB
        num_components: Number of filter elements (2-9)

    Returns:
        Tuple of (inductors, capacitors, order)
    """
    n = num_components
    omega = 2 * math.pi * cutoff_hz

    # Get g-values from shared calculator
    g = calculate_chebyshev_g_values(n, ripple_db)

    # Convert g-values to L/C (highpass T topology)
    inductors = []
    capacitors = []

    for i in range(1, n + 1):
        if i % 2 == 1:  # Odd position: series inductor
            inductors.append(impedance / (omega * g[i]))
        else:  # Even position: shunt capacitor
            capacitors.append(g[i] / (omega * impedance))

    return inductors, capacitors, n


def calculate_bessel(cutoff_hz: float, impedance: float,
                     num_components: int) -> tuple[list[float], list[float], int]:
    """Calculate Bessel (Thomson) T high-pass filter component values.

    Bessel filters provide maximally-flat group delay (linear phase response).

    Args:
        cutoff_hz: Cutoff frequency in Hz
        impedance: Characteristic impedance in Ohms
        num_components: Number of filter elements (2-9)

    Returns:
        Tuple of (inductors, capacitors, order)
    """
    n = num_components
    if n not in BESSEL_G_VALUES:
        raise ValueError(f"Bessel filter supports 2-9 components, got {n}")

    omega = 2 * math.pi * cutoff_hz
    g_values = BESSEL_G_VALUES[n]

    inductors = []
    capacitors = []

    # Loop over g-values array (0-indexed)
    # Physical position = i + 1 (1-indexed in schematic)
    # Even array indices (0, 2, 4) = physical positions 1, 3, 5 = series inductors
    # Odd array indices (1, 3, 5) = physical positions 2, 4, 6 = shunt capacitors
    for i in range(n):
        g = g_values[i]
        if i % 2 == 0:  # Even index -> series inductor (positions 1, 3, 5...)
            inductors.append(impedance / (omega * g))
        else:  # Odd index -> shunt capacitor (positions 2, 4, 6...)
            capacitors.append(g / (omega * impedance))

    return inductors, capacitors, n
