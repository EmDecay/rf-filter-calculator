"""Set each band-pass tank's trimmer so its node susceptance matches the calculated design.

A built tank with a trimmer (``tank_trimmers``) is its fixed part, the assumed stray, and
the trimmer: a capacitor ``CTRIM_<tank>`` at its knob setting with the series inductance its
fit assumes (written to SPICE as ``LTRIM_<tank>`` in series). The trimmer is ``fixed``: the
tolerance cases never vary it; tuning sets the knob instead.

Tuning solves, at the calibrated tank frequency, the knob setting whose trimmer admittance
makes the node's susceptance (``tank_susceptance.node_susceptance``, with every built
branch, its Q and the ports) equal the calculated design's. The setting stays within the
range the fit relied on: from the guaranteed maximum of the minimum capacitance to the
setting that reaches the top of the range the fit relied on, on the rising (capacitive) part
of the knob's travel, so a solve never crosses the trimmer's series resonance. A tank whose
required value is outside that range is flagged; its setting is the nearer reachable end.

Retuning restores each tank's resonance, not the coupling between tanks or the external
Q, so a tuned response is not the design's response.
"""

from __future__ import annotations

import math
from collections.abc import Callable, Mapping
from dataclasses import dataclass, replace

from .build_loss_models import derive_series_resistance
from .build_types import TrimmerSetting
from .circuit_display_names import TRIMMER_PREFIX
from .circuit_model import CircuitElement, NamedCircuit
from .tank_susceptance import TWO_PI, node_susceptance
from .tank_trimmers import (
    TankParts,
    capacitive_branch_top,
    trimmer_admittance,
    trimmer_range_f,
)

# A required setting this close (relative) to a range end counts as inside it.
_RANGE_TOLERANCE = 1e-12
_BISECTION_STEPS = 200


@dataclass(frozen=True)
class TrimmerPlan:
    """What tuning one tank's trimmer needs.

    ``knob_f`` is the range of knob settings used; ``range_f`` the capacitance equivalent
    relied on at ``frequency_hz`` under the build's Q (``None``: none, so every required
    value is out of range).
    """

    tank: str
    node: int
    trimmer_element: str
    series_inductance_h: float
    knob_f: tuple[float, float]
    range_f: tuple[float, float] | None
    frequency_hz: float
    target_susceptance_s: float
    q: float | None
    reference_hz: float

    def susceptance(self, setting_f: float) -> float:
        """The trimmer branch's susceptance at the tank frequency for a knob setting."""
        omega = TWO_PI * self.frequency_hz
        return trimmer_admittance(
            setting_f, self.series_inductance_h, omega, self.q, self.reference_hz
        ).imag

    @property
    def excluded(self) -> tuple[str, ...]:
        return (self.trimmer_element,)


@dataclass(frozen=True)
class TuningPlan:
    """Every trimmer of a build, the resonator nodes and the ports tuning uses."""

    trimmers: tuple[TrimmerPlan, ...]
    tank_nodes: tuple[int, ...]
    ports: Mapping[int, float]


def _trimmer_resistance(setting_f: float, q: float | None, reference_hz: float) -> float:
    """The series resistance that gives a trimmer at ``setting_f`` its Q; none when lossless."""
    return 0.0 if q is None else derive_series_resistance("C", setting_f, q, reference_hz)


def trimmer_element(
    element: CircuitElement,
    series_inductance_h: float,
    setting_f: float,
    q: float | None,
    reference_hz: float,
) -> CircuitElement:
    """The trimmer of tank ``element``: its capacitance with its series inductance."""
    return CircuitElement(
        name=f"{TRIMMER_PREFIX}{element.name}",
        node1=element.node1,
        node2=element.node2,
        kind="C",
        value=setting_f,
        logical_name=element.name,
        quality_factor=q,
        loss_reference_frequency_hz=reference_hz if q is not None else None,
        series_resistance_ohm=_trimmer_resistance(setting_f, q, reference_hz),
        fixed=True,
        series_inductance_h=series_inductance_h,
    )


def _bisect(function: Callable[[float], float], target: float, low: float, high: float) -> float:
    """The knob setting in ``[low, high]`` where the increasing ``function`` is ``target``."""
    for _ in range(_BISECTION_STEPS):
        middle = (low + high) / 2.0
        if middle in (low, high):
            break
        if function(middle) < target:
            low = middle
        else:
            high = middle
    return (low + high) / 2.0


def plan_trimmer(
    tank: TankParts,
    element: CircuitElement,
    q: float | None,
    reference_hz: float,
) -> TrimmerPlan:
    """The tuning plan of a tank with a fitting split (``tank.split``).

    The split was sized from the design alone; the build has its own capacitor Q (``q``
    at ``reference_hz``), so the range relied on is worked out again under it
    (``trimmer_range_f``), and is ``None`` when the trimmer has no rising part left. The
    knob is used only on its rising (capacitive) part, from its minimum stop to the setting
    that reaches the top of that range.
    """
    split = tank.split
    assert split is not None
    trimmer = split.trimmer
    inductance = split.series_inductance_h
    frequency = tank.tuning_frequency_hz
    omega = TWO_PI * frequency
    relied = trimmer_range_f(trimmer, inductance, frequency, q, reference_hz)
    low = trimmer.cmin_max_f
    branch_top = min(trimmer.cmax_min_f, capacitive_branch_top(inductance, omega, q, reference_hz))

    def susceptance(setting: float) -> float:
        return trimmer_admittance(setting, inductance, omega, q, reference_hz).imag

    # The rising part's top (just short of the pole when lossless and the knob reaches the
    # series resonance), and the setting that reaches the range's top on it.
    if q is None and branch_top < trimmer.cmax_min_f:
        branch_top = math.nextafter(branch_top, 0.0)
    if branch_top <= low:
        knob_high = low
    elif relied is None or susceptance(branch_top) <= relied[1] * omega:
        knob_high = branch_top
    else:
        knob_high = _bisect(susceptance, relied[1] * omega, low, branch_top)
    return TrimmerPlan(
        tank=tank.name,
        node=tank.node,
        trimmer_element=f"{TRIMMER_PREFIX}{element.name}",
        series_inductance_h=inductance,
        knob_f=(low, knob_high),
        range_f=relied,
        frequency_hz=frequency,
        target_susceptance_s=tank.target_susceptance_s,
        q=q,
        reference_hz=reference_hz,
    )


def _setting(circuit: NamedCircuit, plan: TrimmerPlan, tuning: TuningPlan) -> TrimmerSetting:
    rest = node_susceptance(
        circuit, plan.node, plan.frequency_hz, tuning.tank_nodes, tuning.ports, plan.excluded
    )
    needed = plan.target_susceptance_s - rest
    omega = TWO_PI * plan.frequency_hz
    low, high = plan.knob_f
    low_b, high_b = plan.susceptance(low), plan.susceptance(high)
    # In range: inside the range relied on under the build's Q.
    in_range = False
    if plan.range_f is not None:
        range_low, range_high = (value * omega for value in plan.range_f)
        margin = _RANGE_TOLERANCE * max(abs(range_low), abs(range_high))
        in_range = range_low - margin <= needed <= range_high + margin
    if needed <= low_b:
        setting = low
    elif needed >= high_b:
        setting = high
    else:
        setting = _bisect(plan.susceptance, needed, low, high)
    return TrimmerSetting(
        tank=plan.tank,
        required_f=needed / omega,
        setting_f=setting,
        effective_f=plan.susceptance(setting) / omega,
        in_range=in_range,
    )


def tune(
    circuit: NamedCircuit, tuning: TuningPlan
) -> tuple[NamedCircuit, tuple[TrimmerSetting, ...]]:
    """Set every trimmer of ``circuit``; return the tuned circuit and the settings.

    Each tank's setting depends only on the branches at its node, and a trimmer is a
    branch to ground, so the tanks are tuned independently.
    """
    settings = tuple(_setting(circuit, plan, tuning) for plan in tuning.trimmers)
    by_element = {
        plan.trimmer_element: (plan, setting) for plan, setting in zip(tuning.trimmers, settings)
    }
    elements = []
    for element in circuit.elements:
        if element.name in by_element:
            plan, setting = by_element[element.name]
            resistance = _trimmer_resistance(setting.setting_f, plan.q, plan.reference_hz)
            element = replace(element, value=setting.setting_f, series_resistance_ohm=resistance)
        elements.append(element)
    return replace(circuit, elements=tuple(elements)), settings
