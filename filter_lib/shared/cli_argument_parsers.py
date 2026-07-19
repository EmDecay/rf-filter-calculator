"""Reusable argparse definitions for filter-calculator commands."""

from argparse import Action, ArgumentParser, Namespace
from typing import Any

from .cli_aliases import (
    DEFAULT_COMPONENTS,
    DEFAULT_ESERIES,
    DEFAULT_IMPEDANCE,
    DEFAULT_RIPPLE_DB,
)

FILTER_TYPE_CHOICES = ["butterworth", "chebyshev", "bessel", "bw", "ch", "bs", "b", "c"]
TOPOLOGY_CHOICES = ["pi", "t"]
FREQ_SUFFIX_HELP = "suffixes: k/M/G = kHz/MHz/GHz (case-insensitive; m is MHz, not milli)"


class _StoreExplicitValue(Action):
    """Store an argparse value and remember that the option was supplied."""

    def __call__(
        self,
        parser: ArgumentParser,
        namespace: Namespace,
        values: Any,
        option_string: str | None = None,
    ) -> None:
        del parser, option_string
        setattr(namespace, self.dest, values)
        setattr(namespace, f"_{self.dest}_explicit", True)


def add_filter_type_args(parser: ArgumentParser, filter_category: str = "lowpass") -> None:
    """Add filter type, topology, and cutoff-frequency arguments."""
    parser.add_argument("filter_type", nargs="?", choices=FILTER_TYPE_CHOICES, help="Filter type")
    if filter_category in ("lowpass", "highpass"):
        parser.add_argument(
            "topology_pos",
            nargs="?",
            choices=TOPOLOGY_CHOICES,
            help="Ladder form (pi=shunt-first, t=series-first)",
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
            help="Ladder form: pi (shunt-first) or t (series-first)",
        )


def add_common_filter_args(parser: ArgumentParser) -> None:
    """Add impedance, ripple, and component-count arguments."""
    parser.add_argument(
        "-z",
        "--impedance",
        default=DEFAULT_IMPEDANCE,
        help=f"Characteristic impedance (default: {DEFAULT_IMPEDANCE})",
    )
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
    """Add component-output format arguments."""
    parser.add_argument("--raw", action="store_true", help="Output raw values in Farads/Henries")
    parser.add_argument(
        "--explain",
        action="store_true",
        help="Print a standalone filter-type explanation and exit",
    )
    parser.add_argument("-q", "--quiet", action="store_true", help="Minimal output")
    parser.add_argument(
        "--format",
        choices=["table", "json", "csv", "spice"],
        default="table",
        help="Output format (SPICE supports calculated or nominal-build decks)",
    )


def add_eseries_args(parser: ArgumentParser) -> None:
    """Add preferred-value selection arguments."""
    parser.set_defaults(_eseries_explicit=False)
    parser.add_argument(
        "-e",
        "--eseries",
        choices=["E12", "E24", "E96"],
        default=DEFAULT_ESERIES,
        action=_StoreExplicitValue,
        help=f"Preferred-value density, not part tolerance (default: {DEFAULT_ESERIES})",
    )
    parser.add_argument("--no-match", action="store_true", help="Disable E-series matching")


def add_sim_matched_arg(parser: ArgumentParser) -> None:
    """Add the deprecated matched-value compatibility flag."""
    parser.add_argument(
        "--sim-matched",
        action="store_true",
        help="Deprecated alias for a nominal-build comparison; use --sim-build "
        "for explicit loss, tolerance, and evaluation controls",
    )


def add_plot_args(parser: ArgumentParser) -> None:
    """Add plot and standalone response-export arguments."""
    parser.add_argument("--plot", action="store_true", help="Show ASCII frequency response")
    parser.add_argument(
        "--plot-data", choices=["json", "csv"], help="Export frequency response data"
    )
