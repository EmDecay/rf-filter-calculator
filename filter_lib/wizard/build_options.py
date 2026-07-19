"""Parsing and state mapping for wizard realized-build controls."""

from __future__ import annotations

from dataclasses import dataclass

from filter_lib.shared.build_simulation import BuildConfig
from filter_lib.shared.parsing import parse_impedance

from .state import FilterState

BUILD_INPUT_FLOW = (
    "build-source-resistance",
    "build-load-resistance",
    "build-capacitor-tolerance",
    "build-inductor-tolerance",
    "build-inductor-q",
    "build-capacitor-q",
    "build-resonator-q",
    "build-sample-count",
    "build-seed",
    "build-grid-points",
)

BUILD_ERROR_INPUTS = (
    (("source",), "build-source-resistance"),
    (("load",), "build-load-resistance"),
    (("capacitor_tolerance", "capacitor tolerance"), "build-capacitor-tolerance"),
    (("inductor_tolerance", "inductor tolerance"), "build-inductor-tolerance"),
    (("inductor_q", "inductor Q"), "build-inductor-q"),
    (("capacitor_q", "capacitor Q"), "build-capacitor-q"),
    (("resonator_q", "resonator Q", "mutually exclusive"), "build-resonator-q"),
    (("sample_count", "sample count"), "build-sample-count"),
    (("seed",), "build-seed"),
    (("grid_points", "analysis points"), "build-grid-points"),
)


@dataclass(frozen=True)
class BuildOptionIssue:
    """One incompatible output/build selection and its focus target."""

    message: str
    focus_selector: str


@dataclass(frozen=True)
class BuildOptionValues:
    """Raw values collected from the optional advanced-controls form."""

    source_resistance: str = ""
    load_resistance: str = ""
    capacitor_tolerance: str = "5"
    inductor_tolerance: str = "10"
    inductor_q: str = ""
    capacitor_q: str = ""
    resonator_q: str = ""
    sample_count: str = "0"
    seed: str = "0"
    grid_points: str = "601"
    use_toroid_candidates: bool = True


def output_option_issue(
    *,
    output_format: str,
    raw: bool,
    quiet: bool,
    show_plot: bool,
    eseries: str,
    build_enabled: bool,
) -> BuildOptionIssue | None:
    """Return an incompatible primary-output selection instead of ignoring it."""
    if output_format != "table":
        selected = [
            label
            for enabled, label in (
                (raw, "raw units"),
                (quiet, "quiet mode"),
                (show_plot, "the frequency-response plot"),
            )
            if enabled
        ]
        if selected:
            return BuildOptionIssue(
                f"{', '.join(selected)} can be used only with table component output",
                "#options-list",
            )
    if quiet and show_plot:
        return BuildOptionIssue(
            "Quiet mode and the frequency-response plot cannot be combined",
            "#options-list",
        )
    # Raw component rows do not display E-series recommendations, but an
    # enabled build analysis still consumes the series to select its physical
    # capacitor realization.  This matches the CLI's --raw --sim-build
    # contract.  Quiet output cannot represent either result.
    if eseries != "none" and (quiet or (raw and not build_enabled)):
        hidden_by = "raw units" if raw else "quiet mode"
        return BuildOptionIssue(
            f"The selected E-series is not represented by {hidden_by}; select None or disable it",
            "#eseries",
        )
    return None


def build_option_issue(
    *,
    enabled: bool,
    output_format: str,
    quiet: bool,
    eseries: str,
    has_custom_controls: bool = False,
) -> BuildOptionIssue | None:
    """Return the first incompatible build/output selection, if any."""
    if enabled and output_format not in {"table", "json"}:
        return BuildOptionIssue(
            "Realized-build analysis is supported only with table or JSON component output",
            "#format",
        )
    if enabled and quiet:
        return BuildOptionIssue(
            "Realized-build analysis cannot be combined with quiet output",
            "#options-list",
        )
    if enabled and eseries == "none":
        return BuildOptionIssue(
            "Realized-build analysis requires an E-series for nominal capacitor selection",
            "#eseries",
        )
    if not enabled and has_custom_controls:
        return BuildOptionIssue(
            "Enable realized-build analysis to use the advanced build settings",
            "#build-analysis-enabled",
        )
    return None


def build_error_input_id(error: str) -> str | None:
    """Map a shared validation error to the most relevant build input."""
    for tokens, input_id in BUILD_ERROR_INPUTS:
        if any(token in error for token in tokens):
            return input_id
    return None


def parse_build_config(eseries: str, values: BuildOptionValues) -> BuildConfig:
    """Parse raw form values and validate them through ``BuildConfig``."""

    def optional_float(value: str, label: str) -> float | None:
        if not value:
            return None
        try:
            return float(value)
        except ValueError as error:
            raise ValueError(f"{label} must be a number") from error

    def required_float(value: str, label: str) -> float:
        try:
            return float(value)
        except ValueError as error:
            raise ValueError(f"{label} must be a number") from error

    def required_int(value: str, label: str) -> int:
        try:
            return int(value)
        except ValueError as error:
            raise ValueError(f"{label} must be an integer") from error

    def optional_impedance(value: str, label: str) -> float | None:
        if not value:
            return None
        try:
            return parse_impedance(value)
        except ValueError as error:
            raise ValueError(f"{label}: {error}") from error

    return BuildConfig(
        eseries=eseries,
        capacitor_tolerance_pct=required_float(values.capacitor_tolerance, "capacitor tolerance"),
        inductor_tolerance_pct=required_float(values.inductor_tolerance, "inductor tolerance"),
        inductor_q=optional_float(values.inductor_q, "inductor Q"),
        capacitor_q=optional_float(values.capacitor_q, "capacitor Q"),
        resonator_q=optional_float(values.resonator_q, "resonator Q"),
        source_resistance_ohm=optional_impedance(values.source_resistance, "source resistance"),
        load_resistance_ohm=optional_impedance(values.load_resistance, "load resistance"),
        sample_count=required_int(values.sample_count, "sample count"),
        seed=required_int(values.seed, "seed"),
        grid_points=required_int(values.grid_points, "analysis points"),
        use_toroid_candidates=values.use_toroid_candidates,
    )


def has_custom_build_controls(config: BuildConfig) -> bool:
    """Return whether any advanced value differs from the visible defaults."""
    default = BuildConfig(eseries=config.eseries)
    fields = (
        "capacitor_tolerance_pct",
        "inductor_tolerance_pct",
        "inductor_q",
        "capacitor_q",
        "resonator_q",
        "source_resistance_ohm",
        "load_resistance_ohm",
        "sample_count",
        "seed",
        "grid_points",
        "use_toroid_candidates",
    )
    return any(getattr(config, name) != getattr(default, name) for name in fields)


def apply_build_config(state: FilterState, enabled: bool, config: BuildConfig) -> None:
    """Persist a validated shared-engine configuration into wizard state."""
    state.build_analysis_enabled = enabled
    state.build_capacitor_tolerance_pct = config.capacitor_tolerance_pct
    state.build_inductor_tolerance_pct = config.inductor_tolerance_pct
    state.build_inductor_q = config.inductor_q
    state.build_capacitor_q = config.capacitor_q
    state.build_resonator_q = config.resonator_q
    state.build_source_resistance_ohm = config.source_resistance_ohm
    state.build_load_resistance_ohm = config.load_resistance_ohm
    state.build_sample_count = config.sample_count
    state.build_seed = config.seed
    state.build_grid_points = config.grid_points
    state.build_use_toroid_candidates = config.use_toroid_candidates
