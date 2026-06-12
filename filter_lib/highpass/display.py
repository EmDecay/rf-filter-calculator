"""Display functions for highpass filters."""

from ..shared.display_common import (
    format_csv_result,
    format_json_result,
    format_quiet_result,
    print_component_table,
    print_header,
)
from ..shared.display_helpers import format_eseries_match
from ..shared.formatting import format_capacitance
from ..shared.plotting import find_db_thresholds, format_threshold_table, render_plot_pair
from ..shared.topology_diagrams import print_pi_topology_diagram, print_t_topology_diagram
from ..shared.toroid_display import (
    format_recommendation_block,
    format_recommendation_block_compact,
)
from ..shared.toroid_selection import recommend_cores
from ..shared.transfer_response_dispatch import make_hp_response_db
from .transfer import frequency_response, generate_frequency_points


def _primary_component(result: dict) -> str:
    """Return primary component type based on topology.

    HPF T: caps at series (odd) positions = primary.
    HPF Pi: inds at shunt (odd) positions = primary.
    """
    return "inductors" if result.get("topology", "t") == "pi" else "capacitors"


def format_json(
    result: dict,
    eseries: str | None = None,
    include_toroids: bool = True,
) -> str:
    """Format results as JSON."""
    return format_json_result(
        result,
        primary_component=_primary_component(result),
        eseries=eseries,
        toroid_freq_hz=result["freq_hz"],
        include_toroids=include_toroids,
    )


def format_csv(
    result: dict,
    eseries: str | None = None,
    include_toroids: bool = True,
) -> str:
    """Format results as CSV."""
    return format_csv_result(
        result,
        primary_component=_primary_component(result),
        eseries=eseries,
        toroid_freq_hz=result["freq_hz"],
        include_toroids=include_toroids,
    )


def format_quiet(result: dict, raw: bool = False) -> str:
    """Format minimal output."""
    return format_quiet_result(result, raw, primary_component=_primary_component(result))


def display_results(
    result: dict,
    raw: bool = False,
    output_format: str = "table",
    quiet: bool = False,
    eseries: str = "E24",
    show_match: bool = True,
    show_plot: bool = False,
    include_toroids: bool = True,
    toroid_compact: bool = False,
) -> None:
    """Display calculated filter component values."""
    if output_format == "json":
        print(
            format_json(
                result,
                eseries=eseries if show_match else None,
                include_toroids=include_toroids,
            )
        )
        return
    if output_format == "csv":
        print(
            format_csv(
                result,
                eseries=eseries if show_match else None,
                include_toroids=include_toroids,
            ),
            end="",
        )
        return
    if quiet:
        print(format_quiet(result, raw))
        return

    topology = result.get("topology", "t")
    primary = _primary_component(result)

    # Use shared header and table printing
    print_header(result, topology=topology.upper(), filter_category="High Pass")

    n_inds = len(result["inductors"])
    n_caps = len(result["capacitors"])

    print("\nTopology:")
    # HPF swaps component types: series C + shunt L
    if topology == "t":
        print_t_topology_diagram(n_caps, n_inds, series_label="C", shunt_label="L")
    else:
        print_pi_topology_diagram(n_inds, n_caps, series_label="C", shunt_label="L")

    print_component_table(result, raw=raw, primary_component=primary)

    if show_match and not raw:
        print(f"\n{eseries} Standard Capacitor Recommendations")
        print("-" * 45)
        print("(Calculated values with nearest standard matches)")
        print()
        for i, cap in enumerate(result["capacitors"]):
            print(f"C{i + 1} Calculated: {format_capacitance(cap)}")
            for line in format_eseries_match(
                cap, eseries, format_capacitance, parallel_mode="additive"
            ):
                print(line)

    if include_toroids:
        _print_toroid_block(result, compact=toroid_compact)

    if show_plot:
        freqs = generate_frequency_points(result["freq_hz"])
        ripple = result.get("ripple") or 0.5
        response = frequency_response(
            result["filter_type"], freqs, result["freq_hz"], result["order"], ripple
        )
        cutoff = result["freq_hz"]
        response_fn = make_hp_response_db(result["filter_type"], cutoff, result["order"], ripple)
        print()
        print(
            render_plot_pair(
                freqs,
                response,
                cutoff,
                filter_type="highpass",
                ripple_db=ripple,
                response_fn=response_fn,
            )
        )
        thresholds = find_db_thresholds(freqs, response, filter_type="highpass")
        print(format_threshold_table(thresholds, filter_type="highpass"))

    print()


def _print_toroid_block(result: dict, compact: bool) -> None:
    """Render per-inductor toroid recommendations (full or compact)."""
    formatter = format_recommendation_block_compact if compact else format_recommendation_block
    freq_hz = result["freq_hz"]
    print()
    print("Toroid Winding Recommendations (Iron-Powder T-Series)")
    print("-" * 55)
    if not compact:
        print("(Accuracy: A_L tolerance ±5% per spec; N rounding shown as %)")
    print()
    for i, L in enumerate(result["inductors"]):
        recs = recommend_cores(L, freq_hz)
        for line in formatter(f"L{i + 1}", L, freq_hz, recs):
            print(line)
        print()
