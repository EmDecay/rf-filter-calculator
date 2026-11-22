"""Outcome of one ``design()`` call."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from ..shared.build_types import resolve_build_config

if TYPE_CHECKING:
    from ..shared.build_types import BuildAnalysisResult, BuildConfig
    from ..shared.eseries import MatchPolicy
    from ..shared.resolved_parts import ResolvedParts
    from .coupling_advice import CouplingAdvice
    from .design_request import DesignRequest


@dataclass(frozen=True)
class DesignResult:
    """Synthesis result, the resolved parts, and the optional build analysis.

    Only ``design()`` builds one. ``result`` is the unchanged calculator dict that every
    formatter consumes. ``warnings`` repeats the bandpass design warnings (always empty
    for ladders) so a surface can show them without knowing the dict layout.
    ``request`` is the request it answers, and ``parts`` every part ``design()`` chose
    for it: the capacitor match policy and choices, and each inductor's suggestions and
    build part. Every output (table, JSON, CSV, the build simulation, the chosen-parts
    SPICE deck) reads its parts from ``parts``, never from its own settings.
    ``coupling_advice`` is the band-pass tank-inductance advice when a coupling capacitor
    has no part of 1 pF or more (``None`` otherwise).
    """

    category: str
    result: dict
    request: DesignRequest
    parts: ResolvedParts
    warnings: tuple[str, ...] = field(default_factory=tuple)
    build_analysis: BuildAnalysisResult | None = None
    coupling_advice: CouplingAdvice | None = None

    @property
    def match_policy(self) -> MatchPolicy:
        """The capacitor match policy ``design()`` resolved from the request."""
        return self.parts.match_policy

    @property
    def eseries(self) -> str | None:
        """The standard capacitor series, or ``None`` when no standard values are chosen."""
        return self.request.eseries

    @property
    def allow_sub_pf(self) -> bool:
        """Whether standard capacitors below 1 pF may be chosen."""
        return self.match_policy.allow_sub_pf

    @property
    def realization(self) -> BuildConfig:
        """The build settings a chosen-parts deck or build uses (the defaults when unset)."""
        return resolve_build_config(self.request.realization)
