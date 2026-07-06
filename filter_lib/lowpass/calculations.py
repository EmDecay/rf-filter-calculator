"""LC lowpass filter calculations (Pi and T topologies).

Provides Butterworth, Chebyshev, and Bessel filter coefficient calculations.
Topology parameter controls component position mapping:
  Pi: odd positions = shunt C, even positions = series L
  T:  odd positions = series L, even positions = shunt C

This module is a thin wrapper around the shared base calculations.
"""

from ..shared.lp_hp_base_calculations import (
    calculate_lowpass_bessel,
    calculate_lowpass_butterworth,
    calculate_lowpass_chebyshev,
)


def calculate_butterworth(
    cutoff_hz: float, impedance: float, num_components: int, topology: str
) -> tuple[list[float], list[float], int]:
    """Calculate Butterworth low-pass filter component values.

    Args:
        cutoff_hz: -3 dB cutoff frequency in Hz
        impedance: Characteristic impedance in Ohms
        num_components: Number of filter elements (2-9)
        topology: 'pi' or 't'

    Returns:
        Tuple of (capacitors in Farads, inductors in Henries, order)

    Raises:
        ValueError: If any input is non-positive/non-finite, num_components is
            outside 2-9, or topology is not 'pi'/'t'.
    """
    return calculate_lowpass_butterworth(cutoff_hz, impedance, num_components, topology)


def calculate_chebyshev(
    cutoff_hz: float, impedance: float, ripple_db: float, num_components: int, topology: str
) -> tuple[list[float], list[float], int]:
    """Calculate Chebyshev low-pass filter component values.

    Convention: ``cutoff_hz`` is the ripple-band edge (attenuation = ripple_db
    there), not the -3 dB point, which lies above it.

    Args:
        cutoff_hz: Ripple-band edge frequency in Hz
        impedance: Characteristic impedance in Ohms
        ripple_db: Passband ripple in dB (> 0; the CLI adds a 3.0 dB cap for
            bandpass/wizard but LP/HP accepts any positive finite value)
        num_components: Number of filter elements; odd only (3/5/7/9) because
            equal source/load terminations require odd Chebyshev order
        topology: 'pi' or 't'

    Returns:
        Tuple of (capacitors in Farads, inductors in Henries, order)

    Raises:
        ValueError: If inputs are non-positive/non-finite, order is even or
            outside 2-9, or topology is not 'pi'/'t'.
    """
    return calculate_lowpass_chebyshev(cutoff_hz, impedance, ripple_db, num_components, topology)


def calculate_bessel(
    cutoff_hz: float, impedance: float, num_components: int, topology: str
) -> tuple[list[float], list[float], int]:
    """Calculate Bessel (Thomson) low-pass filter component values.

    Bessel filters provide maximally-flat group delay (linear phase response).
    g-values come from the Zverev lookup table (orders 2-9 only).

    Args:
        cutoff_hz: -3 dB cutoff frequency in Hz
        impedance: Characteristic impedance in Ohms
        num_components: Number of filter elements (2-9)
        topology: 'pi' or 't'

    Returns:
        Tuple of (capacitors in Farads, inductors in Henries, order)

    Raises:
        ValueError: If any input is non-positive/non-finite, num_components is
            outside 2-9, or topology is not 'pi'/'t'.
    """
    return calculate_lowpass_bessel(cutoff_hz, impedance, num_components, topology)
