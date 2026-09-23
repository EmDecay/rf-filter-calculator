"""Output formatting utilities for filter values.

Every formatter emits "<number> <unit>" with exactly one space — display
code (split_value_unit in display_helpers.py) splits on that space to
separate value from unit for CSV columns.
"""

from decimal import Decimal

from .numeric import require_finite_real

# A magnitude at or above this multiple of the largest prefix prints in scientific
# notation in the base unit; a prefixed mantissa would otherwise grow without bound
# (a 1e-300 Hz design has a 300-digit millifarad capacitance).
_PREFIX_SPAN = 1000

_FREQUENCY_UNITS = [(1e9, "GHz"), (1e6, "MHz"), (1e3, "kHz"), (1, "Hz")]

# The shortest decimal that round-trips a binary64 value is the text a user typed for
# any input of up to 15 significant digits. Computed values (a geometric center, a
# reconstructed band edge) need 16-17 digits, and fewer than one in a thousand of them
# has a shortest form of 12 digits or fewer, so a header restates inputs of up to 12
# significant digits exactly and rounds everything else.
_MAX_RESTATED_DIGITS = 12


def _format_with_units(
    value: float,
    units: list[tuple[float, str]],
    precision: str = ".4g",
    *,
    base_unit: str,
) -> str:
    """Format value using the first unit whose threshold it meets.

    `units` must be ordered largest threshold first; the scan picks the
    first (threshold, suffix) with abs(value) >= threshold, so unsorted
    entries would select the wrong prefix. From 1000x the largest threshold
    the value prints in scientific notation in ``base_unit``. A fixed-point
    ``precision`` would round a value far below the smallest threshold to
    zero, so such callers handle that range themselves (capacitance and
    inductance switch to scientific notation below 1 fF and 1 pH).
    """
    require_finite_real(value, "formatted value")
    if abs(value) >= _PREFIX_SPAN * units[0][0]:
        # Same text as raw output, so an oversized value reads identically in both.
        return f"{value:.6e} {base_unit}"

    threshold, suffix = units[-1]
    for candidate_threshold, candidate_suffix in units:
        if abs(value) >= candidate_threshold:
            threshold, suffix = candidate_threshold, candidate_suffix
            break
    return f"{value / threshold:{precision}} {suffix}"


def format_frequency(freq_hz: float) -> str:
    """Format frequency with appropriate unit (GHz, MHz, kHz, Hz)."""
    return _format_with_units(freq_hz, _FREQUENCY_UNITS, base_unit="Hz")


def format_capacitance(value_farads: float) -> str:
    """Format capacitance with appropriate unit (F, mF, µF, nF, pF, fF)."""
    require_finite_real(value_farads, "formatted value")
    # Below 1 fF the smallest suffix would print a misleading "0.00 fF";
    # scientific notation in plain Farads keeps sub-fF values readable.
    if abs(value_farads) < 1e-15:
        return f"{value_farads:.2e} F"
    return _format_with_units(
        value_farads,
        [(1, "F"), (1e-3, "mF"), (1e-6, "µF"), (1e-9, "nF"), (1e-12, "pF"), (1e-15, "fF")],
        ".2f",
        base_unit="F",
    )


def format_inductance(value_henries: float) -> str:
    """Format inductance with appropriate unit (H, mH, µH, nH, pH)."""
    require_finite_real(value_henries, "formatted value")
    # Mirrors capacitance: below 1 pH the smallest suffix would lose the value to
    # "0.00 pH", so scientific notation in plain henries keeps it readable.
    if abs(value_henries) < 1e-12:
        return f"{value_henries:.2e} H"
    return _format_with_units(
        value_henries,
        [(1, "H"), (1e-3, "mH"), (1e-6, "µH"), (1e-9, "nH"), (1e-12, "pH")],
        ".2f",
        base_unit="H",
    )


def format_impedance(value_ohms: float) -> str:
    """Format impedance with appropriate unit (MΩ, kΩ, Ω)."""
    return _format_with_units(value_ohms, [(1e6, "MΩ"), (1e3, "kΩ"), (1, "Ω")], base_unit="Ω")


def _restated_decimal(value: float, min_digits: int) -> Decimal:
    """Return the decimal a header prints for ``value``, in the value's own unit.

    A short shortest-round-trip decimal is the typed input, restated exactly. Any longer
    value is computed and is rounded to ``min_digits`` significant digits, so float noise
    such as ``14.175000000000002`` never reaches a header.
    """
    require_finite_real(value, "formatted value")
    shortest = Decimal(repr(float(value)))
    if len(shortest.normalize().as_tuple().digits) <= _MAX_RESTATED_DIGITS:
        return shortest.normalize()
    return Decimal(f"{value:.{min_digits - 1}e}").normalize()


def _decimal_text(number: Decimal, *, scientific: bool = False) -> str:
    """Positional text without trailing zeros; scientific where ``repr`` would use it."""
    if scientific or not -4 <= number.adjusted() < 16:
        return f"{float(number):.{len(number.as_tuple().digits) - 1}e}"
    return format(number, "f")


def format_restated_value(value: float, min_digits: int = 4) -> str:
    """Restate a design value in its own unit (``12345`` for 12345 Ω, ``1e+300``).

    Headers use this rule, and :func:`format_restated_frequency`, to repeat what the
    user asked for: a typed value prints exactly, a computed one at ``min_digits``
    significant digits.
    """
    return _decimal_text(_restated_decimal(value, min_digits))


def format_restated_frequency(freq_hz: float, min_digits: int = 4) -> str:
    """Restate a design frequency with a prefix (``7.0735 MHz``, ``14.175 MHz``).

    Rounding happens before the prefix is chosen, so a computed 999999.99 Hz reads
    ``1 MHz``. From 1000 GHz the value prints in scientific notation in hertz.
    """
    number = _restated_decimal(freq_hz, min_digits)
    if abs(number) >= _PREFIX_SPAN * Decimal(repr(_FREQUENCY_UNITS[0][0])):
        return f"{_decimal_text(number, scientific=True)} Hz"
    for threshold, suffix in _FREQUENCY_UNITS[:-1]:
        scale = Decimal(repr(threshold))
        if abs(number) >= scale:
            # Dividing by a power of ten is exact in decimal arithmetic.
            return f"{_decimal_text((number / scale).normalize())} {suffix}"
    return f"{_decimal_text(number)} Hz"


def band_edge_digits(f_high_hz: float, bandwidth_hz: float) -> int:
    """Significant digits that let two printed band edges restate ``bandwidth_hz``.

    Rounding each edge to this many digits keeps their difference within a tenth of a
    unit in the bandwidth's fourth significant digit (the idea behind the threshold
    table's narrow-band labels). At least four digits are used, and never more than
    the 17 that identify any binary64 value. Below a fractional bandwidth of about 1e-11
    the two edges are only a few binary64 units apart, so even 17 digits restate the
    bandwidth only approximately; the printed bandwidth line stays exact.
    """
    edge_exponent = Decimal(repr(float(f_high_hz))).adjusted()
    bandwidth_exponent = Decimal(repr(float(bandwidth_hz))).adjusted()
    return max(4, min(17, edge_exponent - bandwidth_exponent + 5))


def format_fixed(value: float, decimals: int, *, explicit_sign: bool = False) -> str:
    """Format ``value`` with ``decimals`` fixed places, never printing a negative zero.

    A small negative value that rounds to zero prints as ``0.00`` (or ``+0.00`` with
    ``explicit_sign``) instead of ``-0.00``. Python 3.10 has no ``z`` format flag.
    """
    rendered = f"{value:{'+' if explicit_sign else ''}.{decimals}f}"
    if rendered.startswith("-") and float(rendered) == 0:
        return ("+" if explicit_sign else "") + rendered[1:]
    return rendered
