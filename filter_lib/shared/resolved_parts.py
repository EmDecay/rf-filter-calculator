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

from .eseries import ESeriesMatch, MatchPolicy
from .inductor_suggestion import (
    DEFAULT_BUILD_INDUCTORS,
    DEFAULT_INDUCTOR_DETAIL,
    InductorSuggestion,
    KindSuggestions,
)


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
    """

    eseries: str | None
    match_policy: MatchPolicy
    capacitors: Mapping[str, ESeriesMatch] = field(default_factory=dict)
    inductors: Mapping[str, InductorParts] = field(default_factory=dict)
    inductor_detail: str = DEFAULT_INDUCTOR_DETAIL
    build_inductors: str = DEFAULT_BUILD_INDUCTORS

    def __post_init__(self) -> None:
        # Own copies, so a caller's later change to its mapping cannot reach the parts.
        object.__setattr__(self, "capacitors", dict(self.capacitors))
        object.__setattr__(self, "inductors", dict(self.inductors))

    @property
    def shows_suggestions(self) -> bool:
        """Whether outputs list inductor suggestions (every detail but ``none``)."""
        return self.inductor_detail != "none"

    def capacitor(self, name: str) -> ESeriesMatch:
        """The standard-value choice of capacitor ``name`` (a circuit element name)."""
        if self.eseries is None:
            raise ValueError("No standard capacitor values were chosen for this design")
        return self.capacitors[name]

    def inductor(self, name: str) -> InductorParts:
        """The suggestions and build part of inductor ``name`` (a circuit element name)."""
        return self.inductors[name]
