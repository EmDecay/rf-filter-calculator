"""Build-simulation fields of the web form, mapped like ``make_build_config``.

Field names follow the CLI's ``build_*`` destinations; a fresh form is filled with the
CLI defaults and blanks take them too.
Resistances use the CLI's parsers and labels, so their messages match the CLI. The Q
frequency's message names the form label, which says what the CLI's flag name does not.
"""

from __future__ import annotations

from ..design.q_reference_frequency import Q_FREQUENCY_LABEL, parse_q_frequency
from ..shared.build_types import (
    RESONATOR_AND_COMPONENT_Q_MESSAGE,
    BuildConfig,
    require_seed_with_samples,
)
from ..shared.inductor_suggestion import DEFAULT_BUILD_INDUCTORS
from ..shared.parsing import parse_impedance
from .form_values import FormData, int_or, optional_float, text

# The Q frequency label is shared with the wizard; the template reads it from here.
__all__ = [
    "BUILD_FIELD_DEFAULTS",
    "Q_FREQUENCY_LABEL",
    "parse_build_config",
]

# The CLI's build defaults (``BuildConfig``'s), shown in the fields of a fresh form.
_DEFAULTS = BuildConfig()
BUILD_FIELD_DEFAULTS = {
    "build_sample_count": str(_DEFAULTS.sample_count),
    "build_seed": str(_DEFAULTS.seed),
    "build_grid_points": str(_DEFAULTS.grid_points),
    # "Inductors in the build": the CLI's --build-inductors default.
    "build_inductors": DEFAULT_BUILD_INDUCTORS,
}


def parse_build_config(form: FormData, *, resonator_q_supplied: bool) -> BuildConfig:
    """Return the ``BuildConfig`` for the submitted build controls."""
    inductor_q = optional_float(form, "build_inductor_q", "Inductor Q")
    capacitor_q = optional_float(form, "build_capacitor_q", "Capacitor Q")
    if resonator_q_supplied and (inductor_q is not None or capacitor_q is not None):
        raise ValueError(RESONATOR_AND_COMPONENT_Q_MESSAGE)
    source = text(form, "build_source_resistance")
    load = text(form, "build_load_resistance")
    reference = text(form, "build_reference_frequency")
    config = BuildConfig(
        inductor_tolerance_pct=optional_float(
            form, "build_inductor_tolerance_pct", "Inductor tolerance"
        ),
        inductor_q=inductor_q,
        capacitor_q=capacitor_q,
        source_resistance_ohm=(
            parse_impedance(source, label="Simulation source resistance") if source else None
        ),
        load_resistance_ohm=parse_impedance(load, label="Simulation load resistance")
        if load
        else None,
        reference_frequency_hz=(parse_q_frequency(reference) if reference else None),
        sample_count=int_or(
            form, "build_sample_count", "Extra random tolerance cases", _DEFAULTS.sample_count
        ),
        seed=int_or(form, "build_seed", "Random seed", _DEFAULTS.seed),
        grid_points=int_or(form, "build_grid_points", "Frequency points", _DEFAULTS.grid_points),
    )
    # After each field is checked, as in the wizard (the CLI's --seed rule, in labels).
    require_seed_with_samples(config.seed, config.sample_count)
    return config
