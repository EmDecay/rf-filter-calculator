"""CLI definitions and conversion for realized-build analysis."""

from argparse import ArgumentParser, Namespace

from .cli_aliases import DEFAULT_ESERIES


def add_build_analysis_args(parser: ArgumentParser) -> None:
    """Add realized-build analysis and SPICE realization controls."""
    parser.add_argument(
        "--sim-build",
        action="store_true",
        help="Analyze selected nominal parts, finite component Q, deterministic "
        "tolerance corners, and optional seeded screening samples",
    )
    parser.add_argument(
        "--capacitor-tolerance",
        "--cap-tolerance",
        dest="build_capacitor_tolerance_pct",
        type=float,
        default=None,
        metavar="PCT",
        help="Capacitor tolerance bound for --sim-build (default: 5)",
    )
    parser.add_argument(
        "--inductor-tolerance",
        "--ind-tolerance",
        dest="build_inductor_tolerance_pct",
        type=float,
        default=None,
        metavar="PCT",
        help="Inductor tolerance bound for --sim-build (default: 10)",
    )
    parser.add_argument(
        "--inductor-q",
        dest="build_inductor_q",
        type=float,
        default=None,
        metavar="Q",
        help="Inductor Q at the loss-reference frequency",
    )
    parser.add_argument(
        "--capacitor-q",
        dest="build_capacitor_q",
        type=float,
        default=None,
        metavar="Q",
        help="Capacitor Q at the loss-reference frequency",
    )
    parser.add_argument(
        "--source-resistance",
        dest="build_source_resistance",
        default=None,
        metavar="OHMS",
        help="Evaluation source resistance; does not change equal-termination synthesis",
    )
    parser.add_argument(
        "--load-resistance",
        dest="build_load_resistance",
        default=None,
        metavar="OHMS",
        help="Evaluation load resistance; does not change equal-termination synthesis",
    )
    parser.add_argument(
        "--loss-reference-frequency",
        dest="build_reference_frequency",
        default=None,
        metavar="FREQ",
        help="Frequency where supplied Q values are converted to series loss "
        "(default: design frequency)",
    )
    parser.add_argument(
        "--sample-count",
        "--samples",
        dest="build_sample_count",
        type=int,
        default=None,
        metavar="N",
        help="Additional repeatable uniform-bounds screening cases (default: 0)",
    )
    parser.add_argument(
        "--seed",
        dest="build_seed",
        type=int,
        default=None,
        help="Seed for --sample-count; screening is not a probability/yield model",
    )
    parser.add_argument(
        "--analysis-points",
        dest="build_grid_points",
        type=int,
        default=None,
        metavar="N",
        help="Frequency-grid points for --sim-build (default: 601)",
    )
    parser.add_argument(
        "--no-toroid-build",
        action="store_true",
        help="Keep calculated inductance as an explicit nominal fallback instead "
        "of using screened integer-turn candidates",
    )
    parser.add_argument(
        "--spice-realization",
        choices=["exact", "nominal-build"],
        default=None,
        help="With --format spice, export calculated values or selected nominal parts "
        "(default: nominal-build)",
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
            parse_impedance(str(source_arg)) if source_arg is not None else None
        ),
        load_resistance_ohm=(parse_impedance(str(load_arg)) if load_arg is not None else None),
        reference_frequency_hz=(
            parse_frequency(str(reference_arg)) if reference_arg is not None else None
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
