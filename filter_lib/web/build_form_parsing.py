"""Realized-build fields of the web form, mapped like ``make_build_config``.

Field names follow the CLI's ``build_*`` destinations; blanks take the CLI defaults,
and resistances and the loss-reference frequency use the CLI's parsers and labels.
"""

from __future__ import annotations

from ..shared.build_types import BuildConfig
from ..shared.parsing import parse_frequency, parse_impedance
from .form_values import FormData, flag, float_or, int_or, optional_float, text

LOSS_MODEL_CONFLICT = (
    "Use either resonator Q (Qu, QL, QC) or component Q (inductor, capacitor), not both loss models"
)


def parse_build_config(
    form: FormData, eseries: str, *, use_toroids: bool, resonator_q_supplied: bool
) -> BuildConfig:
    """Return the ``BuildConfig`` for the submitted build controls."""
    inductor_q = optional_float(form, "build_inductor_q", "Inductor Q")
    capacitor_q = optional_float(form, "build_capacitor_q", "Capacitor Q")
    if resonator_q_supplied and (inductor_q is not None or capacitor_q is not None):
        raise ValueError(LOSS_MODEL_CONFLICT)
    source = text(form, "build_source_resistance")
    load = text(form, "build_load_resistance")
    reference = text(form, "build_reference_frequency")
    return BuildConfig(
        eseries=eseries,
        capacitor_tolerance_pct=float_or(
            form, "build_capacitor_tolerance_pct", "Capacitor tolerance", 5.0
        ),
        inductor_tolerance_pct=float_or(
            form, "build_inductor_tolerance_pct", "Inductor tolerance", 10.0
        ),
        inductor_q=inductor_q,
        capacitor_q=capacitor_q,
        source_resistance_ohm=(
            parse_impedance(source, label="Source resistance") if source else None
        ),
        load_resistance_ohm=parse_impedance(load, label="Load resistance") if load else None,
        reference_frequency_hz=(
            parse_frequency(reference, label="Loss reference frequency") if reference else None
        ),
        sample_count=int_or(form, "build_sample_count", "Sample count", 0),
        seed=int_or(form, "build_seed", "Seed", 0),
        grid_points=int_or(form, "build_grid_points", "Analysis points", 601),
        use_toroid_candidates=use_toroids and not flag(form, "no_toroid_build"),
    )
