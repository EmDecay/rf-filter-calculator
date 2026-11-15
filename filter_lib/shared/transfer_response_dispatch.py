"""Factory for creating single-frequency response functions.

Eliminates the duplicated closure pattern across LP/HP display and wizard
modules. Every factory returns ``f(freq_hz) -> dB``, so plotting and
threshold code can stay agnostic of filter category.

The lowpass/highpass transfer modules are imported inside each
factory, not at module level: those packages' display modules import this
module at load time, so top-level imports here would be circular.
"""

import math
from collections.abc import Callable

from .cli_aliases import DEFAULT_RIPPLE_DB, FILTER_TYPE_ALIASES
from .numeric import require_positive_finite
from .transfer_functions import magnitude_to_db, validate_frequency_sequence

_CANONICAL_LP_HP_TYPES = ("butterworth", "chebyshev", "bessel")


def _canonicalize_filter_type(filter_type: str, valid: tuple[str, ...]) -> str:
    """Normalize an LP/HP filter type string to its canonical form.

    Accepts canonical names and every CLI alias (bw/b → butterworth,
    ch/c → chebyshev, bs → bessel). Raises ValueError for None or unknown.
    """
    if filter_type is None:
        raise ValueError("Filter type must be provided, got None")
    if not isinstance(filter_type, str):
        raise ValueError("filter_type must be a string")
    ft = filter_type.lower()
    canonical = FILTER_TYPE_ALIASES.get(ft, ft)
    if canonical not in valid:
        raise ValueError(
            f"Unknown filter type '{filter_type}'; expected one of "
            f"{', '.join(valid)} (or an alias: bw, ch, bs, b, c)"
        )
    return canonical


LinearResponse = Callable[[float], float]


def _select_response(
    filter_type: str,
    responses: tuple[Callable[..., float], Callable[..., float], Callable[..., float]],
    cutoff_hz: float,
    order: int,
    ripple_db: float,
) -> LinearResponse:
    """Return f(freq_hz) -> linear magnitude for one canonical LP or HP type.

    ``responses`` is that category's (butterworth, chebyshev, bessel) functions.
    """
    butterworth, chebyshev, bessel = responses
    if filter_type == "butterworth":
        return lambda f: butterworth(f, cutoff_hz, order)
    if filter_type == "chebyshev":
        return lambda f: chebyshev(f, cutoff_hz, order, ripple_db)
    return lambda f: bessel(f, cutoff_hz, order)


def ladder_frequency_response(
    responses: tuple[Callable[..., float], Callable[..., float], Callable[..., float]],
    filter_type: str,
    freqs: list[float],
    cutoff_hz: float,
    order: int,
    ripple_db: float,
) -> list[float]:
    """Shared body of the lowpass and highpass ``frequency_response`` functions."""
    if not isinstance(filter_type, str):
        raise ValueError("filter_type must be a string")
    freqs = validate_frequency_sequence(freqs)
    filter_type = _canonicalize_filter_type(filter_type, _CANONICAL_LP_HP_TYPES)
    response_fn = _select_response(filter_type, responses, cutoff_hz, order, ripple_db)
    # Evaluate once before the sweep so bad cutoff/order inputs raise even for an
    # empty frequency list.
    response_fn(1.0)
    return [magnitude_to_db(response_fn(f)) for f in freqs]


def _make_response_db(
    responses: tuple[Callable[..., float], Callable[..., float], Callable[..., float]],
    filter_type: str,
    cutoff_hz: float,
    order: int,
    ripple_db: float,
) -> Callable[[float], float]:
    ft = _canonicalize_filter_type(filter_type, _CANONICAL_LP_HP_TYPES)
    response_fn = _select_response(ft, responses, cutoff_hz, order, ripple_db)
    return lambda f: magnitude_to_db(response_fn(f))


def make_lp_response_db(
    filter_type: str, cutoff_hz: float, order: int, ripple_db: float = DEFAULT_RIPPLE_DB
) -> Callable[[float], float]:
    """Return f(freq_hz) -> dB for an idealized lowpass prototype response.

    Args:
        filter_type: Canonical name or CLI alias (bw/ch/bs/b/c)
        cutoff_hz: Cutoff frequency in Hz (Chebyshev: ripple edge)
        order: Filter order
        ripple_db: Passband ripple in dB; only Chebyshev reads it

    Returns:
        Callable mapping frequency in Hz to response in dB (<= 0).

    Raises:
        ValueError: If filter_type is None or not a known type/alias.
    """
    from ..lowpass.transfer import bessel_response, butterworth_response, chebyshev_response

    responses = (butterworth_response, chebyshev_response, bessel_response)
    return _make_response_db(responses, filter_type, cutoff_hz, order, ripple_db)


def make_hp_response_db(
    filter_type: str, cutoff_hz: float, order: int, ripple_db: float = DEFAULT_RIPPLE_DB
) -> Callable[[float], float]:
    """Return f(freq_hz) -> dB for an idealized highpass prototype response.

    Args and return value are as for ``make_lp_response_db``.
    """
    from ..highpass.transfer import bessel_response, butterworth_response, chebyshev_response

    responses = (butterworth_response, chebyshev_response, bessel_response)
    return _make_response_db(responses, filter_type, cutoff_hz, order, ripple_db)


def make_bp_netlist_response_db(result: dict) -> Callable[[float], float]:
    """Return f(freq_hz) -> dB simulated from the synthesized bandpass netlist.

    The returned function evaluates |S21| of the exact prescribed circuit
    (tank/coupling/end capacitors from the result dict), so plots and
    threshold tables agree with a built filter rather than the idealized
    prototype in ``bandpass.ideal_response``.
    """
    from .netlist_builders import build_bandpass_top_c_netlist
    from .nodal_solver import make_transducer_gain_evaluator

    n_nodes, branches, in_node, out_node = build_bandpass_top_c_netlist(result)
    z0 = result.get("z0")
    require_positive_finite(z0, "result z0")
    # Validates the circuit once; each call is the same arithmetic as solve_s21 for
    # one frequency (|S21| = sqrt(transducer gain)), so values are bit-identical.
    transducer_gain = make_transducer_gain_evaluator(n_nodes, branches, z0, z0, in_node, out_node)
    return lambda f: magnitude_to_db(math.sqrt(transducer_gain(f)))
