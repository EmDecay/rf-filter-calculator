"""LC low-pass filter calculations (Pi and T topologies).

Provides Butterworth, Chebyshev, and Bessel filter coefficient calculations.
Topology parameter controls component position mapping:
  Pi: odd positions = shunt C, even positions = series L
  T:  odd positions = series L, even positions = shunt C
"""
import math
from ..shared.constants import BESSEL_G_VALUES
from ..shared.chebyshev_g_calculator import calculate_chebyshev_g_values


def _validate_topology(topology: str) -> None:
    """Validate topology parameter."""
    if topology not in ('pi', 't'):
        raise ValueError(f"Topology must be 'pi' or 't', got '{topology}'")


def calculate_butterworth(cutoff_hz: float, impedance: float,
                          num_components: int,
                          topology: str) -> tuple[list[float], list[float], int]:
    """Calculate Butterworth low-pass filter component values.

    Args:
        cutoff_hz: Cutoff frequency in Hz
        impedance: Characteristic impedance in Ohms
        num_components: Number of filter elements (2-9)
        topology: 'pi' or 't'

    Returns:
        Tuple of (capacitors, inductors, order)
    """
    _validate_topology(topology)
    n = num_components
    omega = 2 * math.pi * cutoff_hz

    capacitors = []
    inductors = []

    for i in range(1, n + 1):
        k = (2 * i - 1) * math.pi / (2 * n)
        g = 2 * math.sin(k)

        cap_value = g / (impedance * omega)
        ind_value = g * impedance / omega

        # Pi: odd=cap, even=ind; T: odd=ind, even=cap
        if (topology == 'pi') == (i % 2 == 1):
            capacitors.append(cap_value)
        else:
            inductors.append(ind_value)

    return capacitors, inductors, n


def calculate_chebyshev(cutoff_hz: float, impedance: float, ripple_db: float,
                        num_components: int,
                        topology: str) -> tuple[list[float], list[float], int]:
    """Calculate Chebyshev low-pass filter component values.

    Args:
        cutoff_hz: Cutoff frequency in Hz
        impedance: Characteristic impedance in Ohms
        ripple_db: Passband ripple in dB
        num_components: Number of filter elements (2-9)
        topology: 'pi' or 't'

    Returns:
        Tuple of (capacitors, inductors, order)
    """
    _validate_topology(topology)
    n = num_components
    omega = 2 * math.pi * cutoff_hz

    # Get g-values from shared calculator
    g = calculate_chebyshev_g_values(n, ripple_db)

    capacitors = []
    inductors = []

    for i in range(1, n + 1):
        cap_value = g[i] / (impedance * omega)
        ind_value = g[i] * impedance / omega

        # Pi: odd=cap, even=ind; T: odd=ind, even=cap
        if (topology == 'pi') == (i % 2 == 1):
            capacitors.append(cap_value)
        else:
            inductors.append(ind_value)

    return capacitors, inductors, n


def calculate_bessel(cutoff_hz: float, impedance: float,
                     num_components: int,
                     topology: str) -> tuple[list[float], list[float], int]:
    """Calculate Bessel (Thomson) low-pass filter component values.

    Bessel filters provide maximally-flat group delay (linear phase response).

    Args:
        cutoff_hz: Cutoff frequency in Hz
        impedance: Characteristic impedance in Ohms
        num_components: Number of filter elements (2-9)
        topology: 'pi' or 't'

    Returns:
        Tuple of (capacitors, inductors, order)
    """
    _validate_topology(topology)
    n = num_components
    if n not in BESSEL_G_VALUES:
        raise ValueError(f"Bessel filter supports 2-9 components, got {n}")

    omega = 2 * math.pi * cutoff_hz
    g_values = BESSEL_G_VALUES[n]

    capacitors = []
    inductors = []

    # 0-indexed loop; physical position = i+1
    # Pi: even-idx (pos 1,3,5) = cap; odd-idx (pos 2,4,6) = ind
    # T:  even-idx (pos 1,3,5) = ind; odd-idx (pos 2,4,6) = cap
    for i in range(n):
        g = g_values[i]
        cap_value = g / (impedance * omega)
        ind_value = g * impedance / omega

        if (topology == 'pi') == (i % 2 == 0):
            capacitors.append(cap_value)
        else:
            inductors.append(ind_value)

    return capacitors, inductors, n
