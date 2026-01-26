"""Shared CLI argument handling for filter commands.

Provides common argument definitions, validation, and output handling.
"""
from argparse import ArgumentParser, Namespace
from typing import Callable

from .cli_aliases import (
    DEFAULT_IMPEDANCE, DEFAULT_RIPPLE_DB, DEFAULT_COMPONENTS, DEFAULT_ESERIES,
)


# Standard filter type choices (shared across all commands)
FILTER_TYPE_CHOICES = ['butterworth', 'chebyshev', 'bessel', 'bw', 'ch', 'bs', 'b', 'c']

# Topology choices for LPF/HPF
TOPOLOGY_CHOICES = ['pi', 't']


def add_filter_type_args(parser: ArgumentParser, filter_category: str = 'lowpass') -> None:
    """Add filter type, topology, and frequency arguments.

    Args:
        parser: ArgumentParser to add arguments to
        filter_category: 'lowpass', 'highpass', or 'bandpass' (for help text)
    """
    parser.add_argument('filter_type', nargs='?',
                        choices=FILTER_TYPE_CHOICES,
                        help='Filter type')
    if filter_category in ('lowpass', 'highpass'):
        parser.add_argument('topology_pos', nargs='?',
                            choices=TOPOLOGY_CHOICES,
                            help='Topology (pi or t)')
    parser.add_argument('frequency', nargs='?',
                        help='Cutoff frequency (e.g., 10MHz)')

    parser.add_argument('-t', '--type', dest='type_flag',
                        choices=FILTER_TYPE_CHOICES,
                        help='Filter type (alternative)')
    parser.add_argument('-f', '--freq', dest='freq_flag',
                        help='Cutoff frequency (alternative)')
    if filter_category in ('lowpass', 'highpass'):
        parser.add_argument('--topology', choices=TOPOLOGY_CHOICES,
                            dest='topology_flag',
                            help='Filter topology: pi or t')


def add_common_filter_args(parser: ArgumentParser) -> None:
    """Add common filter design arguments (impedance, ripple, components)."""
    parser.add_argument('-z', '--impedance', default=DEFAULT_IMPEDANCE,
                        help=f'Characteristic impedance (default: {DEFAULT_IMPEDANCE})')
    parser.add_argument('-r', '--ripple', type=float, default=DEFAULT_RIPPLE_DB,
                        help=f'Chebyshev ripple in dB (default: {DEFAULT_RIPPLE_DB})')
    parser.add_argument('-n', '--components', type=int, default=DEFAULT_COMPONENTS,
                        help=f'Number of components: 2-9 (default: {DEFAULT_COMPONENTS})')


def add_output_args(parser: ArgumentParser) -> None:
    """Add output format arguments."""
    parser.add_argument('--raw', action='store_true',
                        help='Output raw values in Farads/Henries')
    parser.add_argument('--explain', action='store_true',
                        help='Explain filter type')
    parser.add_argument('-q', '--quiet', action='store_true',
                        help='Minimal output')
    parser.add_argument('--format', choices=['table', 'json', 'csv'],
                        default='table', help='Output format')


def add_eseries_args(parser: ArgumentParser) -> None:
    """Add E-series matching arguments."""
    parser.add_argument('-e', '--eseries', choices=['E12', 'E24', 'E96'],
                        default=DEFAULT_ESERIES, help=f'E-series (default: {DEFAULT_ESERIES})')
    parser.add_argument('--no-match', action='store_true',
                        help='Disable E-series matching')


def add_plot_args(parser: ArgumentParser) -> None:
    """Add plot-related arguments."""
    parser.add_argument('--plot', action='store_true',
                        help='Show ASCII frequency response')
    parser.add_argument('--plot-data', choices=['json', 'csv'],
                        help='Export frequency response data')


def validate_filter_args(freq_hz: float, impedance: float, components: int) -> None:
    """Validate common filter arguments.

    Raises:
        ValueError: If any argument is invalid
    """
    if freq_hz <= 0:
        raise ValueError("Frequency must be positive")
    if impedance <= 0:
        raise ValueError("Impedance must be positive")
    if not 2 <= components <= 9:
        raise ValueError("Components must be 2-9")


def export_plot_data(args: Namespace, freqs: list[float], response_db: list[float],
                     result: dict,
                     export_json_fn: Callable, export_csv_fn: Callable) -> bool:
    """Export plot data if requested.

    Args:
        args: Parsed arguments with plot_data attribute
        freqs: Frequency points
        response_db: Response in dB
        result: Filter result dict (for JSON metadata)
        export_json_fn: Function to export JSON
        export_csv_fn: Function to export CSV

    Returns:
        True if data was exported, False otherwise
    """
    if not args.plot_data:
        return False

    if args.plot_data == 'json':
        print(export_json_fn(freqs, response_db, result))
    else:
        print(export_csv_fn(freqs, response_db))
    return True
