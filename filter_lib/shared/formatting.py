"""Output formatting utilities for filter values."""


def _format_with_units(value: float, units: list[tuple[float, str]],
                       precision: str = ".4g") -> str:
    """Generic formatter for values with unit suffixes."""
    for threshold, suffix in units:
        if abs(value) >= threshold:
            return f"{value/threshold:{precision}} {suffix}"
    # Use last unit if value is smaller than all thresholds
    _, suffix = units[-1]
    return f"{value/units[-1][0]:{precision}} {suffix}"


def format_frequency(freq_hz: float) -> str:
    """Format frequency with appropriate unit (GHz, MHz, kHz, Hz)."""
    return _format_with_units(freq_hz, [
        (1e9, 'GHz'), (1e6, 'MHz'), (1e3, 'kHz'), (1, 'Hz')
    ])


def format_capacitance(value_farads: float) -> str:
    """Format capacitance with appropriate unit (mF, µF, nF, pF)."""
    return _format_with_units(value_farads, [
        (1e-3, 'mF'), (1e-6, 'µF'), (1e-9, 'nF'), (1e-12, 'pF')
    ], ".2f")


def format_inductance(value_henries: float) -> str:
    """Format inductance with appropriate unit (H, mH, µH, nH)."""
    return _format_with_units(value_henries, [
        (1, 'H'), (1e-3, 'mH'), (1e-6, 'µH'), (1e-9, 'nH')
    ], ".2f")


def format_impedance(value_ohms: float) -> str:
    """Format impedance with appropriate unit (MΩ, kΩ, Ω)."""
    return _format_with_units(value_ohms, [
        (1e6, 'MΩ'), (1e3, 'kΩ'), (1, 'Ω')
    ])
