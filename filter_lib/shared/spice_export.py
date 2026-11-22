"""Generic finite SPICE decks from the authoritative named circuits."""

from __future__ import annotations

import math
import unicodedata

from .build_response import build_frequency_grid, evaluation_ports
from .build_types import (
    BuildConfig,
    ComponentSubstitution,
    NominalRealization,
    resolve_build_config,
)
from .capacitor_choice import assumed_tolerance_pct
from .circuit_builders import build_named_circuit
from .circuit_display_names import (
    SELF_CAPACITANCE_PREFIX,
    STRAY_PREFIX,
    TRIMMER_INDUCTANCE_PREFIX,
    TRIMMER_PREFIX,
    series_inductance_name,
    spice_names_comment,
)
from .circuit_model import CircuitElement
from .component_realization import FIXED_PLUS_TRIMMER_METHOD
from .eseries import TOLERANCE_NOT_SOURCED, MatchPolicy
from .inductor_suggestion import (
    KIND_LABELS,
    NO_QUALIFYING_SUGGESTION,
    SUGGESTED_INDUCTOR_METHOD,
    SUGGESTIONS_NOT_USED,
)
from .nominal_realization import (
    applicable_part_limitations,
    grouped_part_warnings,
    realize_nominal_build,
)
from .numeric import require_positive_finite
from .resolved_parts import ResolvedParts


def _number(value: float) -> str:
    require_positive_finite(value, "SPICE values")
    return f"{value:.12g}"


# SPICE readers differ in how they treat non-ASCII bytes, even in comments, so the
# deck is kept plain ASCII; the readable symbols used in table text map to these.
# Ohm and micro have two code points each (the sign and the Greek letter).
_ASCII_REPLACEMENTS = str.maketrans(
    {
        "–": "-",
        "−": "-",
        "Ω": "ohm",
        "\u2126": "ohm",
        "µ": "u",
        "\u03bc": "u",
        "±": "+/-",
        "×": "x",
        "≤": "<=",
        "≥": ">=",
    }
)


def _ascii_text(text: str) -> str:
    """Return ``text`` as ASCII: the symbols above, then accents dropped (NFKD).

    Any other character becomes "?", so new wording can never break an export.
    """
    decomposed = unicodedata.normalize("NFKD", text.translate(_ASCII_REPLACEMENTS))
    plain = "".join(char for char in decomposed if not unicodedata.combining(char))
    return plain.translate(_ASCII_REPLACEMENTS).encode("ascii", "replace").decode("ascii")


def _comment(text: str) -> str:
    return " ".join(_ascii_text(text).splitlines())


def _element_lines(element: CircuitElement) -> list[str]:
    """One element, with its series resistance and series inductance in series after it."""
    value = _number(element.value)
    chain = []
    if element.series_resistance_ohm:
        chain.append(
            (f"RLOSS{element.name}", f"NLOSS{element.name}", element.series_resistance_ohm)
        )
    if element.series_inductance_h:
        chain.append(
            (
                series_inductance_name(element.name),
                f"NSERIES{element.name}",
                element.series_inductance_h,
            )
        )
    if not chain:
        return [f"{element.name} {element.node1} {element.node2} {value}"]
    first_node = chain[0][1]
    lines = [f"{element.name} {element.node1} {first_node} {value}"]
    for index, (name, start, part_value) in enumerate(chain):
        end = chain[index + 1][1] if index + 1 < len(chain) else element.node2
        lines.append(f"{name} {start} {end} {_number(part_value)}")
    return lines


# Plain words for the substitution method/status values; JSON keeps the enum values.
_FALLBACK_REASONS = {
    "expert_override_required": "(below 1 pF)",
    NO_QUALIFYING_SUGGESTION: "(no inductor suggestion used)",
    SUGGESTIONS_NOT_USED: "(inductor suggestions not used)",
}


def _part_description(substitution: ComponentSubstitution, eseries: str) -> str:
    if substitution.method == "e_series_single":
        return f"{eseries} single"
    if substitution.method == "e_series_parallel":
        return f"{eseries} parallel pair"
    if substitution.method == SUGGESTED_INDUCTOR_METHOD:
        return KIND_LABELS[substitution.inductor_kind].lower()
    if substitution.method == FIXED_PLUS_TRIMMER_METHOD:
        return (
            f"{eseries} fixed part plus trimmer" if substitution.physical_parts else "trimmer alone"
        )
    reason = _FALLBACK_REASONS.get(substitution.status, "(no part chosen)")
    return f"calculated value {reason}"


def _nominal_comments(
    realization: NominalRealization, eseries: str, policy: MatchPolicy
) -> list[str]:
    comments: list[str] = []
    for substitution in realization.substitutions:
        details = [
            substitution.logical_name,
            _part_description(substitution, eseries),
            f"calculated={_number(substitution.calculated_value)}",
            f"nominal={_number(substitution.nominal_value)}",
        ]
        if substitution.part_name is not None:
            details.append(f"part={substitution.part_name}")
        if substitution.turns is not None:
            details.append(f"turns={substitution.turns}")
        if substitution.stray_capacitance_f:
            details.append(f"stray={_number(substitution.stray_capacitance_f)}")
        if substitution.self_capacitance_f is not None:
            details.append(f"self-capacitance={_number(substitution.self_capacitance_f)}")
        if substitution.status == TOLERANCE_NOT_SOURCED:
            details.append(f"tolerance-not-sourced={assumed_tolerance_pct(policy):g}%-assumed")
        trimmer = substitution.trimmer
        if trimmer is not None:
            basis = "assumed" if trimmer.series_inductance_assumed else "bound-from-minimum-SRF"
            details.extend(
                (
                    f"trimmer={trimmer.part_numbers[0]}",
                    f"setting={_number(trimmer.setting.setting_f)}",
                    f"effective={_number(trimmer.setting.effective_f)}",
                    f"tank-frequency={_number(trimmer.tuning_frequency_hz)}",
                    f"series-inductance={_number(trimmer.series_inductance_h)}-{basis}",
                )
            )
        # Part names come from the packaged data, so they pass through the comment filter.
        comments.append("* part used: " + _comment(" ".join(details)))
        if substitution.stray_capacitance_f:
            across = (
                "this tank's extra parts beside its trimmer"
                if substitution.trimmer is not None
                else "this pair"
            )
            comments.append(
                f"* stray: {STRAY_PREFIX}{substitution.logical_name} is the assumed stray "
                f"across {across}, the same in every tolerance case"
            )
        if trimmer is not None:
            inductance = (
                f" in series with {TRIMMER_INDUCTANCE_PREFIX}{substitution.logical_name}, the "
                "series inductance its fit assumes"
                if trimmer.series_inductance_h
                else ""
            )
            comments.append(
                f"* trimmer: {TRIMMER_PREFIX}{substitution.logical_name} is this tank's trimmer "
                f"at its nominal setting{inductance}; the setting restores the calculated "
                "design's susceptance at the tank frequency"
            )
        if substitution.self_capacitance_f is not None:
            comments.append(
                f"* self-capacitance: {SELF_CAPACITANCE_PREFIX}{substitution.logical_name} is "
                "this inductor's self-capacitance from its minimum SRF, the same in every "
                f"tolerance case; {substitution.logical_name} is the inductance without it"
            )
    # Same rules as the table's build block: each warning once with the parts it names,
    # and the toroid caveat only when a toroid winding was used.
    comments.extend(
        f"* warning: {_comment(warning)}"
        for warning in grouped_part_warnings(realization.substitutions)
    )
    comments.extend(
        f"* limitation: {_comment(limitation)}"
        for limitation in applicable_part_limitations(realization)
    )
    return comments


def _limitations_comment(nominal: NominalRealization | None) -> str:
    if nominal is None:
        return (
            "* limitations: ideal values; no layout, parasitic, SRF, temperature, or power effects"
        )
    has_stray = any(item.stray_capacitance_f for item in nominal.substitutions)
    has_self_capacitance = any(item.self_capacitance_f for item in nominal.substitutions)
    if nominal.tuning is not None:
        stray = " the assumed stray across extra parts," if has_stray else ""
        chips = " each chip inductor's self-capacitance," if has_self_capacitance else ""
        return (
            f"* limitations: chosen parts at nominal values plus{stray}{chips} and each tank's "
            "trimmer at its nominal setting with its assumed series inductance; no other "
            "layout, parasitic (capacitor ESL, package), SRF, temperature, or power effects"
        )
    if has_self_capacitance:
        stray = " the assumed stray across each pair and" if has_stray else ""
        return (
            f"* limitations: chosen parts at nominal values plus{stray} each chip inductor's "
            "self-capacitance; no other layout, parasitic (capacitor ESL, package), SRF, "
            "temperature, or power effects"
        )
    if has_stray:
        return (
            "* limitations: chosen parts at nominal values plus the assumed stray across each "
            "pair; no other layout, parasitic, SRF, temperature, or power effects"
        )
    return (
        "* limitations: chosen parts at nominal values; no layout, parasitic, SRF, "
        "temperature, or power effects"
    )


def export_spice_deck(
    result: dict,
    category: str,
    *,
    realization: str = "exact",
    config: BuildConfig | None = None,
    parts: ResolvedParts | None = None,
) -> str:
    """Export an exact or nominal-build passive network as generic SPICE.

    The deck includes a 1 V AC Thevenin source, separate finite source/load
    resistances, a bandwidth-aware BP sweep (logarithmic for LP/HP), and losses.
    The chosen-parts deck uses the parts ``design()`` resolved (``parts``, required for
    it); the exact deck uses the calculated values.
    """
    active_config = resolve_build_config(config)
    nominal: NominalRealization | None = None
    if realization == "exact":
        circuit = build_named_circuit(result, category)
        realization_label = "calculated, lossless (exact)"
    elif realization == "nominal_build":
        if parts is None:
            raise ValueError("A chosen-parts SPICE deck needs the design's resolved parts")
        nominal = realize_nominal_build(result, category, active_config, parts=parts)
        circuit = nominal.circuit
        realization_label = "chosen parts (nominal-build)"
    else:
        raise ValueError("realization must be 'exact' or 'nominal_build'")

    source, load = evaluation_ports(result, category, active_config)
    frequency_grid = build_frequency_grid(result, category, active_config.grid_points)
    start, stop = frequency_grid[0], frequency_grid[-1]
    # Validate the complete numeric envelope before rendering any text.
    for value in (source, load, start, stop):
        _number(value)
    sweep = f".ac dec 200 {_number(start)} {_number(stop)}"
    if category == "bandpass":
        # At least 128 intervals per resonator per requested bandwidth, even
        # when that bandwidth occupies a tiny fraction of a decade.
        points = math.ceil((stop - start) / result["bw"] * 128 * result["n_resonators"]) + 1
        if not 2 <= points <= 1_000_000:
            raise ValueError("bandpass SPICE sweep exceeds the supported resolution budget")
        sweep = f".ac lin {points} {_number(start)} {_number(stop)}"

    lines = [
        "* RF Filter Calculator generic AC deck",
        f"* category: {category}",
        f"* values: {realization_label}",
        f"* printed trace: vm({circuit.out_node}) is load-node voltage, not gain in dB",
        f"* transducer gain: Gt=4*Rs/Rl*|V({circuit.out_node})/V(NSOURCE)|^2",
        _limitations_comment(nominal),
        f"* ports: input={circuit.in_node} output={circuit.out_node} ground=0 source=NSOURCE",
    ]
    names = spice_names_comment(circuit)
    if names is not None:
        lines.append(names)
    if nominal is not None:
        lines.extend(_nominal_comments(nominal, parts.eseries, parts.match_policy))
    lines.extend(
        (
            "VINPUT NSOURCE 0 AC 1",
            f"RSOURCE NSOURCE {circuit.in_node} {_number(source)}",
        )
    )
    for element in circuit.elements:
        lines.extend(_element_lines(element))
    lines.extend(
        (
            f"RLOAD {circuit.out_node} 0 {_number(load)}",
            sweep,
            f".print ac vm({circuit.out_node})",
            ".end",
        )
    )
    # Comments carry readable wording; the whole deck is made ASCII the same way.
    deck = _ascii_text("\n".join(lines) + "\n")
    lowered = deck.lower()
    if any(token in lowered.split() for token in ("nan", "inf", "+inf", "-inf")):
        raise ValueError("SPICE deck must contain only finite numeric values")
    return deck
