"""Shared utilities for filter calculations."""

from .parsing import parse_frequency, parse_impedance
from .formatting import (
    format_frequency, format_capacitance, format_inductance, format_impedance
)
from .eseries import ESeriesMatch, match_component, find_closest_single
from .constants import BESSEL_G_VALUES
from .chebyshev_g_calculator import calculate_chebyshev_g_values
from .cli_aliases import (
    FILTER_TYPE_ALIASES, COUPLING_ALIASES,
    DEFAULT_IMPEDANCE, DEFAULT_RIPPLE_DB, DEFAULT_COMPONENTS,
    DEFAULT_RESONATORS, DEFAULT_Q_SAFETY, DEFAULT_ESERIES,
    FILTER_EXPLANATIONS, FILTER_EXPLANATIONS_HIGHPASS, FILTER_EXPLANATIONS_BANDPASS,
    resolve_filter_type, resolve_coupling,
)
from .cli_helpers import (
    FILTER_TYPE_CHOICES,
    add_filter_type_args, add_common_filter_args, add_output_args,
    add_eseries_args, add_plot_args, validate_filter_args, export_plot_data,
)
from .display_helpers import (
    format_eseries_match, format_component_value, split_value_unit
)
from .transfer_functions import (
    BESSEL_COEFFS, BESSEL_SCALE,
    generate_frequency_points, chebyshev_polynomial,
    magnitude_to_db, export_response_json, export_response_csv,
)

__all__ = [
    # Parsing
    'parse_frequency', 'parse_impedance',
    # Formatting
    'format_frequency', 'format_capacitance', 'format_inductance', 'format_impedance',
    # E-series
    'ESeriesMatch', 'match_component', 'find_closest_single',
    # Constants
    'BESSEL_G_VALUES',
    # Chebyshev calculator
    'calculate_chebyshev_g_values',
    # CLI aliases
    'FILTER_TYPE_ALIASES', 'COUPLING_ALIASES',
    'DEFAULT_IMPEDANCE', 'DEFAULT_RIPPLE_DB', 'DEFAULT_COMPONENTS',
    'DEFAULT_RESONATORS', 'DEFAULT_Q_SAFETY', 'DEFAULT_ESERIES',
    'FILTER_EXPLANATIONS', 'FILTER_EXPLANATIONS_HIGHPASS', 'FILTER_EXPLANATIONS_BANDPASS',
    'resolve_filter_type', 'resolve_coupling',
    # CLI helpers
    'FILTER_TYPE_CHOICES',
    'add_filter_type_args', 'add_common_filter_args', 'add_output_args',
    'add_eseries_args', 'add_plot_args', 'validate_filter_args', 'export_plot_data',
    # Display helpers
    'format_eseries_match', 'format_component_value', 'split_value_unit',
    # Transfer functions
    'BESSEL_COEFFS', 'BESSEL_SCALE',
    'generate_frequency_points', 'chebyshev_polynomial',
    'magnitude_to_db', 'export_response_json', 'export_response_csv',
]
