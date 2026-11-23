"""Choose chip inductors from the sourced catalog for a target inductance.

Every orderable part in ``chip_inductor_data`` is screened over the design's check
window (``srf_screen``) with its guaranteed tolerance and minimum SRF. Qualifying parts
rank by the smallest worst-case error, then by part number; the minimum Q is shown,
never used for ranking.
"""

from __future__ import annotations

from dataclasses import dataclass

from .chip_inductor_data import ChipPart, catalog_range_h, chip_parts
from .formatting import format_inductance
from .inductor_suggestion import (
    MAX_SUGGESTIONS_PER_KIND,
    SRF_GUARANTEED_MINIMUM,
    ErrorBudget,
    InductorSuggestion,
    KindSuggestions,
    PartSource,
)
from .numeric import require_positive_finite
from .srf_screen import (
    DESIGN_ALLOWANCE_PCT,
    DRIFT_ALLOWANCE_PCT,
    LIMIT_ALLOWANCE,
    LIMIT_DRIFT,
    CheckWindow,
    PartModel,
    ScreenResult,
    screen_part,
)

# Stated once per table section and with every JSON/CSV suggestion and build.
CHIP_NOT_ASSESSED_WARNING = (
    "Not checked: Q (the minimum is shown, not used), current rating, heating, power "
    "handling, and the SRF once mounted on a board. Measure before use."
)
CHIP_STATUS = "qualified_by_guaranteed_limits"


@dataclass(frozen=True)
class ChipSuggestion:
    """One qualifying chip inductor: the part, its model, and its screen over the window."""

    part: ChipPart
    window: CheckWindow
    model: PartModel
    screen: ScreenResult


def _screen_catalog(
    target_h: float, window: CheckWindow
) -> tuple[list[ChipSuggestion], frozenset[str]]:
    """Every qualifying part, ranked, and the limits that rejected the others."""
    require_positive_finite(target_h, "target inductance")
    qualifying = []
    rejected: set[str] = set()
    for part in chip_parts():
        model = PartModel(part.inductance_h, part.test_frequency_hz, part.srf_min_hz)
        screen = screen_part(target_h, window, model, part.tolerance_pct)
        if screen.passed:
            qualifying.append(ChipSuggestion(part, window, model, screen))
        else:
            rejected |= screen.failed_limits
    qualifying.sort(key=lambda item: (item.screen.worst_abs_pct, item.part.part_number))
    return qualifying, frozenset(rejected)


def qualifying_chips(target_h: float, window: CheckWindow) -> list[ChipSuggestion]:
    """Every chip inductor that qualifies for ``target_h`` over ``window``, best first."""
    return _screen_catalog(target_h, window)[0]


def no_qualifying_chip_reason(rejected: frozenset[str], window: CheckWindow) -> str:
    """Why no chip inductor qualifies, naming the limit (or limits) that failed."""
    low, high = catalog_range_h()
    catalog = f"the built-in chip catalog ({format_inductance(low)} to {format_inductance(high)})"
    span = window.describe()
    allowance = (
        f"misses this inductance by more than ±{DESIGN_ALLOWANCE_PCT:g}% once its tolerance "
        "and SRF drift are counted"
    )
    drift = (
        f"drifts more than ±{DRIFT_ALLOWANCE_PCT:g}% from its catalog value from {span} "
        "because of its self-resonance"
    )
    if rejected == {LIMIT_ALLOWANCE}:
        limit = f"every part in {catalog} {allowance} (checked from {span})"
    elif rejected == {LIMIT_DRIFT}:
        limit = f"every part in {catalog} {drift}"
    else:
        limit = f"each part in {catalog} either {drift} or {allowance}"
    return f"No chip inductor qualifies: {limit}."


def _source(part: ChipPart) -> PartSource:
    source = part.family.source
    return PartSource(
        publisher=source.publisher,
        title=f"{source.title}, {source.revision}",
        url=source.url,
    )


def _suggestion(target_h: float, rank: int, chip: ChipSuggestion) -> InductorSuggestion:
    screen = chip.screen
    assert screen.budget_pct is not None and screen.achieved_h is not None
    mismatch, tolerance, drift = screen.budget_pct
    return InductorSuggestion(
        kind="chip",
        rank=rank,
        part_name=chip.part.part_number,
        target_h=target_h,
        achieved_h=screen.achieved_h,
        tolerance_pct=chip.part.tolerance_pct,
        srf_basis=SRF_GUARANTEED_MINIMUM,
        error_budget=ErrorBudget(mismatch, tolerance, drift),
        source=_source(chip.part),
        build=chip,
        status=CHIP_STATUS,
        warnings=(CHIP_NOT_ASSESSED_WARNING,),
        part_model=chip.model,
        allowance_range_hz=screen.allowance_range_hz,
    )


def suggest_chips(target_h: float, window: CheckWindow) -> KindSuggestions:
    """Up to three chip inductors for ``target_h``, or the limit that failed."""
    qualifying, rejected = _screen_catalog(target_h, window)
    if not qualifying:
        return KindSuggestions("chip", reason_none=no_qualifying_chip_reason(rejected, window))
    return KindSuggestions(
        "chip",
        tuple(
            _suggestion(target_h, rank, chip)
            for rank, chip in enumerate(qualifying[:MAX_SUGGESTIONS_PER_KIND], start=1)
        ),
    )
