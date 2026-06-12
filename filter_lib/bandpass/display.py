"""Main display function for bandpass filter results.

Orchestrates output formatting, topology diagrams, and E-series matching.
"""

from typing import Any

from ..shared.formatting import format_capacitance, format_frequency, format_inductance
from ..shared.plotting import (
    find_db_thresholds,
    format_threshold_table,
    render_bandpass_plot_pair,
)
from ..shared.response_export import export_response_csv, export_response_json, response_meta
from ..shared.toroid_display import (
    format_recommendation_block,
    format_recommendation_block_compact,
)
from ..shared.toroid_selection import recommend_cores
from .diagrams import print_top_c_diagram
from .formatters import format_csv, format_eseries_match, format_json, format_quiet
from .transfer import netlist_frequency_sweep

# Type alias for filter result dict
FilterResult = dict[str, Any]

# Default number of points for frequency sweep plots
PLOT_POINTS = 61


def display_results(
    result: FilterResult,
    raw: bool = False,
    output_format: str = "table",
    quiet: bool = False,
    eseries: str | None = "E24",
    show_plot: bool = False,
    plot_data: str | None = None,
    include_toroids: bool = True,
    toroid_compact: bool = False,
    toroid_full: bool = False,
) -> None:
    """Display calculated filter component values.

    Args:
        result: Dict from calculate_bandpass_filter()
        raw: If True, display values in scientific notation
        output_format: 'table', 'json', or 'csv'
        quiet: If True, output only component values
        eseries: E-series for matching (None to disable)
        show_plot: Show ASCII frequency response
        plot_data: Export plot data as 'json' or 'csv'
        include_toroids: Include toroid recommendations in output
        toroid_compact: Use compact 1-line-per-rec text format
        toroid_full: Show top-3 cores in table output (default top-1;
            json/csv always carry top-3)
    """
    # Handle plot data export (simulated from the synthesized circuit)
    if plot_data:
        sweep = netlist_frequency_sweep(result, points=PLOT_POINTS)
        freqs = [f for f, _ in sweep]
        response_db = [db for _, db in sweep]
        if plot_data == "json":
            print(export_response_json(freqs, response_db, response_meta("bandpass", result)))
        else:
            print(export_response_csv(freqs, response_db))
        return

    if output_format == "json":
        print(format_json(result, eseries=eseries, include_toroids=include_toroids))
        return
    if output_format == "csv":
        print(format_csv(result, eseries=eseries, include_toroids=include_toroids), end="")
        return
    if quiet:
        print(format_quiet(result, raw))
        return

    _print_table_output(
        result, raw, eseries, show_plot, include_toroids, toroid_compact, toroid_full
    )


def _print_table_output(
    result: FilterResult,
    raw: bool,
    eseries: str | None,
    show_plot: bool,
    include_toroids: bool = True,
    toroid_compact: bool = False,
    toroid_full: bool = False,
) -> None:
    """Print full table output with diagram and component values."""
    coupling_name = "Top-C (Series)"
    title = f"{result['filter_type'].title()} Coupled Resonator Bandpass Filter"

    print(f"\n{title}")
    print("=" * 50)
    print(f"Center Frequency f₀: {format_frequency(result['f0'])}")
    print(f"Lower Cutoff fₗ:     {format_frequency(result['f_low'])}")
    print(f"Upper Cutoff fₕ:     {format_frequency(result['f_high'])}")
    print(f"Bandwidth BW:        {format_frequency(result['bw'])}")
    print(f"Fractional BW:       {result['fbw'] * 100:.2f}%")
    print(f"Impedance Z₀:        {result['z0']:.4g} Ω")
    if result["ripple_db"] is not None:
        print(f"Ripple:              {result['ripple_db']} dB")
    print(f"Resonators:          {result['n_resonators']}")
    print(f"Coupling:            {coupling_name}")
    print("=" * 50)

    if result["warnings"]:
        print("\nWarnings:")
        for w in result["warnings"]:
            print(f"  ⚠ {w}")

    print(f"\nMinimum Component Q: {result['q_min']:.0f}")
    print(f"  (Q safety factor: {result['q_safety']})")

    _print_topology(result)
    _print_component_tables(result, raw)
    _print_external_q(result)

    if eseries and not raw:
        _print_eseries_matching(result, eseries)

    if include_toroids:
        _print_toroid_block(result, compact=toroid_compact, top_n=3 if toroid_full else 1)

    if show_plot:
        _print_frequency_response(result)

    print()


def _print_toroid_block(result: FilterResult, compact: bool, top_n: int = 1) -> None:
    """Render shared-L_resonant toroid recommendations (full or compact)."""
    formatter = format_recommendation_block_compact if compact else format_recommendation_block
    L0 = result["L_resonant"]
    n = result["n_resonators"]
    f0 = result["f0"]
    recs = recommend_cores(L0, f0, top_n=top_n)
    label = f"L_resonant (applies to L1…L{n})"
    print()
    print("Toroid Winding Recommendations (Iron-Powder T-Series)")
    print("-" * 55)
    if not compact:
        print("(Accuracy: A_L tolerance ±5% per spec; N rounding shown as %)")
    print()
    for line in formatter(label, L0, f0, recs):
        print(line)
    print()


def _print_topology(result: FilterResult) -> None:
    """Print topology diagram."""
    print("\nTopology:")
    print_top_c_diagram(result["n_resonators"])


def _print_component_tables(result: FilterResult, raw: bool) -> None:
    """Print component value tables."""
    n = result["n_resonators"]

    print(f"\n{'Component Values':^50}")
    print(f"┌{'─' * 24}┬{'─' * 24}┐")
    print(f"│{'Tank Capacitors':^24}│{'Inductors':^24}│")
    print(f"├{'─' * 24}┼{'─' * 24}┤")

    for i in range(n):
        if raw:
            cap_str = f"Cp{i + 1}: {result['c_tank'][i]:.6e} F"
            ind_str = f"L{i + 1}: {result['L_resonant']:.6e} H"
        else:
            cap_str = f"Cp{i + 1}: {format_capacitance(result['c_tank'][i])}"
            ind_str = f"L{i + 1}: {format_inductance(result['L_resonant'])}"
        print(f"│ {cap_str:<22} │ {ind_str:<22} │")

    print(f"└{'─' * 24}┴{'─' * 24}┘")

    print(f"\n┌{'─' * 24}┐")
    print(f"│{'Coupling Capacitors':^24}│")
    print(f"├{'─' * 24}┤")

    for label, value in _coupling_cap_rows(result):
        if raw:
            cs_str = f"{label}: {value:.6e} F"
        else:
            cs_str = f"{label}: {format_capacitance(value)}"
        print(f"│ {cs_str:<22} │")

    print(f"└{'─' * 24}┘")


def _coupling_cap_rows(result: FilterResult) -> list[tuple[str, float]]:
    """Coupling capacitor rows: end caps (when present) then inter-resonator caps."""
    rows: list[tuple[str, float]] = []
    if result.get("c_end_in") is not None:
        rows.append(("Ce_in", result["c_end_in"]))
    rows.extend((f"Cs{i + 1}{i + 2}", cs) for i, cs in enumerate(result["c_coupling"]))
    if result.get("c_end_out") is not None:
        rows.append(("Ce_out", result["c_end_out"]))
    return rows


def _print_external_q(result: FilterResult) -> None:
    """Print external Q values."""
    realized = " (realized by Ce_in)" if result.get("c_end_in") is not None else ""
    print(f"\nExternal Q (input):  {result['qe_in']:.2f}{realized}")
    realized = " (realized by Ce_out)" if result.get("c_end_out") is not None else ""
    print(f"External Q (output): {result['qe_out']:.2f}{realized}")


def _print_eseries_matching(result: FilterResult, eseries: str) -> None:
    """Print E-series matching recommendations."""
    print(f"\n{eseries} Standard Capacitor Recommendations")
    print("─" * 45)
    print("(Calculated values with nearest standard matches)")
    print()
    for i, ct in enumerate(result["c_tank"]):
        print(f"Cp{i + 1} Calculated: {format_capacitance(ct)}")
        for line in format_eseries_match(ct, eseries, format_capacitance):
            print(line)
    for label, value in _coupling_cap_rows(result):
        print(f"{label} Calculated: {format_capacitance(value)}")
        for line in format_eseries_match(value, eseries, format_capacitance):
            print(line)


def _print_frequency_response(result: FilterResult) -> None:
    """Print frequency response plot with zoomed passband and threshold table.

    The response is simulated from the synthesized component values, not the
    idealized prototype, so it shows what a built filter measures.
    """
    from ..shared.transfer_response_dispatch import make_bp_netlist_response_db

    ripple = result.get("ripple_db") or 0.5
    sweep = netlist_frequency_sweep(result, points=PLOT_POINTS)
    title = f"{result['filter_type'].title()} {result['n_resonators']}-pole Response"
    response_fn = make_bp_netlist_response_db(result)
    print(
        f"\n{render_bandpass_plot_pair(sweep, result['f0'], result['bw'], f_low_hz=result['f_low'], f_high_hz=result['f_high'], title=title, ripple_db=ripple, response_fn=response_fn)}"
    )
    freqs = [f for f, _ in sweep]
    dbs = [db for _, db in sweep]
    thresholds = find_db_thresholds(freqs, dbs, filter_type="bandpass")
    print(format_threshold_table(thresholds, filter_type="bandpass"))
