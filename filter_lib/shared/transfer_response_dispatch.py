"""Factory for creating single-frequency response functions.

Eliminates duplicated closure pattern across LP/HP display and wizard modules.
"""

from collections.abc import Callable

from .transfer_functions import magnitude_to_db


def make_lp_response_db(
    filter_type: str, cutoff_hz: float, order: int, ripple_db: float = 0.5
) -> Callable[[float], float]:
    """Return f(freq_hz) -> dB for a lowpass filter."""
    from ..lowpass.transfer import bessel_response, butterworth_response, chebyshev_response

    ft = filter_type.lower()

    def response_db(f: float) -> float:
        if ft in ("butterworth", "bw"):
            return magnitude_to_db(butterworth_response(f, cutoff_hz, order))
        elif ft in ("chebyshev", "ch"):
            return magnitude_to_db(chebyshev_response(f, cutoff_hz, order, ripple_db))
        else:
            return magnitude_to_db(bessel_response(f, cutoff_hz, order))

    return response_db


def make_hp_response_db(
    filter_type: str, cutoff_hz: float, order: int, ripple_db: float = 0.5
) -> Callable[[float], float]:
    """Return f(freq_hz) -> dB for a highpass filter."""
    from ..highpass.transfer import bessel_response, butterworth_response, chebyshev_response

    ft = filter_type.lower()

    def response_db(f: float) -> float:
        if ft in ("butterworth", "bw"):
            return magnitude_to_db(butterworth_response(f, cutoff_hz, order))
        elif ft in ("chebyshev", "ch"):
            return magnitude_to_db(chebyshev_response(f, cutoff_hz, order, ripple_db))
        else:
            return magnitude_to_db(bessel_response(f, cutoff_hz, order))

    return response_db


def make_bp_response_db(
    f0: float, bw: float, n_resonators: int, filter_type: str, ripple_db: float = 0.5
) -> Callable[[float], float]:
    """Return f(freq_hz) -> dB for a bandpass filter."""
    from ..bandpass.transfer import magnitude_db

    def response_db(f: float) -> float:
        return magnitude_db(f, f0, bw, n_resonators, filter_type, ripple_db)

    return response_db
