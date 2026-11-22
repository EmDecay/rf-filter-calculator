"""The chosen parts of one design, resolved once by ``design()`` and read by every output.

``filter_lib.design.part_resolution`` builds a ``ResolvedParts`` from the request; the
table, JSON, CSV, values-only, both SPICE decks, the build simulation, and the web and
wizard documents read their capacitor choices and inductor suggestions from it and never
select parts themselves. Parts are keyed by the named circuit's element names: ``C1``
and ``L1`` for ladders; ``CT1``, ``LT1``, ``CK1``, ``CIN`` and ``COUT`` for band-pass
(``circuit_display_names`` maps them to the table names).
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from .eseries import ESeriesMatch, MatchPolicy
from .inductor_suggestion import (
    DEFAULT_BUILD_INDUCTORS,
    DEFAULT_INDUCTOR_DETAIL,
    InductorSuggestion,
    KindSuggestions,
)
from .srf_screen import CheckWindow, common_range

if TYPE_CHECKING:
    from .tank_trimmers import TankParts

# A build or deck given another design's parts (the same element names, other values).
PARTS_FROM_ANOTHER_DESIGN_MESSAGE = "The resolved parts belong to another design"


@dataclass(frozen=True)
class InductorParts:
    """One inductor's suggestions by kind, and the part the build uses.

    ``kinds`` lists every kind in the fixed order, each with its ranked suggestions or
    the limit that failed; it is empty when suggestions are off. ``build_pick`` is the
    suggestion the build simulation and the chosen-parts SPICE deck use, or ``None`` for
    the calculated value, with ``build_status`` (JSON ``status``) and ``build_note``
    (the plain reason) saying why.
    """

    name: str
    target_h: float
    kinds: tuple[KindSuggestions, ...]
    build_pick: InductorSuggestion | None
    build_status: str
    build_note: str | None = None

    @property
    def suggestions(self) -> tuple[InductorSuggestion, ...]:
        """Every suggestion, by kind in the fixed order and then by rank."""
        return tuple(item for group in self.kinds for item in group.suggestions)

    @property
    def default_pick(self) -> InductorSuggestion | None:
        """The first suggestion in the fixed order: what the default build (``auto``) uses.

        Unlike ``best`` it never depends on the build's inductor choice, so the band-pass
        tank sizing, which rests on the design alone, uses it.
        """
        suggestions = self.suggestions
        return suggestions[0] if suggestions else None

    @property
    def best(self) -> InductorSuggestion | None:
        """The suggestion "best" shows: the build pick, else the first in the fixed order."""
        if self.build_pick is not None:
            return self.build_pick
        suggestions = self.suggestions
        return suggestions[0] if suggestions else None

    def kind(self, kind: str) -> KindSuggestions:
        """The suggestions of one kind."""
        for group in self.kinds:
            if group.kind == kind:
                return group
        raise KeyError(kind)


@dataclass(frozen=True)
class ResolvedParts:
    """Every chosen part of one design and the policy that chose them.

    ``eseries`` is the standard capacitor series (``None`` for no standard values, when
    ``capacitors`` is empty); ``match_policy`` decided the capacitors.
    ``inductor_detail`` is how much of the suggestions the table shows (``none`` leaves
    them out of every output) and ``build_inductors`` what the build uses.
    ``check_window`` is the frequencies the inductor suggestions were checked over.
    ``tanks`` holds each band-pass tank's fixed-plus-trimmer sizing, keyed by its tank
    capacitor (``CT1``); empty for ladders and without standard values.
    """

    eseries: str | None
    match_policy: MatchPolicy
    capacitors: Mapping[str, ESeriesMatch] = field(default_factory=dict)
    inductors: Mapping[str, InductorParts] = field(default_factory=dict)
    inductor_detail: str = DEFAULT_INDUCTOR_DETAIL
    build_inductors: str = DEFAULT_BUILD_INDUCTORS
    check_window: CheckWindow | None = None
    tanks: Mapping[str, TankParts] = field(default_factory=dict)

    def __post_init__(self) -> None:
        # Own copies, so a caller's later change to its mapping cannot reach the parts.
        object.__setattr__(self, "capacitors", dict(self.capacitors))
        object.__setattr__(self, "inductors", dict(self.inductors))
        object.__setattr__(self, "tanks", dict(self.tanks))

    @property
    def shows_suggestions(self) -> bool:
        """Whether outputs list inductor suggestions (every detail but ``none``)."""
        return self.inductor_detail != "none"

    def qualified_range_hz(self) -> tuple[float, float] | None:
        """The frequencies at which every built part with a checked SRF is within allowance.

        ``None`` when no part in the build has its SRF checked (toroid windings and
        calculated values impose no range), so the build's figures are not limited.
        """
        return common_range(
            inductor.build_pick.allowance_range_hz
            for inductor in self.inductors.values()
            if inductor.build_pick is not None
            and inductor.build_pick.allowance_range_hz is not None
        )

    def capacitor(self, name: str) -> ESeriesMatch:
        """The standard-value choice of capacitor ``name`` (a circuit element name)."""
        if self.eseries is None:
            raise ValueError("No standard capacitor values were chosen for this design")
        return self.capacitors[name]

    def tank(self, name: str) -> TankParts | None:
        """The fixed-plus-trimmer sizing of tank capacitor ``name``, or ``None`` if unsized."""
        return self.tanks.get(name)

    def inductor(self, name: str) -> InductorParts:
        """The suggestions and build part of inductor ``name`` (a circuit element name)."""
        return self.inductors[name]

    def target(self, name: str) -> float:
        """The calculated value part ``name`` was chosen for (to check the parts' design)."""
        if name in self.inductors:
            return self.inductors[name].target_h
        return self.capacitor(name).target
