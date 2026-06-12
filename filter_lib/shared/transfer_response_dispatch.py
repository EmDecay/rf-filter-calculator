"""Factory for creating single-frequency response functions.

Eliminates duplicated closure pattern across LP/HP display and wizard modules.
"""

from collections.abc import Callable

from .cli_aliases import FILTER_TYPE_ALIASES
from .transfer_functions import magnitude_to_db

_CANONICAL_LP_HP_TYPES = ("butterworth", "chebyshev", "bessel")
_CANONICAL_BP_TYPES = ("butterworth", "chebyshev", "bessel")


def _canonicalize_filter_type(filter_type: str, valid: tuple[str, ...]) -> str:
    """Normalize an LP/HP/BP filter type string to its canonical form.

    Accepts canonical names and every CLI alias (bw/b → butterworth,
    ch/c → chebyshev, bs → bessel). Raises ValueError for None or unknown.
    """
    if filter_type is None:
        raise ValueError("Filter type must be provided, got None")
    ft = filter_type.lower()
    canonical = FILTER_TYPE_ALIASES.get(ft, ft)
    if canonical not in valid:
        raise ValueError(
            f"Unknown filter type '{filter_type}'; expected one of "
            f"{', '.join(valid)} (or an alias: bw, ch, bs, b, c)"
        )
    return canonical


def make_lp_response_db(
    filter_type: str, cutoff_hz: float, order: int, ripple_db: float = 0.5
) -> Callable[[float], float]:
    """Return f(freq_hz) -> dB for a lowpass filter."""
    from ..lowpass.transfer import bessel_response, butterworth_response, chebyshev_response

    ft = _canonicalize_filter_type(filter_type, _CANONICAL_LP_HP_TYPES)

    def response_db(f: float) -> float:
        if ft == "butterworth":
            return magnitude_to_db(butterworth_response(f, cutoff_hz, order))
        if ft == "chebyshev":
            return magnitude_to_db(chebyshev_response(f, cutoff_hz, order, ripple_db))
        return magnitude_to_db(bessel_response(f, cutoff_hz, order))

    return response_db


def make_hp_response_db(
    filter_type: str, cutoff_hz: float, order: int, ripple_db: float = 0.5
) -> Callable[[float], float]:
    """Return f(freq_hz) -> dB for a highpass filter."""
    from ..highpass.transfer import bessel_response, butterworth_response, chebyshev_response

    ft = _canonicalize_filter_type(filter_type, _CANONICAL_LP_HP_TYPES)

    def response_db(f: float) -> float:
        if ft == "butterworth":
            return magnitude_to_db(butterworth_response(f, cutoff_hz, order))
        if ft == "chebyshev":
            return magnitude_to_db(chebyshev_response(f, cutoff_hz, order, ripple_db))
        return magnitude_to_db(bessel_response(f, cutoff_hz, order))

    return response_db


def make_bp_response_db(
    f0: float, bw: float, n_resonators: int, filter_type: str, ripple_db: float = 0.5
) -> Callable[[float], float]:
    """Return f(freq_hz) -> dB for the idealized symmetric bandpass prototype."""
    from ..bandpass.transfer import magnitude_db

    ft = _canonicalize_filter_type(filter_type, _CANONICAL_BP_TYPES)

    def response_db(f: float) -> float:
        return magnitude_db(f, f0, bw, n_resonators, ft, ripple_db)

    return response_db


def make_bp_netlist_response_db(result: dict) -> Callable[[float], float]:
    """Return f(freq_hz) -> dB simulated from the synthesized bandpass netlist.

    The returned function evaluates |S21| of the exact prescribed circuit
    (tank/coupling/end capacitors from the result dict), so plots and
    threshold tables agree with a built filter rather than the idealized
    symmetric prototype.
    """
    from .netlist_builders import build_bandpass_top_c_netlist
    from .netlist_simulation import solve_s21

    n_nodes, branches, in_node, out_node = build_bandpass_top_c_netlist(result)
    z0 = result["z0"]

    def response_db(f: float) -> float:
        (mag,) = solve_s21(n_nodes, branches, z0, z0, in_node, out_node, [f])
        return magnitude_to_db(mag)

    return response_db
