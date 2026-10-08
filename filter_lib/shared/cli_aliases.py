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

# --spice-realization plain-language aliases -> canonical choice. The canonical
# values stay the spelling used in help defaults, validation messages, and SPICE
# comments; the CLI resolves an alias at parse time so nothing downstream sees it.
SPICE_REALIZATION_ALIASES: dict[str, str] = {
    "calculated": "exact",
    "chosen-parts": "nominal-build",
}
SPICE_REALIZATION_CHOICES: list[str] = ["exact", "nominal-build", *SPICE_REALIZATION_ALIASES]

# Default parameter values
DEFAULT_IMPEDANCE: str = "50"
DEFAULT_RIPPLE_DB: float = 0.5
DEFAULT_COMPONENTS: int = 3
# 3 (not 2) so the default works with Chebyshev, which needs an odd count
DEFAULT_RESONATORS: int = 3
DEFAULT_Q_SAFETY: float = 2.0
DEFAULT_ESERIES: str = "E24"

# One message per input rule, shared by the CLI, the LP/HP calculators, and
# DesignRequest, so every surface rejects the same input with the same text.
MAX_RIPPLE_DB: float = 3.0
RIPPLE_RANGE_MESSAGE = f"Ripple must be greater than 0 and at most {MAX_RIPPLE_DB} dB"
COMPONENT_COUNT_MESSAGE = "Number of components must be from 2 to 9"


def chebyshev_odd_count_message(noun: str) -> str:
    """Odd-count rule for Chebyshev ladders (``components``) and bandpass (``resonators``)."""
    return (
        f"Chebyshev needs an odd number of {noun} (3, 5, 7, or 9) for equal source and load "
        "impedance"
    )


# Facts shared by the LP and HP Chebyshev explanations. Both are enforced in
# code: the cutoff is placed at the ripple-band edge, and lp_hp_base_calculations
# rejects even orders because the design assumes equal source/load impedance.
_CHEBYSHEV_LADDER_FACTS = """- Cutoff is the ripple-band edge; the -3 dB point lies beyond it
- Odd order only (3, 5, 7, 9) for equal source and load impedance"""

# Lowpass explanations (filter-calc lp <type> --explain)
FILTER_EXPLANATIONS: dict[str, str] = {
    "butterworth": """Butterworth Low-Pass Filter (Maximally Flat Magnitude)
- Flattest possible passband response
- No ripple in passband
- Moderate rolloff steepness
- Good general-purpose choice
- Supports Pi and T topologies""",
    "chebyshev": f"""Chebyshev Low-Pass Filter (Equiripple)
- Steeper rolloff than Butterworth for same order
- Ripple in passband (specified in dB)
- Better stopband attenuation
{_CHEBYSHEV_LADDER_FACTS}
- Good for RF applications requiring sharp cutoff
- Supports Pi and T topologies""",
    "bessel": """Bessel Low-Pass Filter (Maximally Flat Delay)
- Best pulse response (minimal overshoot)
- Nearly linear phase in the passband (maximally flat group delay)
- Gentlest rolloff
- Good for data/pulse applications
- Supports Pi and T topologies""",
}

# Highpass explanations (filter-calc hp <type> --explain)
FILTER_EXPLANATIONS_HIGHPASS: dict[str, str] = {
    "butterworth": """Butterworth High-Pass Filter (Maximally Flat Magnitude)
- Flattest possible passband response
- No ripple in passband
- Moderate rolloff steepness
- Good general-purpose choice
- Supports Pi and T topologies""",
    "chebyshev": f"""Chebyshev High-Pass Filter (Equiripple)
- Steeper rolloff than Butterworth for same order
- Ripple in passband (specified in dB)
- Better stopband attenuation
{_CHEBYSHEV_LADDER_FACTS}
- Good for RF applications requiring sharp cutoff
- Supports Pi and T topologies""",
    "bessel": """Bessel High-Pass Filter
- Smooth monotonic rolloff
- Note: the LP prototype's flat group delay is NOT preserved
  through the high-pass transformation
- Gentlest rolloff
- Supports Pi and T topologies""",
}

# Bandpass explanations (filter-calc bp <type> --explain)
FILTER_EXPLANATIONS_BANDPASS: dict[str, str] = {
    "butterworth": """Butterworth Band-Pass Filter (Maximally Flat)
- Flattest possible passband response
- No ripple in passband
- Good for general RF applications""",
    "chebyshev": """Chebyshev Band-Pass Filter (Equiripple)
- Steeper skirts than Butterworth for the same number of resonators
- Ripple in passband (specified in dB)
- Requires odd number of resonators""",
    "bessel": """Bessel Band-Pass Filter
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


def resolve_spice_realization(alias: str) -> str:
    """Resolve a ``--spice-realization`` alias to its canonical value (others pass through)."""
    if not isinstance(alias, str):
        raise ValueError("SPICE realization alias must be a string")
    return SPICE_REALIZATION_ALIASES.get(alias, alias)
