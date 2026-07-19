"""LC highpass filter calculations (Pi and T topologies).

Provides Butterworth, Chebyshev, and Bessel filter coefficient calculations.
Topology parameter controls component position mapping:
  T:  odd positions = series C, even positions = shunt L
  Pi: odd positions = shunt L, even positions = series C

This module is a thin wrapper around the shared base calculations.
"""

from ..shared.lp_hp_base_calculations import (
    calculate_highpass_bessel,
    calculate_highpass_butterworth,
    calculate_highpass_chebyshev,
)


def calculate_butterworth(
    cutoff_hz: float, impedance: float, num_components: int, topology: str
) -> tuple[list[float], list[float], int]:
    """Calculate Butterworth high-pass filter component values.

    Args:
        cutoff_hz: -3 dB cutoff frequency in Hz
        impedance: Characteristic impedance in Ohms
        num_components: Number of filter elements (2-9)
        topology: 'pi' or 't'

    Returns:
        Tuple of (inductors in Henries, capacitors in Farads, order).
        Note the inductors-first ordering — reversed from the lowpass API.

    Raises:
        ValueError: If any input is non-positive/non-finite, num_components is
            outside 2-9, or topology is not 'pi'/'t'.
    """
    return calculate_highpass_butterworth(cutoff_hz, impedance, num_components, topology)


def calculate_chebyshev(
    cutoff_hz: float, impedance: float, ripple_db: float, num_components: int, topology: str
) -> tuple[list[float], list[float], int]:
    """Calculate Chebyshev high-pass filter component values.

    Convention: ``cutoff_hz`` is the ripple-band edge (attenuation = ripple_db
    there), not the -3 dB point, which lies below it for a highpass.

    Args:
        cutoff_hz: Ripple-band edge frequency in Hz
        impedance: Characteristic impedance in Ohms
        ripple_db: Passband ripple in dB, in (0, 3.0]
        num_components: Number of filter elements; odd only (3/5/7/9) because
            equal source/load terminations require odd Chebyshev order
        topology: 'pi' or 't'

    Returns:
        Tuple of (inductors in Henries, capacitors in Farads, order).
        Note the inductors-first ordering — reversed from the lowpass API.

    Raises:
        ValueError: If inputs are non-positive/non-finite, ripple is above
            3.0 dB, order is even or outside 2-9, or topology is not 'pi'/'t'.
    """
    return calculate_highpass_chebyshev(cutoff_hz, impedance, ripple_db, num_components, topology)


def calculate_bessel(
    cutoff_hz: float, impedance: float, num_components: int, topology: str
) -> tuple[list[float], list[float], int]:
    """Calculate Bessel-prototype high-pass filter component values.

    The transformed magnitude is smooth and monotonic. The low-pass
    prototype's maximally-flat group delay is not preserved by the
    low-pass-to-high-pass transformation.
    g-values come from the Zverev lookup table (orders 2-9 only). Note the
    LP-to-HP transformation does not preserve the flat group delay exactly.

    Args:
        cutoff_hz: -3 dB cutoff frequency in Hz
        impedance: Characteristic impedance in Ohms
        num_components: Number of filter elements (2-9)
        topology: 'pi' or 't'

    Returns:
        Tuple of (inductors in Henries, capacitors in Farads, order).
        Note the inductors-first ordering — reversed from the lowpass API.

    Raises:
        ValueError: If any input is non-positive/non-finite, num_components is
            outside 2-9, or topology is not 'pi'/'t'.
    """
    return calculate_highpass_bessel(cutoff_hz, impedance, num_components, topology)
