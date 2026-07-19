"""Band-pass-only validation for loss/Q output semantics."""

from argparse import Namespace

from .cli_aliases import DEFAULT_Q_SAFETY
from .cli_output_validation import usage_error


def _supplied_q_flags(args: Namespace) -> list[str]:
    return [
        flag
        for name, flag in (("qu", "--qu"), ("ql", "--ql"), ("qc", "--qc"))
        if getattr(args, name, None) is not None
    ]


def validate_bandpass_output_args(args: Namespace) -> None:
    """Reject Q controls in modes that cannot represent their loss model."""
    q_flags = _supplied_q_flags(args)
    output_format = getattr(args, "format", "table")
    exact_spice = output_format == "spice" and (getattr(args, "spice_realization", None) == "exact")
    invisible_mode = (
        bool(getattr(args, "explain", False))
        or bool(getattr(args, "quiet", False))
        or bool(getattr(args, "plot_data", None))
        or output_format == "csv"
        or exact_spice
    )
    if q_flags and invisible_mode:
        usage_error(
            args,
            f"Loss-Q input {', '.join(q_flags)} is not represented by this output mode; "
            "use table, JSON, or nominal-build SPICE",
        )

    q_safety = getattr(args, "q_safety", DEFAULT_Q_SAFETY)
    if q_safety != DEFAULT_Q_SAFETY and (
        bool(getattr(args, "explain", False))
        or bool(getattr(args, "quiet", False))
        or bool(getattr(args, "plot_data", None))
        or output_format != "json"
    ):
        usage_error(args, "--q-safety is a compatibility-only JSON field; use --format json")
