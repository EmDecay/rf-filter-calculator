"""Transfer function calculations for lowpass filter frequency response.

This module is a thin wrapper around the shared base transfer functions.
"""

from ..shared.lp_hp_base_transfer_functions import (
    lowpass_bessel_response,
    lowpass_butterworth_response,
    lowpass_chebyshev_response,
)
from ..shared.transfer_functions import (
    generate_frequency_points,  # noqa: F401
    magnitude_to_db,
    validate_frequency_sequence,
)
from ..shared.transfer_response_dispatch import (
    _CANONICAL_LP_HP_TYPES,
    _canonicalize_filter_type,
)


def butterworth_response(freq_hz: float, cutoff_hz: float, order: int) -> float:
    """Calculate Butterworth filter magnitude response (linear, 0 to 1)."""
    return lowpass_butterworth_response(freq_hz, cutoff_hz, order)


def chebyshev_response(freq_hz: float, cutoff_hz: float, order: int, ripple_db: float) -> float:
    """Calculate Chebyshev Type I magnitude response (linear, 0 to 1).

    ``cutoff_hz`` is the ripple-band edge, matching the calculation module's
    component-value convention (not the -3 dB point).
    """
    return lowpass_chebyshev_response(freq_hz, cutoff_hz, order, ripple_db)


def bessel_response(freq_hz: float, cutoff_hz: float, order: int) -> float:
    """Calculate Bessel filter magnitude response (linear, 0 to 1)."""
    return lowpass_bessel_response(freq_hz, cutoff_hz, order)


def frequency_response(
    filter_type: str, freqs: list[float], cutoff_hz: float, order: int, ripple_db: float = 0.5
) -> list[float]:
    """Calculate frequency response in dB for a list of frequencies.

    Args:
        filter_type: 'butterworth', 'chebyshev', 'bessel', or any
            ``FILTER_TYPE_ALIASES`` key (bw/b, ch/c, bs), case-insensitive
        freqs: Frequencies to evaluate, in Hz
        cutoff_hz: Cutoff frequency in Hz (ripple-band edge for Chebyshev)
        order: Filter order
        ripple_db: Chebyshev passband ripple in dB (ignored for other types)

    Returns:
        Magnitudes in dB, one per input frequency, floored at -120 dB.

    Raises:
        ValueError: If filter_type is not one of the accepted names/aliases.
    """
    if not isinstance(filter_type, str):
        raise ValueError("filter_type must be a string")
    freqs = validate_frequency_sequence(freqs)
    filter_type = _canonicalize_filter_type(filter_type, _CANONICAL_LP_HP_TYPES)
    if filter_type == "butterworth":

        def response_fn(f: float) -> float:
            return butterworth_response(f, cutoff_hz, order)

    elif filter_type == "chebyshev":

        def response_fn(f: float) -> float:
            return chebyshev_response(f, cutoff_hz, order, ripple_db)

    else:

        def response_fn(f: float) -> float:
            return bessel_response(f, cutoff_hz, order)

    response_fn(1.0)
    return [magnitude_to_db(response_fn(f)) for f in freqs]
