"""Format toroid winding suggestions as text, JSON, and CSV.

Pure formatters, no I/O.  Every format keeps the boundary explicit: the rated
frequency range, whole-turn inductance, and wire fit are checked; RF Q, core
loss, SRF, saturation, heating, and power handling are not.  Table text maps
the enum values (capacity and provenance status) to plain labels; JSON and CSV
keep the raw values.
"""

from collections.abc import Sequence

from .display_helpers import SECTION_RULE
from .formatting import format_fixed, format_frequency, format_inductance
from .toroid_core_data import ToroidCore, get_source
from .toroid_selection import NOT_ASSESSED_WARNING, ToroidRecommendation, recommend_cores

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

# Section name, also used by the inductor note that points at the section.
TOROID_SECTION_NAME = "Toroid Winding Suggestions"
TOROID_SECTION_HEADING = f"{TOROID_SECTION_NAME} (iron-powder T-series)"
CHECKED_LINE = (
    "Checked: rated frequency range, whole-turn inductance within A_L tolerance, wire fit."
)

_TURN_ERROR_NOTE = "% vs target: error from rounding to whole turns."
# The compact line has no room for "vs target" after the percentage, so its legend says it.
_COMPACT_TURN_ERROR_NOTE = "% in parentheses: error vs target from rounding to whole turns."

# A core is rejected for any of the three checked reasons, so the message names all three.
_EMPTY_LINES = [
    "  No suitable core in the built-in list. A core must be rated for this frequency,",
    "  reach this inductance within its A_L tolerance using whole turns, and fit the",
    "  winding. Choose a core manually.",
]

# Table labels for toroid_wire capacity statuses (JSON/CSV keep the raw values).
# "manufacturer_exceeded" never reaches the table: such cores are excluded.
_CAPACITY_LABELS = {
    "manufacturer_single_layer": "single layer (datasheet)",
    "manufacturer_full_winding": "full winding (datasheet)",
    "estimated": "estimated from core size",
}

# Table labels for core-data source types (JSON/CSV keep the raw values).
_SOURCE_TYPE_LABELS = {
    "manufacturer_datasheet": "datasheet",
    "manufacturer_material_table": "material table",
    "official_distributor_material_guide": "distributor material guide",
    "legacy_secondary_snapshot": "secondary data",
}

_INDUCTOR_NOTE = "Inductors: no standard values; wind to the calculated value"


def inductor_note_line(points_to_suggestions: bool) -> str:
    """Footnote under the component table, shared by LP/HP and bandpass.

    Args:
        points_to_suggestions: True when the toroid section is shown and holds at
            least one suggestion, so the pointer names a section that has content.
    """
    if points_to_suggestions:
        return f"{_INDUCTOR_NOTE} (see {TOROID_SECTION_NAME})."
    return f"{_INDUCTOR_NOTE}."


def has_winding_suggestion(inductances_h: Sequence[float], design_freq_hz: float) -> bool:
    """True when at least one inductance gets a toroid winding suggestion."""
    return any(recommend_cores(value, design_freq_hz, top_n=1) for value in inductances_h)


def _plain_label(value: str, labels: dict[str, str]) -> str:
    """Map an enum value to its table label; an unknown value reads with spaces."""
    return labels.get(value, value.replace("_", " "))


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
        f"{core.name}  "
        f"(mix {core.mix}, {core.color_code.lower()}, {core.temp_coeff_ppm_per_c:g} ppm/°C)"
    )


def _fmt_error_pct(error_pct: float) -> str:
    """Signed two-decimal turn error; a tiny negative error prints as +0.00, not -0.00."""
    return f"{format_fixed(error_pct, 2, explicit_sign=True)}%"


def _fmt_turns_line(rec: ToroidRecommendation) -> str:
    winding = rec.winding
    mechanical = rec.mechanical
    return (
        f"     {winding.n_turns} turns of AWG {mechanical.awg}   "
        f"L: {format_inductance(winding.l_actual_h)} "
        f"({_fmt_error_pct(winding.error_pct)} vs target)"
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
        f"({mechanical.wire_diameter_mm:.3f} mm dia.)   DCR: "
        f"{_dcr_display(mechanical.dc_resistance_ohm)}   "
        f"Fit: {_plain_label(mechanical.capacity_status, _CAPACITY_LABELS)}"
    )


def _fmt_q_limit_line(rec: ToroidRecommendation) -> str:
    """ωL/DCR from the copper DC resistance alone: an upper bound, never a Q estimate."""
    return (
        "     Q limit from wire DCR alone (ωL/DCR): "
        f"{rec.wire_dcr_reactance_ratio_ceiling:,.0f} at "
        f"{format_frequency(rec.design_freq_hz)}. Real Q is lower."
    )


def _fmt_size_line(core: ToroidCore) -> str:
    source = get_source(core.core_source_id) if core.core_source_id else None
    if source is None:
        provenance = "unavailable"
    else:
        provenance = f"{source.publisher} {_plain_label(source.source_type, _SOURCE_TYPE_LABELS)}"
    return (
        f"     Size: {core.od_mm:.2f} × {core.id_mm:.2f} × {core.height_mm:.2f} mm "
        f"(OD × ID × H)   Source: {provenance}"
    )


def _fmt_compact_line(idx: int, rec: ToroidRecommendation) -> str:
    winding = rec.winding
    mechanical = rec.mechanical
    return (
        f"  {idx}. {rec.core.name:<8} "
        f"{winding.n_turns} turns AWG {mechanical.awg}   "
        f"{format_inductance(winding.l_actual_h)} ({_fmt_error_pct(winding.error_pct)})   "
        f"DCR {_dcr_display(mechanical.dc_resistance_ohm)}   "
        f"Q limit (wire DCR): {rec.wire_dcr_reactance_ratio_ceiling:,.0f}"
    )


def _fmt_target_line(label: str, l_target_h: float, design_freq_hz: float) -> str:
    """Target line, identical in the full and compact views."""
    return (
        f"  {label} target: {format_inductance(l_target_h)} at {format_frequency(design_freq_hz)}"
    )


def format_recommendation_block(
    label: str,
    l_target_h: float,
    design_freq_hz: float,
    recs: list[ToroidRecommendation],
) -> list[str]:
    """Full multi-line block per inductor."""
    lines = [
        _fmt_target_line(label, l_target_h, design_freq_hz),
        # Indented sub-rule ends in the same column as SECTION_RULE.
        "  " + SECTION_RULE[2:],
    ]
    if not recs:
        lines.extend(_EMPTY_LINES)
        return lines
    for idx, rec in enumerate(recs, start=1):
        lines.append(f"  {idx}. {_fmt_core_title(rec)}")
        lines.append(_fmt_turns_line(rec))
        lines.append(_fmt_l_range(rec))
        lines.append(_fmt_wire_line(rec))
        lines.append(_fmt_q_limit_line(rec))
        lines.append(_fmt_size_line(rec.core))
    return lines


def format_recommendation_block_compact(
    label: str,
    l_target_h: float,
    design_freq_hz: float,
    recs: list[ToroidRecommendation],
) -> list[str]:
    """Condensed one-line-per-candidate view."""
    lines = [_fmt_target_line(label, l_target_h, design_freq_hz)]
    if not recs:
        lines.extend(_EMPTY_LINES)
        return lines
    for idx, rec in enumerate(recs, start=1):
        lines.append(_fmt_compact_line(idx, rec))
    return lines


def format_winding_candidate_section(
    targets: Sequence[tuple[str, float]],
    design_freq_hz: float,
    compact: bool = False,
    top_n: int = 1,
) -> list[str]:
    """Build the table-output toroid section shared by CLI and wizard renderers.

    Args:
        targets: ``(label, inductance_h)`` per block; band-pass passes a single
            shared ``L_resonant`` entry, LP/HP one entry per inductor.
        design_freq_hz: Frequency used for core gating and ωL/Rdc ceilings.
        compact: One line per candidate instead of the multi-line block.
        top_n: Maximum suggestions per target (1 by default, 3 for the
            "full" detail level).

    Returns:
        Lines starting with a blank separator and ending with a blank line
        after each target block.
    """
    formatter = format_recommendation_block_compact if compact else format_recommendation_block
    blocks = [
        (label, inductance_h, recommend_cores(inductance_h, design_freq_hz, top_n=top_n))
        for label, inductance_h in targets
    ]
    lines = [
        "",
        TOROID_SECTION_HEADING,
        SECTION_RULE,
        CHECKED_LINE,
        NOT_ASSESSED_WARNING,
    ]
    if compact:
        if any(recs for _label, _l, recs in blocks):
            lines.append(_COMPACT_TURN_ERROR_NOTE)
    else:
        tolerances = {rec.core.al_tolerance_pct for _label, _l, recs in blocks for rec in recs}
        if len(tolerances) == 1:
            lines.append(_TURN_ERROR_NOTE)
            lines.append(
                f"L range: the same turns across the core's ±{tolerances.pop():g}% A_L tolerance."
            )
        elif tolerances:
            lines.append(_TURN_ERROR_NOTE)
            lines.append("L range: the same turns across each core's A_L tolerance.")
    lines.append("")
    for label, inductance_h, recs in blocks:
        lines.extend(formatter(label, inductance_h, design_freq_hz, recs))
        lines.append("")
    return lines


def build_json_recommendations(recs: list[ToroidRecommendation]) -> list[dict]:
    """Build JSON-serializable winding-suggestion records (raw enum values kept)."""
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
                        "note": "ωL/DCR uses the wire's DC resistance only; it is an upper limit, not RF Q.",
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
        format_fixed(winding.error_pct, 2),
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
