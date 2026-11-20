"""Outcome of one ``design()`` call."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ..shared.build_types import BuildAnalysisResult, BuildConfig
    from ..shared.eseries import MatchPolicy
    from .design_request import DesignRequest


@dataclass(frozen=True)
class DesignResult:
    """Synthesis result, the resolved part policy, and the optional build analysis.

    Only ``design()`` builds one. ``result`` is the unchanged calculator dict that every
    formatter consumes. ``warnings`` repeats the bandpass design warnings (always empty
    for ladders) so a surface can show them without knowing the dict layout.
    ``request`` is the request it answers, and ``match_policy`` the capacitor match
    policy ``design()`` resolved from it; every output (table, JSON, CSV, the build
    simulation, the chosen-parts SPICE deck) reads its parts from these, never from
    its own settings.
    """

    category: str
    result: dict
    request: DesignRequest
    match_policy: MatchPolicy
    warnings: tuple[str, ...] = field(default_factory=tuple)
    build_analysis: BuildAnalysisResult | None = None

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
        from ..shared.build_types import resolve_build_config

        return resolve_build_config(self.request.realization)
