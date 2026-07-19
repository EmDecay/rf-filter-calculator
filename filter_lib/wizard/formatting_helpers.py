"""Formatting helpers for wizard calculation output.

Contains table formatting functions for bandpass results display; LP/HP
rendering goes through shared.lp_hp_display instead, so only bandpass needs
wizard-local formatters.
"""

from .state import FilterState


def format_bandpass_eseries_recs(result: dict, eseries: str) -> list[str]:
    """Format E-series recommendations for bandpass capacitor values.

    Covers tank and coupling capacitors only — inductors are wound to value,
    so they get no standard-value matching anywhere in this project.

    Args:
        result: Bandpass result dict from calculate_bandpass_filter
        eseries: E-series name ("E12"/"E24"/"E96")

    Returns:
        Display lines listing each capacitor with its nearest standard match.
    """
    from filter_lib.shared.display_helpers import format_eseries_match
    from filter_lib.shared.formatting import format_capacitance

    lines = []
    lines.append(f"\n{eseries} Preferred-Value Capacitor Selection")
    lines.append("-" * 45)
    lines.append(
        "(Series density is not part tolerance; policy selects at most one realization; "
        "expert action may be required)"
    )
    lines.append("")

    for i, ct in enumerate(result["c_tank"]):
        lines.append(f"Cp{i + 1} Calculated: {format_capacitance(ct)}")
        for line in format_eseries_match(ct, eseries, format_capacitance, parallel_mode="additive"):
            lines.append(line)

    for label, value in _coupling_cap_items(result):
        lines.append(f"{label} Calculated: {format_capacitance(value)}")
        for line in format_eseries_match(
            value, eseries, format_capacitance, parallel_mode="additive"
        ):
            lines.append(line)

    return lines


def _coupling_cap_items(result: dict) -> list[tuple[str, float]]:
    """Coupling capacitors with end caps (when present) framing the Cs list.

    Ordering mirrors the physical circuit left-to-right (Ce_in, Cs12…, Ce_out)
    so the table and E-series sections read in the same order as the topology
    diagram.
    """
    items: list[tuple[str, float]] = []
    if result.get("c_end_in") is not None:
        items.append(("Ce_in", result["c_end_in"]))
    items.extend((f"Cs{i + 1}{i + 2}", cs) for i, cs in enumerate(result["c_coupling"]))
    if result.get("c_end_out") is not None:
        items.append(("Ce_out", result["c_end_out"]))
    return items


def format_bandpass_table(result: dict, state: FilterState) -> list[str]:
    """Format bandpass filter results as table.

    Args:
        result: Bandpass result dict from calculate_bandpass_filter
        state: Wizard state (consulted for the raw-units toggle)

    Returns:
        Display lines: design summary, warnings, Q figures, topology diagram,
        and box-drawn component tables.
    """
    from filter_lib.bandpass.diagrams import format_top_c_diagram
    from filter_lib.shared.formatting import format_capacitance, format_frequency, format_inductance

    lines = []
    coupling_name = "Top-C Coupled"
    title = f"{result['filter_type'].title()} {coupling_name} Band-Pass Filter"
    lines.append(f"\n{title}")
    lines.append("=" * 60)
    lines.append(f"Center Frequency:    {format_frequency(result['f0'])}")
    lines.append(f"Bandwidth:           {format_frequency(result['bw'])}")
    lines.append(f"Fractional BW:       {result['fbw'] * 100:.2f}%")
    lines.append(f"Impedance Z0:        {result['z0']:.4g} Ohm")
    lines.append(f"Resonators:          {result['n_resonators']}")
    if result.get("ripple_db"):
        lines.append(f"Ripple:              {result['ripple_db']} dB")
    validation_status = result.get("response_validation_status")
    if validation_status == "validated":
        lines.append("Response validation: Passed synthesized-response checks")
    elif validation_status == "outside_validated_envelope":
        lines.append("Response validation: Outside validated envelope; see warnings")
    lines.append("=" * 60)

    if result.get("warnings"):
        lines.append("\nWarnings:")
        for w in result["warnings"]:
            lines.append(f"  ! {w}")

    from filter_lib.bandpass.display import format_insertion_loss_line, format_q_model_lines

    lines.extend(format_q_model_lines(result))

    il_line = format_insertion_loss_line(result)
    if il_line:
        lines.append(il_line)

    lines.append("\nTopology:")
    lines.append(format_top_c_diagram(result["n_resonators"]))

    # 24-char box-drawing rule; cell contents below are padded to 22 chars
    # plus one space each side, so changing one width without the other
    # breaks the table borders.
    n = result["n_resonators"]
    h24 = "\u2500" * 24
    lines.append(f"\n{'Component Values':^50}")
    lines.append(f"\u250c{h24}\u252c{h24}\u2510")
    lines.append(f"\u2502{'Tank Capacitors':^24}\u2502{'Inductors':^24}\u2502")
    lines.append(f"\u251c{h24}\u253c{h24}\u2524")

    for i in range(n):
        if state.raw_units:
            cap_str = f"Cp{i + 1}: {result['c_tank'][i]:.6e} F"
            ind_str = f"L{i + 1}: {result['L_resonant']:.6e} H"
        else:
            cap_str = f"Cp{i + 1}: {format_capacitance(result['c_tank'][i])}"
            ind_str = f"L{i + 1}: {format_inductance(result['L_resonant'])}"
        lines.append(f"\u2502 {cap_str:<22} \u2502 {ind_str:<22} \u2502")

    lines.append(f"\u2514{h24}\u2534{h24}\u2518")
    lines.append("Inductors: wind to value")

    lines.append(f"\n\u250c{h24}\u2510")
    lines.append(f"\u2502{'Coupling Capacitors':^24}\u2502")
    lines.append(f"\u251c{h24}\u2524")

    for label, value in _coupling_cap_items(result):
        if state.raw_units:
            cs_str = f"{label}: {value:.6e} F"
        else:
            cs_str = f"{label}: {format_capacitance(value)}"
        lines.append(f"\u2502 {cs_str:<22} \u2502")

    lines.append(f"\u2514{h24}\u2518")

    realized_in = " (realized by Ce_in)" if result.get("c_end_in") is not None else ""
    realized_out = " (realized by Ce_out)" if result.get("c_end_out") is not None else ""
    lines.append(f"\nExternal Q (input):  {result['qe_in']:.2f}{realized_in}")
    lines.append(f"External Q (output): {result['qe_out']:.2f}{realized_out}")

    return lines
