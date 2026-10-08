"""Outcome of one ``design()`` call."""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from typing import TYPE_CHECKING

from ..shared.eseries import DEFAULT_MATCH_POLICY, MatchPolicy

if TYPE_CHECKING:
    from ..shared.build_types import BuildAnalysisResult


@dataclass(frozen=True)
class DesignResult:
    """Synthesis result plus the optional realized-build analysis.

    ``result`` is the unchanged calculator dict that every formatter consumes.
    ``warnings`` repeats the bandpass design warnings (always empty for ladders) so a
    surface can show them without knowing the dict layout. ``allow_sub_pf`` is the
    request's switch combined with the build config's, and sets the capacitor match
    policy for every later output.
    """

    category: str
    result: dict
    warnings: tuple[str, ...] = field(default_factory=tuple)
    build_analysis: BuildAnalysisResult | None = None
    allow_sub_pf: bool = False

    @property
    def match_policy(self) -> MatchPolicy:
        """The E-series match policy for this design's standard capacitor choices."""
        return replace(DEFAULT_MATCH_POLICY, allow_sub_pf=self.allow_sub_pf)
