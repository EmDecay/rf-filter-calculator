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

from .build_loss_models import LossModel, derive_series_resistance, loss_model
from .build_types import DEFAULT_INDUCTOR_TOLERANCE_PCT, BuildConfig
from .cancellation import CancellationCheck, raise_if_cancelled
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


def _series_resistance(kind: str, value: float, q: float | None, reference_hz: float) -> float:
    """The series resistance that gives a part its Q; none for a lossless part."""
    return 0.0 if q is None else derive_series_resistance(kind, value, q, reference_hz)


def _capacitor_admittance(
    value: float, omega: float, q: float | None, reference_hz: float
) -> complex:
    resistance = _series_resistance("C", value, q, reference_hz)
    return 1.0 / complex(resistance, -1.0 / (omega * value))


def _inductor_admittance(
    value: float, omega: float, q: float | None, reference_hz: float
) -> complex:
    resistance = _series_resistance("L", value, q, reference_hz)
    return 1.0 / complex(resistance, omega * value)


def trimmer_admittance(
    setting_f: float,
    inductance_h: float,
    omega: float,
    q: float | None,
    reference_hz: float,
) -> complex:
    """A trimmer at knob value ``setting_f`` with its series inductance and Q."""
    resistance = _series_resistance("C", setting_f, q, reference_hz)
    return 1.0 / complex(resistance, omega * inductance_h - 1.0 / (omega * setting_f))


def _loss_ratio(omega: float, q: float | None, reference_hz: float) -> float:
    """``alpha = R/X_C`` of a capacitor with Q at ``reference_hz``, seen at ``omega``.

    Q sets the series resistance ``R = 1/(omega_ref C Q)`` from the part's own value, so
    the ratio to its reactance ``1/(omega C)`` is the same for every setting.
    """
    return 0.0 if q is None else omega / (TWO_PI * reference_hz * q)


def capacitive_branch_top(
    inductance_h: float, omega: float, q: float | None, reference_hz: float
) -> float:
    """The largest knob setting up to which the trimmer's susceptance rises.

    With ``u = 1/(omega C)``, ``a = omega Ls`` and ``alpha`` (``_loss_ratio``), the branch
    susceptance ``(u - a) / ((alpha u)^2 + (u - a)^2)`` rises with C until
    ``u = a (1 + alpha / sqrt(1 + alpha^2))``: the series resonance when lossless, and a
    loss peak before it otherwise. Infinite without series inductance.
    """
    if inductance_h == 0:
        return math.inf
    alpha = _loss_ratio(omega, q, reference_hz)
    beta = alpha / math.sqrt(1.0 + alpha * alpha)
    return 1.0 / (omega * omega * inductance_h * (1.0 + beta))


def trimmer_range_f(
    trimmer: TrimmerPart,
    inductance_h: float,
    frequency_hz: float,
    q: float | None,
    reference_hz: float,
) -> tuple[float, float] | None:
    """The range relied on at ``frequency_hz``, for any series inductance up to ``inductance_h``.

    Only the rising (capacitive) part of the knob's travel is used
    (``capacitive_branch_top``). For each inductance the knob then reaches every value from
    its minimum stop up to that branch's top, so the range relied on runs from the largest
    of those minimums to the smallest of those tops. At the minimum stop the susceptance
    peaks over the inductance where the remaining reactance equals the loss resistance, so
    that inductance, zero and the bound are the candidates; the top is smallest at zero or
    the bound. ``None`` when the knob's minimum is already past the rising part.
    """
    omega = TWO_PI * frequency_hz
    cmin, cmax = trimmer.cmin_max_f, trimmer.cmax_min_f
    if cmin >= capacitive_branch_top(inductance_h, omega, q, reference_hz):
        return None

    def susceptance(setting: float, inductance: float) -> float:
        return trimmer_admittance(setting, inductance, omega, q, reference_hz).imag

    alpha = _loss_ratio(omega, q, reference_hz)
    reactance = 1.0 / (omega * cmin)
    candidates = [0.0, inductance_h]
    turning = reactance * (1.0 - alpha) / omega
    if 0.0 < turning < inductance_h:
        candidates.append(turning)
    low = max(susceptance(cmin, inductance) for inductance in candidates)

    def top(inductance: float) -> float:
        branch_top = capacitive_branch_top(inductance, omega, q, reference_hz)
        if q is None and cmax >= branch_top:
            return math.inf  # lossless past resonance: the knob reaches any value
        return susceptance(min(cmax, branch_top), inductance)

    high = min(top(0.0), top(inductance_h))
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


def _tolerance_ends(
    values: tuple[float, ...], tolerances: tuple[float, ...]
) -> tuple[float, float]:
    """The sum of parts with every one at the low end of its tolerance, then the high end."""
    return (
        math.fsum(v - t for v, t in zip(values, tolerances)),
        math.fsum(v + t for v, t in zip(values, tolerances)),
    )


@dataclass(frozen=True)
class _Values:
    """A capacitor's parts as (values, tolerances), its stray, and any assumption."""

    values: tuple[float, ...]
    tolerances: tuple[float, ...]
    stray_f: float
    assumption: str | None


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
    omega: float,
    losses: LossModel,
) -> tuple[float, float, str | None]:
    """The inductor branch's susceptance range and the assumption it rests on, if any.

    The inductor is its first suggestion in the fixed order (``InductorParts.default_pick``,
    whatever the build's inductor choice): a chip inductor at its guaranteed tolerance, a
    toroid winding at the assumed 10%, or, with no suggestion, the calculated value at the
    assumed 10%.
    """
    shown = parts.default_pick
    q, reference = losses.inductor_q, losses.reference_frequency_hz
    if shown is not None and shown.part_model is not None:
        tolerance = shown.tolerance_pct / 100.0
        model = shown.part_model
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
    # Only a toroid winding is shown without a part model; its tolerance is assumed.
    pct = DEFAULT_INDUCTOR_TOLERANCE_PCT
    if shown is None:
        nominal, assumption = element.value, calculated_inductor_assumption(pct)
    else:
        nominal, assumption = shown.achieved_h, toroid_assumption(pct)
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
    parts_low, parts_high = _tolerance_ends(values.values, values.tolerances)
    if port_resistance is not None:
        return port_branch_range(
            (parts_low, parts_high), values.stray_f, port_resistance, omega, q, reference
        )
    low = _capacitor_admittance(parts_low, omega, q, reference).imag
    high = (
        _capacitor_admittance(parts_high, omega, q, reference) + 1j * omega * values.stray_f
    ).imag
    return low, high


def _exact_pf(value_f: float) -> Fraction:
    """A float capacitance in exact pF (its own binary value, not its decimal text)."""
    return Fraction(value_f) * _PF_PER_F


def _farads(value_pf: Fraction) -> float:
    """An exact pF value as the nearest float in farads."""
    return float(value_pf / _PF_PER_F)


# A fixed part as its values and their ± tolerances, in farads (both empty: no fixed part).
_FixedOption = tuple[tuple[float, ...], tuple[float, ...]]


def _fixed_options(
    target_f: float,
    upper_f: float,
    stray_per_part_f: float,
    scale: float,
    candidates: list[tuple[Fraction, Fraction]],
) -> list[_FixedOption]:
    """The best single part and the best pair for ``target_f`` (capacitance equivalent).

    ``scale`` converts a part's value to its capacitance equivalent (its Q lowers it);
    each extra part beside the trimmer adds ``stray_per_part_f`` at the upper end. Only
    parts up to ``upper_f`` (the window's top) can fit, so no larger part is searched.
    """
    if target_f <= 0:
        return []
    upper = _exact_pf(upper_f / scale)
    candidates = candidates[: bisect_right([value for value, _t in candidates], upper)]
    if not candidates:
        return []
    target = _exact_pf(target_f / scale)
    stray_one = _exact_pf(stray_per_part_f / scale)
    _score, value, tolerance = min(
        (max(abs(v - t - target), abs(v + t + stray_one - target)), v, t) for v, t in candidates
    )
    options: list[_FixedOption] = [((_farads(value),), (_farads(tolerance),))]
    pair = best_pair(candidates, target, PAIR_RATIO_LIMIT, 2 * stray_one)
    if pair is not None:
        _pair_score, _ratio, _total, (low, low_tol), (high, high_tol) = pair
        options.append(((_farads(low), _farads(high)), (_farads(low_tol), _farads(high_tol))))
    return options


def _best_split_for(
    trimmer: TrimmerPart,
    need: TankNeed,
    frequency_hz: float,
    q: float | None,
    reference_hz: float,
    policy: MatchPolicy,
    candidates: list[tuple[Fraction, Fraction]],
    found: dict[tuple[float, float, float, float], list[_FixedOption]] | None = None,
) -> TankSplit | None:
    """The best-centred fitting split with ``trimmer``, or ``None`` when none fits.

    ``found`` keeps the fixed-part options already searched for these ``candidates``, by
    window centre, window top, stray and scale: trimmers with the same range ask for the
    same ones, and the exact search is the costly step.
    """
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
    options: list[_FixedOption] = [((), ())]
    key = (middle, window_high, stray, scale)
    fixed = None if found is None else found.get(key)
    if fixed is None:
        fixed = _fixed_options(middle, window_high, stray, scale, candidates)
        if found is not None:
            found[key] = fixed
    options.extend(fixed)
    fits = []
    for values, tolerances in options:
        extra_stray = stray * len(values)
        parts_low, parts_high = _tolerance_ends(values, tolerances)
        low = scale * parts_low
        high = scale * parts_high + extra_stray
        if low < window_low or high > window_high:
            continue
        fits.append(
            TankSplit(
                trimmer=trimmer,
                fixed_parts_f=values,
                fixed_tolerances_f=tolerances,
                stray_f=extra_stray,
                series_inductance_h=inductance,
                series_inductance_assumed=assumed,
                trimmer_range_f=trimmer_range,
                required_f=(need.low_f - high, need.high_f - low),
                centring_f=max(abs(low - middle), abs(high - middle)),
            )
        )
    # The best-centred fit; on a tie, the one with fewer parts, then the first listed.
    return min(fits, key=lambda split: (split.centring_f, len(split.fixed_parts_f)), default=None)


def tank_nodes(result: Mapping) -> tuple[int, ...]:
    """The resonator nodes of a band-pass named circuit (1 to n)."""
    return tuple(range(1, int(result["n_resonators"]) + 1))


def tank_ports(circuit: NamedCircuit, source_ohm: float, load_ohm: float) -> dict[int, float]:
    """Each port node and its resistance."""
    return {circuit.in_node: source_ohm, circuit.out_node: load_ohm}


def tuning_frequency(result: Mapping) -> float:
    """The calibrated tank frequency, where the calculated tanks are resonant."""
    return float(result.get("f_tank_hz") or result["f0"])


def _split_rank(split: TankSplit) -> tuple[float, float, int, str]:
    """Smallest trimmer range, then best-centred fixed part, then fewer parts, then part number."""
    low, high = split.trimmer_range_f
    return (high - low, split.centring_f, len(split.fixed_parts_f), split.trimmer.part_name)


def size_tanks(
    result: dict,
    circuit: NamedCircuit,
    capacitors: Mapping[str, ESeriesMatch],
    inductors: Mapping[str, InductorParts],
    policy: MatchPolicy,
    eseries: str,
    should_cancel: CancellationCheck | None = None,
) -> dict[str, TankParts]:
    """Size every tank of a band-pass design (see the module docstring).

    The sizing rests on the design alone, so every output of a design shows the same
    split: its equal terminations, the losses of its resonator Q (``loss_model`` with no
    build settings), each inductor's first suggestion and the parts' own or assumed
    tolerances. A build's own ports, Q and inductor choice change only the settings it
    simulates. ``should_cancel`` is polled before each tank and each trimmer tried for it.
    """
    losses = loss_model(result, "bandpass", BuildConfig())
    z0 = float(result["z0"])
    ports = tank_ports(circuit, z0, z0)
    frequency = tuning_frequency(result)
    omega = TWO_PI * frequency
    reference = losses.reference_frequency_hz
    nodes = tank_nodes(result)
    ports_ohm = (ports[circuit.in_node], ports[circuit.out_node])
    # Every part the worst-case rule may choose, ascending, for the fixed part's search.
    candidates = eligible_parts_pf(policy, eseries)
    found: dict[tuple[float, float, float, float], list[_FixedOption]] = {}
    tanks: dict[str, TankParts] = {}
    for node in nodes:
        raise_if_cancelled(should_cancel)
        name = f"CT{node}"
        target = node_susceptance(circuit, node, frequency, nodes, ports)
        rest_low = rest_high = 0.0
        assumptions: list[tuple[str, str]] = []
        for element in circuit.elements:
            if element.name == name or node not in (element.node1, element.node2):
                continue
            if element.kind == "L":
                low, high, assumption = _inductor_range(
                    element, inductors[element.name], omega, losses
                )
            else:
                other = element.node2 if element.node1 == node else element.node1
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
        fits = []
        for trimmer in trimmer_parts():
            raise_if_cancelled(should_cancel)
            fits.append(
                _best_split_for(trimmer, need, frequency, q, reference, policy, candidates, found)
            )
        splits = sorted((split for split in fits if split is not None), key=_split_rank)
        tanks[name] = TankParts(
            name=name,
            node=node,
            tuning_frequency_hz=frequency,
            target_susceptance_s=target,
            need=need,
            ports_ohm=ports_ohm,
            splits=tuple(splits[:MAX_TANK_SPLITS]),
        )
    return tanks
