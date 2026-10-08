"""Parsing and state mapping for the wizard's build-simulation controls.

The fields, their labels, help, and order are the web form's (``build_options.html``);
a blank field takes the CLI default (``BuildConfig()``), which is also what a fresh form
shows. Which output and build options apply is decided by the shared rule
(``filter_lib.design.option_applicability``), never here.
"""

from __future__ import annotations

from dataclasses import dataclass, replace

from filter_lib.design.q_reference_frequency import (
    Q_FREQUENCY_HELP,
    Q_FREQUENCY_LABEL,
    parse_q_frequency,
)
from filter_lib.shared.build_simulation import BuildConfig
from filter_lib.shared.build_types import (
    RESONATOR_AND_COMPONENT_Q_MESSAGE,
    require_seed_with_samples,
)
from filter_lib.shared.parsing import parse_impedance
from filter_lib.shared.physical_input_limits import require_port_resistance

from .state import FilterState

BUILD_OPTION_PREFIX = "Build simulation: "
BUILD_OPTION_LABEL = "Simulate the built filter"
BUILD_OPTION_HELP = (
    "Simulates the filter with the parts you would actually fit: standard capacitor "
    "values, the suggested toroid windings, optional part Q, and component tolerances. "
    "Choose Table or JSON format and E12, E24, or E96 first. Simulated, not measured."
)
TOROID_BUILD_LABEL = "Simulate inductors as the suggested toroid windings"
TOROID_BUILD_HELP = (
    "Uses the inductance of each suggested whole-turn toroid winding. Untick to simulate "
    "each inductor at its calculated value."
)

_DEFAULTS = BuildConfig()


@dataclass(frozen=True)
class BuildField:
    """One build-simulation input: its widget id, label, and help, as on the web form."""

    input_id: str
    label: str
    help: str


# In the web form's order; Enter moves through them in this order.
BUILD_FIELDS = (
    BuildField(
        "build-capacitor-tolerance",
        "Capacitor tolerance (±%)",
        f"Blank = {_DEFAULTS.capacitor_tolerance_pct:g}.",
    ),
    BuildField(
        "build-inductor-tolerance",
        "Inductor tolerance (±%)",
        f"Blank = {_DEFAULTS.inductor_tolerance_pct:g}.",
    ),
    BuildField(
        "build-inductor-q",
        "Inductor Q",
        "Q of each inductor; blank = lossless. For band-pass, enter Q here or in the "
        "Resonator Qu, QL, and QC fields, not both.",
    ),
    BuildField("build-capacitor-q", "Capacitor Q", "Q of each capacitor; blank = lossless."),
    BuildField("build-reference-frequency", Q_FREQUENCY_LABEL, Q_FREQUENCY_HELP),
    BuildField(
        "build-source-resistance",
        "Simulation source resistance (Ω)",
        "Used only to simulate; component values are still designed for the impedance "
        "you entered. Blank = that impedance.",
    ),
    BuildField(
        "build-load-resistance",
        "Simulation load resistance (Ω)",
        "Blank = the impedance you entered.",
    ),
    BuildField(
        "build-sample-count",
        "Extra random tolerance cases",
        "Random part values within tolerance, added to the fixed tolerance cases. "
        f"0 to 10000; blank = {_DEFAULTS.sample_count}.",
    ),
    BuildField(
        "build-seed",
        "Random seed",
        f"The same seed repeats the same random cases. Blank = {_DEFAULTS.seed}.",
    ),
    BuildField(
        "build-grid-points",
        "Frequency points",
        "Points in the simulated frequency sweep, 51 to 5001; refined automatically "
        f"between points. Blank = {_DEFAULTS.grid_points}.",
    ),
)
BUILD_INPUT_FLOW = tuple(field.input_id for field in BUILD_FIELDS)

_PORT_FIELDS = ("source_resistance_ohm", "load_resistance_ohm")


class BuildOptionError(ValueError):
    """A rejected build-simulation setting and the input that produced it.

    ``field_id`` is the Input id to focus, or ``None`` when no single input is at
    fault. It is recorded while each field is parsed; message text is never searched,
    because parser messages echo whatever the user typed.
    """

    def __init__(self, message: str, field_id: str | None) -> None:
        super().__init__(message)
        self.field_id = field_id


@dataclass(frozen=True)
class BuildOptionValues:
    """Raw values collected from the build-simulation form, in form order."""

    capacitor_tolerance: str = f"{_DEFAULTS.capacitor_tolerance_pct:g}"
    inductor_tolerance: str = f"{_DEFAULTS.inductor_tolerance_pct:g}"
    inductor_q: str = ""
    capacitor_q: str = ""
    reference_frequency: str = ""
    source_resistance: str = ""
    load_resistance: str = ""
    sample_count: str = str(_DEFAULTS.sample_count)
    seed: str = str(_DEFAULTS.seed)
    grid_points: str = str(_DEFAULTS.grid_points)
    use_toroid_candidates: bool = True


def build_field_values(state: FilterState) -> dict[str, str]:
    """The text each build input shows for ``state`` (the CLI defaults on a fresh form).

    Text typed earlier (``state.build_field_text``) is shown as typed, even when the
    build was then unticked or could not be read.
    """

    def number(value: float | None) -> str:
        if value is None:
            return ""
        short = f"{value:g}"
        # Keep every digit the user entered: "5" for 5.0, the full value otherwise.
        return short if float(short) == value else repr(value)

    values = {
        "build-capacitor-tolerance": number(state.build_capacitor_tolerance_pct),
        "build-inductor-tolerance": number(state.build_inductor_tolerance_pct),
        "build-inductor-q": number(state.build_inductor_q),
        "build-capacitor-q": number(state.build_capacitor_q),
        "build-reference-frequency": number(state.build_reference_frequency_hz),
        "build-source-resistance": number(state.build_source_resistance_ohm),
        "build-load-resistance": number(state.build_load_resistance_ohm),
        "build-sample-count": str(state.build_sample_count),
        "build-seed": str(state.build_seed),
        "build-grid-points": str(state.build_grid_points),
    }
    typed = {key: text for key, text in state.build_field_text.items() if key in values}
    return {**values, **typed}


def parse_build_config(
    eseries: str,
    values: BuildOptionValues,
    *,
    design_impedance: float | None = None,
    resonator_q_supplied: bool = False,
) -> BuildConfig:
    """Parse raw form values and validate them through ``BuildConfig``.

    Fields are handled in form order; a blank field takes the CLI default. Each one is
    parsed and then validated by ``BuildConfig`` on its own, so any rejection is raised
    as a ``BuildOptionError`` naming the input that caused it. With
    ``design_impedance``, an explicit source or load resistance is also checked against
    the ratio that analysis would enforce, so the form can focus that input instead of
    failing later on Results. ``resonator_q_supplied`` (band-pass Qu, QL, or QC entered)
    refuses inductor or capacitor Q with the shared message, as the web does.
    """

    def number(value: str, label: str) -> float | None:
        if not value:
            return None
        try:
            return float(value)
        except ValueError as error:
            raise ValueError(f"{label} must be a number") from error

    def whole_number(value: str, label: str) -> int | None:
        if not value:
            return None
        try:
            return int(value)
        except ValueError as error:
            raise ValueError(f"{label} must be a whole number") from error

    def impedance(value: str, label: str) -> float | None:
        return parse_impedance(value, label=label) if value else None

    def frequency(value: str, _label: str) -> float | None:
        return parse_q_frequency(value) if value else None

    try:
        defaults = BuildConfig(eseries=eseries, use_toroid_candidates=values.use_toroid_candidates)
    except ValueError as error:
        raise BuildOptionError(str(error), None) from error

    # (BuildConfig field, Input id, parser, raw text, label used in messages), in form order.
    fields = (
        (
            "capacitor_tolerance_pct",
            "build-capacitor-tolerance",
            number,
            values.capacitor_tolerance,
            "Capacitor tolerance",
        ),
        (
            "inductor_tolerance_pct",
            "build-inductor-tolerance",
            number,
            values.inductor_tolerance,
            "Inductor tolerance",
        ),
        ("inductor_q", "build-inductor-q", number, values.inductor_q, "Inductor Q"),
        ("capacitor_q", "build-capacitor-q", number, values.capacitor_q, "Capacitor Q"),
        (
            "reference_frequency_hz",
            "build-reference-frequency",
            frequency,
            values.reference_frequency,
            Q_FREQUENCY_LABEL,
        ),
        (
            "source_resistance_ohm",
            "build-source-resistance",
            impedance,
            values.source_resistance,
            "Simulation source resistance",
        ),
        (
            "load_resistance_ohm",
            "build-load-resistance",
            impedance,
            values.load_resistance,
            "Simulation load resistance",
        ),
        (
            "sample_count",
            "build-sample-count",
            whole_number,
            values.sample_count,
            "Extra random tolerance cases",
        ),
        ("seed", "build-seed", whole_number, values.seed, "Random seed"),
        ("grid_points", "build-grid-points", whole_number, values.grid_points, "Frequency points"),
    )
    # Optional values stay None when blank; the others then take the CLI default.
    optional = {"inductor_q", "capacitor_q", "reference_frequency_hz", *_PORT_FIELDS}
    parsed: dict[str, object] = {}
    for config_name, field_id, parse, text, label in fields:
        try:
            value = parse(text, label)
            if value is None and config_name not in optional:
                value = getattr(defaults, config_name)
            # Validate this field alone against the shared contract.
            replace(defaults, **{config_name: value})
            if config_name in _PORT_FIELDS and value is not None and design_impedance:
                require_port_resistance(value, design_impedance, label)
        except ValueError as error:
            raise BuildOptionError(str(error), field_id) from error
        parsed[config_name] = value
        if config_name == "capacitor_q" and resonator_q_supplied:
            # The one cross-field rule: resonator Q from the design or part Q, not both.
            for name, input_id in (
                ("inductor_q", "build-inductor-q"),
                ("capacitor_q", "build-capacitor-q"),
            ):
                if parsed[name] is not None:
                    raise BuildOptionError(RESONATOR_AND_COMPONENT_Q_MESSAGE, input_id)

    try:
        config = replace(defaults, **parsed)
    except ValueError as error:
        # Every field passed on its own, and no build rule combines fields.
        raise BuildOptionError(str(error), None) from error
    try:
        # After each field is checked, as on the web (the CLI's --seed rule, in labels).
        require_seed_with_samples(config.seed, config.sample_count)
    except ValueError as error:
        raise BuildOptionError(str(error), "build-seed") from error
    return config


def apply_build_config(state: FilterState, enabled: bool, config: BuildConfig) -> None:
    """Persist a validated shared-engine configuration into wizard state."""
    state.build_analysis_enabled = enabled
    state.build_capacitor_tolerance_pct = config.capacitor_tolerance_pct
    state.build_inductor_tolerance_pct = config.inductor_tolerance_pct
    state.build_inductor_q = config.inductor_q
    state.build_capacitor_q = config.capacitor_q
    state.build_reference_frequency_hz = config.reference_frequency_hz
    state.build_source_resistance_ohm = config.source_resistance_ohm
    state.build_load_resistance_ohm = config.load_resistance_ohm
    state.build_sample_count = config.sample_count
    state.build_seed = config.seed
    state.build_grid_points = config.grid_points
    state.build_use_toroid_candidates = config.use_toroid_candidates
