"""Size each band-pass tank as a fixed standard part plus a sourced trimmer.

At the calibrated tank frequency the calculated design gives every tank node a
susceptance (zero, up to rounding: synthesis makes each tank resonant there). A built tank
must give the same, whatever the other parts at the node turn out to be within their
tolerances. So the fixed part and the trimmer together must cover an interval of
capacitance (the *need*): the target less every other branch at the node, taken at the
extreme corners of its tolerance (``tank_susceptance`` defines a node's admittance).

The branches at a node are its inductor (a chip inductor at both tolerance ends, each at
its minimum SRF and with no drift; a toroid winding or a calculated value at its assumed
tolerance), its coupling capacitors (the chosen parts at both ends of their tolerance plus
the assumed stray across a pair; no chosen part: the calculated value at the assumed
tolerance), and an end capacitor in series with its port resistance, whose effective shunt
``Ce / (1 + (omega R Ce)^2)`` is largest at ``Ce = 1 / (omega R)``: both ends of its interval
and that stationary point are used. Every term keeps the part Q the build applies. The terms
are independent, so their extremes add, in pF.

A trimmer's guaranteed range is measured at 200 kHz or 1 MHz, or at a frequency the maker
does not state. At the tank frequency its series inductance raises its effective
capacitance ``C / (1 - omega^2 Ls C)``. The inductance is bounded only by Vishay's minimum
SRF at the maximum capacitance (``TrimmerPart.series_inductance_bound_h``); for every
other part it is ``ASSUMED_TRIMMER_SERIES_INDUCTANCE_H``, an assumption. Either value is
treated as an upper bound, so the range relied on is from the raised minimum to the
unraised maximum, and every fit is conditional on that inductance.

A split fits when the trimmer's range contains what the trimmer must supply: the need
less the fixed part at either end of its tolerance and the assumed stray across each extra
part (a trimmer with one fixed part has one; with a pair, two). The fixed part is the
trimmer alone, or the best single part or pair by the worst-case rule for the middle of
the range. Splits rank by the smallest trimmer range, then the best-centred fixed part,
then fewer parts, then part number.
"""

from __future__ import annotations

import math
from bisect import bisect_right
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from fractions import Fraction

from .build_loss_models import LossModel, derive_series_resistance
from .build_types import DEFAULT_INDUCTOR_TOLERANCE_PCT, BuildConfig
from .capacitor_choice import (
    assumed_tolerance_pct,
    best_pair,
    eligible_parts_pf,
)
from .circuit_display_names import display_component_name
from .circuit_model import CircuitElement, NamedCircuit
from .eseries import PAIR_RATIO_LIMIT, TOLERANCE_NOT_SOURCED, ESeriesMatch, MatchPolicy
from .resolved_parts import InductorParts
from .tank_susceptance import TWO_PI, node_susceptance
from .trimmer_data import TrimmerPart, trimmer_parts

# The series inductance assumed for a trimmer whose maker states no bound: about the bound
# Vishay's minimum SRF gives its 1.5-5 pF and 3-10 pF parts (10.3 and 10.1 nH).
ASSUMED_TRIMMER_SERIES_INDUCTANCE_H = 10e-9
# JSON lists up to this many splits per tank (one per trimmer row); the table shows the first.
MAX_TANK_SPLITS = 3
_PF_PER_F = Fraction(10) ** 12
_GOLDEN = (math.sqrt(5.0) - 1.0) / 2.0


@dataclass(frozen=True)
class TankNeed:
    """What a tank's fixed part and trimmer must cover together, in farads.

    The capacitance equivalent (susceptance over omega) at the tank frequency.
    ``assumptions`` names each input whose tolerance is not sourced (``(part, text)``);
    the need is conditional on them, and sourced when there are none.
    """

    low_f: float
    high_f: float
    assumptions: tuple[tuple[str, str], ...] = ()

    @property
    def conditional(self) -> bool:
        return bool(self.assumptions)


@dataclass(frozen=True)
class TankSplit:
    """One fitting split: a fixed part (or none) plus a trimmer.

    ``fixed_parts_f`` and ``fixed_tolerances_f`` are the fixed part's values and ±
    tolerances (empty for the trimmer alone); ``stray_f`` is the assumed stray across the
    extra parts. ``series_inductance_h`` is the trimmer's series inductance the fit
    assumes (``series_inductance_assumed``: the labelled default, not a bound from the
    maker's minimum SRF). ``trimmer_range_f`` is the trimmer's range at the tank frequency
    under that inductance, and ``required_f`` what it must supply there.
    """

    trimmer: TrimmerPart
    fixed_parts_f: tuple[float, ...]
    fixed_tolerances_f: tuple[float, ...]
    stray_f: float
    series_inductance_h: float
    series_inductance_assumed: bool
    trimmer_range_f: tuple[float, float]
    required_f: tuple[float, float]
    centring_f: float

    @property
    def fixed_value_f(self) -> float:
        return math.fsum(self.fixed_parts_f)


@dataclass(frozen=True)
class TankParts:
    """One tank's need and its fitting splits, ranked (the build uses the first).

    ``name`` is the tank capacitor's circuit name (``CT1``) at ``node``;
    ``target_susceptance_s`` is the calculated design's susceptance there at
    ``tuning_frequency_hz``, which the build's trimmer setting restores. ``ports_ohm`` is
    the source and load resistance the end capacitors were sized through.
    """

    name: str
    node: int
    tuning_frequency_hz: float
    target_susceptance_s: float
    need: TankNeed
    ports_ohm: tuple[float, float]
    splits: tuple[TankSplit, ...] = ()

    @property
    def split(self) -> TankSplit | None:
        """The split the table shows and the build uses, or ``None`` when none fits."""
        return self.splits[0] if self.splits else None


def effective_capacitance(capacitance_f: float, inductance_h: float, frequency_hz: float) -> float:
    """``C / (1 - omega^2 L C)``: a capacitor with series inductance ``L`` at ``f``.

    Raises ``ValueError`` at or above the series resonance, where it is not a capacitor.
    """
    product = (TWO_PI * frequency_hz) ** 2 * inductance_h * capacitance_f
    if product >= 1.0:
        raise ValueError("The trimmer is at or above its series resonance at this frequency")
    return capacitance_f / (1.0 - product)


def series_inductance(trimmer: TrimmerPart) -> tuple[float, bool]:
    """The series inductance a fit assumes for ``trimmer`` and whether it is the default."""
    bound = trimmer.series_inductance_bound_h
    if bound is None:
        return ASSUMED_TRIMMER_SERIES_INDUCTANCE_H, True
    return bound, False


def _capacitor_admittance(value: float, omega: float, q: float | None, reference_hz: float):
    resistance = 0.0 if q is None else derive_series_resistance("C", value, q, reference_hz)
    return 1.0 / complex(resistance, -1.0 / (omega * value))


def _inductor_admittance(value: float, omega: float, q: float | None, reference_hz: float):
    resistance = 0.0 if q is None else derive_series_resistance("L", value, q, reference_hz)
    return 1.0 / complex(resistance, omega * value)


def trimmer_admittance(
    setting_f: float,
    inductance_h: float,
    omega: float,
    q: float | None,
    reference_hz: float,
) -> complex:
    """A trimmer at knob value ``setting_f`` with its series inductance and Q."""
    resistance = 0.0 if q is None else derive_series_resistance("C", setting_f, q, reference_hz)
    return 1.0 / complex(resistance, omega * inductance_h - 1.0 / (omega * setting_f))


def trimmer_range_f(
    trimmer: TrimmerPart,
    inductance_h: float,
    frequency_hz: float,
    q: float | None,
    reference_hz: float,
) -> tuple[float, float] | None:
    """The range relied on at ``frequency_hz``: the raised minimum to the unraised maximum.

    ``None`` when the trimmer is not a capacitor there (at or above series resonance).
    """
    omega = TWO_PI * frequency_hz
    if omega * inductance_h * omega * trimmer.cmin_max_f >= 1.0:
        return None
    low = trimmer_admittance(trimmer.cmin_max_f, inductance_h, omega, q, reference_hz).imag
    high = trimmer_admittance(trimmer.cmax_min_f, 0.0, omega, q, reference_hz).imag
    if not low < high:
        return None
    return low / omega, high / omega


def _golden_maximum(function: Callable[[float], float], low: float, high: float) -> float:
    """The largest value of a unimodal ``function`` on ``[low, high]``."""
    if not high > low:
        return function(low)
    a, b = low, high
    c = b - _GOLDEN * (b - a)
    d = a + _GOLDEN * (b - a)
    fc, fd = function(c), function(d)
    for _ in range(200):
        if b - a <= 1e-15 * max(abs(a), abs(b)):
            break
        if fc >= fd:
            b, d, fd = d, c, fc
            c = b - _GOLDEN * (b - a)
            fc = function(c)
        else:
            a, c, fc = c, d, fd
            d = a + _GOLDEN * (b - a)
            fd = function(d)
    return max(function(low), function(high), fc, fd)


def port_branch_range(
    capacitance_f: tuple[float, float],
    stray_f: float,
    resistance_ohm: float,
    omega: float,
    q: float | None,
    reference_hz: float,
) -> tuple[float, float]:
    """The susceptance range of an end capacitor in series with its port resistance.

    The capacitor's parts sum to ``capacitance_f`` (low, high), with their Q, plus an
    assumed stray from zero to ``stray_f``. Its effective shunt has one maximum, at
    ``1 / (omega R)`` when lossless, so the extremes are at the corners or at the maximum
    along an edge.
    """

    def susceptance(parts_f: float, stray: float) -> float:
        parts = _capacitor_admittance(parts_f, omega, q, reference_hz)
        branch = parts + 1j * omega * stray
        return (branch / (1.0 + resistance_ohm * branch)).imag

    low_c, high_c = capacitance_f
    corners = [susceptance(c, s) for c in (low_c, high_c) for s in (0.0, stray_f)]
    edges = [
        _golden_maximum(lambda c, s=s: susceptance(c, s), low_c, high_c) for s in (0.0, stray_f)
    ]
    if stray_f > 0:
        edges += [
            _golden_maximum(lambda s, c=c: susceptance(c, s), 0.0, stray_f) for c in (low_c, high_c)
        ]
    if q is None:
        # Lossless, the parts and the stray add, and the maximum is exactly at 1/(omega R).
        stationary = 1.0 / (omega * resistance_ohm)
        if low_c <= stationary <= high_c + stray_f:
            corners.append(susceptance(stationary, 0.0))
    values = corners + edges
    return min(values), max(values)


@dataclass(frozen=True)
class _Values:
    """A capacitor's parts as (values, tolerances), its stray, and any assumption."""

    values: tuple[float, ...]
    tolerances: tuple[float, ...]
    stray_f: float
    assumption: str | None

    @property
    def low(self) -> float:
        return math.fsum(v - t for v, t in zip(self.values, self.tolerances))

    @property
    def high(self) -> float:
        return math.fsum(v + t for v, t in zip(self.values, self.tolerances))


def not_sourced_assumption(pct: float) -> str:
    """A capacitor whose tolerance the sourced table does not give."""
    return f"tolerance not sourced; ±{pct:g}% assumed"


def no_part_assumption(pct: float) -> str:
    """A capacitor with no chosen part: its calculated value at an assumed tolerance."""
    return f"no standard part chosen; its calculated value at ±{pct:g}% assumed"


def toroid_assumption(pct: float) -> str:
    """A toroid winding, whose tolerance is an assumption."""
    return f"toroid winding; ±{pct:g}% assumed"


def calculated_inductor_assumption(pct: float) -> str:
    """An inductor built at its calculated value, at an assumed tolerance."""
    return f"no inductor part; the calculated value at ±{pct:g}% assumed"


def _capacitor_values(element: CircuitElement, match: ESeriesMatch, policy: MatchPolicy) -> _Values:
    selected = match.selected_components
    if selected is None:
        pct = assumed_tolerance_pct(policy)
        return _Values(
            (element.value,), (element.value * pct / 100.0,), 0.0, no_part_assumption(pct)
        )
    stray = policy.stray_capacitance_f if len(selected) > 1 else 0.0
    assumption = None
    if match.status == TOLERANCE_NOT_SOURCED:
        assumption = not_sourced_assumption(assumed_tolerance_pct(policy))
    return _Values(tuple(selected), tuple(match.part_tolerances_f or ()), stray, assumption)


def _inductor_range(
    element: CircuitElement,
    parts: InductorParts,
    config: BuildConfig,
    omega: float,
    losses: LossModel,
) -> tuple[float, float, str | None]:
    """The inductor branch's susceptance range and the assumption it rests on, if any."""
    entered = config.inductor_tolerance_pct
    pick = parts.build_pick
    q, reference = losses.inductor_q, losses.reference_frequency_hz
    if pick is not None and pick.part_model is not None:
        # A sourced part: its guaranteed tolerance, which an entered one can only loosen.
        tolerance = max(pick.tolerance_pct, entered or 0.0) / 100.0
        model = pick.part_model
        values = []
        for catalog in (
            model.catalog_inductance_h * (1 - tolerance),
            model.catalog_inductance_h * (1 + tolerance),
        ):
            # At the minimum SRF (with its self-capacitance) and with no drift.
            l0 = catalog * (1.0 - (model.test_frequency_hz / model.srf_hz) ** 2)
            c_self = 1.0 / ((TWO_PI * model.srf_hz) ** 2 * l0)
            values.append(
                (_inductor_admittance(l0, omega, q, reference) + 1j * omega * c_self).imag
            )
            values.append(_inductor_admittance(catalog, omega, q, reference).imag)
        return min(values), max(values), None
    # Only a toroid winding is built without a part model; its tolerance is assumed.
    pct = entered if entered is not None else DEFAULT_INDUCTOR_TOLERANCE_PCT
    if pick is None:
        nominal, assumption = element.value, calculated_inductor_assumption(pct)
    else:
        nominal, assumption = pick.achieved_h, toroid_assumption(pct)
    values = [
        _inductor_admittance(nominal * (1 + sign * pct / 100.0), omega, q, reference).imag
        for sign in (-1.0, 1.0)
    ]
    return min(values), max(values), assumption


def _capacitor_range(
    element: CircuitElement,
    values: _Values,
    port_resistance: float | None,
    omega: float,
    losses: LossModel,
) -> tuple[float, float]:
    q = losses.capacitor_q_for(element.name)
    reference = losses.reference_frequency_hz
    if port_resistance is not None:
        return port_branch_range(
            (values.low, values.high), values.stray_f, port_resistance, omega, q, reference
        )
    low = _capacitor_admittance(values.low, omega, q, reference).imag
    high = (
        _capacitor_admittance(values.high, omega, q, reference) + 1j * omega * values.stray_f
    ).imag
    return low, high


def _fixed_options(
    target_f: float,
    upper_f: float,
    stray_per_part_f: float,
    scale: float,
    candidates: list[tuple[Fraction, Fraction]],
) -> list[tuple[tuple[float, ...], tuple[float, ...]]]:
    """The best single part and the best pair for ``target_f`` (capacitance equivalent).

    ``scale`` converts a part's value to its capacitance equivalent (its Q lowers it);
    each extra part beside the trimmer adds ``stray_per_part_f`` at the upper end. Only
    parts up to ``upper_f`` (the window's top) can fit, so no larger part is searched.
    """
    if target_f <= 0:
        return []
    upper = Fraction(upper_f / scale) * _PF_PER_F
    candidates = candidates[: bisect_right([value for value, _t in candidates], upper)]
    if not candidates:
        return []
    target = Fraction(target_f / scale) * _PF_PER_F
    stray_one = Fraction(stray_per_part_f / scale) * _PF_PER_F
    _score, value, tolerance = min(
        (max(abs(v - t - target), abs(v + t + stray_one - target)), v, t) for v, t in candidates
    )
    options: list[tuple[tuple[float, ...], tuple[float, ...]]] = [
        ((float(value / _PF_PER_F),), (float(tolerance / _PF_PER_F),))
    ]
    pair = best_pair(candidates, target, PAIR_RATIO_LIMIT, 2 * stray_one)
    if pair is not None:
        _pair_score, _ratio, _total, (low, low_tol), (high, high_tol) = pair
        options.append(
            (
                (float(low / _PF_PER_F), float(high / _PF_PER_F)),
                (float(low_tol / _PF_PER_F), float(high_tol / _PF_PER_F)),
            )
        )
    return options


def _best_split_for(
    trimmer: TrimmerPart,
    need: TankNeed,
    frequency_hz: float,
    q: float | None,
    reference_hz: float,
    policy: MatchPolicy,
    candidates: list[tuple[Fraction, Fraction]],
) -> TankSplit | None:
    """The best-centred fitting split with ``trimmer``, or ``None`` when none fits."""
    inductance, assumed = series_inductance(trimmer)
    trimmer_range = trimmer_range_f(trimmer, inductance, frequency_hz, q, reference_hz)
    if trimmer_range is None:
        return None
    range_low, range_high = trimmer_range
    window_low, window_high = need.high_f - range_high, need.low_f - range_low
    if window_low > window_high:
        return None
    middle = (window_low + window_high) / 2.0
    omega = TWO_PI * frequency_hz
    # A part's capacitance equivalent with its Q (exactly linear in its value).
    scale = _capacitor_admittance(1e-12, omega, q, reference_hz).imag / (omega * 1e-12)
    stray = policy.stray_capacitance_f
    options: list[tuple[tuple[float, ...], tuple[float, ...]]] = [((), ())]
    options.extend(_fixed_options(middle, window_high, stray, scale, candidates))
    best = None
    for values, tolerances in options:
        extra_stray = stray * len(values)
        low = scale * math.fsum(v - t for v, t in zip(values, tolerances))
        high = scale * math.fsum(v + t for v, t in zip(values, tolerances)) + extra_stray
        if low < window_low or high > window_high:
            continue
        centring = max(abs(low - middle), abs(high - middle))
        key = (centring, len(values))
        if best is None or key < best[0]:
            best = (key, values, tolerances, extra_stray, low, high)
    if best is None:
        return None
    (centring, _count), values, tolerances, extra_stray, low, high = best
    return TankSplit(
        trimmer=trimmer,
        fixed_parts_f=values,
        fixed_tolerances_f=tolerances,
        stray_f=extra_stray,
        series_inductance_h=inductance,
        series_inductance_assumed=assumed,
        trimmer_range_f=trimmer_range,
        required_f=(need.low_f - high, need.high_f - low),
        centring_f=centring,
    )


def tank_nodes(result: Mapping) -> tuple[int, ...]:
    """The resonator nodes of a band-pass named circuit (1 to n)."""
    return tuple(range(1, int(result["n_resonators"]) + 1))


def tank_ports(circuit: NamedCircuit, source_ohm: float, load_ohm: float) -> dict[int, float]:
    """Each port node and its resistance."""
    return {circuit.in_node: source_ohm, circuit.out_node: load_ohm}


def tuning_frequency(result: Mapping) -> float:
    """The calibrated tank frequency, where the calculated tanks are resonant."""
    return float(result.get("f_tank_hz") or result["f0"])


def size_tanks(
    result: dict,
    circuit: NamedCircuit,
    capacitors: Mapping[str, ESeriesMatch],
    inductors: Mapping[str, InductorParts],
    policy: MatchPolicy,
    eseries: str,
    config: BuildConfig,
    ports: Mapping[int, float],
    losses: LossModel,
) -> dict[str, TankParts]:
    """Size every tank of a band-pass design (see the module docstring)."""
    frequency = tuning_frequency(result)
    omega = TWO_PI * frequency
    nodes = tank_nodes(result)
    design_ports = {node: float(result["z0"]) for node in ports}
    # Every part the worst-case rule may choose, ascending, for the fixed part's search.
    candidates = eligible_parts_pf(policy, eseries)
    tanks: dict[str, TankParts] = {}
    for node in nodes:
        name = f"CT{node}"
        target = node_susceptance(circuit, node, frequency, nodes, design_ports)
        rest_low = rest_high = 0.0
        assumptions: list[tuple[str, str]] = []
        for element in circuit.elements:
            if element.name == name or node not in (element.node1, element.node2):
                continue
            other = element.node2 if element.node1 == node else element.node1
            if element.kind == "L":
                low, high, assumption = _inductor_range(
                    element, inductors[element.name], config, omega, losses
                )
            else:
                values = _capacitor_values(element, capacitors[element.name], policy)
                low, high = _capacitor_range(element, values, ports.get(other), omega, losses)
                assumption = values.assumption
            rest_low += low
            rest_high += high
            if assumption is not None:
                assumptions.append((display_component_name(element.name), assumption))
        need = TankNeed(
            low_f=(target - rest_high) / omega,
            high_f=(target - rest_low) / omega,
            assumptions=tuple(assumptions),
        )
        q = losses.capacitor_q_for(name)
        splits = [
            split
            for trimmer in trimmer_parts()
            if (
                split := _best_split_for(
                    trimmer, need, frequency, q, losses.reference_frequency_hz, policy, candidates
                )
            )
            is not None
        ]
        splits.sort(
            key=lambda item: (
                item.trimmer_range_f[1] - item.trimmer_range_f[0],
                item.centring_f,
                len(item.fixed_parts_f),
                item.trimmer.part_name,
            )
        )
        tanks[name] = TankParts(
            name=name,
            node=node,
            tuning_frequency_hz=frequency,
            target_susceptance_s=target,
            need=need,
            ports_ohm=(ports[circuit.in_node], ports[circuit.out_node]),
            splits=tuple(splits[:MAX_TANK_SPLITS]),
        )
    return tanks
