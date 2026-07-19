"""Cross-option validation specific to SPICE export."""

from argparse import Namespace

from .cli_validation_error import usage_error


def validate_spice_mode(args: Namespace) -> None:
    """Reject controls that the selected SPICE realization cannot honor."""
    if getattr(args, "sim_matched", False) or getattr(args, "sim_build", False):
        usage_error(args, "--format spice is a standalone output mode")
    unused = [
        flag
        for value, flag in (
            (getattr(args, "build_capacitor_tolerance_pct", None), "--capacitor-tolerance"),
            (getattr(args, "build_inductor_tolerance_pct", None), "--inductor-tolerance"),
            (getattr(args, "build_sample_count", None), "--sample-count"),
            (getattr(args, "build_seed", None), "--seed"),
            (getattr(args, "build_grid_points", None), "--analysis-points"),
        )
        if value is not None
    ]
    if unused:
        usage_error(
            args,
            f"{', '.join(unused)} affect tolerance analysis, not a SPICE deck; use --sim-build",
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
                (bool(getattr(args, "_eseries_explicit", False)), "--eseries"),
            )
            if enabled
        ]
        if exact_unused:
            usage_error(args, f"{', '.join(exact_unused)} cannot affect an exact lossless deck")
    elif getattr(args, "no_match", False):
        usage_error(
            args,
            "nominal-build SPICE requires selected capacitor values; remove --no-match "
            "or use --spice-realization exact",
        )
