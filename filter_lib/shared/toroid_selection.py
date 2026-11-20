"""Screen primary-sourced toroid winding candidates for a target inductance.

The screen covers material-frequency guidance, integer-turn inductance, and
manufacturer winding capacity when available.  It does not assess RF Q, core
loss, SRF, saturation, thermal rise, or power handling.
"""

import math
from dataclasses import dataclass

from .formatting import format_frequency
from .inductor_suggestion import (
    MAX_SUGGESTIONS_PER_KIND,
    SRF_NOT_CHECKED,
    VHF_TOROID_EXCLUSION,
    ErrorBudget,
    InductorSuggestion,
    KindSuggestions,
    PartSource,
)
from .numeric import require_positive_finite
from .toroid_core_data import (
    ToroidCore,
    get_source,
    iter_auto_selectable_cores_for_frequency,
    list_cores,
)
from .toroid_inductance import WindingSolution, compute_ideal_turns, solve_winding
from .toroid_wire import MechanicalFit, fit_wire

# Stated once per table section and once per JSON/CSV candidate.
NOT_ASSESSED_WARNING = (
    "Not checked: RF Q, core loss, SRF, saturation, heating, power handling. Measure before use."
)


@dataclass(frozen=True)
class ToroidRecommendation:
    """Backward-compatible name for one ranked, explicitly limited candidate."""

    core: ToroidCore
    winding: WindingSolution
    mechanical: MechanicalFit
    wire_dcr_reactance_ratio_ceiling: float
    design_freq_hz: float
    candidate_status: str = "screened_candidate"
    frequency_status: str = "within_published_guidance"
    q_status: str = "not_assessed"
    srf_status: str = "not_assessed"
    power_status: str = "not_assessed"
    warnings: tuple[str, ...] = ()

    @property
    def q_dc_upper_bound(self) -> float:
        """Legacy API alias; this ratio is not a measured or predicted RF Q."""
        return self.wire_dcr_reactance_ratio_ceiling


def _wire_dcr_reactance_ratio_ceiling(l_actual_h: float, freq_hz: float, r_dc_ohm: float) -> float:
    """Compute ωL/Rdc as a wire-only diagnostic ceiling, not RF Q."""
    if r_dc_ohm <= 0:
        return float("inf")
    return 2.0 * math.pi * freq_hz * l_actual_h / r_dc_ohm


def _q_dc_upper_bound(l_actual_h: float, freq_hz: float, r_dc_ohm: float) -> float:
    """Compatibility wrapper for the formerly public private helper."""
    return _wire_dcr_reactance_ratio_ceiling(l_actual_h, freq_hz, r_dc_ohm)


def _accuracy_band(rec: ToroidRecommendation) -> int:
    """Group insignificant nominal-error differences before practicality ranking."""
    error = abs(rec.winding.error_pct)
    if error <= 1.0:
        return 0
    if error <= rec.core.al_tolerance_pct:
        return 1
    return 2


def _mechanical_rank(status: str) -> int:
    return {
        "manufacturer_single_layer": 0,
        "manufacturer_full_winding": 1,
        "estimated": 2,
    }.get(status, 3)


def _sort_key(rec: ToroidRecommendation) -> tuple[int, int, int, float, float, str]:
    """Accuracy band, credible winding practicality, then stable tie-breaks."""
    return (
        _accuracy_band(rec),
        _mechanical_rank(rec.mechanical.capacity_status),
        rec.winding.n_turns,
        rec.core.od_mm,
        abs(rec.winding.error_pct),
        rec.core.name,
    )


def find_core_candidates(
    l_target_h: float, design_freq_hz: float, *, top_n: int = 3
) -> list[ToroidRecommendation]:
    """Return verified winding candidates without implying RF suitability.

    Unverified legacy records are inspectable through ``toroid_core_data`` but
    never enter this automatic screen.  A manufacturer capacity exceedance is
    a hard exclusion; an unsourced geometric estimate is warning metadata only.
    """
    require_positive_finite(l_target_h, "l_target_h")
    require_positive_finite(design_freq_hz, "design_freq_hz")
    if not isinstance(top_n, int) or isinstance(top_n, bool) or top_n < 1:
        raise ValueError("top_n must be >= 1 and an integer")

    candidates: list[ToroidRecommendation] = []
    for core in iter_auto_selectable_cores_for_frequency(design_freq_hz):
        ideal_turns = compute_ideal_turns(l_target_h, core.al_nh_per_turn2)
        if ideal_turns < 1:
            one_turn_log_ratio = (
                math.log(core.al_nh_per_turn2) + math.log(1e-9) - math.log(l_target_h)
            )
            if one_turn_log_ratio > math.log1p(core.al_tolerance_pct / 100.0):
                continue
        if core.winding_table and max(1, math.floor(ideal_turns)) > max(
            row.full_winding_turns for row in core.winding_table
        ):
            continue
        winding = solve_winding(l_target_h, core)
        if abs(winding.error_pct) > core.al_tolerance_pct:
            continue
        mechanical = fit_wire(core, winding.n_turns)
        if mechanical.capacity_status == "manufacturer_exceeded":
            continue

        warnings = [NOT_ASSESSED_WARNING]
        if mechanical.capacity_status == "estimated":
            warnings.append(
                "Mechanical capacity is a geometry estimate and was not used as an exclusion."
            )
        ceiling = _wire_dcr_reactance_ratio_ceiling(
            winding.l_actual_h,
            design_freq_hz,
            mechanical.dc_resistance_ohm,
        )
        candidates.append(
            ToroidRecommendation(
                core=core,
                winding=winding,
                mechanical=mechanical,
                wire_dcr_reactance_ratio_ceiling=ceiling,
                design_freq_hz=design_freq_hz,
                warnings=tuple(warnings),
            )
        )

    candidates.sort(key=_sort_key)
    return candidates[:top_n]


def recommend_cores(
    l_target_h: float, design_freq_hz: float, *, top_n: int = 3
) -> list[ToroidRecommendation]:
    """Compatibility wrapper returning screened candidates, not suitability claims."""
    return find_core_candidates(l_target_h, design_freq_hz, top_n=top_n)


# Why no toroid winding qualifies when some core is rated for the frequency: a core is
# rejected for either of the other checked reasons, so the message names all three.
NO_SUITABLE_CORE_REASON = (
    "No suitable toroid core in the built-in list. A core must be rated for this frequency, "
    "reach this inductance within its A_L tolerance using whole turns, and fit the winding. "
    "Choose a core manually."
)


def no_rated_core_reason(design_freq_hz: float) -> str:
    """Why no toroid qualifies when no built-in core is rated for ``design_freq_hz``.

    Above every automatic core's rated range the VHF exclusion says why no other core
    is offered there.
    """
    reason = f"No built-in toroid core is rated for {format_frequency(design_freq_hz)}."
    highest = max(core.freq_max_hz for core in list_cores() if core.is_auto_selectable)
    if design_freq_hz > highest:
        reason = f"{reason} {VHF_TOROID_EXCLUSION}"
    return reason


def _part_source(core: ToroidCore) -> PartSource | None:
    if core.core_source_id is None:
        return None
    source = get_source(core.core_source_id)
    return PartSource(publisher=source.publisher, title=source.title, url=source.url)


def suggest_toroids(l_target_h: float, design_freq_hz: float) -> KindSuggestions:
    """Return up to three toroid winding suggestions, or the limit that failed.

    Legacy HF windings keep their "SRF not checked" basis: the core maker publishes no
    self-resonance data, so the error budget lists no SRF drift.
    """
    candidates = find_core_candidates(l_target_h, design_freq_hz, top_n=MAX_SUGGESTIONS_PER_KIND)
    if not candidates:
        rated = any(True for _core in iter_auto_selectable_cores_for_frequency(design_freq_hz))
        reason = NO_SUITABLE_CORE_REASON if rated else no_rated_core_reason(design_freq_hz)
        return KindSuggestions("toroid", reason_none=reason)
    return KindSuggestions(
        "toroid",
        tuple(
            InductorSuggestion(
                kind="toroid",
                rank=rank,
                part_name=candidate.core.name,
                target_h=l_target_h,
                achieved_h=candidate.winding.l_actual_h,
                tolerance_pct=candidate.core.al_tolerance_pct,
                srf_basis=SRF_NOT_CHECKED,
                error_budget=ErrorBudget(
                    nominal_mismatch_pct=candidate.winding.error_pct,
                    tolerance_pct=candidate.core.al_tolerance_pct,
                ),
                source=_part_source(candidate.core),
                build=candidate,
                status=candidate.candidate_status,
                warnings=candidate.warnings,
            )
            for rank, candidate in enumerate(candidates, start=1)
        ),
    )
