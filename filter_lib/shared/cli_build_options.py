"""CLI definitions and conversion for the build simulation (--sim-build) and SPICE."""

from argparse import Action, ArgumentParser, Namespace
from typing import Any

from .cli_aliases import DEFAULT_ESERIES, SPICE_REALIZATION_CHOICES, resolve_spice_realization


class _StoreSpiceRealization(Action):
    """Store the canonical ``--spice-realization`` value so an alias behaves identically."""

    def __call__(
        self,
        parser: ArgumentParser,
        namespace: Namespace,
        values: Any,
        option_string: str | None = None,
    ) -> None:
        del parser, option_string
        setattr(namespace, self.dest, resolve_spice_realization(values))


def add_build_analysis_args(parser: ArgumentParser) -> None:
    """Add build simulation and SPICE realization controls."""
    parser.add_argument(
        "--sim-build",
        action="store_true",
        help="Build simulation: simulate the filter with the chosen parts (standard "
        "capacitor values and suggested toroid windings) at nominal values and across "
        "tolerance cases (all parts low, all high, each part alone low and high). Add part "
        "losses (Q) with the Q options. Table or JSON output only",
    )
    parser.add_argument(
        "--capacitor-tolerance",
        "--cap-tolerance",
        dest="build_capacitor_tolerance_pct",
        type=float,
        default=None,
        metavar="PCT",
        help="Capacitor tolerance in ± percent for --sim-build, 0 to under 100 (default: 5)",
    )
    parser.add_argument(
        "--inductor-tolerance",
        "--ind-tolerance",
        dest="build_inductor_tolerance_pct",
        type=float,
        default=None,
        metavar="PCT",
        help="Inductor tolerance in ± percent for --sim-build, 0 to under 100 (default: 10)",
    )
    parser.add_argument(
        "--inductor-q",
        dest="build_inductor_q",
        type=float,
        default=None,
        metavar="Q",
        help="Inductor Q for --sim-build and nominal-build SPICE, 0.01 to 1e9, at "
        "--loss-reference-frequency. Omit for lossless inductors",
    )
    parser.add_argument(
        "--capacitor-q",
        dest="build_capacitor_q",
        type=float,
        default=None,
        metavar="Q",
        help="Capacitor Q for --sim-build and nominal-build SPICE, 0.01 to 1e9, at "
        "--loss-reference-frequency. Omit for lossless capacitors",
    )
    parser.add_argument(
        "--source-resistance",
        dest="build_source_resistance",
        default=None,
        metavar="OHMS",
        help=_port_help("source"),
    )
    parser.add_argument(
        "--load-resistance",
        dest="build_load_resistance",
        default=None,
        metavar="OHMS",
        help=_port_help("load"),
    )
    parser.add_argument(
        "--loss-reference-frequency",
        dest="build_reference_frequency",
        default=None,
        metavar="FREQ",
        help="Frequency at which the Q values apply; each part's loss is a fixed series "
        "resistance set from its Q there (default: cutoff or center frequency)",
    )
    parser.add_argument(
        "--sample-count",
        "--samples",
        dest="build_sample_count",
        type=int,
        default=None,
        metavar="N",
        help="Number of extra random tolerance cases for --sim-build, 0 to 10000; each part "
        "is drawn uniformly within its tolerance (default: 0)",
    )
    parser.add_argument(
        "--seed",
        dest="build_seed",
        type=int,
        default=None,
        metavar="SEED",
        help="Random seed for --sample-count; the same seed repeats the same cases. The "
        "cases show spread, not a production-yield estimate (default: 0)",
    )
    parser.add_argument(
        "--analysis-points",
        dest="build_grid_points",
        type=int,
        default=None,
        metavar="N",
        help="Frequency points in the --sim-build sweep, 51 to 5001; measurements are "
        "refined between points automatically (default: 601)",
    )
    parser.add_argument(
        "--no-toroid-build",
        action="store_true",
        help="In --sim-build and nominal-build SPICE, use the calculated inductances "
        "instead of the inductance of the suggested whole-turn toroid windings",
    )
    parser.add_argument(
        "--spice-realization",
        choices=SPICE_REALIZATION_CHOICES,
        default=None,
        action=_StoreSpiceRealization,
        help="Values in the --format spice deck: nominal-build (or chosen-parts) uses the "
        "chosen parts (standard capacitor values and suggested toroid windings) with any Q "
        "losses; exact (or calculated) uses the calculated values without losses "
        "(default: nominal-build)",
    )


def _port_help(port: str) -> str:
    return (
        f"Simulation {port} resistance in ohms for --sim-build and SPICE; component values "
        "are still designed for equal -z source and load impedance. Allowed: 1e-6 to 1e6 "
        "times -z (default: same as -z)"
    )


def make_build_config(args: Namespace):
    """Translate parsed CLI controls into a validated ``BuildConfig``."""
    from .build_simulation import BuildConfig
    from .parsing import parse_frequency, parse_impedance

    source_arg = getattr(args, "build_source_resistance", None)
    load_arg = getattr(args, "build_load_resistance", None)
    reference_arg = getattr(args, "build_reference_frequency", None)
    return BuildConfig(
        eseries=getattr(args, "eseries", DEFAULT_ESERIES),
        capacitor_tolerance_pct=(
            getattr(args, "build_capacitor_tolerance_pct", None)
            if getattr(args, "build_capacitor_tolerance_pct", None) is not None
            else 5.0
        ),
        inductor_tolerance_pct=(
            getattr(args, "build_inductor_tolerance_pct", None)
            if getattr(args, "build_inductor_tolerance_pct", None) is not None
            else 10.0
        ),
        inductor_q=getattr(args, "build_inductor_q", None),
        capacitor_q=getattr(args, "build_capacitor_q", None),
        source_resistance_ohm=(
            parse_impedance(str(source_arg), label="Simulation source resistance")
            if source_arg is not None
            else None
        ),
        load_resistance_ohm=(
            parse_impedance(str(load_arg), label="Simulation load resistance")
            if load_arg is not None
            else None
        ),
        reference_frequency_hz=(
            parse_frequency(str(reference_arg), label="Loss reference frequency")
            if reference_arg is not None
            else None
        ),
        sample_count=(
            getattr(args, "build_sample_count", None)
            if getattr(args, "build_sample_count", None) is not None
            else 0
        ),
        seed=(
            getattr(args, "build_seed", None)
            if getattr(args, "build_seed", None) is not None
            else 0
        ),
        grid_points=(
            getattr(args, "build_grid_points", None)
            if getattr(args, "build_grid_points", None) is not None
            else 601
        ),
        use_toroid_candidates=not (
            bool(getattr(args, "no_toroid_build", False))
            or bool(getattr(args, "no_toroids", False))
        ),
    )
