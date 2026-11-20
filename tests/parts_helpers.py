"""Resolved parts for tests that call a formatter or the build directly.

``design()`` resolves the parts of every real design; a test with a hand-made or
calculator result resolves them here with the same function and explicit settings.
"""

from __future__ import annotations

from filter_lib.design.part_resolution import resolve_parts_for
from filter_lib.shared.eseries import MatchPolicy
from filter_lib.shared.resolved_parts import ResolvedParts


def parts_for(
    result: dict,
    category: str,
    eseries: str | None = "E24",
    policy: MatchPolicy | None = None,
    *,
    inductor_detail: str = "best",
    build_inductors: str = "auto",
) -> ResolvedParts:
    """The parts ``design()`` would resolve for ``result`` under these settings."""
    return resolve_parts_for(
        result,
        category,
        eseries=eseries,
        policy=policy,
        inductor_detail=inductor_detail,
        build_inductors=build_inductors,
    )
