"""Compatibility facade for shared CLI argument and output helpers."""

import sys
from argparse import Namespace

from .cli_aliases import DEFAULT_RIPPLE_DB
from .cli_argument_parsers import (
    FILTER_TYPE_CHOICES,
    FREQ_SUFFIX_HELP,
    TOPOLOGY_CHOICES,
    add_common_filter_args,
    add_eseries_args,
    add_filter_type_args,
    add_output_args,
    add_plot_args,
    add_sim_matched_arg,
)
from .cli_build_options import add_build_analysis_args, make_build_config
from .cli_output_validation import usage_error, validate_output_mode_args
from .numeric import require_positive_finite


def validate_filter_args(freq_hz: float, impedance: float, components: int) -> None:
    """Validate common design frequency, impedance, and order inputs."""
    require_positive_finite(freq_hz, "Frequency")
    require_positive_finite(impedance, "Impedance")
    if isinstance(components, bool) or not isinstance(components, int) or not 2 <= components <= 9:
        raise ValueError("Components must be 2-9")


def resolve_ripple_arg(args: Namespace, filter_type: str) -> float:
    """Resolve the Chebyshev-ripple default and warn when it is ignored."""
    if args.ripple is not None and filter_type != "chebyshev":
        print("Warning: ripple is only used by Chebyshev; ignoring", file=sys.stderr)
    if filter_type == "chebyshev" and args.ripple is not None and args.ripple > 3.0:
        raise ValueError("Ripple must be at most 3.0 dB")
    return args.ripple if args.ripple is not None else DEFAULT_RIPPLE_DB


def resolve_alternative_arg(
    args: Namespace,
    positional_name: str,
    flag_name: str,
    label: str,
) -> str | None:
    """Resolve a value supplied either positionally or by flag, never both."""
    positional = getattr(args, positional_name, None)
    flagged = getattr(args, flag_name, None)
    if positional is not None and flagged is not None:
        usage_error(args, f"{label} supplied both positionally and by flag; use only one form")
    return positional if positional is not None else flagged


def get_filter_type_arg(args: Namespace) -> str | None:
    """Resolve the positional or flag form of a filter type."""
    return resolve_alternative_arg(args, "filter_type", "type_flag", "filter type")


def export_plot_data(
    args: Namespace,
    freqs: list[float],
    response_db: list[float],
    meta: dict,
) -> bool:
    """Print frequency-response data in the selected standalone format."""
    from .response_export import export_response_csv, export_response_json

    if not args.plot_data:
        return False
    if args.plot_data == "json":
        print(export_response_json(freqs, response_db, meta))
    else:
        print(export_response_csv(freqs, response_db))
    return True


__all__ = [
    "FILTER_TYPE_CHOICES",
    "FREQ_SUFFIX_HELP",
    "TOPOLOGY_CHOICES",
    "add_build_analysis_args",
    "add_common_filter_args",
    "add_eseries_args",
    "add_filter_type_args",
    "add_output_args",
    "add_plot_args",
    "add_sim_matched_arg",
    "export_plot_data",
    "get_filter_type_arg",
    "make_build_config",
    "resolve_alternative_arg",
    "resolve_ripple_arg",
    "usage_error",
    "validate_filter_args",
    "validate_output_mode_args",
]
