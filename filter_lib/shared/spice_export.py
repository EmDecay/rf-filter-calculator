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
from .circuit_builders import build_named_circuit
from .circuit_display_names import spice_names_comment
from .circuit_model import CircuitElement
from .nominal_realization import (
    applicable_part_limitations,
    grouped_part_warnings,
    realize_nominal_build,
)
from .numeric import is_finite_real


def _number(value: float) -> str:
    if not is_finite_real(value) or value <= 0:
        raise ValueError("SPICE values must be positive and finite")
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
    value = _number(element.value)
    if not element.series_resistance_ohm:
        return [f"{element.name} {element.node1} {element.node2} {value}"]
    internal_node = f"NLOSS{element.name}"
    return [
        f"{element.name} {element.node1} {internal_node} {value}",
        f"RLOSS{element.name} {internal_node} {element.node2} "
        f"{_number(element.series_resistance_ohm)}",
    ]


# Plain words for the substitution method/status values; JSON keeps the enum values.
_FALLBACK_REASONS = {
    "expert_override_required": "(below 1 pF)",
    "no_verified_candidate": "(no suitable toroid)",
    "candidate_screen_disabled": "(toroid windings off)",
}


def _part_description(substitution: ComponentSubstitution, eseries: str) -> str:
    if substitution.method == "e_series_single":
        return f"{eseries} single"
    if substitution.method == "e_series_parallel":
        return f"{eseries} parallel pair"
    if substitution.method == "verified_toroid_integer_turns":
        return "toroid winding"
    reason = _FALLBACK_REASONS.get(substitution.status, "(no part chosen)")
    return f"calculated value {reason}"


def _nominal_comments(realization: NominalRealization, eseries: str) -> list[str]:
    comments: list[str] = []
    for substitution in realization.substitutions:
        details = [
            substitution.logical_name,
            _part_description(substitution, eseries),
            f"calculated={_number(substitution.calculated_value)}",
            f"nominal={_number(substitution.nominal_value)}",
        ]
        if substitution.core_name is not None:
            details.append(f"core={substitution.core_name}")
        if substitution.turns is not None:
            details.append(f"turns={substitution.turns}")
        comments.append("* part used: " + " ".join(details))
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


def export_spice_deck(
    result: dict,
    category: str,
    *,
    realization: str = "exact",
    config: BuildConfig | None = None,
) -> str:
    """Export an exact or nominal-build passive network as generic SPICE.

    The deck includes a 1 V AC Thevenin source, separate finite source/load
    resistances, a bandwidth-aware BP sweep (logarithmic for LP/HP), and losses.
    """
    active_config = resolve_build_config(config)
    nominal: NominalRealization | None = None
    if realization == "exact":
        circuit = build_named_circuit(result, category)
        realization_label = "calculated, lossless (exact)"
    elif realization == "nominal_build":
        nominal = realize_nominal_build(result, category, active_config)
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
        (
            "* limitations: ideal values; no layout, parasitic, SRF, temperature, or power effects"
            if nominal is None
            else "* limitations: chosen parts at nominal values; no layout, parasitic, SRF, "
            "temperature, or power effects"
        ),
        f"* ports: input={circuit.in_node} output={circuit.out_node} ground=0 source=NSOURCE",
    ]
    names = spice_names_comment(circuit)
    if names is not None:
        lines.append(names)
    if nominal is not None:
        lines.extend(_nominal_comments(nominal, active_config.eseries))
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
