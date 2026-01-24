"""Main display function for bandpass filter results.

Orchestrates output formatting, topology diagrams, and E-series matching.
"""
from __future__ import annotations
from typing import Any

from ..shared.formatting import format_frequency, format_capacitance, format_inductance
from ..shared.plotting import render_bandpass_plot, export_json as plot_export_json, export_csv as plot_export_csv
from .transfer import frequency_sweep
from .diagrams import print_top_c_diagram, print_shunt_c_diagram
from .formatters import format_json, format_csv, format_quiet, format_eseries_match

# Type alias for filter result dict
FilterResult = dict[str, Any]

# Default number of points for frequency sweep plots
PLOT_POINTS = 61


def display_results(result: FilterResult, raw: bool = False,
                    output_format: str = 'table', quiet: bool = False,
                    eseries: str | None = 'E24',
                    show_plot: bool = False,
                    plot_data: str | None = None) -> None:
    """Display calculated filter component values.

    Args:
        result: Dict from calculate_bandpass_filter()
        raw: If True, display values in scientific notation
        output_format: 'table', 'json', or 'csv'
        quiet: If True, output only component values
        eseries: E-series for matching (None to disable)
        show_plot: Show ASCII frequency response
        plot_data: Export plot data as 'json' or 'csv'
    """
    # Handle plot data export
    if plot_data:
        sweep = frequency_sweep(
            result['f0'], result['bw'], result['n_resonators'],
            result['filter_type'],
            ripple_db=result.get('ripple_db') or 0.5,
            points=PLOT_POINTS
        )
        if plot_data == 'json':
            print(plot_export_json(sweep, result['f0'], result['bw'],
                                   result['filter_type'], result['n_resonators'],
                                   result.get('ripple_db')))
        else:
            print(plot_export_csv(sweep))
        return

    if output_format == 'json':
        print(format_json(result))
        return
    if output_format == 'csv':
        print(format_csv(result), end='')
        return
    if quiet:
        print(format_quiet(result, raw))
        return

    _print_table_output(result, raw, eseries, show_plot)


def _print_table_output(result: FilterResult, raw: bool, eseries: str | None,
                        show_plot: bool) -> None:
    """Print full table output with diagram and component values."""
    coupling_name = "Top-C (Series)" if result['coupling'] == 'top' else "Shunt-C (Parallel)"
    title = f"{result['filter_type'].title()} Coupled Resonator Bandpass Filter"

    print(f"\n{title}")
    print("=" * 50)
    print(f"Center Frequency f₀: {format_frequency(result['f0'])}")
    print(f"Lower Cutoff fₗ:     {format_frequency(result['f_low'])}")
    print(f"Upper Cutoff fₕ:     {format_frequency(result['f_high'])}")
    print(f"Bandwidth BW:        {format_frequency(result['bw'])}")
    print(f"Fractional BW:       {result['fbw']*100:.2f}%")
    print(f"Impedance Z₀:        {result['z0']:.4g} Ω")
    if result['ripple_db'] is not None:
        print(f"Ripple:              {result['ripple_db']} dB")
    print(f"Resonators:          {result['n_resonators']}")
    print(f"Coupling:            {coupling_name}")
    print("=" * 50)

    if result['warnings']:
        print("\nWarnings:")
        for w in result['warnings']:
            print(f"  ⚠ {w}")

    print(f"\nMinimum Component Q: {result['q_min']:.0f}")
    print(f"  (Q safety factor: {result['q_safety']})")

    _print_topology(result)
    _print_component_tables(result, raw)
    _print_external_q(result)

    if eseries and not raw:
        _print_eseries_matching(result, eseries)

    if show_plot:
        _print_frequency_response(result)

    print()


def _print_topology(result: FilterResult) -> None:
    """Print topology diagram."""
    n = result['n_resonators']
    print("\nTopology:")
    if result['coupling'] == 'top':
        print_top_c_diagram(n)
    else:
        print_shunt_c_diagram(n)


def _print_component_tables(result: FilterResult, raw: bool) -> None:
    """Print component value tables."""
    n = result['n_resonators']

    print(f"\n{'Component Values':^50}")
    print(f"┌{'─' * 24}┬{'─' * 24}┐")
    print(f"│{'Tank Capacitors':^24}│{'Inductors':^24}│")
    print(f"├{'─' * 24}┼{'─' * 24}┤")

    for i in range(n):
        if raw:
            cap_str = f"Cp{i+1}: {result['c_tank'][i]:.6e} F"
            ind_str = f"L{i+1}: {result['L_resonant']:.6e} H"
        else:
            cap_str = f"Cp{i+1}: {format_capacitance(result['c_tank'][i])}"
            ind_str = f"L{i+1}: {format_inductance(result['L_resonant'])}"
        print(f"│ {cap_str:<22} │ {ind_str:<22} │")

    print(f"└{'─' * 24}┴{'─' * 24}┘")

    print(f"\n┌{'─' * 24}┐")
    print(f"│{'Coupling Capacitors':^24}│")
    print(f"├{'─' * 24}┤")

    for i, cs in enumerate(result['c_coupling']):
        if raw:
            cs_str = f"Cs{i+1}{i+2}: {cs:.6e} F"
        else:
            cs_str = f"Cs{i+1}{i+2}: {format_capacitance(cs)}"
        print(f"│ {cs_str:<22} │")

    print(f"└{'─' * 24}┘")


def _print_external_q(result: FilterResult) -> None:
    """Print external Q values."""
    print(f"\nExternal Q (input):  {result['qe_in']:.2f}")
    print(f"External Q (output): {result['qe_out']:.2f}")


def _print_eseries_matching(result: FilterResult, eseries: str) -> None:
    """Print E-series matching recommendations."""
    print(f"\n{eseries} Standard Capacitor Recommendations")
    print("─" * 45)
    print("(Calculated values with nearest standard matches)")
    print()
    for i, ct in enumerate(result['c_tank']):
        print(f"Cp{i+1} Calculated: {format_capacitance(ct)}")
        for line in format_eseries_match(ct, eseries, format_capacitance):
            print(line)
    for i, cs in enumerate(result['c_coupling']):
        print(f"Cs{i+1}{i+2} Calculated: {format_capacitance(cs)}")
        for line in format_eseries_match(cs, eseries, format_capacitance):
            print(line)


def _print_frequency_response(result: FilterResult) -> None:
    """Print frequency response plot."""
    sweep = frequency_sweep(
        result['f0'], result['bw'], result['n_resonators'],
        result['filter_type'],
        ripple_db=result.get('ripple_db') or 0.5,
        points=PLOT_POINTS
    )
    title = f"{result['filter_type'].title()} {result['n_resonators']}-pole Response"
    print(f"\n{render_bandpass_plot(sweep, result['f0'], result['bw'], title=title)}")
