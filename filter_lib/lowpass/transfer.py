"""Transfer function calculations for lowpass filter frequency response.

This module is a thin wrapper around the shared base transfer functions.
"""

from ..shared.cli_aliases import DEFAULT_RIPPLE_DB
from ..shared.lp_hp_base_transfer_functions import (
    lowpass_bessel_response,
    lowpass_butterworth_response,
    lowpass_chebyshev_response,
)
from ..shared.transfer_functions import generate_frequency_points  # noqa: F401
from ..shared.transfer_response_dispatch import ladder_frequency_response


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
    filter_type: str,
    freqs: list[float],
    cutoff_hz: float,
    order: int,
    ripple_db: float = DEFAULT_RIPPLE_DB,
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
    return ladder_frequency_response(
        (butterworth_response, chebyshev_response, bessel_response),
        filter_type,
        freqs,
        cutoff_hz,
        order,
        ripple_db,
    )
