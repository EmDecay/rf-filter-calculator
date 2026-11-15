"""Shared base calculations for lowpass and highpass filters.

This module contains common calculation logic using strategy pattern to handle
LP vs HP specific formulas and component ordering.

Key differences between LP and HP:
- LP: capacitors in shunt, inductors in series (Pi: C-L-C, T: L-C-L)
- HP: inverted - capacitors in series, inductors in shunt
- Component formulas are duals (LP: C=g/(Z*omega), L=g*Z/omega;
  HP: C=1/(g*omega*Z), L=Z/(omega*g))
"""

import math
from collections.abc import Callable, Sequence
from typing import NamedTuple

from .chebyshev_g_calculator import calculate_chebyshev_g_values
from .cli_aliases import (
    COMPONENT_COUNT_MESSAGE,
    MAX_RIPPLE_DB,
    RIPPLE_RANGE_MESSAGE,
    chebyshev_odd_count_message,
)
from .constants import BESSEL_G_VALUES
from .numeric import is_finite_real, require_count, require_positive_finite


def _validate_topology(topology: str) -> None:
    """Validate topology parameter."""
    if topology not in ("pi", "t"):
        raise ValueError(f"Topology must be 'pi' or 't', got '{topology}'")


def _validate_lp_hp_inputs(cutoff_hz: float, impedance: float, num_components: int) -> None:
    """Validate shared LP/HP numeric inputs. Rejects NaN and inf explicitly."""
    require_positive_finite(cutoff_hz, "Cutoff frequency")
    require_positive_finite(impedance, "Impedance")
    require_count(num_components, COMPONENT_COUNT_MESSAGE)


def _component_kind(position_1based: int, topology: str, is_lowpass: bool) -> str:
    """Return component kind for a physical ladder position."""
    # LP Pi and HP T both start with a capacitor at odd positions; LP T and HP Pi
    # both start with an inductor. Even positions alternate to the opposite kind.
    starts_with_cap = (topology == "pi") if is_lowpass else (topology == "t")
    is_odd_position = position_1based % 2 == 1
    return "cap" if starts_with_cap == is_odd_position else "ind"


def _evaluate_component_formula(
    formula: Callable[[float, float, float], float],
    g_value: float,
    impedance: float,
    cutoff_hz: float,
) -> float:
    """Evaluate one scaled prototype value without leaking float overflow."""
    try:
        value = formula(g_value, impedance, cutoff_hz)
    except (OverflowError, ZeroDivisionError) as error:
        raise ValueError("Inputs do not produce finite positive component values") from error
    if not math.isfinite(value) or value <= 0:
        raise ValueError("Inputs do not produce finite positive component values")
    return value


class _Ladder(NamedTuple):
    """LP or HP strategy: the two component formulas and the placement rule."""

    cap_formula: Callable[[float, float, float], float]
    ind_formula: Callable[[float, float, float], float]
    is_lowpass: bool


def _place_components(
    g_values: Sequence[float],
    impedance: float,
    cutoff_hz: float,
    topology: str,
    ladder: _Ladder,
) -> tuple[list[float], list[float]]:
    """Scale prototype values ``g_1..g_n`` into (capacitors, inductors) in ladder order."""
    capacitors = []
    inductors = []
    for position, g in enumerate(g_values, start=1):
        if _component_kind(position, topology, ladder.is_lowpass) == "cap":
            capacitors.append(
                _evaluate_component_formula(ladder.cap_formula, g, impedance, cutoff_hz)
            )
        else:
            inductors.append(
                _evaluate_component_formula(ladder.ind_formula, g, impedance, cutoff_hz)
            )
    return capacitors, inductors


def _calculate_butterworth_base(
    cutoff_hz: float,
    impedance: float,
    num_components: int,
    topology: str,
    ladder: _Ladder,
) -> tuple[list[float], list[float], int]:
    """Base Butterworth calculation; returns (capacitors, inductors, order).

    The HP public wrappers reorder the lists for display; this base function
    never swaps them.
    """
    _validate_topology(topology)
    _validate_lp_hp_inputs(cutoff_hz, impedance, num_components)
    n = num_components
    # Closed-form Butterworth prototype element for equal 1-ohm
    # terminations, -3 dB at omega = 1: g_k = 2·sin((2k-1)·pi / 2n).
    # (Matthaei, Young, Jones Sec. 4.05) — no lookup table needed.
    g_values = [2 * math.sin((2 * i - 1) * math.pi / (2 * n)) for i in range(1, n + 1)]
    return (*_place_components(g_values, impedance, cutoff_hz, topology, ladder), n)


def _calculate_chebyshev_base(
    cutoff_hz: float,
    impedance: float,
    ripple_db: float,
    num_components: int,
    topology: str,
    ladder: _Ladder,
) -> tuple[list[float], list[float], int]:
    """Base Chebyshev calculation; returns (capacitors, inductors, order).

    ``cutoff_hz`` is the equal-ripple band edge (the last frequency at
    -ripple_db), not the -3 dB point — the same convention the LP/HP
    transfer functions use, so component tables and plotted responses agree.
    """
    _validate_topology(topology)
    _validate_lp_hp_inputs(cutoff_hz, impedance, num_components)
    if not is_finite_real(ripple_db) or ripple_db <= 0 or ripple_db > MAX_RIPPLE_DB:
        raise ValueError(RIPPLE_RANGE_MESSAGE)
    n = num_components
    # Even-order Chebyshev designs cannot meet equal source/load terminations
    # (ripple does not return to 0 dB at DC for LP / at infinity for HP),
    # which this library assumes. Match bandpass behavior by restricting to odd.
    if n % 2 == 0:
        raise ValueError(chebyshev_odd_count_message("order"))
    # g[0] is index padding; g[1..n] are the ladder elements.
    g = calculate_chebyshev_g_values(n, ripple_db)
    return (*_place_components(g[1 : n + 1], impedance, cutoff_hz, topology, ladder), n)


def _calculate_bessel_base(
    cutoff_hz: float,
    impedance: float,
    num_components: int,
    topology: str,
    ladder: _Ladder,
) -> tuple[list[float], list[float], int]:
    """Base Bessel calculation; returns (capacitors, inductors, order)."""
    _validate_topology(topology)
    _validate_lp_hp_inputs(cutoff_hz, impedance, num_components)
    n = num_components
    return (*_place_components(BESSEL_G_VALUES[n], impedance, cutoff_hz, topology, ladder), n)


# Component formulas, evaluated in log space so extreme inputs whose factor scales
# cancel still give a representable value.
def _lp_cap_formula(g: float, impedance: float, cutoff_hz: float) -> float:
    """Lowpass capacitor formula: C = g / (Z * ω)"""
    return math.exp(math.log(g) - math.log(impedance) - math.log(2 * math.pi) - math.log(cutoff_hz))


def _lp_ind_formula(g: float, impedance: float, cutoff_hz: float) -> float:
    """Lowpass inductor formula: L = g * Z / ω"""
    return math.exp(math.log(g) + math.log(impedance) - math.log(2 * math.pi) - math.log(cutoff_hz))


def _hp_cap_formula(g: float, impedance: float, cutoff_hz: float) -> float:
    """Highpass capacitor formula: C = 1 / (g * ω * Z)"""
    return math.exp(
        -math.log(g) - math.log(2 * math.pi) - math.log(cutoff_hz) - math.log(impedance)
    )


def _hp_ind_formula(g: float, impedance: float, cutoff_hz: float) -> float:
    """Highpass inductor formula: L = Z / (ω * g)"""
    return math.exp(math.log(impedance) - math.log(2 * math.pi) - math.log(cutoff_hz) - math.log(g))


_LOWPASS = _Ladder(_lp_cap_formula, _lp_ind_formula, is_lowpass=True)
_HIGHPASS = _Ladder(_hp_cap_formula, _hp_ind_formula, is_lowpass=False)


# Public API: Lowpass filter calculations
def calculate_lowpass_butterworth(
    cutoff_hz: float, impedance: float, num_components: int, topology: str
) -> tuple[list[float], list[float], int]:
    """Calculate Butterworth low-pass filter component values.

    Args:
        cutoff_hz: Cutoff frequency in Hz (-3 dB point)
        impedance: Characteristic impedance in Ohms
        num_components: Number of filter elements (2-9)
        topology: 'pi' or 't'

    Returns:
        Tuple of (capacitors in F, inductors in H, order)

    Raises:
        ValueError: If topology is invalid, cutoff/impedance is not positive
            and finite, or num_components is outside 2-9.
    """
    return _calculate_butterworth_base(
        cutoff_hz,
        impedance,
        num_components,
        topology,
        _LOWPASS,
    )


def calculate_lowpass_chebyshev(
    cutoff_hz: float, impedance: float, ripple_db: float, num_components: int, topology: str
) -> tuple[list[float], list[float], int]:
    """Calculate Chebyshev low-pass filter component values.

    Args:
        cutoff_hz: Cutoff frequency in Hz (equal-ripple band edge, not -3 dB)
        impedance: Characteristic impedance in Ohms
        ripple_db: Passband ripple in dB (> 0)
        num_components: Number of filter elements; must be odd (3, 5, 7, 9)
        topology: 'pi' or 't'

    Returns:
        Tuple of (capacitors in F, inductors in H, order)

    Raises:
        ValueError: If topology is invalid, cutoff/impedance/ripple is not
            positive and finite, or num_components is outside 2-9 or even.
    """
    return _calculate_chebyshev_base(
        cutoff_hz,
        impedance,
        ripple_db,
        num_components,
        topology,
        _LOWPASS,
    )


def calculate_lowpass_bessel(
    cutoff_hz: float, impedance: float, num_components: int, topology: str
) -> tuple[list[float], list[float], int]:
    """Calculate Bessel (Thomson) low-pass filter component values.

    Args:
        cutoff_hz: Cutoff frequency in Hz (-3 dB point)
        impedance: Characteristic impedance in Ohms
        num_components: Number of filter elements (2-9)
        topology: 'pi' or 't'

    Returns:
        Tuple of (capacitors in F, inductors in H, order)

    Raises:
        ValueError: If topology is invalid, cutoff/impedance is not positive
            and finite, or num_components is outside 2-9.
    """
    return _calculate_bessel_base(
        cutoff_hz,
        impedance,
        num_components,
        topology,
        _LOWPASS,
    )


# Public API: Highpass filter calculations
def calculate_highpass_butterworth(
    cutoff_hz: float, impedance: float, num_components: int, topology: str
) -> tuple[list[float], list[float], int]:
    """Calculate Butterworth high-pass filter component values.

    Args:
        cutoff_hz: Cutoff frequency in Hz (-3 dB point)
        impedance: Characteristic impedance in Ohms
        num_components: Number of filter elements (2-9)
        topology: 'pi' or 't'

    Returns:
        Tuple of (inductors in H, capacitors in F, order)

    Raises:
        ValueError: If topology is invalid, cutoff/impedance is not positive
            and finite, or num_components is outside 2-9.
    """
    capacitors, inductors, n = _calculate_butterworth_base(
        cutoff_hz,
        impedance,
        num_components,
        topology,
        _HIGHPASS,
    )
    return inductors, capacitors, n  # HP returns inductors first


def calculate_highpass_chebyshev(
    cutoff_hz: float, impedance: float, ripple_db: float, num_components: int, topology: str
) -> tuple[list[float], list[float], int]:
    """Calculate Chebyshev high-pass filter component values.

    Args:
        cutoff_hz: Cutoff frequency in Hz (equal-ripple band edge, not -3 dB)
        impedance: Characteristic impedance in Ohms
        ripple_db: Passband ripple in dB (> 0)
        num_components: Number of filter elements; must be odd (3, 5, 7, 9)
        topology: 'pi' or 't'

    Returns:
        Tuple of (inductors in H, capacitors in F, order)

    Raises:
        ValueError: If topology is invalid, cutoff/impedance/ripple is not
            positive and finite, or num_components is outside 2-9 or even.
    """
    capacitors, inductors, n = _calculate_chebyshev_base(
        cutoff_hz,
        impedance,
        ripple_db,
        num_components,
        topology,
        _HIGHPASS,
    )
    return inductors, capacitors, n  # HP returns inductors first


def calculate_highpass_bessel(
    cutoff_hz: float, impedance: float, num_components: int, topology: str
) -> tuple[list[float], list[float], int]:
    """Calculate Bessel (Thomson) high-pass filter component values.

    Args:
        cutoff_hz: Cutoff frequency in Hz (-3 dB point)
        impedance: Characteristic impedance in Ohms
        num_components: Number of filter elements (2-9)
        topology: 'pi' or 't'

    Returns:
        Tuple of (inductors in H, capacitors in F, order)

    Raises:
        ValueError: If topology is invalid, cutoff/impedance is not positive
            and finite, or num_components is outside 2-9.
    """
    capacitors, inductors, n = _calculate_bessel_base(
        cutoff_hz,
        impedance,
        num_components,
        topology,
        _HIGHPASS,
    )
    return inductors, capacitors, n  # HP returns inductors first
