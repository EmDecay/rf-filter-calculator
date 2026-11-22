"""The Tank Trimmers section, JSON record and CSV columns of a band-pass design.

Every surface shows the same sizing (``ResolvedParts.tanks``, sized once by ``design()``):
the table section here, the JSON ``tank_trimmers`` object and the CSV trimmer columns.
"""

from __future__ import annotations

from typing import Any

from ..shared.circuit_display_names import display_component_name, format_name_list
from ..shared.display_helpers import SECTION_RULE, wrap_keeping_units
from ..shared.formatting import (
    format_capacitance,
    format_fixed,
    format_inductance,
    format_tank_frequency,
)
from ..shared.resolved_parts import ResolvedParts
from ..shared.tank_trimmers import ASSUMED_TRIMMER_SERIES_INDUCTANCE_H, TankParts, TankSplit
from ..shared.trimmer_data import TrimmerPart

TANK_TRIMMERS_HEADING = "Tank Trimmers"
COUPLING_ADVICE_HEADING = "Coupling Advice"
_WRAP_WIDTH = 88
_INDENT = "  "


def tank_trimmer_intro(tuning_frequency_hz: float, stray_f: float, ports: str) -> str:
    """What the section's fits mean, for one design."""
    return (
        "Each tank is a fixed standard part plus a trimmer, set at the tank frequency "
        f"({format_tank_frequency(tuning_frequency_hz)}) so that the tank's susceptance matches "
        "the calculated design's. A trimmer fits when its guaranteed range contains what it "
        "must supply there: the other parts at the tank at either end of their tolerance, the "
        f"assumed {stray_f * 1e12:g} pF stray across each extra part, and the end "
        f"capacitors through {ports}. A trimmer's range is guaranteed at 200 kHz or 1 MHz, or "
        "at a frequency the maker does not state; at the tank frequency its series inductance "
        "raises it, so every fit assumes the series inductance given and is not guaranteed."
    )


def _ports_text(source_ohm: float, load_ohm: float) -> str:
    if source_ohm == load_ohm:
        return f"the {source_ohm:g} Ω source and load"
    return f"the {source_ohm:g} Ω source and the {load_ohm:g} Ω load"


def _pf(value: float) -> str:
    return format_fixed(value * 1e12, 2)


def _range(low: float, high: float) -> str:
    return f"{_pf(low)}–{_pf(high)} pF"


def series_inductance_text(split: TankSplit) -> str:
    """The series inductance a fit assumes, and where it comes from."""
    trimmer = split.trimmer
    inductance = format_inductance(split.series_inductance_h)
    if split.series_inductance_assumed:
        return f"at most {inductance} series inductance (an assumption; the maker states no bound)"
    srf = format_tank_frequency(trimmer.srf_min_at_cmax_hz)
    return (
        f"at most {inductance} series inductance (the bound from its minimum SRF of {srf} at "
        "its maximum)"
    )


def _trimmer_title(trimmer: TrimmerPart) -> str:
    alternatives = trimmer.part_numbers[1:]
    others = f" (or {', '.join(alternatives)})" if alternatives else ""
    return (
        f"{trimmer.maker} {trimmer.part_name}{others}, "
        f"{_pf(trimmer.cmin_max_f)}–{_pf(trimmer.cmax_min_f)} pF guaranteed"
    )


def _trimmer_details(trimmer: TrimmerPart) -> str:
    measured = (
        f"range guaranteed at {format_tank_frequency(trimmer.range_measured_at_hz)}"
        if trimmer.range_measured_at_hz is not None
        else "range measurement frequency not stated"
    )
    srf = f"; SRF {trimmer.srf_as_stated}" if trimmer.srf_as_stated else ""
    return (
        f"{trimmer.family}; {trimmer.mounting}; {trimmer.dielectric}, "
        f"{trimmer.working_voltage_v:g} V; Q as stated: {trimmer.q_as_stated}{srf}; {measured}."
    )


def _source_text(trimmer: TrimmerPart) -> str:
    source = trimmer.source
    return f"Source: {source.publisher}, {source.title}, {source.revision}, {trimmer.page}"


def _wrap(text: str, indent: str) -> list[str]:
    return wrap_keeping_units(
        text, _WRAP_WIDTH, initial_indent=indent, subsequent_indent=indent + "  "
    )


def assumptions_text(tank: TankParts) -> str:
    """Why a tank's need is conditional: each unsourced input, grouped by assumption."""
    groups: dict[str, list[str]] = {}
    for part, assumption in tank.need.assumptions:
        groups.setdefault(assumption, []).append(part)
    reasons = "; ".join(f"{format_name_list(parts)} ({text})" for text, parts in groups.items())
    return f"Conditional on assumed tolerances: {reasons}."


def _fixed_text(split: TankSplit) -> str:
    if not split.fixed_parts_f:
        return "no fixed part,"
    return " || ".join(format_capacitance(value) for value in split.fixed_parts_f) + " +"


def tank_lines(tank: TankParts) -> list[str]:
    """One tank's split (or why none fits), its need and its trimmer's details."""
    name = display_component_name(tank.name)
    frequency = format_tank_frequency(tank.tuning_frequency_hz)
    need = _range(tank.need.low_f, tank.need.high_f)
    split = tank.split
    if split is None:
        lines = _wrap(
            f"{name}: no packaged trimmer fits. The fixed part and trimmer together must supply "
            f"{need} at {frequency}.",
            "",
        )
    else:
        lines = _wrap(f"{name}: {_fixed_text(split)} trimmer {_trimmer_title(split.trimmer)}", "")
        lines += _wrap(
            f"Together they must supply {need} at {frequency}; the trimmer must supply "
            f"{_range(*split.required_f)}, and its range there is "
            f"{_range(*split.trimmer_range_f)}, assuming {series_inductance_text(split)}.",
            _INDENT,
        )
        lines += _wrap(_trimmer_details(split.trimmer), _INDENT)
        lines += _wrap(_source_text(split.trimmer), _INDENT)
    if tank.need.conditional:
        lines += _wrap(assumptions_text(tank), _INDENT)
    return lines


def tank_trimmer_lines(parts: ResolvedParts) -> list[str]:
    """The table's Tank Trimmers section; empty when no tank was sized."""
    tanks = list(parts.tanks.values())
    if not tanks:
        return []
    lines = [f"\n{TANK_TRIMMERS_HEADING}", SECTION_RULE]
    lines += _wrap(
        tank_trimmer_intro(
            tanks[0].tuning_frequency_hz,
            parts.match_policy.stray_capacitance_f,
            _ports_text(*tanks[0].ports_ohm),
        ),
        "",
    )
    for tank in tanks:
        lines.append("")
        lines.extend(tank_lines(tank))
    return lines


def _trimmer_payload(trimmer: TrimmerPart) -> dict[str, Any]:
    source = trimmer.source
    return {
        "maker": trimmer.maker,
        "family": trimmer.family,
        "part_numbers": list(trimmer.part_numbers),
        "cmin_maximum_f": trimmer.cmin_max_f,
        "cmax_minimum_f": trimmer.cmax_min_f,
        "range_measured_at_hz": trimmer.range_measured_at_hz,
        "srf_minimum_at_cmax_hz": trimmer.srf_min_at_cmax_hz,
        "srf_as_stated": trimmer.srf_as_stated,
        "q_as_stated": trimmer.q_as_stated,
        "dielectric": trimmer.dielectric,
        "working_voltage_v": trimmer.working_voltage_v,
        "mounting": trimmer.mounting,
        "source": {
            "id": source.source_id,
            "publisher": source.publisher,
            "title": source.title,
            "revision": source.revision,
            "url": source.url,
            "sha256": source.sha256,
            "page": trimmer.page,
        },
    }


def _split_payload(split: TankSplit) -> dict[str, Any]:
    return {
        "fixed_parts_f": list(split.fixed_parts_f),
        "fixed_tolerances_f": list(split.fixed_tolerances_f),
        "stray_f": split.stray_f,
        "trimmer": _trimmer_payload(split.trimmer),
        "series_inductance_h": split.series_inductance_h,
        "series_inductance_basis": (
            "assumed" if split.series_inductance_assumed else "bound_from_minimum_srf"
        ),
        "trimmer_range_f": list(split.trimmer_range_f),
        "required_trimmer_f": list(split.required_f),
        # Every fit rests on the stated series inductance; none is guaranteed.
        "fit": "conditional_on_series_inductance",
    }


def tank_trimmers_payload(parts: ResolvedParts) -> dict[str, Any] | None:
    """The JSON ``tank_trimmers`` object; ``None`` when no tank was sized."""
    tanks = list(parts.tanks.values())
    if not tanks:
        return None
    return {
        "tuning_frequency_hz": tanks[0].tuning_frequency_hz,
        "source_resistance_ohm": tanks[0].ports_ohm[0],
        "load_resistance_ohm": tanks[0].ports_ohm[1],
        "stray_capacitance_f": parts.match_policy.stray_capacitance_f,
        "assumed_series_inductance_h": ASSUMED_TRIMMER_SERIES_INDUCTANCE_H,
        "tanks": [
            {
                "name": display_component_name(tank.name),
                "circuit_name": tank.name,
                "target_susceptance_s": tank.target_susceptance_s,
                "need_f": [tank.need.low_f, tank.need.high_f],
                "need_basis": "conditional" if tank.need.conditional else "sourced",
                "assumptions": [
                    {"part": part, "assumption": assumption}
                    for part, assumption in tank.need.assumptions
                ],
                "fits": tank.split is not None,
                "splits": [_split_payload(split) for split in tank.splits],
            }
            for tank in tanks
        ],
    }


CSV_TRIMMER_HEADER = [
    "TankFixedParts",
    "TrimmerPart",
    "TrimmerRequiredMinPF",
    "TrimmerRequiredMaxPF",
    "TrimmerRangeMinPF",
    "TrimmerRangeMaxPF",
    "TankNeedMinPF",
    "TankNeedMaxPF",
    "TankNeedBasis",
]


def trimmer_csv_columns(tank: TankParts | None) -> list[str]:
    """One tank row's trimmer columns; blank for every other row."""
    if tank is None:
        return [""] * len(CSV_TRIMMER_HEADER)
    need = [_pf(tank.need.low_f), _pf(tank.need.high_f)]
    basis = "conditional" if tank.need.conditional else "sourced"
    split = tank.split
    if split is None:
        return ["", "", "", "", "", "", *need, basis]
    fixed = " || ".join(format_capacitance(value) for value in split.fixed_parts_f) or "none"
    return [
        fixed,
        split.trimmer.part_name,
        _pf(split.required_f[0]),
        _pf(split.required_f[1]),
        _pf(split.trimmer_range_f[0]),
        _pf(split.trimmer_range_f[1]),
        *need,
        basis,
    ]


def coupling_advice_lines(advice) -> list[str]:
    """The table's Coupling Advice section (``design/coupling_advice.py``)."""
    from ..design.coupling_advice import advice_lines_text

    lines = [f"\n{COUPLING_ADVICE_HEADING}", SECTION_RULE]
    for paragraph in advice_lines_text(advice):
        lines.extend(_wrap(paragraph, ""))
    return lines


def coupling_advice_payload(advice) -> dict[str, Any] | None:
    """The JSON ``coupling_advice`` object; ``None`` when the advice does not apply."""
    if advice is None:
        return None
    from ..design.coupling_advice import CLI_FLAG

    advised = None
    if advice.advised:
        part = advice.part
        advised = {
            "tank_inductance_h": advice.inductance_h,
            "setting": advice.setting,
            "cli": f"{CLI_FLAG} {advice.setting}",
            "inductor_kind": part.kind,
            "inductor_part": part.part_name,
            "coupling_capacitors": [
                {
                    "name": display_component_name(name),
                    "circuit_name": name,
                    "parts_f": list(match.selected_components or ()),
                }
                for name, match in advice.couplers.items()
            ],
            "response_validation_status": advice.response_validation_status,
        }
    return {
        "short_coupling_capacitors": [
            display_component_name(name) for name in advice.short_couplers
        ],
        "minimum_part_f": advice.floor_f,
        "tank_inductance_h": advice.original_inductance_h,
        "inverse_l_estimate_h": advice.estimate_h,
        "max_trials": advice.max_trials,
        "trials": [
            {
                "tank_inductance_h": trial.inductance_h,
                "setting": trial.setting,
                "every_coupling_capacitor_has_part": trial.couplers_ok,
                "suggestion_supplies_value": trial.supplied,
                "failure": trial.reason,
            }
            for trial in advice.trials
        ],
        "advised": advised,
        "reason_none": advice.reason_none,
    }
