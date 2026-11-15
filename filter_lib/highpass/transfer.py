"""Transfer function calculations for highpass filter frequency response.

HPF response is derived from LPF response using frequency transformation:
H_HP(f) = H_LP(fc^2/f)

This module is a thin wrapper around the shared base transfer functions.
"""

from ..shared.cli_aliases import DEFAULT_RIPPLE_DB
from ..shared.lp_hp_base_transfer_functions import (
    highpass_bessel_response,
    highpass_butterworth_response,
    highpass_chebyshev_response,
)
from ..shared.transfer_functions import generate_frequency_points  # noqa: F401
from ..shared.transfer_response_dispatch import ladder_frequency_response


def butterworth_response(freq_hz: float, cutoff_hz: float, order: int) -> float:
    """Calculate Butterworth HPF magnitude response (linear, 0 to 1).

    HPF response: H(f) = 1 / sqrt(1 + (fc/f)^(2n))
    """
    return highpass_butterworth_response(freq_hz, cutoff_hz, order)


def chebyshev_response(freq_hz: float, cutoff_hz: float, order: int, ripple_db: float) -> float:
    """Calculate Chebyshev Type I HPF magnitude response (linear, 0 to 1).

    HPF uses inverted frequency ratio: fc/f instead of f/fc. ``cutoff_hz`` is
    the ripple-band edge, matching the component-value convention (not -3 dB).
    """
    return highpass_chebyshev_response(freq_hz, cutoff_hz, order, ripple_db)


def bessel_response(freq_hz: float, cutoff_hz: float, order: int) -> float:
    """Calculate Bessel HPF magnitude response (linear, 0 to 1).

    HPF uses inverted frequency transformation: w_hp = fc/f * scale
    """
    return highpass_bessel_response(freq_hz, cutoff_hz, order)


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
