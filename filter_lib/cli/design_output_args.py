"""Map parsed CLI output flags onto the shared design dispatcher's options."""

from argparse import Namespace
from typing import Any

from ..design import RenderOptions
from ..shared.capacitor_grades import DEFAULT_GRADE
from ..shared.cli_helpers import make_build_config
from ..shared.eseries import DEFAULT_STRAY_CAPACITANCE_F
from ..shared.inductor_suggestion import DEFAULT_BUILD_INDUCTORS, DEFAULT_INDUCTOR_DETAIL
from ..shared.parsing import parse_stray_capacitance


def part_policy_args(args: Namespace) -> dict[str, Any]:
    """The ``DesignRequest`` part policy and build fields the CLI flags select.

    The build settings (``realization``) are always attached: a chosen-parts SPICE deck
    uses them without ``--sim-build``, and the flags that only the build simulation uses
    are refused elsewhere unless it runs.
    """
    stray = getattr(args, "stray_capacitance", None)
    return {
        "eseries": None if args.no_match else args.eseries,
        "allow_sub_pf": bool(getattr(args, "allow_sub_pf", False)),
        "capacitor_grade": getattr(args, "capacitor_grade", None) or DEFAULT_GRADE,
        "capacitor_tolerance_pct": getattr(args, "capacitor_tolerance_pct", None),
        "stray_capacitance_f": (
            DEFAULT_STRAY_CAPACITANCE_F if stray is None else parse_stray_capacitance(stray)
        ),
        "inductor_suggestions": getattr(args, "inductor_suggestions", None)
        or DEFAULT_INDUCTOR_DETAIL,
        "build_inductors": getattr(args, "build_inductors", None) or DEFAULT_BUILD_INDUCTORS,
        "realization": make_build_config(args),
        "run_build_analysis": bool(getattr(args, "sim_build", False)),
    }


def render_options_from_args(args: Namespace) -> RenderOptions:
    """Return the CLI's render options; ``--quiet`` selects the quiet format."""
    return RenderOptions(
        output_format="quiet" if args.quiet else args.format,
        raw=args.raw,
        show_plot=args.plot,
    )


def spice_realization_from_args(args: Namespace) -> str:
    """Return the SPICE realization id; nominal-build is the CLI default."""
    return (getattr(args, "spice_realization", None) or "nominal-build").replace("-", "_")
