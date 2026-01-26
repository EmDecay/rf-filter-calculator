"""Filter result dataclass for consistent return types.

Provides a standardized way to return filter calculation results,
eliminating confusion from different tuple ordering between modules.
"""
from dataclasses import dataclass


@dataclass
class FilterResult:
    """Standardized filter calculation result.

    Using a dataclass instead of tuples prevents ordering confusion
    between lowpass (caps, inds) and highpass (inds, caps) returns.

    Attributes:
        filter_type: Response type ('butterworth', 'chebyshev', 'bessel')
        freq_hz: Cutoff/center frequency in Hz
        impedance: System impedance in Ohms
        order: Filter order (number of components)
        capacitors: List of capacitor values in Farads
        inductors: List of inductor values in Henries
        ripple: Chebyshev passband ripple in dB (None for other types)
    """
    filter_type: str
    freq_hz: float
    impedance: float
    order: int
    capacitors: list[float]
    inductors: list[float]
    topology: str | None = None
    ripple: float | None = None

    def to_dict(self) -> dict:
        """Convert to dictionary for display functions.

        Returns:
            Dict compatible with existing display_results() functions.
        """
        d = {
            'filter_type': self.filter_type,
            'freq_hz': self.freq_hz,
            'impedance': self.impedance,
            'order': self.order,
            'capacitors': self.capacitors,
            'inductors': self.inductors,
            'ripple': self.ripple,
        }
        if self.topology is not None:
            d['topology'] = self.topology
        return d
