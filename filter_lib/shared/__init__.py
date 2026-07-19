"""Shared utilities for filter calculations.

Flat re-export facade: filter modules and tests import from
``filter_lib.shared`` rather than individual submodules, so moving code
between submodules doesn't break callers. New public names should be
added to both the import block and ``__all__``.
"""

from .build_simulation import (
    BuildAnalysisResult,
    BuildConfig,
    CircuitMeasurement,
    ComponentSubstitution,
    MetricSummary,
    NominalRealization,
    ScreeningCase,
    analyze_build,
    derive_series_resistance,
    realize_nominal_build,
)
from .chebyshev_g_calculator import CHEBYSHEV_DB_TO_NEPER_FACTOR, calculate_chebyshev_g_values
from .cli_aliases import (
    COUPLING_ALIASES,
    DEFAULT_COMPONENTS,
    DEFAULT_ESERIES,
    DEFAULT_IMPEDANCE,
    DEFAULT_Q_SAFETY,
    DEFAULT_RESONATORS,
    DEFAULT_RIPPLE_DB,
    FILTER_EXPLANATIONS,
    FILTER_EXPLANATIONS_BANDPASS,
    FILTER_EXPLANATIONS_HIGHPASS,
    FILTER_TYPE_ALIASES,
    resolve_coupling,
    resolve_filter_type,
)
from .cli_helpers import (
    FILTER_TYPE_CHOICES,
    add_common_filter_args,
    add_eseries_args,
    add_filter_type_args,
    add_output_args,
    add_plot_args,
    export_plot_data,
    validate_filter_args,
)
from .constants import BESSEL_G_VALUES
from .display_common import (
    build_standard_match,
    format_csv_result,
    format_json_result,
    format_quiet_result,
    print_component_table,
    print_header,
)
from .display_helpers import format_component_value, format_eseries_match, split_value_unit
from .eseries import ESeriesMatch, find_closest_single, match_component
from .formatting import format_capacitance, format_frequency, format_impedance, format_inductance
from .netlist_builders import (
    CircuitElement,
    NamedCircuit,
    build_bandpass_top_c_netlist,
    build_hp_netlist,
    build_lp_netlist,
    build_named_circuit,
)
from .netlist_simulation import (
    find_3db_edges,
    passband_ripple_db,
    solve_s21,
    solve_transducer_power_gain,
)
from .parsing import parse_frequency, parse_impedance, parse_inductance
from .response_export import export_response_csv, export_response_json, response_meta
from .spice_export import export_spice_deck
from .transfer_functions import (
    BESSEL_COEFFS,
    BESSEL_SCALE,
    chebyshev_polynomial,
    generate_frequency_points,
    magnitude_to_db,
)

__all__ = [
    # Parsing
    "parse_frequency",
    "parse_impedance",
    "parse_inductance",
    # Formatting
    "format_frequency",
    "format_capacitance",
    "format_inductance",
    "format_impedance",
    # E-series
    "ESeriesMatch",
    "match_component",
    "find_closest_single",
    # Constants
    "BESSEL_G_VALUES",
    "CHEBYSHEV_DB_TO_NEPER_FACTOR",
    # Chebyshev calculator
    "calculate_chebyshev_g_values",
    # CLI aliases
    "FILTER_TYPE_ALIASES",
    "COUPLING_ALIASES",
    "DEFAULT_IMPEDANCE",
    "DEFAULT_RIPPLE_DB",
    "DEFAULT_COMPONENTS",
    "DEFAULT_RESONATORS",
    "DEFAULT_Q_SAFETY",
    "DEFAULT_ESERIES",
    "FILTER_EXPLANATIONS",
    "FILTER_EXPLANATIONS_HIGHPASS",
    "FILTER_EXPLANATIONS_BANDPASS",
    "resolve_filter_type",
    "resolve_coupling",
    # CLI helpers
    "FILTER_TYPE_CHOICES",
    "add_filter_type_args",
    "add_common_filter_args",
    "add_output_args",
    "add_eseries_args",
    "add_plot_args",
    "validate_filter_args",
    "export_plot_data",
    # Display helpers
    "format_eseries_match",
    "format_component_value",
    "split_value_unit",
    # Display common
    "build_standard_match",
    "format_json_result",
    "format_csv_result",
    "format_quiet_result",
    "print_header",
    "print_component_table",
    # Netlist simulation
    "CircuitElement",
    "NamedCircuit",
    "solve_s21",
    "solve_transducer_power_gain",
    "find_3db_edges",
    "passband_ripple_db",
    "build_named_circuit",
    "build_lp_netlist",
    "build_hp_netlist",
    "build_bandpass_top_c_netlist",
    # Build realization and SPICE
    "BuildConfig",
    "ComponentSubstitution",
    "NominalRealization",
    "CircuitMeasurement",
    "ScreeningCase",
    "MetricSummary",
    "BuildAnalysisResult",
    "derive_series_resistance",
    "realize_nominal_build",
    "analyze_build",
    "export_spice_deck",
    # Transfer functions
    "BESSEL_COEFFS",
    "BESSEL_SCALE",
    "generate_frequency_points",
    "chebyshev_polynomial",
    "magnitude_to_db",
    # Response export (unified schema)
    "export_response_json",
    "export_response_csv",
    "response_meta",
]
