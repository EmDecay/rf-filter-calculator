"""Outcome of one ``design()`` call."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ..shared.build_types import BuildAnalysisResult


@dataclass(frozen=True)
class DesignResult:
    """Synthesis result plus the optional realized-build analysis.

    ``result`` is the unchanged calculator dict that every formatter consumes.
    ``warnings`` repeats the bandpass design warnings (always empty for ladders) so a
    surface can show them without knowing the dict layout.
    """

    category: str
    result: dict
    warnings: tuple[str, ...] = field(default_factory=tuple)
    build_analysis: BuildAnalysisResult | None = None
