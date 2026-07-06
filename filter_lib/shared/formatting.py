"""Output formatting utilities for filter values.

Every formatter emits "<number> <unit>" with exactly one space — display
code (split_value_unit in display_helpers.py) splits on that space to
separate value from unit for CSV columns.
"""


def _format_with_units(value: float, units: list[tuple[float, str]], precision: str = ".4g") -> str:
    """Format value using the first unit whose threshold it meets.

    `units` must be ordered largest threshold first; the scan picks the
    first (threshold, suffix) with abs(value) >= threshold, so unsorted
    entries would select the wrong prefix.
    """
    for threshold, suffix in units:
        if abs(value) >= threshold:
            return f"{value / threshold:{precision}} {suffix}"
    # Below every threshold (including exactly 0): scale by the smallest
    # unit rather than fail, e.g. 0.4 nH renders as "0.40 nH".
    _, suffix = units[-1]
    return f"{value / units[-1][0]:{precision}} {suffix}"


def format_frequency(freq_hz: float) -> str:
    """Format frequency with appropriate unit (GHz, MHz, kHz, Hz)."""
    return _format_with_units(freq_hz, [(1e9, "GHz"), (1e6, "MHz"), (1e3, "kHz"), (1, "Hz")])


def format_capacitance(value_farads: float) -> str:
    """Format capacitance with appropriate unit (mF, µF, nF, pF, fF)."""
    # Below 1 fF the smallest suffix would print a misleading "0.00 fF";
    # scientific notation in plain Farads keeps sub-fF values readable.
    if abs(value_farads) < 1e-15:
        return f"{value_farads:.2e} F"
    return _format_with_units(
        value_farads,
        [(1e-3, "mF"), (1e-6, "µF"), (1e-9, "nF"), (1e-12, "pF"), (1e-15, "fF")],
        ".2f",
    )


def format_inductance(value_henries: float) -> str:
    """Format inductance with appropriate unit (H, mH, µH, nH)."""
    return _format_with_units(
        value_henries, [(1, "H"), (1e-3, "mH"), (1e-6, "µH"), (1e-9, "nH")], ".2f"
    )


def format_impedance(value_ohms: float) -> str:
    """Format impedance with appropriate unit (MΩ, kΩ, Ω)."""
    return _format_with_units(value_ohms, [(1e6, "MΩ"), (1e3, "kΩ"), (1, "Ω")])
