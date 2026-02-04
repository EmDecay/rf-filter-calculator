"""Transfer function calculations for low-pass filter frequency response.

This module is a thin wrapper around the shared base transfer functions.
"""
from ..shared.lp_hp_base_transfer_functions import (
    lowpass_butterworth_response,
    lowpass_chebyshev_response,
    lowpass_bessel_response,
)
from ..shared.transfer_functions import (
    magnitude_to_db,
    generate_frequency_points,
    export_response_json,
    export_response_csv,
)


def butterworth_response(freq_hz: float, cutoff_hz: float, order: int) -> float:
    """Calculate Butterworth filter magnitude response (0 to 1)."""
    return lowpass_butterworth_response(freq_hz, cutoff_hz, order)


def chebyshev_response(freq_hz: float, cutoff_hz: float, order: int,
                       ripple_db: float) -> float:
    """Calculate Chebyshev Type I filter magnitude response."""
    return lowpass_chebyshev_response(freq_hz, cutoff_hz, order, ripple_db)


def bessel_response(freq_hz: float, cutoff_hz: float, order: int) -> float:
    """Calculate Bessel filter magnitude response."""
    return lowpass_bessel_response(freq_hz, cutoff_hz, order)


def frequency_response(filter_type: str, freqs: list[float], cutoff_hz: float,
                       order: int, ripple_db: float = 0.5) -> list[float]:
    """Calculate frequency response in dB for a list of frequencies."""
    filter_type = filter_type.lower()

    if filter_type in ('butterworth', 'bw'):
        response_fn = lambda f: butterworth_response(f, cutoff_hz, order)
    elif filter_type in ('chebyshev', 'ch'):
        response_fn = lambda f: chebyshev_response(f, cutoff_hz, order, ripple_db)
    elif filter_type in ('bessel', 'bs'):
        response_fn = lambda f: bessel_response(f, cutoff_hz, order)
    else:
        raise ValueError(f"Unknown filter type: {filter_type}")

    return [magnitude_to_db(response_fn(f)) for f in freqs]
