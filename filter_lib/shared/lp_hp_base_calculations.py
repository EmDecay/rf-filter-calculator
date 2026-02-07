"""Shared base calculations for lowpass and highpass filters.

This module contains common calculation logic using strategy pattern to handle
LP vs HP specific formulas and component ordering.

Key differences between LP and HP:
- LP: capacitors in shunt, inductors in series (Pi: C-L-C, T: L-C-L)
- HP: inverted - capacitors in series, inductors in shunt
- Component formulas are duals (LP: C=g/(Z*omega), L=g*Z/omega;
  HP: C=1/(g*omega*Z), L=Z/(omega*g))
"""
import math
from typing import Callable
from .constants import BESSEL_G_VALUES
from .chebyshev_g_calculator import calculate_chebyshev_g_values


def _validate_topology(topology: str) -> None:
    """Validate topology parameter."""
    if topology not in ('pi', 't'):
        raise ValueError(f"Topology must be 'pi' or 't', got '{topology}'")


def _calculate_butterworth_base(
    cutoff_hz: float,
    impedance: float,
    num_components: int,
    topology: str,
    cap_formula: Callable[[float, float, float], float],
    ind_formula: Callable[[float, float, float], float],
    is_lowpass: bool
) -> tuple[list[float], list[float], int]:
    """Base Butterworth calculation with strategy functions for LP/HP differences.

    Args:
        cutoff_hz: Cutoff frequency in Hz
        impedance: Characteristic impedance in Ohms
        num_components: Number of filter elements (2-9)
        topology: 'pi' or 't'
        cap_formula: Function(g, impedance, omega) -> capacitor value
        ind_formula: Function(g, impedance, omega) -> inductor value
        is_lowpass: True for lowpass, False for highpass

    Returns:
        Tuple of (capacitors, inductors, order) for LP or (inductors, capacitors, order) for HP
    """
    _validate_topology(topology)
    n = num_components
    omega = 2 * math.pi * cutoff_hz

    capacitors = []
    inductors = []

    for i in range(1, n + 1):
        k = (2 * i - 1) * math.pi / (2 * n)
        g = 2 * math.sin(k)

        cap_value = cap_formula(g, impedance, omega)
        ind_value = ind_formula(g, impedance, omega)

        # Determine component placement based on filter type and topology
        if is_lowpass:
            # LP: Pi topology = odd positions are caps, even are inductors
            #     T topology = odd positions are inductors, even are caps
            if (topology == 'pi') == (i % 2 == 1):
                capacitors.append(cap_value)
            else:
                inductors.append(ind_value)
        else:
            # HP: T topology = odd positions are caps (series), even are inductors (shunt)
            #     Pi topology = odd positions are inductors (shunt), even are caps (series)
            if (topology == 't') == (i % 2 == 1):
                capacitors.append(cap_value)
            else:
                inductors.append(ind_value)

    return capacitors, inductors, n


def _calculate_chebyshev_base(
    cutoff_hz: float,
    impedance: float,
    ripple_db: float,
    num_components: int,
    topology: str,
    cap_formula: Callable[[float, float, float], float],
    ind_formula: Callable[[float, float, float], float],
    is_lowpass: bool
) -> tuple[list[float], list[float], int]:
    """Base Chebyshev calculation with strategy functions for LP/HP differences.

    Args:
        cutoff_hz: Cutoff frequency in Hz
        impedance: Characteristic impedance in Ohms
        ripple_db: Passband ripple in dB
        num_components: Number of filter elements (2-9)
        topology: 'pi' or 't'
        cap_formula: Function(g, impedance, omega) -> capacitor value
        ind_formula: Function(g, impedance, omega) -> inductor value
        is_lowpass: True for lowpass, False for highpass

    Returns:
        Tuple of (capacitors, inductors, order) for LP or (inductors, capacitors, order) for HP
    """
    _validate_topology(topology)
    n = num_components
    omega = 2 * math.pi * cutoff_hz

    # Get g-values from shared calculator
    g = calculate_chebyshev_g_values(n, ripple_db)

    capacitors = []
    inductors = []

    for i in range(1, n + 1):
        cap_value = cap_formula(g[i], impedance, omega)
        ind_value = ind_formula(g[i], impedance, omega)

        # Determine component placement based on filter type and topology
        if is_lowpass:
            # LP: Pi topology = odd positions are caps, even are inductors
            #     T topology = odd positions are inductors, even are caps
            if (topology == 'pi') == (i % 2 == 1):
                capacitors.append(cap_value)
            else:
                inductors.append(ind_value)
        else:
            # HP: T topology = odd positions are caps (series), even are inductors (shunt)
            #     Pi topology = odd positions are inductors (shunt), even are caps (series)
            if (topology == 't') == (i % 2 == 1):
                capacitors.append(cap_value)
            else:
                inductors.append(ind_value)

    return capacitors, inductors, n


def _calculate_bessel_base(
    cutoff_hz: float,
    impedance: float,
    num_components: int,
    topology: str,
    cap_formula: Callable[[float, float, float], float],
    ind_formula: Callable[[float, float, float], float],
    is_lowpass: bool
) -> tuple[list[float], list[float], int]:
    """Base Bessel calculation with strategy functions for LP/HP differences.

    Args:
        cutoff_hz: Cutoff frequency in Hz
        impedance: Characteristic impedance in Ohms
        num_components: Number of filter elements (2-9)
        topology: 'pi' or 't'
        cap_formula: Function(g, impedance, omega) -> capacitor value
        ind_formula: Function(g, impedance, omega) -> inductor value
        is_lowpass: True for lowpass, False for highpass

    Returns:
        Tuple of (capacitors, inductors, order) for LP or (inductors, capacitors, order) for HP
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
    for i in range(n):
        g = g_values[i]
        cap_value = cap_formula(g, impedance, omega)
        ind_value = ind_formula(g, impedance, omega)

        # Determine component placement based on filter type and topology
        if is_lowpass:
            # LP Pi: even-idx (pos 1,3,5) = cap; odd-idx (pos 2,4,6) = ind
            # LP T:  even-idx (pos 1,3,5) = ind; odd-idx (pos 2,4,6) = cap
            if (topology == 'pi') == (i % 2 == 0):
                capacitors.append(cap_value)
            else:
                inductors.append(ind_value)
        else:
            # HP T: even-idx(pos 1,3,5)=cap(series); odd-idx(pos 2,4,6)=ind(shunt)
            # HP Pi: even-idx(pos 1,3,5)=ind(shunt); odd-idx(pos 2,4,6)=cap(series)
            if (topology == 't') == (i % 2 == 0):
                capacitors.append(cap_value)
            else:
                inductors.append(ind_value)

    return capacitors, inductors, n


# Strategy functions for lowpass filter component calculations
def _lp_cap_formula(g: float, impedance: float, omega: float) -> float:
    """Lowpass capacitor formula: C = g / (Z * ω)"""
    return g / (impedance * omega)


def _lp_ind_formula(g: float, impedance: float, omega: float) -> float:
    """Lowpass inductor formula: L = g * Z / ω"""
    return g * impedance / omega


# Strategy functions for highpass filter component calculations
def _hp_cap_formula(g: float, impedance: float, omega: float) -> float:
    """Highpass capacitor formula: C = 1 / (g * ω * Z)"""
    return 1.0 / (g * omega * impedance)


def _hp_ind_formula(g: float, impedance: float, omega: float) -> float:
    """Highpass inductor formula: L = Z / (ω * g)"""
    return impedance / (omega * g)


# Public API: Lowpass filter calculations
def calculate_lowpass_butterworth(cutoff_hz: float, impedance: float,
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
    return _calculate_butterworth_base(
        cutoff_hz, impedance, num_components, topology,
        _lp_cap_formula, _lp_ind_formula, is_lowpass=True
    )


def calculate_lowpass_chebyshev(cutoff_hz: float, impedance: float, ripple_db: float,
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
    return _calculate_chebyshev_base(
        cutoff_hz, impedance, ripple_db, num_components, topology,
        _lp_cap_formula, _lp_ind_formula, is_lowpass=True
    )


def calculate_lowpass_bessel(cutoff_hz: float, impedance: float,
                              num_components: int,
                              topology: str) -> tuple[list[float], list[float], int]:
    """Calculate Bessel (Thomson) low-pass filter component values.

    Args:
        cutoff_hz: Cutoff frequency in Hz
        impedance: Characteristic impedance in Ohms
        num_components: Number of filter elements (2-9)
        topology: 'pi' or 't'

    Returns:
        Tuple of (capacitors, inductors, order)
    """
    return _calculate_bessel_base(
        cutoff_hz, impedance, num_components, topology,
        _lp_cap_formula, _lp_ind_formula, is_lowpass=True
    )


# Public API: Highpass filter calculations
def calculate_highpass_butterworth(cutoff_hz: float, impedance: float,
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
    capacitors, inductors, n = _calculate_butterworth_base(
        cutoff_hz, impedance, num_components, topology,
        _hp_cap_formula, _hp_ind_formula, is_lowpass=False
    )
    return inductors, capacitors, n  # HP returns inductors first


def calculate_highpass_chebyshev(cutoff_hz: float, impedance: float, ripple_db: float,
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
    capacitors, inductors, n = _calculate_chebyshev_base(
        cutoff_hz, impedance, ripple_db, num_components, topology,
        _hp_cap_formula, _hp_ind_formula, is_lowpass=False
    )
    return inductors, capacitors, n  # HP returns inductors first


def calculate_highpass_bessel(cutoff_hz: float, impedance: float,
                               num_components: int,
                               topology: str) -> tuple[list[float], list[float], int]:
    """Calculate Bessel (Thomson) high-pass filter component values.

    Args:
        cutoff_hz: Cutoff frequency in Hz
        impedance: Characteristic impedance in Ohms
        num_components: Number of filter elements (2-9)
        topology: 'pi' or 't'

    Returns:
        Tuple of (inductors, capacitors, order)
    """
    capacitors, inductors, n = _calculate_bessel_base(
        cutoff_hz, impedance, num_components, topology,
        _hp_cap_formula, _hp_ind_formula, is_lowpass=False
    )
    return inductors, capacitors, n  # HP returns inductors first
