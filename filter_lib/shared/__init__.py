"""Shared utilities for filter calculations."""

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
    format_csv_result,
    format_json_result,
    format_quiet_result,
    print_component_table,
    print_header,
)
from .display_helpers import format_component_value, format_eseries_match, split_value_unit
from .eseries import ESeriesMatch, find_closest_single, match_component
from .filter_result import FilterResult
from .formatting import format_capacitance, format_frequency, format_impedance, format_inductance
from .parsing import parse_frequency, parse_impedance
from .transfer_functions import (
    BESSEL_COEFFS,
    BESSEL_SCALE,
    chebyshev_polynomial,
    export_response_csv,
    export_response_json,
    generate_frequency_points,
    magnitude_to_db,
)

__all__ = [
    # Parsing
    "parse_frequency",
    "parse_impedance",
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
    # Filter result dataclass
    "FilterResult",
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
    "format_json_result",
    "format_csv_result",
    "format_quiet_result",
    "print_header",
    "print_component_table",
    # Transfer functions
    "BESSEL_COEFFS",
    "BESSEL_SCALE",
    "generate_frequency_points",
    "chebyshev_polynomial",
    "magnitude_to_db",
    "export_response_json",
    "export_response_csv",
]
