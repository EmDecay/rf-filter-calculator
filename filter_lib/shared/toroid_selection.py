"""Screen primary-sourced toroid winding candidates for a target inductance.

The screen covers material-frequency guidance, integer-turn inductance, and
manufacturer winding capacity when available.  It does not assess RF Q, core
loss, SRF, saturation, thermal rise, or power handling.
"""

import math
from dataclasses import dataclass

from .numeric import require_positive_finite
from .toroid_core_data import ToroidCore, iter_auto_selectable_cores_for_frequency
from .toroid_inductance import WindingSolution, compute_ideal_turns, solve_winding
from .toroid_wire import MechanicalFit, fit_wire


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

    @property
    def ranking_key(self) -> tuple[int, int, int, float, float, str]:
        """Public deterministic key used to explain ordering in tests/exports."""
        return _sort_key(self)


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

        warnings = [
            "RF Q, core loss, SRF, saturation, thermal rise, and power handling are not assessed."
        ]
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
