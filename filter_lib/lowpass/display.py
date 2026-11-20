"""Display functions for lowpass filters.

All rendering is delegated to the shared LP/HP display layer; this module only
supplies the lowpass-specific configuration (labels, topology-to-component
mapping, diagram builders, and response functions).
"""

from ..shared.lp_hp_display import (
    DiagramConfig,
    LpHpDisplayConfig,
    format_csv_for_config,
    format_json_for_config,
    format_quiet_for_config,
)
from ..shared.resolved_parts import ResolvedParts
from ..shared.topology_diagrams import format_pi_topology_diagram, format_t_topology_diagram
from ..shared.transfer_response_dispatch import make_lp_response_db
from .transfer import frequency_response, generate_frequency_points

# Lowpass Pi places shunt capacitors first (odd positions), so caps are the
# "primary" component there; T leads with series inductors instead. The diagram
# tuples list (odd-position, even-position) component keys in that order.
LOWPASS_DISPLAY_CONFIG = LpHpDisplayConfig(
    category="Low-Pass",
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


def format_json(result: dict, parts: ResolvedParts, build_analysis=None) -> str:
    """Format results as JSON with the parts ``design()`` resolved."""
    return format_json_for_config(result, LOWPASS_DISPLAY_CONFIG, parts, build_analysis)


def format_csv(result: dict, parts: ResolvedParts) -> str:
    """Format results as CSV with the parts ``design()`` resolved."""
    return format_csv_for_config(result, LOWPASS_DISPLAY_CONFIG, parts)


def format_quiet(result: dict, raw: bool = False) -> str:
    """Format minimal output."""
    return format_quiet_for_config(result, LOWPASS_DISPLAY_CONFIG, raw)
