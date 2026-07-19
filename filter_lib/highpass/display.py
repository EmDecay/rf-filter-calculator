"""Display functions for highpass filters.

All rendering is delegated to the shared LP/HP display layer; this module only
supplies the highpass-specific configuration (labels, topology-to-component
mapping, diagram builders, and response functions).
"""

from ..shared.lp_hp_display import (
    CAPACITOR_MATCH,
    DiagramConfig,
    LpHpDisplayConfig,
    display_results_for_config,
    format_csv_for_config,
    format_json_for_config,
    format_quiet_for_config,
    primary_component,
)
from ..shared.topology_diagrams import format_pi_topology_diagram, format_t_topology_diagram
from ..shared.transfer_response_dispatch import make_hp_response_db
from .transfer import frequency_response, generate_frequency_points

# Highpass swaps component roles relative to lowpass: T leads with series
# capacitors (odd positions), Pi leads with shunt inductors. The diagram tuples
# list (odd-position, even-position) component keys, and the explicit
# series/shunt labels override the lowpass-oriented diagram defaults.
HIGHPASS_DISPLAY_CONFIG = LpHpDisplayConfig(
    category="High Pass",
    plot_filter_type="highpass",
    default_topology="t",
    primary_for_topology={"pi": "inductors", "t": "capacitors"},
    diagrams={
        "pi": DiagramConfig(
            format_pi_topology_diagram,
            ("inductors", "capacitors"),
            series_label="C",
            shunt_label="L",
        ),
        "t": DiagramConfig(
            format_t_topology_diagram,
            ("capacitors", "inductors"),
            series_label="C",
            shunt_label="L",
        ),
    },
    frequency_points=generate_frequency_points,
    frequency_response=frequency_response,
    response_db_factory=make_hp_response_db,
)


def _primary_component(result: dict) -> str:
    """Return primary component type based on topology."""
    return primary_component(result, HIGHPASS_DISPLAY_CONFIG)


def format_json(
    result: dict,
    eseries: str | None = None,
    include_toroids: bool = True,
    matched_sim: dict | None = None,
    build_analysis=None,
) -> str:
    """Format results as JSON."""
    return format_json_for_config(
        result,
        HIGHPASS_DISPLAY_CONFIG,
        eseries,
        include_toroids,
        matched_sim,
        build_analysis,
    )


def format_csv(
    result: dict,
    eseries: str | None = None,
    include_toroids: bool = True,
) -> str:
    """Format results as CSV."""
    return format_csv_for_config(result, HIGHPASS_DISPLAY_CONFIG, eseries, include_toroids)


def format_quiet(result: dict, raw: bool = False) -> str:
    """Format minimal output."""
    return format_quiet_for_config(result, HIGHPASS_DISPLAY_CONFIG, raw)


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
    toroid_full: bool = False,
    matched_sim: dict | None = None,
    build_analysis=None,
) -> None:
    """Display calculated filter component values.

    Args:
        result: Dict from the highpass calculation functions (inductors in
            Henries, capacitors in Farads, plus freq/impedance/topology
            metadata)
        raw: If True, display values in scientific notation
        output_format: 'table', 'json', or 'csv'
        quiet: If True, output only component values
        eseries: E-series name for capacitor matching (E12/E24/E96)
        show_match: Include E-series matching section in table output
        show_plot: Show ASCII frequency response
        include_toroids: Include toroid winding recommendations
        toroid_compact: Use compact 1-line-per-rec toroid text format
        toroid_full: Show up to three qualified cores in table output (default top-1)
    """
    display_results_for_config(
        result,
        HIGHPASS_DISPLAY_CONFIG,
        raw=raw,
        output_format=output_format,
        quiet=quiet,
        eseries=eseries,
        show_match=show_match,
        show_plot=show_plot,
        include_toroids=include_toroids,
        toroid_compact=toroid_compact,
        toroid_full=toroid_full,
        matched_sim=matched_sim,
        build_analysis=build_analysis,
    )


# Wizard match-mode hook: capacitors get E-series matching (inductors are
# wound to value, so they are never matched). Named per filter type so the
# wizard can import one symbol regardless of filter category.
HP_WIZARD_MATCH = CAPACITOR_MATCH
