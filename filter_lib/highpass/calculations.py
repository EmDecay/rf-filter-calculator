"""LC high-pass filter calculations (Pi and T topologies).

Provides Butterworth, Chebyshev, and Bessel filter coefficient calculations.
Topology parameter controls component position mapping:
  T:  odd positions = series C, even positions = shunt L
  Pi: odd positions = shunt L, even positions = series C
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
    """Calculate Butterworth high-pass filter component values.

    Args:
        cutoff_hz: Cutoff frequency in Hz
        impedance: Characteristic impedance in Ohms
        num_components: Number of filter elements (2-9)
        topology: 'pi' or 't'

    Returns:
        Tuple of (inductors, capacitors, order)
    """
    _validate_topology(topology)
    n = num_components
    omega = 2 * math.pi * cutoff_hz

    inductors = []
    capacitors = []

    for i in range(1, n + 1):
        k = (2 * i - 1) * math.pi / (2 * n)
        g = 2 * math.sin(k)

        # HPF formulas: derived from LPF prototype via 1/g transformation
        ind_value = impedance / (omega * g)
        cap_value = 1.0 / (g * omega * impedance)

        # T: odd=cap(series), even=ind(shunt); Pi: odd=ind(shunt), even=cap(series)
        if (topology == 't') == (i % 2 == 1):
            capacitors.append(cap_value)
        else:
            inductors.append(ind_value)

    return inductors, capacitors, n


def calculate_chebyshev(cutoff_hz: float, impedance: float, ripple_db: float,
                        num_components: int,
                        topology: str) -> tuple[list[float], list[float], int]:
    """Calculate Chebyshev high-pass filter component values.

    Args:
        cutoff_hz: Cutoff frequency in Hz
        impedance: Characteristic impedance in Ohms
        ripple_db: Passband ripple in dB
        num_components: Number of filter elements (2-9)
        topology: 'pi' or 't'

    Returns:
        Tuple of (inductors, capacitors, order)
    """
    _validate_topology(topology)
    n = num_components
    omega = 2 * math.pi * cutoff_hz

    # Get g-values from shared calculator
    g = calculate_chebyshev_g_values(n, ripple_db)

    inductors = []
    capacitors = []

    for i in range(1, n + 1):
        ind_value = impedance / (omega * g[i])
        cap_value = 1.0 / (g[i] * omega * impedance)

        # T: odd=cap(series), even=ind(shunt); Pi: odd=ind(shunt), even=cap(series)
        if (topology == 't') == (i % 2 == 1):
            capacitors.append(cap_value)
        else:
            inductors.append(ind_value)

    return inductors, capacitors, n


def calculate_bessel(cutoff_hz: float, impedance: float,
                     num_components: int,
                     topology: str) -> tuple[list[float], list[float], int]:
    """Calculate Bessel (Thomson) high-pass filter component values.

    Bessel filters provide maximally-flat group delay (linear phase response).

    Args:
        cutoff_hz: Cutoff frequency in Hz
        impedance: Characteristic impedance in Ohms
        num_components: Number of filter elements (2-9)
        topology: 'pi' or 't'

    Returns:
        Tuple of (inductors, capacitors, order)
    """
    _validate_topology(topology)
    n = num_components
    if n not in BESSEL_G_VALUES:
        raise ValueError(f"Bessel filter supports 2-9 components, got {n}")

    omega = 2 * math.pi * cutoff_hz
    g_values = BESSEL_G_VALUES[n]

    inductors = []
    capacitors = []

    # 0-indexed loop; physical position = i+1
    # T: even-idx (pos 1,3,5) = ind; odd-idx (pos 2,4,6) = cap
    # Pi: even-idx (pos 1,3,5) = cap; odd-idx (pos 2,4,6) = ind
    for i in range(n):
        g = g_values[i]
        ind_value = impedance / (omega * g)
        cap_value = 1.0 / (g * omega * impedance)

        # T: even-idx(pos 1,3,5)=cap(series); odd-idx(pos 2,4,6)=ind(shunt)
        if (topology == 't') == (i % 2 == 0):
            capacitors.append(cap_value)
        else:
            inductors.append(ind_value)

    return inductors, capacitors, n
