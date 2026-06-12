"""Display functions for lowpass filters."""

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
from ..shared.transfer_response_dispatch import make_lp_response_db
from .transfer import frequency_response, generate_frequency_points

LOWPASS_DISPLAY_CONFIG = LpHpDisplayConfig(
    category="Low Pass",
    plot_filter_type="lowpass",
    default_topology="pi",
    primary_for_topology={"pi": "capacitors", "t": "inductors"},
    diagrams={
        "pi": DiagramConfig(format_pi_topology_diagram, ("capacitors", "inductors")),
        "t": DiagramConfig(format_t_topology_diagram, ("inductors", "capacitors")),
    },
    frequency_points=generate_frequency_points,
    frequency_response=frequency_response,
    response_db_factory=make_lp_response_db,
)


def _primary_component(result: dict) -> str:
    """Return primary component type based on topology."""
    return primary_component(result, LOWPASS_DISPLAY_CONFIG)


def format_json(
    result: dict,
    eseries: str | None = None,
    include_toroids: bool = True,
) -> str:
    """Format results as JSON."""
    return format_json_for_config(result, LOWPASS_DISPLAY_CONFIG, eseries, include_toroids)


def format_csv(
    result: dict,
    eseries: str | None = None,
    include_toroids: bool = True,
) -> str:
    """Format results as CSV."""
    return format_csv_for_config(result, LOWPASS_DISPLAY_CONFIG, eseries, include_toroids)


def format_quiet(result: dict, raw: bool = False) -> str:
    """Format minimal output."""
    return format_quiet_for_config(result, LOWPASS_DISPLAY_CONFIG, raw)


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
) -> None:
    """Display calculated filter component values."""
    display_results_for_config(
        result,
        LOWPASS_DISPLAY_CONFIG,
        raw=raw,
        output_format=output_format,
        quiet=quiet,
        eseries=eseries,
        show_match=show_match,
        show_plot=show_plot,
        include_toroids=include_toroids,
        toroid_compact=toroid_compact,
        toroid_full=toroid_full,
    )


LP_WIZARD_MATCH = CAPACITOR_MATCH
