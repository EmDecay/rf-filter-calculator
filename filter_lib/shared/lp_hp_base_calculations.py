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
from collections.abc import Callable

from .chebyshev_g_calculator import calculate_chebyshev_g_values
from .constants import BESSEL_G_VALUES
from .numeric import is_finite_real


def _validate_topology(topology: str) -> None:
    """Validate topology parameter."""
    if topology not in ("pi", "t"):
        raise ValueError(f"Topology must be 'pi' or 't', got '{topology}'")


def _validate_lp_hp_inputs(cutoff_hz: float, impedance: float, num_components: int) -> None:
    """Validate shared LP/HP numeric inputs. Rejects NaN and inf explicitly."""
    if not is_finite_real(cutoff_hz) or cutoff_hz <= 0:
        raise ValueError("Cutoff frequency must be positive and finite")
    if not is_finite_real(impedance) or impedance <= 0:
        raise ValueError("Impedance must be positive and finite")
    if (
        isinstance(num_components, bool)
        or not isinstance(num_components, int)
        or not 2 <= num_components <= 9
    ):
        raise ValueError("Number of components must be between 2 and 9")


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


def _calculate_butterworth_base(
    cutoff_hz: float,
    impedance: float,
    num_components: int,
    topology: str,
    cap_formula: Callable[[float, float, float], float],
    ind_formula: Callable[[float, float, float], float],
    is_lowpass: bool,
) -> tuple[list[float], list[float], int]:
    """Base Butterworth calculation with strategy functions for LP/HP differences.

    Args:
        cutoff_hz: Cutoff frequency in Hz
        impedance: Characteristic impedance in Ohms
        num_components: Number of filter elements (2-9)
        topology: 'pi' or 't'
        cap_formula: Function(g, impedance, cutoff_hz) -> capacitor value
        ind_formula: Function(g, impedance, cutoff_hz) -> inductor value
        is_lowpass: True for lowpass, False for highpass

    Returns:
        Tuple of (capacitors, inductors, order). The HP public wrappers reorder
        the lists for display; this base function never swaps them.
    """
    _validate_topology(topology)
    _validate_lp_hp_inputs(cutoff_hz, impedance, num_components)
    n = num_components
    capacitors = []
    inductors = []

    for i in range(1, n + 1):
        # Closed-form Butterworth prototype element for equal 1-ohm
        # terminations, -3 dB at omega = 1: g_k = 2·sin((2k-1)·pi / 2n).
        # (Matthaei, Young, Jones Sec. 4.05) — no lookup table needed.
        k = (2 * i - 1) * math.pi / (2 * n)
        g = 2 * math.sin(k)

        if _component_kind(i, topology, is_lowpass) == "cap":
            capacitors.append(_evaluate_component_formula(cap_formula, g, impedance, cutoff_hz))
        else:
            inductors.append(_evaluate_component_formula(ind_formula, g, impedance, cutoff_hz))

    return capacitors, inductors, n


def _calculate_chebyshev_base(
    cutoff_hz: float,
    impedance: float,
    ripple_db: float,
    num_components: int,
    topology: str,
    cap_formula: Callable[[float, float, float], float],
    ind_formula: Callable[[float, float, float], float],
    is_lowpass: bool,
) -> tuple[list[float], list[float], int]:
    """Base Chebyshev calculation with strategy functions for LP/HP differences.

    ``cutoff_hz`` is the equal-ripple band edge (the last frequency at
    -ripple_db), not the -3 dB point — the same convention the LP/HP
    transfer functions use, so component tables and plotted responses agree.

    Args:
        cutoff_hz: Cutoff frequency in Hz (ripple band edge)
        impedance: Characteristic impedance in Ohms
        ripple_db: Passband ripple in dB
        num_components: Number of filter elements (2-9)
        topology: 'pi' or 't'
        cap_formula: Function(g, impedance, cutoff_hz) -> capacitor value
        ind_formula: Function(g, impedance, cutoff_hz) -> inductor value
        is_lowpass: True for lowpass, False for highpass

    Returns:
        Tuple of (capacitors, inductors, order). The HP public wrappers reorder
        the lists for display; this base function never swaps them.
    """
    _validate_topology(topology)
    _validate_lp_hp_inputs(cutoff_hz, impedance, num_components)
    if not is_finite_real(ripple_db) or ripple_db <= 0 or ripple_db > 3.0:
        raise ValueError("ripple_db must be positive, finite, and at most 3.0 dB for Chebyshev")
    n = num_components
    # Even-order Chebyshev designs cannot meet equal source/load terminations
    # (ripple does not return to 0 dB at DC for LP / at infinity for HP),
    # which this library assumes. Match bandpass behavior by restricting to odd.
    if n % 2 == 0:
        raise ValueError(
            "Chebyshev LP/HP requires odd order for equal source/load terminations "
            "(use 3, 5, 7, or 9)"
        )
    # Get g-values from shared calculator
    g = calculate_chebyshev_g_values(n, ripple_db)

    capacitors = []
    inductors = []

    for i in range(1, n + 1):
        if _component_kind(i, topology, is_lowpass) == "cap":
            capacitors.append(_evaluate_component_formula(cap_formula, g[i], impedance, cutoff_hz))
        else:
            inductors.append(_evaluate_component_formula(ind_formula, g[i], impedance, cutoff_hz))

    return capacitors, inductors, n


def _calculate_bessel_base(
    cutoff_hz: float,
    impedance: float,
    num_components: int,
    topology: str,
    cap_formula: Callable[[float, float, float], float],
    ind_formula: Callable[[float, float, float], float],
    is_lowpass: bool,
) -> tuple[list[float], list[float], int]:
    """Base Bessel calculation with strategy functions for LP/HP differences.

    Args:
        cutoff_hz: Cutoff frequency in Hz
        impedance: Characteristic impedance in Ohms
        num_components: Number of filter elements (2-9)
        topology: 'pi' or 't'
        cap_formula: Function(g, impedance, cutoff_hz) -> capacitor value
        ind_formula: Function(g, impedance, cutoff_hz) -> inductor value
        is_lowpass: True for lowpass, False for highpass

    Returns:
        Tuple of (capacitors, inductors, order). The HP public wrappers reorder
        the lists for display; this base function never swaps them.
    """
    _validate_topology(topology)
    _validate_lp_hp_inputs(cutoff_hz, impedance, num_components)
    n = num_components
    if n not in BESSEL_G_VALUES:
        raise ValueError(f"Bessel filter supports 2-9 components, got {n}")

    g_values = BESSEL_G_VALUES[n]

    capacitors = []
    inductors = []

    for position, g in enumerate(g_values, start=1):
        if _component_kind(position, topology, is_lowpass) == "cap":
            capacitors.append(_evaluate_component_formula(cap_formula, g, impedance, cutoff_hz))
        else:
            inductors.append(_evaluate_component_formula(ind_formula, g, impedance, cutoff_hz))

    return capacitors, inductors, n


# Strategy functions for lowpass filter component calculations
def _component_from_log(log_value: float) -> float:
    """Exponentiate a component formula only after cancelling factor scales."""
    return math.exp(log_value)


def _lp_cap_formula(g: float, impedance: float, cutoff_hz: float) -> float:
    """Lowpass capacitor formula: C = g / (Z * ω)"""
    return _component_from_log(
        math.log(g) - math.log(impedance) - math.log(2 * math.pi) - math.log(cutoff_hz)
    )


def _lp_ind_formula(g: float, impedance: float, cutoff_hz: float) -> float:
    """Lowpass inductor formula: L = g * Z / ω"""
    return _component_from_log(
        math.log(g) + math.log(impedance) - math.log(2 * math.pi) - math.log(cutoff_hz)
    )


# Strategy functions for highpass filter component calculations
def _hp_cap_formula(g: float, impedance: float, cutoff_hz: float) -> float:
    """Highpass capacitor formula: C = 1 / (g * ω * Z)"""
    return _component_from_log(
        -math.log(g) - math.log(2 * math.pi) - math.log(cutoff_hz) - math.log(impedance)
    )


def _hp_ind_formula(g: float, impedance: float, cutoff_hz: float) -> float:
    """Highpass inductor formula: L = Z / (ω * g)"""
    return _component_from_log(
        math.log(impedance) - math.log(2 * math.pi) - math.log(cutoff_hz) - math.log(g)
    )


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
        _lp_cap_formula,
        _lp_ind_formula,
        is_lowpass=True,
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
        _lp_cap_formula,
        _lp_ind_formula,
        is_lowpass=True,
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
        _lp_cap_formula,
        _lp_ind_formula,
        is_lowpass=True,
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
        _hp_cap_formula,
        _hp_ind_formula,
        is_lowpass=False,
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
        _hp_cap_formula,
        _hp_ind_formula,
        is_lowpass=False,
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
        _hp_cap_formula,
        _hp_ind_formula,
        is_lowpass=False,
    )
    return inductors, capacitors, n  # HP returns inductors first
