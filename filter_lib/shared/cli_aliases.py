"""Shared CLI aliases and constants for filter commands.

FILTER_TYPE_ALIASES is the single source of truth for alias
canonicalization — dispatch code must resolve through it (see
resolve_filter_type) rather than re-implementing the mapping.
"""

# Filter type aliases: short -> canonical. Adding an alias also requires
# listing it in cli_helpers.FILTER_TYPE_CHOICES so argparse accepts it.
FILTER_TYPE_ALIASES: dict[str, str] = {
    "bw": "butterworth",
    "b": "butterworth",
    "ch": "chebyshev",
    "c": "chebyshev",
    "bs": "bessel",
}

# Coupling topology aliases. Only Top-C exists: capacitive bottom (shunt)
# coupling cannot realize the designed response (simulation-verified), so it
# was removed.
COUPLING_ALIASES: dict[str, str] = {
    "t": "top",
}

# Default parameter values
DEFAULT_IMPEDANCE: str = "50"
DEFAULT_RIPPLE_DB: float = 0.5
DEFAULT_COMPONENTS: int = 3
# 3 (not 2) so the default works with Chebyshev, which needs an odd count
DEFAULT_RESONATORS: int = 3
DEFAULT_Q_SAFETY: float = 2.0
DEFAULT_ESERIES: str = "E24"

# Filter type explanations
FILTER_EXPLANATIONS: dict[str, str] = {
    "butterworth": """Butterworth Filter (Maximally Flat Magnitude)
- Flattest possible passband response
- No ripple in passband
- Moderate rolloff steepness
- Good general-purpose choice""",
    "chebyshev": """Chebyshev Filter (Equiripple)
- Steeper rolloff than Butterworth for same order
- Ripple in passband (specified in dB)
- Better stopband attenuation
- Good for RF applications requiring sharp cutoff""",
    "bessel": """Bessel Filter (Maximally Flat Delay)
- Best pulse response (minimal overshoot)
- Linear phase response
- Gentlest rolloff
- Good for data/pulse applications""",
}

# Highpass-specific explanations
FILTER_EXPLANATIONS_HIGHPASS: dict[str, str] = {
    "butterworth": """Butterworth High-Pass Filter (Maximally Flat Magnitude)
- Flattest possible passband response
- No ripple in passband
- Moderate rolloff steepness
- Supports Pi and T topologies""",
    "chebyshev": """Chebyshev High-Pass Filter (Equiripple)
- Steeper rolloff than Butterworth for same order
- Ripple in passband (specified in dB)
- Better stopband attenuation
- Supports Pi and T topologies""",
    "bessel": """Bessel High-Pass Filter
- Smooth monotonic rolloff
- Note: the LP prototype's flat group delay is NOT preserved
  through the high-pass transformation
- Gentlest rolloff
- Supports Pi and T topologies""",
}

# Bandpass-specific explanations
FILTER_EXPLANATIONS_BANDPASS: dict[str, str] = {
    "butterworth": """Butterworth Bandpass Filter (Maximally Flat)
- Flattest possible passband response
- No ripple in passband
- Good for general RF applications""",
    "chebyshev": """Chebyshev Bandpass Filter (Equiripple)
- Steeper skirts than Butterworth
- Ripple in passband (specified in dB)
- Requires odd number of resonators
- Better selectivity for same order""",
    "bessel": """Bessel Bandpass Filter
- Smooth, gentle magnitude response
- The low-pass prototype's flat group delay is not preserved by the
  band-pass transformation
- Gentlest rolloff""",
}


def resolve_filter_type(alias: str) -> str:
    """Resolve filter type alias to canonical name.

    Unknown strings pass through unchanged — validity is enforced
    upstream by argparse choices, not here.
    """
    if not isinstance(alias, str):
        raise ValueError("filter type alias must be a string")
    return FILTER_TYPE_ALIASES.get(alias, alias)


def resolve_coupling(alias: str) -> str:
    """Resolve coupling alias to canonical name (unknown values pass through)."""
    if not isinstance(alias, str):
        raise ValueError("coupling alias must be a string")
    return COUPLING_ALIASES.get(alias, alias)
