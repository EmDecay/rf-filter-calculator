"""Display functions for highpass filters.

All rendering is delegated to the shared LP/HP display layer; this module only
supplies the highpass-specific configuration (labels, topology-to-component
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
from ..shared.transfer_response_dispatch import make_hp_response_db
from .transfer import frequency_response, generate_frequency_points

# Highpass swaps component roles relative to lowpass: T leads with series
# capacitors (odd positions), Pi leads with shunt inductors. The diagram tuples
# list (odd-position, even-position) component keys, and the explicit
# series/shunt labels override the lowpass-oriented diagram defaults.
HIGHPASS_DISPLAY_CONFIG = LpHpDisplayConfig(
    category="High-Pass",
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


def format_json(result: dict, parts: ResolvedParts, build_analysis=None) -> str:
    """Format results as JSON with the parts ``design()`` resolved."""
    return format_json_for_config(result, HIGHPASS_DISPLAY_CONFIG, parts, build_analysis)


def format_csv(result: dict, parts: ResolvedParts) -> str:
    """Format results as CSV with the parts ``design()`` resolved."""
    return format_csv_for_config(result, HIGHPASS_DISPLAY_CONFIG, parts)


def format_quiet(result: dict, raw: bool = False) -> str:
    """Format minimal output."""
    return format_quiet_for_config(result, HIGHPASS_DISPLAY_CONFIG, raw)
