"""Format toroid recommendations as text / JSON / CSV.

Pure formatters, no I/O. Callers (LP/HP/BP display.py, format_json_result,
format_csv_result) integrate the output. Supports full-block and compact
(1-line-per-rec) text modes.
"""

from .formatting import format_frequency, format_inductance
from .toroid_core_data import ToroidCore
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
    "ToroidQ_DC_Upper",
    "ToroidTempCoeff_ppm",
]

_EMPTY_MSG = "  No iron-powder T-series core covers this frequency or fits mechanically."


def _dcr_display(ohm: float) -> str:
    if ohm < 1.0:
        return f"{ohm * 1000.0:.1f} mΩ"
    return f"{ohm:.3f} Ω"


def _fmt_core_title(rec: ToroidRecommendation) -> str:
    c = rec.core
    return f"{c.name}  ({c.color_code}, mix {c.mix}, {c.temp_coeff_ppm_per_c:g} ppm/°C)"


def _fmt_turns_line(rec: ToroidRecommendation) -> str:
    w = rec.winding
    m = rec.mechanical
    sign = "+" if w.error_pct >= 0 else ""
    return (
        f"     Turns: {w.n_turns} of AWG {m.awg}   "
        f"Actual L: {format_inductance(w.l_actual_h)}  "
        f"({sign}{w.error_pct:.2f}%)"
    )


def _fmt_l_range(rec: ToroidRecommendation) -> str:
    w = rec.winding
    return (
        f"     L range (A_L ±{rec.core.al_tolerance_pct:g}%): "
        f"{format_inductance(w.l_min_h)} – {format_inductance(w.l_max_h)}"
    )


def _fmt_wire_line(rec: ToroidRecommendation) -> str:
    m = rec.mechanical
    return (
        f"     Wire: {m.wire_length_mm:.0f} mm of AWG {m.awg} "
        f"({m.wire_diameter_mm:.3f} mm)   DCR: {_dcr_display(m.dc_resistance_ohm)}"
    )


def _fmt_q_line(rec: ToroidRecommendation) -> str:
    return (
        f"     Q (DC est, upper bound): {rec.q_dc_upper_bound:,.0f} @ "
        f"{format_frequency(rec.design_freq_hz)}"
    )


def _fmt_dims_line(core: ToroidCore) -> str:
    return f"     Dims: {core.od_mm:.2f} × {core.id_mm:.2f} × {core.height_mm:.2f} mm (OD × ID × H)"


def _fmt_compact_line(idx: int, rec: ToroidRecommendation) -> str:
    w = rec.winding
    m = rec.mechanical
    sign = "+" if w.error_pct >= 0 else ""
    dcr_m = m.dc_resistance_ohm * 1000.0
    return (
        f"  {idx}. {rec.core.name:<8} "
        f"N={w.n_turns} AWG{m.awg} "
        f"L={w.l_actual_h * 1e6:.3f}µH ({sign}{w.error_pct:.2f}%) "
        f"R={dcr_m:.0f}mΩ Q≈{rec.q_dc_upper_bound:,.0f}"
    )


def format_recommendation_block(
    label: str,
    l_target_h: float,
    design_freq_hz: float,
    recs: list[ToroidRecommendation],
) -> list[str]:
    """Full multi-line block per inductor: header + rule + 6 lines x N recs."""
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
        lines.append(_fmt_q_line(rec))
        lines.append(_fmt_dims_line(rec.core))
    return lines


def format_recommendation_block_compact(
    label: str,
    l_target_h: float,
    design_freq_hz: float,
    recs: list[ToroidRecommendation],
) -> list[str]:
    """Condensed 1-line-per-rec view for --toroid-compact."""
    lines = [
        f"  {label} target: {format_inductance(l_target_h)} @ {format_frequency(design_freq_hz)}",
    ]
    if not recs:
        lines.append(_EMPTY_MSG)
        return lines
    for idx, rec in enumerate(recs, start=1):
        lines.append(_fmt_compact_line(idx, rec))
    return lines


def build_json_recommendations(recs: list[ToroidRecommendation]) -> list[dict]:
    """Build JSON-serialisable list of recommendation dicts."""
    out = []
    for idx, r in enumerate(recs, start=1):
        c, w, m = r.core, r.winding, r.mechanical
        out.append(
            {
                "rank": idx,
                "core": {
                    "name": c.name,
                    "mix": c.mix,
                    "color_code": c.color_code,
                    "od_mm": c.od_mm,
                    "id_mm": c.id_mm,
                    "height_mm": c.height_mm,
                    "al_nh_per_turn2": c.al_nh_per_turn2,
                    "al_tolerance_pct": c.al_tolerance_pct,
                    "temp_coeff_ppm_per_c": c.temp_coeff_ppm_per_c,
                    "freq_min_hz": c.freq_min_hz,
                    "freq_max_hz": c.freq_max_hz,
                },
                "winding": {
                    "turns": w.n_turns,
                    "l_target_henries": w.l_target_h,
                    "l_actual_henries": w.l_actual_h,
                    "error_pct": w.error_pct,
                    "l_min_henries": w.l_min_h,
                    "l_max_henries": w.l_max_h,
                },
                "wire": {
                    "awg": m.awg,
                    "diameter_mm": m.wire_diameter_mm,
                    "length_mm": m.wire_length_mm,
                    "dc_resistance_ohm": m.dc_resistance_ohm,
                    "n_max": m.n_max,
                    "fits": m.fits,
                },
                "q_dc_upper_bound": r.q_dc_upper_bound,
                "design_freq_hz": r.design_freq_hz,
            }
        )
    return out


def csv_columns_for_best(recs: list[ToroidRecommendation]) -> list[str]:
    """10 CSV columns for the best-ranked recommendation, or empties if none."""
    if not recs:
        return [""] * len(CSV_TOROID_HEADER)
    r = recs[0]
    return [
        r.core.name,
        r.core.mix,
        str(r.winding.n_turns),
        str(r.mechanical.awg),
        f"{r.winding.l_actual_h * 1e6:.4f}",
        f"{r.winding.error_pct:.2f}",
        f"{r.mechanical.wire_length_mm:.1f}",
        f"{r.mechanical.dc_resistance_ohm * 1000:.2f}",
        f"{r.q_dc_upper_bound:.0f}",
        f"{r.core.temp_coeff_ppm_per_c:g}",
    ]
