"""LC high-pass filter calculations (Pi and T topologies).

Provides Butterworth, Chebyshev, and Bessel filter coefficient calculations.
Topology parameter controls component position mapping:
  T:  odd positions = series C, even positions = shunt L
  Pi: odd positions = shunt L, even positions = series C

This module is a thin wrapper around the shared base calculations.
"""
from ..shared.lp_hp_base_calculations import (
    calculate_highpass_butterworth,
    calculate_highpass_chebyshev,
    calculate_highpass_bessel,
)


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
    return calculate_highpass_butterworth(cutoff_hz, impedance, num_components, topology)


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
    return calculate_highpass_chebyshev(cutoff_hz, impedance, ripple_db, num_components, topology)


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
    return calculate_highpass_bessel(cutoff_hz, impedance, num_components, topology)
