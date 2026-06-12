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
)


def butterworth_response(freq_hz: float, cutoff_hz: float, order: int) -> float:
    """Calculate Butterworth filter magnitude response (0 to 1)."""
    return lowpass_butterworth_response(freq_hz, cutoff_hz, order)


def chebyshev_response(freq_hz: float, cutoff_hz: float, order: int, ripple_db: float) -> float:
    """Calculate Chebyshev Type I filter magnitude response."""
    return lowpass_chebyshev_response(freq_hz, cutoff_hz, order, ripple_db)


def bessel_response(freq_hz: float, cutoff_hz: float, order: int) -> float:
    """Calculate Bessel filter magnitude response."""
    return lowpass_bessel_response(freq_hz, cutoff_hz, order)


def frequency_response(
    filter_type: str, freqs: list[float], cutoff_hz: float, order: int, ripple_db: float = 0.5
) -> list[float]:
    """Calculate frequency response in dB for a list of frequencies."""
    filter_type = filter_type.lower()

    def response_fn(f: float) -> float:
        if filter_type in ("butterworth", "bw"):
            return butterworth_response(f, cutoff_hz, order)
        elif filter_type in ("chebyshev", "ch"):
            return chebyshev_response(f, cutoff_hz, order, ripple_db)
        elif filter_type in ("bessel", "bs"):
            return bessel_response(f, cutoff_hz, order)
        else:
            raise ValueError(f"Unknown filter type: {filter_type}")

    return [magnitude_to_db(response_fn(f)) for f in freqs]
