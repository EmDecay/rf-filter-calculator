"""Format screened toroid winding candidates as text, JSON, and CSV.

Pure formatters, no I/O.  Every format keeps the boundary explicit: integer
turns and winding capacity are screened; RF Q, SRF, loss, saturation, thermal
rise, and power handling are not assessed.
"""

from .formatting import format_frequency, format_inductance
from .toroid_core_data import ToroidCore, get_source
from .toroid_selection import ToroidRecommendation

CSV_TOROID_HEADER: list[str] = [
    "ToroidCore",
    "ToroidMix",
    "ToroidTurns",
    "ToroidAWG",
    "ToroidActualL_uH",
    "ToroidErrorPct",
    "ToroidWireLength_mm",
    "ToroidDCR_mohm",
    "ToroidWireDCRReactanceRatioCeiling",
    "ToroidTempCoeff_ppm",
    "ToroidCandidateStatus",
    "ToroidProvenanceStatus",
    "ToroidCoreSourceURL",
    "ToroidFrequencySourceURL",
    "ToroidMechanicalStatus",
    "ToroidMechanicalSourceURL",
    "ToroidRFQStatus",
    "ToroidSRFStatus",
    "ToroidPowerStatus",
    "ToroidWarnings",
]

_EMPTY_MSG = (
    "  No iron-powder winding candidate with primary-verified core data covers "
    "this frequency and published capacity screen."
)


def _dcr_display(ohm: float) -> str:
    """Format DC resistance: mΩ below 1 Ω, plain Ω above."""
    if ohm < 1.0:
        return f"{ohm * 1000.0:.1f} mΩ"
    return f"{ohm:.3f} Ω"


def _source_url(source_id: str | None) -> str:
    return get_source(source_id).url if source_id else ""


def _source_payload(source_id: str | None) -> dict | None:
    if source_id is None:
        return None
    source = get_source(source_id)
    return {
        "source_id": source.source_id,
        "publisher": source.publisher,
        "source_type": source.source_type,
        "title": source.title,
        "url": source.url,
        "accessed_on": source.accessed_on,
    }


def _fmt_core_title(rec: ToroidRecommendation) -> str:
    core = rec.core
    return (
        f"{core.name} screened candidate  "
        f"({core.color_code}, mix {core.mix}, {core.temp_coeff_ppm_per_c:g} ppm/°C)"
    )


def _fmt_turns_line(rec: ToroidRecommendation) -> str:
    winding = rec.winding
    mechanical = rec.mechanical
    sign = "+" if winding.error_pct >= 0 else ""
    return (
        f"     Turns: {winding.n_turns} of AWG {mechanical.awg}   "
        f"Actual L: {format_inductance(winding.l_actual_h)}  "
        f"({sign}{winding.error_pct:.2f}%)"
    )


def _fmt_l_range(rec: ToroidRecommendation) -> str:
    winding = rec.winding
    return (
        f"     L range (A_L ±{rec.core.al_tolerance_pct:g}%): "
        f"{format_inductance(winding.l_min_h)} – {format_inductance(winding.l_max_h)}"
    )


def _fmt_wire_line(rec: ToroidRecommendation) -> str:
    mechanical = rec.mechanical
    return (
        f"     Wire: {mechanical.wire_length_mm:.0f} mm of AWG {mechanical.awg} "
        f"({mechanical.wire_diameter_mm:.3f} mm)   DCR: "
        f"{_dcr_display(mechanical.dc_resistance_ohm)}   "
        f"Capacity: {mechanical.capacity_status}"
    )


def _fmt_assessment_line(rec: ToroidRecommendation) -> str:
    q_status = rec.q_status.replace("_", " ")
    srf_status = rec.srf_status.replace("_", " ")
    power_status = rec.power_status.replace("_", " ")
    return (
        "     Wire-only ωL/Rdc ceiling: "
        f"{rec.wire_dcr_reactance_ratio_ceiling:,.0f} @ "
        f"{format_frequency(rec.design_freq_hz)}; RF Q: {q_status}; "
        f"SRF/power: {srf_status}/{power_status}"
    )


def _fmt_dims_line(core: ToroidCore) -> str:
    source = get_source(core.core_source_id) if core.core_source_id else None
    provenance = source.publisher if source else "source unavailable"
    return (
        f"     Dims: {core.od_mm:.2f} × {core.id_mm:.2f} × {core.height_mm:.2f} mm "
        f"(OD × ID × H); data: {core.provenance_status} ({provenance})"
    )


def _fmt_compact_line(idx: int, rec: ToroidRecommendation) -> str:
    winding = rec.winding
    mechanical = rec.mechanical
    sign = "+" if winding.error_pct >= 0 else ""
    dcr_milliohm = mechanical.dc_resistance_ohm * 1000.0
    return (
        f"  {idx}. {rec.core.name:<8} "
        f"N={winding.n_turns} AWG{mechanical.awg} "
        f"L={winding.l_actual_h * 1e6:.3f}µH ({sign}{winding.error_pct:.2f}%) "
        f"Rdc={dcr_milliohm:.0f}mΩ ωL/Rdc≤"
        f"{rec.wire_dcr_reactance_ratio_ceiling:,.0f} "
        "[RF Q/SRF/power not assessed]"
    )


def format_recommendation_block(
    label: str,
    l_target_h: float,
    design_freq_hz: float,
    recs: list[ToroidRecommendation],
) -> list[str]:
    """Full multi-line block per inductor."""
    lines = [
        f"  {label} target: {format_inductance(l_target_h)}  "
        f"(design freq {format_frequency(design_freq_hz)})",
        "  " + "─" * 60,
    ]
    if not recs:
        lines.append(_EMPTY_MSG)
        return lines
    for idx, rec in enumerate(recs, start=1):
        lines.append(f"  {idx}. {_fmt_core_title(rec)}")
        lines.append(_fmt_turns_line(rec))
        lines.append(_fmt_l_range(rec))
        lines.append(_fmt_wire_line(rec))
        lines.append(_fmt_assessment_line(rec))
        lines.append(_fmt_dims_line(rec.core))
    return lines


def format_recommendation_block_compact(
    label: str,
    l_target_h: float,
    design_freq_hz: float,
    recs: list[ToroidRecommendation],
) -> list[str]:
    """Condensed one-line-per-candidate view."""
    lines = [
        f"  {label} target: {format_inductance(l_target_h)} @ {format_frequency(design_freq_hz)}"
    ]
    if not recs:
        lines.append(_EMPTY_MSG)
        return lines
    for idx, rec in enumerate(recs, start=1):
        lines.append(_fmt_compact_line(idx, rec))
    return lines


def build_json_recommendations(recs: list[ToroidRecommendation]) -> list[dict]:
    """Build JSON-serializable screened-candidate records."""
    output = []
    for idx, recommendation in enumerate(recs, start=1):
        core = recommendation.core
        winding = recommendation.winding
        mechanical = recommendation.mechanical
        output.append(
            {
                "rank": idx,
                "candidate_status": recommendation.candidate_status,
                "core": {
                    "name": core.name,
                    "manufacturer": core.manufacturer,
                    "manufacturer_part_number": core.manufacturer_part_number,
                    "mix": core.mix,
                    "color_code": core.color_code,
                    "od_mm": core.od_mm,
                    "id_mm": core.id_mm,
                    "height_mm": core.height_mm,
                    "al_nh_per_turn2": core.al_nh_per_turn2,
                    "al_tolerance_pct": core.al_tolerance_pct,
                    "temp_coeff_ppm_per_c": core.temp_coeff_ppm_per_c,
                    "freq_min_hz": core.freq_min_hz,
                    "freq_max_hz": core.freq_max_hz,
                    "provenance_status": core.provenance_status,
                    "core_source": _source_payload(core.core_source_id),
                    "frequency_source": _source_payload(core.frequency_source_id),
                    "frequency_guidance_kind": core.frequency_guidance_kind,
                },
                "winding": {
                    "turns": winding.n_turns,
                    "l_target_henries": winding.l_target_h,
                    "l_actual_henries": winding.l_actual_h,
                    "error_pct": winding.error_pct,
                    "l_min_henries": winding.l_min_h,
                    "l_max_henries": winding.l_max_h,
                    "turn_options": [
                        {
                            "turns": option.n_turns,
                            "l_actual_henries": option.l_actual_h,
                            "error_pct": option.error_pct,
                        }
                        for option in winding.turn_options
                    ],
                    "selected_reason": winding.selected_reason,
                },
                "wire": {
                    "awg": mechanical.awg,
                    "diameter_mm": mechanical.wire_diameter_mm,
                    "length_mm": mechanical.wire_length_mm,
                    "dc_resistance_ohm": mechanical.dc_resistance_ohm,
                    "dcr_method": mechanical.dcr_method,
                    "n_max": mechanical.n_max,
                    "fits": mechanical.fits,
                    "capacity_status": mechanical.capacity_status,
                    "capacity_source": _source_payload(mechanical.capacity_source_id),
                    "winding_style": mechanical.winding_style,
                    "single_layer_capacity": mechanical.single_layer_capacity,
                    "full_winding_capacity": mechanical.full_winding_capacity,
                },
                "wire_dcr_reactance_ratio_ceiling": (
                    recommendation.wire_dcr_reactance_ratio_ceiling
                ),
                # Deprecated compatibility alias.  The assessment block below
                # explicitly prevents interpreting this wire-only ratio as RF Q.
                "q_dc_upper_bound": recommendation.q_dc_upper_bound,
                "design_freq_hz": recommendation.design_freq_hz,
                "assessments": {
                    "frequency_guidance": {"status": recommendation.frequency_status},
                    "mechanical_capacity": {"status": mechanical.capacity_status},
                    "rf_q": {
                        "status": recommendation.q_status,
                        "note": "ωL/Rdc is a wire-only diagnostic ceiling, not RF Q.",
                    },
                    "srf": {"status": recommendation.srf_status},
                    "power": {"status": recommendation.power_status},
                },
                "warnings": list(recommendation.warnings),
            }
        )
    return output


def csv_columns_for_best(recs: list[ToroidRecommendation]) -> list[str]:
    """CSV columns for the best-ranked candidate, or blanks when unavailable."""
    if not recs:
        return [""] * len(CSV_TOROID_HEADER)
    recommendation = recs[0]
    core = recommendation.core
    winding = recommendation.winding
    mechanical = recommendation.mechanical
    return [
        core.name,
        core.mix,
        str(winding.n_turns),
        str(mechanical.awg),
        f"{winding.l_actual_h * 1e6:.4f}",
        f"{winding.error_pct:.2f}",
        f"{mechanical.wire_length_mm:.1f}",
        f"{mechanical.dc_resistance_ohm * 1000:.2f}",
        f"{recommendation.wire_dcr_reactance_ratio_ceiling:.0f}",
        f"{core.temp_coeff_ppm_per_c:g}",
        recommendation.candidate_status,
        core.provenance_status,
        _source_url(core.core_source_id),
        _source_url(core.frequency_source_id),
        mechanical.capacity_status,
        _source_url(mechanical.capacity_source_id),
        recommendation.q_status,
        recommendation.srf_status,
        recommendation.power_status,
        "; ".join(recommendation.warnings),
    ]
