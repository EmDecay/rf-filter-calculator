"""Reusable argparse definitions for filter-calculator commands."""

from argparse import Action, ArgumentParser, Namespace
from typing import Any

from .cli_aliases import (
    DEFAULT_COMPONENTS,
    DEFAULT_ESERIES,
    DEFAULT_IMPEDANCE,
    DEFAULT_RIPPLE_DB,
)
from .eseries import SUB_PF_CLI_FLAG

FILTER_TYPE_CHOICES = ["butterworth", "chebyshev", "bessel", "bw", "ch", "bs", "b", "c"]
TOPOLOGY_CHOICES = ["pi", "t"]
# Every subcommand accepts both long spellings of -f; listed in this order everywhere.
FREQUENCY_FLAGS = ("-f", "--frequency", "--freq")
FREQ_SUFFIX_HELP = (
    "in Hz, or with k, M, or G for kHz, MHz, GHz (case-insensitive, so m also means MHz)"
)

# Help shared by the LP/HP and bandpass parsers. Positional arguments get metavars so
# usage errors name them (``argument TOPOLOGY: invalid choice``) and list the choices
# in the help text instead of the usage line.
FILTER_TYPE_HELP = "Response type: butterworth (bw, b), chebyshev (ch, c), or bessel (bs)"
TYPE_FLAG_HELP = "Response type, as a flag instead of the positional argument"
IMPEDANCE_HELP = (
    "Source and load impedance in ohms; k and M suffixes allowed (m also means mega) "
    f"(default: {DEFAULT_IMPEDANCE})"
)


def count_help(noun: str, default: int) -> str:
    """Help for ``-n``: the component count (LP/HP) or the resonator count (bandpass)."""
    return f"Number of {noun}, 2-9; Chebyshev needs an odd number (default: {default})"


def count_type(text: str) -> int | str:
    """Argparse ``type`` for ``-n``: whole numbers become ``int``; other text passes through.

    Nothing is rejected at parse time. ``require_count`` then rejects out-of-range and
    non-integer input alike with the shared count message (``Error: ...``, exit 1), so
    LP/HP and bandpass report every bad ``-n`` the same way, in the same words as the
    wizard and web UI.
    """
    try:
        return int(text)
    except ValueError:
        return text


def require_count(count: object, message: str) -> int:
    """Return ``count`` if it is a whole number from 2 to 9; otherwise raise ``message``."""
    if isinstance(count, bool) or not isinstance(count, int) or not 2 <= count <= 9:
        raise ValueError(message)
    return count


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
    parser.add_argument(
        "filter_type",
        nargs="?",
        choices=FILTER_TYPE_CHOICES,
        metavar="FILTER_TYPE",
        help=FILTER_TYPE_HELP,
    )
    if filter_category in ("lowpass", "highpass"):
        parser.add_argument(
            "topology_pos",
            nargs="?",
            choices=TOPOLOGY_CHOICES,
            metavar="TOPOLOGY",
            help="Topology: pi=shunt-first or t=series-first (the element nearest the input)",
        )
    parser.add_argument(
        "frequency",
        nargs="?",
        metavar="FREQUENCY",
        help="Cutoff frequency, e.g. 10MHz: the -3 dB point for Butterworth and Bessel, "
        "the ripple-band edge for Chebyshev",
    )
    parser.add_argument(
        "--type",
        dest="type_flag",
        choices=FILTER_TYPE_CHOICES,
        help=TYPE_FLAG_HELP,
    )
    parser.add_argument(
        *FREQUENCY_FLAGS,
        dest="freq_flag",
        metavar="FREQ",
        help=f"Cutoff frequency, as a flag instead of the positional argument; {FREQ_SUFFIX_HELP}",
    )
    if filter_category in ("lowpass", "highpass"):
        parser.add_argument(
            "-T",
            "--topology",
            choices=TOPOLOGY_CHOICES,
            dest="topology_flag",
            help="Topology, as a flag instead of the positional argument: "
            "pi (shunt-first) or t (series-first)",
        )


def add_common_filter_args(parser: ArgumentParser) -> None:
    """Add impedance, ripple, and component-count arguments."""
    parser.add_argument("-z", "--impedance", default=DEFAULT_IMPEDANCE, help=IMPEDANCE_HELP)
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
        type=count_type,
        default=DEFAULT_COMPONENTS,
        metavar="N",
        help=count_help("components", DEFAULT_COMPONENTS),
    )


def add_output_args(parser: ArgumentParser) -> None:
    """Add component-output format arguments."""
    parser.add_argument(
        "--raw",
        action="store_true",
        help="Show unrounded values in farads and henries (scientific notation), "
        "without standard-value matching",
    )
    parser.add_argument(
        "--explain",
        action="store_true",
        help="Print a short description of the filter type and exit",
    )
    parser.add_argument(
        "-q", "--quiet", action="store_true", help="Print only the component values, one per line"
    )
    parser.add_argument(
        "--format",
        choices=["table", "json", "csv", "spice"],
        default="table",
        help="Output format: table, json, csv, or spice (a SPICE netlist; see "
        "--spice-realization) (default: table)",
    )


def add_eseries_args(parser: ArgumentParser) -> None:
    """Add standard capacitor value selection arguments."""
    parser.set_defaults(_eseries_explicit=False)
    parser.add_argument(
        "-e",
        "--eseries",
        choices=["E12", "E24", "E96"],
        default=DEFAULT_ESERIES,
        action=_StoreExplicitValue,
        help="Standard capacitor values to choose from: E12, E24, or E96 (12, 24, or 96 "
        "values per decade). It sets how many values there are, not part tolerance (see "
        f"--capacitor-tolerance) (default: {DEFAULT_ESERIES})",
    )
    parser.add_argument(
        "--no-match",
        action="store_true",
        help="Show only calculated capacitor values; do not choose standard E-series values",
    )
    parser.add_argument(
        SUB_PF_CLI_FLAG,
        dest="allow_sub_pf",
        action="store_true",
        help="Also choose standard values for capacitors below 1 pF. Without it no part is "
        "chosen below 1 pF and you choose one manually. Applies to the E-series list, CSV "
        "and JSON, --sim-build, and the nominal-build SPICE deck",
    )


def add_sim_matched_arg(parser: ArgumentParser) -> None:
    """Add the deprecated matched-value compatibility flag."""
    parser.add_argument(
        "--sim-matched",
        action="store_true",
        help="Deprecated; use --sim-build. Compares the calculated design with the "
        "chosen-parts build",
    )


def add_plot_args(parser: ArgumentParser) -> None:
    """Add plot and standalone response-export arguments."""
    parser.add_argument(
        "--plot", action="store_true", help="Add a text plot of the frequency response to the table"
    )
    parser.add_argument(
        "--plot-data",
        choices=["json", "csv"],
        help="Print only the frequency response (frequency and dB) as JSON or CSV, instead "
        "of the component table",
    )
