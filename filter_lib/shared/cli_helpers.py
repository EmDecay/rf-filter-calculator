"""Shared CLI argument handling for filter commands.

Provides common argument definitions, validation, and output handling.
"""

import sys
from argparse import ArgumentParser, Namespace
from typing import NoReturn

from .cli_aliases import (
    DEFAULT_COMPONENTS,
    DEFAULT_ESERIES,
    DEFAULT_IMPEDANCE,
    DEFAULT_RIPPLE_DB,
)

# Standard filter type choices (shared across all commands). Must contain
# the canonical names plus every key of cli_aliases.FILTER_TYPE_ALIASES —
# argparse rejects anything not listed here before canonicalization runs.
FILTER_TYPE_CHOICES = ["butterworth", "chebyshev", "bessel", "bw", "ch", "bs", "b", "c"]

# Topology choices for LPF/HPF
TOPOLOGY_CHOICES = ["pi", "t"]


# Frequency-suffix explanation shared by every frequency flag's help text
FREQ_SUFFIX_HELP = "suffixes: k/M/G = kHz/MHz/GHz (case-insensitive; m is MHz, not milli)"


def add_filter_type_args(parser: ArgumentParser, filter_category: str = "lowpass") -> None:
    """Add filter type, topology, and frequency arguments.

    Args:
        parser: ArgumentParser to add arguments to
        filter_category: 'lowpass', 'highpass', or 'bandpass' (for help text)
    """
    parser.add_argument("filter_type", nargs="?", choices=FILTER_TYPE_CHOICES, help="Filter type")
    if filter_category in ("lowpass", "highpass"):
        parser.add_argument(
            "topology_pos", nargs="?", choices=TOPOLOGY_CHOICES, help="Topology (pi or t)"
        )
    parser.add_argument("frequency", nargs="?", help="Cutoff frequency (e.g., 10MHz)")

    parser.add_argument(
        "--type",
        dest="type_flag",
        choices=FILTER_TYPE_CHOICES,
        help="Filter type (alternative)",
    )
    parser.add_argument(
        "-f",
        "--freq",
        dest="freq_flag",
        help=f"Cutoff frequency (alternative); {FREQ_SUFFIX_HELP}",
    )
    if filter_category in ("lowpass", "highpass"):
        parser.add_argument(
            "-T",
            "--topology",
            choices=TOPOLOGY_CHOICES,
            dest="topology_flag",
            help="Filter topology: pi or t",
        )


def add_common_filter_args(parser: ArgumentParser) -> None:
    """Add common filter design arguments (impedance, ripple, components)."""
    parser.add_argument(
        "-z",
        "--impedance",
        default=DEFAULT_IMPEDANCE,
        help=f"Characteristic impedance (default: {DEFAULT_IMPEDANCE})",
    )
    # default=None is a sentinel: "ripple was explicitly supplied" drives the
    # only-used-by-Chebyshev warning; DEFAULT_RIPPLE_DB is applied afterwards.
    parser.add_argument(
        "-r",
        "--ripple",
        type=float,
        default=None,
        help=f"Chebyshev ripple in dB, 0 < r <= 3.0 (default: {DEFAULT_RIPPLE_DB}; "
        "ignored by other types)",
    )
    parser.add_argument(
        "-n",
        "--components",
        type=int,
        default=DEFAULT_COMPONENTS,
        help=f"Number of components: 2-9 (default: {DEFAULT_COMPONENTS})",
    )


def add_output_args(parser: ArgumentParser) -> None:
    """Add output format arguments."""
    parser.add_argument("--raw", action="store_true", help="Output raw values in Farads/Henries")
    parser.add_argument("--explain", action="store_true", help="Explain filter type")
    parser.add_argument("-q", "--quiet", action="store_true", help="Minimal output")
    parser.add_argument(
        "--format", choices=["table", "json", "csv"], default="table", help="Output format"
    )


def add_eseries_args(parser: ArgumentParser) -> None:
    """Add E-series matching arguments."""
    parser.add_argument(
        "-e",
        "--eseries",
        choices=["E12", "E24", "E96"],
        default=DEFAULT_ESERIES,
        help=f"E-series (default: {DEFAULT_ESERIES})",
    )
    parser.add_argument("--no-match", action="store_true", help="Disable E-series matching")


def add_sim_matched_arg(parser: ArgumentParser) -> None:
    """Add the matched-value simulation flag (shared by LP/HP/BP)."""
    parser.add_argument(
        "--sim-matched",
        action="store_true",
        help="Simulate the circuit with E-series matched capacitor values and "
        "report the measured response shift vs the exact design (table output)",
    )


def add_plot_args(parser: ArgumentParser) -> None:
    """Add plot-related arguments."""
    parser.add_argument("--plot", action="store_true", help="Show ASCII frequency response")
    parser.add_argument(
        "--plot-data", choices=["json", "csv"], help="Export frequency response data"
    )


def validate_filter_args(freq_hz: float, impedance: float, components: int) -> None:
    """Validate common filter arguments.

    Args:
        freq_hz: Cutoff/center frequency in Hz
        impedance: Characteristic impedance in ohms
        components: Filter order (component count)

    Raises:
        ValueError: If frequency or impedance is non-positive, or
            components is outside 2-9
    """
    if freq_hz <= 0:
        raise ValueError("Frequency must be positive")
    if impedance <= 0:
        raise ValueError("Impedance must be positive")
    if not 2 <= components <= 9:
        raise ValueError("Components must be 2-9")


def usage_error(args: Namespace, message: str) -> NoReturn:
    """Exit with the subcommand's argparse usage error (exit code 2).

    Requires setup_parser to have wired the subparser into the namespace via
    ``parser.set_defaults(_parser=parser)``.
    """
    args._parser.error(message)
    raise SystemExit(2)  # unreachable: parser.error always exits


def resolve_ripple_arg(args: Namespace, filter_type: str) -> float:
    """Resolve the -r/--ripple sentinel default; warn when ignored.

    Enforces the CLI-wide Chebyshev ripple ceiling of 3.0 dB: above
    3.0103 dB the -3 dB "crossing" a threshold table reports is an in-band
    ripple dip, not the band edge, so higher values produce misleading
    output. The library layer stays permissive (> 0 only).

    Args:
        args: Parsed arguments (ripple is None unless explicitly supplied)
        filter_type: Canonical filter type

    Returns:
        Ripple in dB (the supplied value, or DEFAULT_RIPPLE_DB)

    Raises:
        ValueError: If a Chebyshev ripple above 3.0 dB was supplied.
    """
    if args.ripple is not None and filter_type != "chebyshev":
        print("Warning: ripple is only used by Chebyshev; ignoring", file=sys.stderr)
    if filter_type == "chebyshev" and args.ripple is not None and args.ripple > 3.0:
        raise ValueError("Ripple must be at most 3.0 dB")
    return args.ripple if args.ripple is not None else DEFAULT_RIPPLE_DB


def get_filter_type_arg(args: Namespace) -> str:
    """Get filter type from positional or flag argument.

    Args:
        args: Parsed arguments with filter_type and type_flag attributes

    Returns:
        Filter type string (may be alias or canonical name)
    """
    return args.filter_type or args.type_flag


def export_plot_data(
    args: Namespace,
    freqs: list[float],
    response_db: list[float],
    meta: dict,
) -> bool:
    """Print frequency-response data in the unified export schema if requested.

    Args:
        args: Parsed arguments with plot_data attribute
        freqs: Frequency points
        response_db: Response in dB
        meta: Export metadata (see shared.response_export.response_meta)

    Returns:
        True if data was exported, False otherwise
    """
    from .response_export import export_response_csv, export_response_json

    if not args.plot_data:
        return False

    if args.plot_data == "json":
        print(export_response_json(freqs, response_db, meta))
    else:
        print(export_response_csv(freqs, response_db))
    return True
