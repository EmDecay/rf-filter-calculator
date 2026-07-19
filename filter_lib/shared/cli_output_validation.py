"""Cross-option validation for CLI output and analysis modes."""

from argparse import Namespace

from .cli_aliases import (
    DEFAULT_COMPONENTS,
    DEFAULT_IMPEDANCE,
    DEFAULT_Q_SAFETY,
    DEFAULT_RESONATORS,
)
from .cli_spice_validation import validate_spice_mode
from .cli_validation_error import usage_error


def _enabled_build_options(args: Namespace) -> list[str]:
    return [
        flag
        for value, flag in (
            (getattr(args, "build_capacitor_tolerance_pct", None), "--capacitor-tolerance"),
            (getattr(args, "build_inductor_tolerance_pct", None), "--inductor-tolerance"),
            (getattr(args, "build_inductor_q", None), "--inductor-q"),
            (getattr(args, "build_capacitor_q", None), "--capacitor-q"),
            (getattr(args, "build_source_resistance", None), "--source-resistance"),
            (getattr(args, "build_load_resistance", None), "--load-resistance"),
            (getattr(args, "build_reference_frequency", None), "--loss-reference-frequency"),
            (getattr(args, "build_sample_count", None), "--sample-count"),
            (getattr(args, "build_seed", None), "--seed"),
            (getattr(args, "build_grid_points", None), "--analysis-points"),
            (True if getattr(args, "no_toroid_build", False) else None, "--no-toroid-build"),
        )
        if value is not None
    ]


def _enabled_explain_design_options(args: Namespace) -> list[str]:
    """Return discoverably supplied design controls ignored by ``--explain``."""
    return [
        flag
        for enabled, flag in (
            (
                bool(getattr(args, "topology_pos", None) or getattr(args, "topology_flag", None)),
                "--topology",
            ),
            (
                bool(getattr(args, "coupling_pos", None) or getattr(args, "coupling_flag", None)),
                "--coupling",
            ),
            (
                bool(getattr(args, "frequency", None) or getattr(args, "freq_flag", None)),
                "--frequency",
            ),
            (bool(getattr(args, "bandwidth", None)), "--bandwidth"),
            (bool(getattr(args, "f_low", None)), "--fl"),
            (bool(getattr(args, "f_high", None)), "--fh"),
            (getattr(args, "impedance", DEFAULT_IMPEDANCE) != DEFAULT_IMPEDANCE, "--impedance"),
            (getattr(args, "components", DEFAULT_COMPONENTS) != DEFAULT_COMPONENTS, "--components"),
            (getattr(args, "resonators", DEFAULT_RESONATORS) != DEFAULT_RESONATORS, "--resonators"),
            (getattr(args, "ripple", None) is not None, "--ripple"),
            (getattr(args, "q_safety", DEFAULT_Q_SAFETY) != DEFAULT_Q_SAFETY, "--q-safety"),
            (getattr(args, "qu", None) is not None, "--qu"),
            (getattr(args, "ql", None) is not None, "--ql"),
            (getattr(args, "qc", None) is not None, "--qc"),
            (getattr(args, "resonator_impedance", None) is not None, "--resonator-impedance"),
            (getattr(args, "resonator_inductance", None) is not None, "--resonator-inductance"),
        )
        if enabled
    ]


def _validate_primary_output_mode(args: Namespace) -> None:
    output_format = getattr(args, "format", "table")
    quiet = bool(getattr(args, "quiet", False))
    raw = bool(getattr(args, "raw", False))
    plot = bool(getattr(args, "plot", False))
    sim_matched = bool(getattr(args, "sim_matched", False))
    sim_build = bool(getattr(args, "sim_build", False))
    explain = bool(getattr(args, "explain", False))
    toroid_text_mode = bool(
        getattr(args, "toroid_compact", False) or getattr(args, "toroid_full", False)
    )
    explicit_eseries = bool(getattr(args, "_eseries_explicit", False))
    no_match = bool(getattr(args, "no_match", False))
    no_toroids = bool(getattr(args, "no_toroids", False))
    if explicit_eseries and no_match:
        usage_error(args, "--eseries cannot be combined with --no-match")
    if getattr(args, "toroid_compact", False) and getattr(args, "toroid_full", False):
        usage_error(args, "use only one of --toroid-compact or --toroid-full")
    if no_toroids and toroid_text_mode:
        usage_error(args, "--no-toroids cannot be combined with a toroid table-detail option")
    if explain:
        incompatible = _enabled_explain_design_options(args) + [
            flag
            for enabled, flag in (
                (output_format != "table", f"--format {output_format}"),
                (quiet, "--quiet"),
                (raw, "--raw"),
                (plot, "--plot"),
                (bool(getattr(args, "plot_data", None)), "--plot-data"),
                (sim_matched, "--sim-matched"),
                (sim_build, "--sim-build"),
                (no_match, "--no-match"),
                (no_toroids, "--no-toroids"),
                (toroid_text_mode, "--toroid-compact/--toroid-full"),
                (explicit_eseries, "--eseries"),
            )
            if enabled
        ]
        if incompatible:
            usage_error(args, f"--explain is standalone; remove {', '.join(incompatible)}")
    if output_format != "table":
        incompatible = [
            flag
            for enabled, flag in (
                (quiet, "--quiet"),
                (raw, "--raw"),
                (plot, "--plot"),
                (toroid_text_mode, "--toroid-compact/--toroid-full"),
            )
            if enabled
        ]
        if incompatible:
            usage_error(
                args, f"{', '.join(incompatible)} cannot be used with --format {output_format}"
            )
    if quiet and plot:
        usage_error(args, "--quiet and --plot cannot be used together")
    if quiet and sim_matched:
        usage_error(args, "--quiet and --sim-matched cannot be used together")
    if quiet and sim_build:
        usage_error(args, "--quiet and --sim-build cannot be used together")
    if quiet and toroid_text_mode:
        usage_error(args, "--toroid-compact/--toroid-full cannot be used with --quiet")
    if quiet and explicit_eseries:
        usage_error(args, "--eseries is not represented by --quiet")
    if raw and explicit_eseries and not (sim_matched or sim_build):
        usage_error(args, "--eseries is not represented by raw component output")
    if sim_matched and sim_build:
        usage_error(args, "--sim-matched is deprecated; use --sim-build alone")


def _validate_plot_data_mode(args: Namespace) -> None:
    if not getattr(args, "plot_data", None):
        return
    output_format = getattr(args, "format", "table")
    incompatible = [
        flag
        for enabled, flag in (
            (output_format != "table", f"--format {output_format}"),
            (bool(getattr(args, "quiet", False)), "--quiet"),
            (bool(getattr(args, "raw", False)), "--raw"),
            (bool(getattr(args, "plot", False)), "--plot"),
            (bool(getattr(args, "sim_matched", False)), "--sim-matched"),
            (bool(getattr(args, "sim_build", False)), "--sim-build"),
            (bool(getattr(args, "_eseries_explicit", False)), "--eseries"),
            (
                bool(getattr(args, "toroid_compact", False) or getattr(args, "toroid_full", False)),
                "--toroid-compact/--toroid-full",
            ),
        )
        if enabled
    ]
    if incompatible:
        usage_error(
            args, f"--plot-data is a standalone output mode; remove {', '.join(incompatible)}"
        )


def _validate_build_mode(args: Namespace) -> None:
    output_format = getattr(args, "format", "table")
    sim_matched = bool(getattr(args, "sim_matched", False))
    sim_build = bool(getattr(args, "sim_build", False))
    no_match = bool(getattr(args, "no_match", False))
    spice_realization = getattr(args, "spice_realization", None)

    if sim_matched and output_format not in {"table", "json"}:
        usage_error(args, "--sim-matched is supported only with table or JSON output")
    if sim_build and output_format not in {"table", "json"}:
        usage_error(args, "--sim-build is supported only with table or JSON output")
    if (sim_matched or sim_build) and no_match:
        flag = "--sim-build" if sim_build else "--sim-matched"
        usage_error(args, f"{flag} requires selected nominal capacitor values; remove --no-match")
    explicit = _enabled_build_options(args)
    if explicit and not sim_build and output_format != "spice":
        usage_error(args, f"{', '.join(explicit)} require --sim-build or --format spice")
    if spice_realization is not None and output_format != "spice":
        usage_error(args, "--spice-realization requires --format spice")
    if output_format == "spice":
        validate_spice_mode(args)

    sample_count = getattr(args, "build_sample_count", None)
    if getattr(args, "build_seed", None) is not None and not sample_count:
        usage_error(args, "--seed requires a positive --sample-count")
    component_q = any(
        getattr(args, name, None) is not None for name in ("build_inductor_q", "build_capacitor_q")
    )
    resonator_q = any(getattr(args, name, None) is not None for name in ("qu", "ql", "qc"))
    if component_q and resonator_q:
        usage_error(
            args, "use either --qu/--ql/--qc or --inductor-q/--capacitor-q, not both loss models"
        )
    has_loss_q = component_q or resonator_q
    if getattr(args, "build_reference_frequency", None) is not None and not has_loss_q:
        usage_error(args, "--loss-reference-frequency requires a Q input")


def validate_output_mode_args(args: Namespace) -> None:
    """Reject supplied output options that the selected mode cannot honor."""
    _validate_primary_output_mode(args)
    _validate_plot_data_mode(args)
    _validate_build_mode(args)
