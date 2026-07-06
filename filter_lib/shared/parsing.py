"""Input parsing utilities for filter calculators.

Conventions shared by both parsers: matching is case-insensitive, suffixes
are tried longest-first so compound units win over bare prefixes, and a
bare "m"/"M" always means mega (this is an RF tool; milli-scale inputs are
not supported). Values must parse to a positive, finite number.
"""

import math


def parse_frequency(freq_str: str) -> float:
    """Parse frequency string with unit suffix (Hz, kHz, MHz, GHz).

    Args:
        freq_str: Frequency string (e.g., "14.2MHz", "500kHz", "1GHz")

    Returns:
        Frequency in Hz

    Raises:
        ValueError: If the string cannot be parsed or the result is not
            positive and finite
    """
    freq_str = freq_str.strip()
    freq_str_lower = freq_str.lower()

    # Ordered longest-first so "mhz" matches before bare "m" and "hz"
    # before nothing; a list (not dict) makes that ordering explicit.
    # Bare "m" is mega, matching the module-wide convention.
    suffixes = [
        ("ghz", 1e9),
        ("mhz", 1e6),
        ("khz", 1e3),
        ("hz", 1),
        ("g", 1e9),
        ("m", 1e6),
        ("k", 1e3),
    ]

    for suffix, mult in suffixes:
        if freq_str_lower.endswith(suffix):
            num_part = freq_str[: -len(suffix)].strip()
            result = float(num_part) * mult
            if not math.isfinite(result) or result <= 0:
                raise ValueError(f"Frequency must be positive: {freq_str}")
            return result

    result = float(freq_str)
    if not math.isfinite(result) or result <= 0:
        raise ValueError(f"Frequency must be positive: {freq_str}")
    return result


def parse_impedance(z_str: str) -> float:
    """Parse impedance string with unit suffix (ohm, kohm, Mohm, Ω, bare k/M).

    Args:
        z_str: Impedance string (e.g., "50ohm", "1kohm", "1k", "50Ω")

    Returns:
        Impedance in Ohms

    Raises:
        ValueError: If the string cannot be parsed or the result is not
            positive and finite
    """
    z_str = z_str.strip()
    # Handle Unicode omega symbols
    for omega_char in ["ω", "Ω"]:
        z_str = z_str.replace(omega_char, "ohm")
    z_str = z_str.lower().replace("omega", "ohm")

    # Longest suffixes first so "kohm" wins over "ohm" and "k". Bare "m"
    # means Mohm (mega, not milli) — same convention as frequency parsing.
    multipliers = {"mohm": 1e6, "kohm": 1e3, "ohm": 1, "m": 1e6, "k": 1e3}

    for suffix, mult in multipliers.items():
        if z_str.endswith(suffix):
            result = float(z_str[: -len(suffix)].strip()) * mult
            if not math.isfinite(result) or result <= 0:
                raise ValueError(f"Impedance must be positive: {z_str}")
            return result

    result = float(z_str)
    if not math.isfinite(result) or result <= 0:
        raise ValueError(f"Impedance must be positive: {z_str}")
    return result
