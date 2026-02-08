"""Transfer function calculations for highpass filter frequency response.

HPF response is derived from LPF response using frequency transformation:
H_HP(f) = H_LP(fc^2/f)

This module is a thin wrapper around the shared base transfer functions.
"""

from ..shared.lp_hp_base_transfer_functions import (
    highpass_bessel_response,
    highpass_butterworth_response,
    highpass_chebyshev_response,
)
from ..shared.transfer_functions import (
    export_response_csv,  # noqa: F401
    export_response_json,  # noqa: F401
    generate_frequency_points,  # noqa: F401
    magnitude_to_db,
)


def butterworth_response(freq_hz: float, cutoff_hz: float, order: int) -> float:
    """Calculate Butterworth HPF magnitude response (0 to 1).

    HPF response: H(f) = 1 / sqrt(1 + (fc/f)^(2n))
    """
    return highpass_butterworth_response(freq_hz, cutoff_hz, order)


def chebyshev_response(freq_hz: float, cutoff_hz: float, order: int, ripple_db: float) -> float:
    """Calculate Chebyshev Type I HPF magnitude response.

    HPF uses inverted frequency ratio: fc/f instead of f/fc
    """
    return highpass_chebyshev_response(freq_hz, cutoff_hz, order, ripple_db)


def bessel_response(freq_hz: float, cutoff_hz: float, order: int) -> float:
    """Calculate Bessel HPF magnitude response.

    HPF uses inverted frequency transformation: w_hp = fc/f * scale
    """
    return highpass_bessel_response(freq_hz, cutoff_hz, order)


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
