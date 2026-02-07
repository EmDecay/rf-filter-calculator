"""Formatting helpers for wizard calculation output.

Separated from calculation_handler.py for better organization.
Contains table formatting functions for filter results display.
"""
from typing import Callable
from .state import FilterState


def format_lp_hp_table(result: dict, state: FilterState, category: str) -> list[str]:
    """Format table output for lowpass/highpass filters."""
    from filter_lib.shared.formatting import format_frequency
    from filter_lib.shared.topology_diagrams import (
        format_pi_topology_diagram, format_t_topology_diagram
    )

    lines = []
    topology = result.get('topology', 'pi')
    title = f"{result['filter_type'].title()} {topology.upper()} {category} Filter"
    lines.append(f"\n{title}")
    lines.append("=" * 50)
    lines.append(f"Cutoff Frequency:    {format_frequency(result['freq_hz'])}")
    lines.append(f"Impedance Z0:        {result['impedance']:.4g} Ohm")
    if result.get('ripple') is not None:
        lines.append(f"Ripple:              {result['ripple']} dB")
    lines.append(f"Order:               {result['order']}")
    lines.append("=" * 50)

    n_caps = len(result['capacitors'])
    n_inds = len(result['inductors'])
    lines.append("\nTopology:")
    if topology == 'pi':
        lines.append(format_pi_topology_diagram(n_caps, n_inds))
    else:
        lines.append(format_t_topology_diagram(n_inds, n_caps))

    lines.append(_format_component_table(result, state.raw_units))
    return lines


def _format_component_table(result: dict, raw: bool) -> str:
    """Format component values as a table."""
    from filter_lib.shared.formatting import format_capacitance, format_inductance

    col_width = 24
    caps = result['capacitors']
    inds = result['inductors']
    max_rows = max(len(caps), len(inds))

    lines = []
    lines.append(f"\n{'Component Values':^50}")
    lines.append(f"\u250c{'\u2500' * col_width}\u252c{'\u2500' * col_width}\u2510")
    lines.append(f"\u2502{'Capacitors':^{col_width}}\u2502{'Inductors':^{col_width}}\u2502")
    lines.append(f"\u251c{'\u2500' * col_width}\u253c{'\u2500' * col_width}\u2524")

    for i in range(max_rows):
        cap_str = ""
        ind_str = ""
        if i < len(caps):
            val = caps[i]
            cap_str = f"C{i+1}: {val:.6e} F" if raw else f"C{i+1}: {format_capacitance(val)}"
        if i < len(inds):
            val = inds[i]
            ind_str = f"L{i+1}: {val:.6e} H" if raw else f"L{i+1}: {format_inductance(val)}"
        lines.append(f"\u2502 {cap_str:<{col_width-2}} \u2502 {ind_str:<{col_width-2}} \u2502")

    lines.append(f"\u2514{'\u2500' * col_width}\u2534{'\u2500' * col_width}\u2518")
    return '\n'.join(lines)


def format_eseries_recs(components: list, prefix: str, name: str,
                        eseries: str, formatter: Callable) -> list[str]:
    """Format E-series recommendations for components."""
    from filter_lib.shared.display_helpers import format_eseries_match

    lines = []
    lines.append(f"\n{eseries} Standard {name} Recommendations")
    lines.append("-" * 45)
    lines.append("(Calculated values with nearest standard matches)")
    lines.append("")
    for i, val in enumerate(components):
        lines.append(f"{prefix}{i+1} Calculated: {formatter(val)}")
        for line in format_eseries_match(val, eseries, formatter):
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

    for i, ct in enumerate(result['c_tank']):
        lines.append(f"Cp{i+1} Calculated: {format_capacitance(ct)}")
        for line in format_eseries_match(ct, eseries, format_capacitance):
            lines.append(line)

    for i, cs in enumerate(result['c_coupling']):
        lines.append(f"Cs{i+1}{i+2} Calculated: {format_capacitance(cs)}")
        for line in format_eseries_match(cs, eseries, format_capacitance):
            lines.append(line)

    return lines


def format_bandpass_table(result: dict, state: FilterState) -> list[str]:
    """Format bandpass filter results as table."""
    from filter_lib.shared.formatting import format_frequency, format_capacitance, format_inductance
    from filter_lib.bandpass.diagrams import format_top_c_diagram, format_shunt_c_diagram

    lines = []
    coupling = result.get('coupling', 'top')
    coupling_name = "Top-C Coupled" if coupling == 'top' else "Shunt-C Coupled"
    title = f"{result['filter_type'].title()} {coupling_name} Band-Pass Filter"
    lines.append(f"\n{title}")
    lines.append("=" * 60)
    lines.append(f"Center Frequency:    {format_frequency(result['f0'])}")
    lines.append(f"Bandwidth:           {format_frequency(result['bw'])}")
    lines.append(f"Fractional BW:       {result['fbw']*100:.2f}%")
    lines.append(f"Impedance Z0:        {result['z0']:.4g} Ohm")
    lines.append(f"Resonators:          {result['n_resonators']}")
    if result.get('ripple_db'):
        lines.append(f"Ripple:              {result['ripple_db']} dB")
    lines.append("=" * 60)

    if result.get('warnings'):
        lines.append("\nWarnings:")
        for w in result['warnings']:
            lines.append(f"  ! {w}")

    lines.append(f"\nMinimum Component Q: {result['q_min']:.0f}")
    lines.append(f"  (Q safety factor: {result['q_safety']})")

    lines.append("\nTopology:")
    if coupling == 'top':
        lines.append(format_top_c_diagram(result['n_resonators']))
    else:
        lines.append(format_shunt_c_diagram(result['n_resonators']))

    n = result['n_resonators']
    lines.append(f"\n{'Component Values':^50}")
    lines.append(f"\u250c{'\u2500' * 24}\u252c{'\u2500' * 24}\u2510")
    lines.append(f"\u2502{'Tank Capacitors':^24}\u2502{'Inductors':^24}\u2502")
    lines.append(f"\u251c{'\u2500' * 24}\u253c{'\u2500' * 24}\u2524")

    for i in range(n):
        if state.raw_units:
            cap_str = f"Cp{i+1}: {result['c_tank'][i]:.6e} F"
            ind_str = f"L{i+1}: {result['L_resonant']:.6e} H"
        else:
            cap_str = f"Cp{i+1}: {format_capacitance(result['c_tank'][i])}"
            ind_str = f"L{i+1}: {format_inductance(result['L_resonant'])}"
        lines.append(f"\u2502 {cap_str:<22} \u2502 {ind_str:<22} \u2502")

    lines.append(f"\u2514{'\u2500' * 24}\u2534{'\u2500' * 24}\u2518")

    lines.append(f"\n\u250c{'\u2500' * 24}\u2510")
    lines.append(f"\u2502{'Coupling Capacitors':^24}\u2502")
    lines.append(f"\u251c{'\u2500' * 24}\u2524")

    for i, cs in enumerate(result['c_coupling']):
        if state.raw_units:
            cs_str = f"Cs{i+1}{i+2}: {cs:.6e} F"
        else:
            cs_str = f"Cs{i+1}{i+2}: {format_capacitance(cs)}"
        lines.append(f"\u2502 {cs_str:<22} \u2502")

    lines.append(f"\u2514{'\u2500' * 24}\u2518")

    lines.append(f"\nExternal Q (input):  {result['qe_in']:.2f}")
    lines.append(f"External Q (output): {result['qe_out']:.2f}")

    return lines
