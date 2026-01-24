"""Pi LC low-pass filter calculations.

Provides Butterworth, Chebyshev, and Bessel filter coefficient calculations.
"""
import math
from ..shared.constants import BESSEL_G_VALUES
from ..shared.chebyshev_g_calculator import calculate_chebyshev_g_values


def calculate_butterworth(cutoff_hz: float, impedance: float,
                          num_components: int) -> tuple[list[float], list[float], int]:
    """Calculate Butterworth Pi low-pass filter component values.

    Args:
        cutoff_hz: Cutoff frequency in Hz
        impedance: Characteristic impedance in Ohms
        num_components: Number of filter elements (2-9)

    Returns:
        Tuple of (capacitors, inductors, order)
    """
    n = num_components
    omega = 2 * math.pi * cutoff_hz

    capacitors = []
    inductors = []

    for i in range(1, n + 1):
        k = (2 * i - 1) * math.pi / (2 * n)
        g = 2 * math.sin(k)

        cap_value = g / (impedance * omega)
        ind_value = g * impedance / omega

        if i % 2 == 1:
            capacitors.append(cap_value)
        else:
            inductors.append(ind_value)

    return capacitors, inductors, n


def calculate_chebyshev(cutoff_hz: float, impedance: float, ripple_db: float,
                        num_components: int) -> tuple[list[float], list[float], int]:
    """Calculate Chebyshev Pi low-pass filter component values.

    Args:
        cutoff_hz: Cutoff frequency in Hz
        impedance: Characteristic impedance in Ohms
        ripple_db: Passband ripple in dB
        num_components: Number of filter elements (2-9)

    Returns:
        Tuple of (capacitors, inductors, order)
    """
    n = num_components
    omega = 2 * math.pi * cutoff_hz

    # Get g-values from shared calculator
    g = calculate_chebyshev_g_values(n, ripple_db)

    # Convert g-values to L/C (lowpass Pi topology)
    capacitors = []
    inductors = []

    for i in range(1, n + 1):
        if i % 2 == 1:
            capacitors.append(g[i] / (impedance * omega))
        else:
            inductors.append(g[i] * impedance / omega)

    return capacitors, inductors, n


def calculate_bessel(cutoff_hz: float, impedance: float,
                     num_components: int) -> tuple[list[float], list[float], int]:
    """Calculate Bessel (Thomson) Pi low-pass filter component values.

    Bessel filters provide maximally-flat group delay (linear phase response).

    Args:
        cutoff_hz: Cutoff frequency in Hz
        impedance: Characteristic impedance in Ohms
        num_components: Number of filter elements (2-9)

    Returns:
        Tuple of (capacitors, inductors, order)
    """
    n = num_components
    if n not in BESSEL_G_VALUES:
        raise ValueError(f"Bessel filter supports 2-9 components, got {n}")

    omega = 2 * math.pi * cutoff_hz
    g_values = BESSEL_G_VALUES[n]

    capacitors = []
    inductors = []

    for i in range(n):
        g = g_values[i]
        if i % 2 == 0:
            capacitors.append(g / (impedance * omega))
        else:
            inductors.append(g * impedance / omega)

    return capacitors, inductors, n
