"""Input parsing utilities for filter calculators.

Conventions shared by both parsers: matching is case-insensitive, suffixes
are tried longest-first so compound units win over bare prefixes, and a
bare "m"/"M" always means mega (this is an RF tool; milli-scale inputs are
not supported). Values must parse to a positive, finite number. Each parser takes
a ``label`` naming the quantity being parsed (``"Bandwidth"``, ``"Load
resistance"``), so its error message names the option the user supplied.
"""

import math
from decimal import Decimal, InvalidOperation


def _parse_scaled_positive(
    number_text: str, multiplier: float, *, label: str, original: str
) -> float:
    """Scale in decimal space before materializing a binary64 result.

    Parsing the numeric token directly as ``float`` can underflow or overflow
    before a compensating unit suffix is applied (for example ``1e-325GHz``).
    Decimal scaling preserves any final result that binary64 can represent.
    """
    try:
        scaled = Decimal(number_text) * Decimal(str(multiplier))
    except (InvalidOperation, ValueError) as error:
        raise ValueError(f"Invalid {label.lower()}: {original}") from error
    except ArithmeticError as error:
        # Any other decimal signal is an exponent beyond the decimal context (Overflow).
        raise ValueError(f"{label} must be positive and finite: {original}") from error
    if not scaled.is_finite() or scaled <= 0:
        raise ValueError(f"{label} must be positive: {original}")
    result = float(scaled)
    if not math.isfinite(result) or result <= 0:
        raise ValueError(f"{label} must be positive and finite: {original}")
    return result


def parse_frequency(freq_str: str, label: str = "Frequency") -> float:
    """Parse frequency string with unit suffix (Hz, kHz, MHz, GHz).

    Args:
        freq_str: Frequency string (e.g., "14.2MHz", "500kHz", "1GHz")
        label: Quantity named in error messages (e.g., "Bandwidth")

    Returns:
        Frequency in Hz

    Raises:
        ValueError: If the string cannot be parsed or the result is not
            positive and finite
    """
    if not isinstance(freq_str, str):
        raise ValueError(f"{label} must be supplied as text")
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
            return _parse_scaled_positive(num_part, mult, label=label, original=freq_str)

    return _parse_scaled_positive(freq_str, 1.0, label=label, original=freq_str)


def parse_impedance(z_str: str, label: str = "Impedance") -> float:
    """Parse impedance string with unit suffix (ohm, kohm, Mohm, Ω, bare k/M).

    Args:
        z_str: Impedance string (e.g., "50ohm", "1kohm", "1k", "50Ω")
        label: Quantity named in error messages (e.g., "Source resistance")

    Returns:
        Impedance in Ohms

    Raises:
        ValueError: If the string cannot be parsed or the result is not
            positive and finite
    """
    if not isinstance(z_str, str):
        raise ValueError(f"{label} must be supplied as text")
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
            return _parse_scaled_positive(
                z_str[: -len(suffix)].strip(),
                mult,
                label=label,
                original=z_str,
            )

    return _parse_scaled_positive(z_str, 1.0, label=label, original=z_str)


def parse_inductance(inductance_str: str, label: str = "Inductance") -> float:
    """Parse an inductance with H, mH, uH/µH/μH, or nH units.

    A value without a suffix is interpreted as Henries.  Unlike the RF
    frequency shorthand, ``m`` here retains its SI meaning of milli because
    the required trailing ``H`` makes the unit unambiguous. ``label`` names
    the quantity in error messages.
    """
    if not isinstance(inductance_str, str):
        raise ValueError(f"{label} must be supplied as text")
    original = inductance_str.strip()
    normalized = original.replace("µ", "u").replace("μ", "u").lower()
    suffixes = (("mh", 1e-3), ("uh", 1e-6), ("nh", 1e-9), ("h", 1.0))

    for suffix, multiplier in suffixes:
        if normalized.endswith(suffix):
            number = normalized[: -len(suffix)].strip()
            return _parse_scaled_positive(
                number,
                multiplier,
                label=label,
                original=original,
            )
    else:
        return _parse_scaled_positive(normalized, 1.0, label=label, original=original)
