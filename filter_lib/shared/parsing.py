"""Input parsing utilities for filter calculators."""
import math


def parse_frequency(freq_str: str) -> float:
    """Parse frequency string with unit suffix (Hz, kHz, MHz, GHz).

    Args:
        freq_str: Frequency string (e.g., "14.2MHz", "500kHz", "1GHz")

    Returns:
        Frequency in Hz

    Raises:
        ValueError: If string cannot be parsed or result is not finite
    """
    freq_str = freq_str.strip()
    freq_str_lower = freq_str.lower()

    suffixes = [('ghz', 1e9), ('mhz', 1e6), ('khz', 1e3), ('hz', 1)]

    for suffix, mult in suffixes:
        if freq_str_lower.endswith(suffix):
            num_part = freq_str[:-len(suffix)].strip()
            result = float(num_part) * mult
            if not math.isfinite(result):
                raise ValueError(f"Invalid frequency: {freq_str}")
            return result

    result = float(freq_str)
    if not math.isfinite(result):
        raise ValueError(f"Invalid frequency: {freq_str}")
    return result


def parse_impedance(z_str: str) -> float:
    """Parse impedance string with unit suffix (ohm, kohm, Mohm, Ω).

    Args:
        z_str: Impedance string (e.g., "50ohm", "1kohm", "50Ω")

    Returns:
        Impedance in Ohms

    Raises:
        ValueError: If string cannot be parsed or result is not finite
    """
    z_str = z_str.strip()
    # Handle Unicode omega symbols
    for omega_char in ['ω', 'Ω']:
        z_str = z_str.replace(omega_char, 'ohm')
    z_str = z_str.lower().replace('omega', 'ohm')

    multipliers = {'mohm': 1e6, 'kohm': 1e3, 'ohm': 1}

    for suffix, mult in multipliers.items():
        if z_str.endswith(suffix):
            result = float(z_str[:-len(suffix)].strip()) * mult
            if not math.isfinite(result):
                raise ValueError(f"Invalid impedance: {z_str}")
            return result

    result = float(z_str)
    if not math.isfinite(result):
        raise ValueError(f"Invalid impedance: {z_str}")
    return result
