"""Cross-option validation specific to SPICE export.

``--sim-build`` and ``--sim-matched`` never reach this check: both are rejected with
``--format spice`` earlier, because they need table or JSON output.
"""

from argparse import Namespace

from .cli_output_validation import join_flags, matching_options, tolerance_analysis_options
from .cli_validation_error import usage_error


def validate_spice_mode(args: Namespace) -> None:
    """Reject controls that the selected SPICE realization cannot honor."""
    unused = tolerance_analysis_options(args)
    if unused:
        usage_error(
            args,
            f"{join_flags(unused, 'applies', 'apply')} only to --sim-build, not to a SPICE "
            f"deck; remove {'it' if len(unused) == 1 else 'them'} or use --sim-build instead "
            "of --format spice",
        )
    realization = getattr(args, "spice_realization", None) or "nominal-build"
    if realization == "exact":
        exact_unused = [
            flag
            for enabled, flag in (
                (getattr(args, "build_inductor_q", None) is not None, "--inductor-q"),
                (getattr(args, "build_capacitor_q", None) is not None, "--capacitor-q"),
                (
                    getattr(args, "build_reference_frequency", None) is not None,
                    "--loss-reference-frequency",
                ),
                (bool(getattr(args, "no_toroid_build", False)), "--no-toroid-build"),
            )
            if enabled
        ] + matching_options(args)
        if exact_unused:
            usage_error(
                args,
                f"{join_flags(exact_unused, 'has', 'have')} no effect on an exact SPICE deck, "
                "which uses the calculated values without losses; remove "
                f"{'it' if len(exact_unused) == 1 else 'them'} or use --spice-realization "
                "nominal-build",
            )
    elif getattr(args, "no_match", False):
        usage_error(
            args,
            "a nominal-build SPICE deck uses standard E-series capacitor values; remove "
            "--no-match or use --spice-realization exact",
        )
