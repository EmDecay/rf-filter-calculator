"""Formatting helpers for wizard calculation output.

Separated from calculation_handler.py for better organization.
Contains table formatting functions for filter results display.
"""

from collections.abc import Callable

from .state import FilterState


def format_lp_hp_table(result: dict, state: FilterState, category: str) -> list[str]:
    """Format table output for lowpass/highpass filters."""
    from filter_lib.highpass.display import HIGHPASS_DISPLAY_CONFIG
    from filter_lib.lowpass.display import LOWPASS_DISPLAY_CONFIG
    from filter_lib.shared.lp_hp_display import LpHpRenderOptions, render_results_lines

    config = (
        HIGHPASS_DISPLAY_CONFIG
        if category.strip().lower() in ("high pass", "highpass", "hp")
        else LOWPASS_DISPLAY_CONFIG
    )
    return render_results_lines(
        result,
        LpHpRenderOptions(
            config=config,
            raw=state.raw_units,
            eseries=None,
            show_match=False,
            show_plot=False,
            include_toroids=False,
            trailing_blank=False,
        ),
    )


def _format_component_table(result: dict, raw: bool) -> str:
    """Format component values as a table."""
    from filter_lib.shared.display_common import format_component_table

    return format_component_table(result, raw=raw, primary_component="capacitors")


def format_eseries_recs(
    components: list,
    prefix: str,
    name: str,
    eseries: str,
    formatter: Callable,
    parallel_mode: str = "additive",
) -> list[str]:
    """Format E-series recommendations for components.

    Capacitors receive E-series matching; inductors are wound to value.
    """
    from filter_lib.shared.display_helpers import format_eseries_match

    if prefix.upper().startswith("L") or name.lower().startswith("inductor"):
        return ["Inductors: wind to value (see toroid recommendations)"]

    lines = []
    lines.append(f"\n{eseries} Standard {name} Recommendations")
    lines.append("-" * 45)
    lines.append("(Calculated values with nearest standard matches)")
    lines.append("")
    for i, val in enumerate(components):
        lines.append(f"{prefix}{i + 1} Calculated: {formatter(val)}")
        for line in format_eseries_match(val, eseries, formatter, parallel_mode=parallel_mode):
            lines.append(line)
    return lines


def format_bandpass_eseries_recs(result: dict, eseries: str) -> list[str]:
    """Format E-series recommendations for bandpass capacitor values."""
    from filter_lib.shared.display_helpers import format_eseries_match
    from filter_lib.shared.formatting import format_capacitance

    lines = []
    lines.append(f"\n{eseries} Standard Capacitor Recommendations")
    lines.append("-" * 45)
    lines.append("(Calculated values with nearest standard matches)")
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
    """Coupling capacitors with end caps (when present) framing the Cs list."""
    items: list[tuple[str, float]] = []
    if result.get("c_end_in") is not None:
        items.append(("Ce_in", result["c_end_in"]))
    items.extend((f"Cs{i + 1}{i + 2}", cs) for i, cs in enumerate(result["c_coupling"]))
    if result.get("c_end_out") is not None:
        items.append(("Ce_out", result["c_end_out"]))
    return items


def format_bandpass_table(result: dict, state: FilterState) -> list[str]:
    """Format bandpass filter results as table."""
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
    lines.append("=" * 60)

    if result.get("warnings"):
        lines.append("\nWarnings:")
        for w in result["warnings"]:
            lines.append(f"  ! {w}")

    lines.append(f"\nMinimum Component Q: {result['q_min']:.0f}")
    lines.append(f"  (Q safety factor: {result['q_safety']})")

    lines.append("\nTopology:")
    lines.append(format_top_c_diagram(result["n_resonators"]))

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
    lines.append("Inductors: wind to value (see toroid recommendations)")

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
