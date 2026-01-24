"""Shared CLI aliases and constants for filter commands."""

# Filter type aliases: short -> canonical
FILTER_TYPE_ALIASES: dict[str, str] = {
    'bw': 'butterworth',
    'b': 'butterworth',
    'ch': 'chebyshev',
    'c': 'chebyshev',
    'bs': 'bessel',
}

# Coupling topology aliases
COUPLING_ALIASES: dict[str, str] = {
    't': 'top',
    's': 'shunt',
}

# Default parameter values
DEFAULT_IMPEDANCE: str = '50'
DEFAULT_RIPPLE_DB: float = 0.5
DEFAULT_COMPONENTS: int = 3
DEFAULT_RESONATORS: int = 2
DEFAULT_Q_SAFETY: float = 2.0
DEFAULT_ESERIES: str = 'E24'

# Filter type explanations
FILTER_EXPLANATIONS: dict[str, str] = {
    'butterworth': """Butterworth Filter (Maximally Flat Magnitude)
- Flattest possible passband response
- No ripple in passband
- Moderate rolloff steepness
- Good for audio applications""",
    'chebyshev': """Chebyshev Filter (Equiripple)
- Steeper rolloff than Butterworth for same order
- Ripple in passband (specified in dB)
- Better stopband attenuation
- Good for RF applications requiring sharp cutoff""",
    'bessel': """Bessel Filter (Maximally Flat Delay)
- Best pulse response (minimal overshoot)
- Linear phase response
- Gentlest rolloff
- Good for data/pulse applications""",
}

# Highpass-specific explanations (T-topology note)
FILTER_EXPLANATIONS_HIGHPASS: dict[str, str] = {
    'butterworth': """Butterworth High-Pass Filter (Maximally Flat Magnitude)
- Flattest possible passband response
- No ripple in passband
- Moderate rolloff steepness
- T-topology: series inductors, shunt capacitors""",
    'chebyshev': """Chebyshev High-Pass Filter (Equiripple)
- Steeper rolloff than Butterworth for same order
- Ripple in passband (specified in dB)
- Better stopband attenuation
- T-topology: series inductors, shunt capacitors""",
    'bessel': """Bessel High-Pass Filter (Maximally Flat Delay)
- Best pulse response (minimal overshoot)
- Linear phase response
- Gentlest rolloff
- T-topology: series inductors, shunt capacitors""",
}

# Bandpass-specific explanations
FILTER_EXPLANATIONS_BANDPASS: dict[str, str] = {
    'butterworth': """Butterworth Bandpass Filter (Maximally Flat)
- Flattest possible passband response
- No ripple in passband
- Good for general RF applications""",
    'chebyshev': """Chebyshev Bandpass Filter (Equiripple)
- Steeper skirts than Butterworth
- Ripple in passband (specified in dB)
- Requires odd number of resonators
- Better selectivity for same order""",
    'bessel': """Bessel Bandpass Filter (Maximally Flat Delay)
- Best pulse response
- Linear phase in passband
- Gentlest rolloff""",
}


def resolve_filter_type(alias: str) -> str:
    """Resolve filter type alias to canonical name."""
    return FILTER_TYPE_ALIASES.get(alias, alias)


def resolve_coupling(alias: str) -> str:
    """Resolve coupling alias to canonical name."""
    return COUPLING_ALIASES.get(alias, alias)
