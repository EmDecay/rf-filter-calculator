"""Which output and build options apply to a set of choices, and why the others do not.

This is the one rule the wizard and the web use to disable a control that cannot
apply, with a one-line reason next to it. It restates, in the interfaces' own words,
the combinations the CLI refuses (``shared/cli_output_validation.py``,
``shared/cli_bandpass_output_validation.py`` for resonator Q, and
``RenderOptions.validate_for_build``/``validate_for_sub_pf``), so an option is offered
exactly when the equivalent CLI flag would be accepted. The build reasons are the
messages ``RenderOptions`` raises, so a refused request and a disabled control say the
same thing. Resonator Q is the one exception: its fields cannot be edited while disabled,
so their reason says what to choose instead (``LOSS_Q_DISABLED_MESSAGE``), while a
request that still sends Qu, QL, or QC is refused with the shared
``loss_q_not_shown_message`` (``require_applicable``).

Typical use::

    choices = OutputChoices(output_format="quiet", eseries="E24")
    inapplicable_options(choices)        # {"eseries": "...", "allow_sub_pf": "...", ...}
    option_reason(choices, TEXT_PLOT)    # the reason, or None when it applies
    require_applicable(choices, [TEXT_PLOT])   # raises ValueError(reason)

A control that does not apply is not applied to that output, which is what leaving out
the CLI flag means. Its visible value is still the user's choice: a surface that offers
other documents of the same design (the web's downloads, the wizard's saved files) judges
it again for each one with ``document_options``.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass, replace

from ..shared.cli_aliases import DEFAULT_ESERIES
from ..shared.cli_bandpass_output_validation import loss_q_not_shown_message
from ..shared.eseries import SUB_PF_OPTION_LABEL
from .render_options import (
    BUILD_NEEDS_ESERIES_MESSAGE,
    BUILD_NEEDS_TABLE_OR_JSON_MESSAGE,
    BUILD_NOT_WITH_VALUES_ONLY_MESSAGE,
    OUTPUT_FORMATS,
    SUB_PF_NEEDS_ESERIES_MESSAGE,
)

# Option names; the web uses them as ``data-option`` values.
ESERIES = "eseries"  # Standard capacitor values (E12/E24/E96/None)
ALLOW_SUB_PF = "allow_sub_pf"  # Allow capacitors below 1 pF
TOROID_DETAIL = "toroid_detail"  # Up to 3, detailed / Best, one line (CLI --toroid-full/-compact)
TEXT_PLOT = "plot"  # Text plot in the table (CLI --plot)
RAW_UNITS = "raw"  # Raw units (F, H) (CLI --raw)
BUILD = "build"  # Simulate the built filter (CLI --sim-build)
TOROID_BUILD = "toroid_build"  # Simulate inductors as the suggested toroid windings
LOSS_Q = "loss_q"  # Band-pass resonator Q: Qu, QL, QC (CLI --qu/--ql/--qc)
OPTIONS = (
    ESERIES,
    ALLOW_SUB_PF,
    TOROID_DETAIL,
    TEXT_PLOT,
    RAW_UNITS,
    BUILD,
    TOROID_BUILD,
    LOSS_Q,
)

TEXT_PLOT_NEEDS_TABLE_MESSAGE = "The text plot can be used only with Table format"
TOROID_DETAIL_NEEDS_TABLE_MESSAGE = "Toroid winding detail can be chosen only with Table format"
RAW_NEEDS_TABLE_MESSAGE = "Raw units can be used only with Table or Values only format"
TOROID_BUILD_NEEDS_TOROIDS_MESSAGE = (
    "There are no toroid windings to simulate when Toroid windings is None"
)
# The shared message every surface gives when resonator Q is refused, for all three fields.
LOSS_Q_NOT_SHOWN_MESSAGE = loss_q_not_shown_message(["Qu", "QL", "QC"])
# Why Qu, QL, and QC are disabled: a disabled field cannot be cleared, so this names the
# outputs that use them instead of asking the user to remove them.
LOSS_Q_DISABLED_MESSAGE = (
    "Resonator Q values are not used with Values only or CSV output; "
    "choose Table or JSON to use them"
)
# A refused request keeps the CLI's wording where it differs from the disabled reason.
_REFUSALS = {LOSS_Q: LOSS_Q_NOT_SHOWN_MESSAGE}
# Outputs that show the resonator-loss model (the CLI refuses --qu/--ql/--qc elsewhere).
_LOSS_Q_FORMATS = frozenset({"table", "json"})


def _no_effect_with_values_only(subject: str, verb: str) -> str:
    return f"{subject} {verb} no effect with Values only, which shows only calculated values"


def _no_effect_with_raw(subject: str, verb: str) -> str:
    return f"{subject} {verb} no effect with Raw units unless the build simulation is on"


_SUB_PF_SUBJECT = f'"{SUB_PF_OPTION_LABEL}"'
ESERIES_VALUES_ONLY_MESSAGE = _no_effect_with_values_only("Standard capacitor values", "have")
ESERIES_RAW_MESSAGE = _no_effect_with_raw("Standard capacitor values", "have")
SUB_PF_VALUES_ONLY_MESSAGE = _no_effect_with_values_only(_SUB_PF_SUBJECT, "has")
SUB_PF_RAW_MESSAGE = _no_effect_with_raw(_SUB_PF_SUBJECT, "has")


@dataclass(frozen=True)
class OutputChoices:
    """The choices that decide which other options apply, as the user set them.

    ``output_format`` is one of ``RenderOptions``' formats; ``"quiet"`` is Values only.
    ``eseries`` is ``None`` for "None" (no standard values). ``raw`` and ``build`` are
    the Raw units and Simulate the built filter boxes as ticked, even when the rule
    says they do not apply: the rule resolves that itself. ``include_toroids`` is
    False when Toroid windings is None (CLI ``--no-toroids``).
    """

    output_format: str = "table"
    eseries: str | None = DEFAULT_ESERIES
    raw: bool = False
    build: bool = False
    include_toroids: bool = True

    def __post_init__(self) -> None:
        if self.output_format not in OUTPUT_FORMATS:
            raise ValueError(f"Unknown output format: {self.output_format}")


def _build_reason(choices: OutputChoices) -> str | None:
    """The build rule, in ``RenderOptions.validate_for_build``'s order and words."""
    if choices.output_format == "quiet":
        return BUILD_NOT_WITH_VALUES_ONLY_MESSAGE
    if choices.output_format not in {"table", "json"}:
        return BUILD_NEEDS_TABLE_OR_JSON_MESSAGE
    if choices.eseries is None:
        return BUILD_NEEDS_ESERIES_MESSAGE
    return None


def inapplicable_options(choices: OutputChoices) -> dict[str, str]:
    """Return ``{option: reason}`` for every option in ``OPTIONS`` that cannot apply.

    Options not in the result apply. The build is judged on the E-series as chosen.
    With Raw units, the E-series applies only for a ticked build that the output
    format allows: the build then needs it, and choosing "None" there must stay
    reversible. Raw units count only where they apply, so a ticked box that does not
    apply never takes another option away.
    """
    reasons: dict[str, str] = {}
    table = choices.output_format == "table"
    values_only = choices.output_format == "quiet"
    if not table:
        reasons[TEXT_PLOT] = TEXT_PLOT_NEEDS_TABLE_MESSAGE
        reasons[TOROID_DETAIL] = TOROID_DETAIL_NEEDS_TABLE_MESSAGE
    if not (table or values_only):
        reasons[RAW_UNITS] = RAW_NEEDS_TABLE_MESSAGE
    build_reason = _build_reason(choices)
    if build_reason is not None:
        reasons[BUILD] = build_reason
    build_needs_eseries = choices.build and choices.output_format in {"table", "json"}
    raw = choices.raw and RAW_UNITS not in reasons

    if values_only:
        reasons[ESERIES] = ESERIES_VALUES_ONLY_MESSAGE
        reasons[ALLOW_SUB_PF] = SUB_PF_VALUES_ONLY_MESSAGE
    elif raw and not build_needs_eseries:
        reasons[ESERIES] = ESERIES_RAW_MESSAGE
        reasons[ALLOW_SUB_PF] = SUB_PF_RAW_MESSAGE
    elif choices.eseries is None:
        reasons[ALLOW_SUB_PF] = SUB_PF_NEEDS_ESERIES_MESSAGE

    if not choices.include_toroids:
        reasons[TOROID_BUILD] = TOROID_BUILD_NEEDS_TOROIDS_MESSAGE
    if choices.output_format not in _LOSS_Q_FORMATS:
        reasons[LOSS_Q] = LOSS_Q_DISABLED_MESSAGE
    return {option: reasons[option] for option in OPTIONS if option in reasons}


def option_reason(choices: OutputChoices, option: str) -> str | None:
    """Return why ``option`` cannot apply to ``choices``, or ``None`` when it applies."""
    if option not in OPTIONS:
        raise ValueError(f"Unknown option: {option}")
    return inapplicable_options(choices).get(option)


def require_applicable(choices: OutputChoices, selected: Iterable[str]) -> None:
    """Refuse the first selected option that cannot apply, with its reason.

    ``selected`` names the options the user actually set (a ticked box, a non-default
    toroid detail), checked in ``OPTIONS`` order. A surface passes only options it can
    tell were set: the web always submits an E-series, so it does not pass ``ESERIES``.
    Resonator Q is refused with the CLI's ``LOSS_Q_NOT_SHOWN_MESSAGE``, which asks for
    the values to be removed, rather than with its disabled-control reason.
    """
    chosen = set(selected)
    unknown = chosen.difference(OPTIONS)
    if unknown:
        raise ValueError(f"Unknown option: {', '.join(sorted(unknown))}")
    for option, reason in inapplicable_options(choices).items():
        if option in chosen:
            raise ValueError(_REFUSALS.get(option, reason))


# The output format whose rules each other document of a design follows: the design
# JSON and the chosen-parts SPICE deck carry the build and the loss model; the CSV, the
# calculated-values deck, and the response data carry neither.
DOCUMENT_FORMATS = {
    "json": "json",
    "spice-nominal": "json",
    "csv": "csv",
    "spice-exact": "csv",
    "response-json": "csv",
    "response-csv": "csv",
}
# The response data documents (CLI ``--plot-data``): the ideal response, which resonator
# Q never changes, so they leave Qu, QL, and QC out instead of refusing them.
RESPONSE_DOCUMENTS = frozenset({"response-json", "response-csv"})


def document_reason(document: str, option: str) -> str | None:
    """Why ``option`` cannot apply to ``document`` (a ``DOCUMENT_FORMATS`` key), or None.

    Judged on the document's own format with the other choices at their defaults, for
    options that depend only on the format (resonator Q, the text plot, raw units).
    """
    if document not in DOCUMENT_FORMATS:
        raise ValueError(f"Unknown document: {document}")
    return option_reason(OutputChoices(output_format=DOCUMENT_FORMATS[document]), option)


def document_options(
    choices: OutputChoices,
    document: str,
    *,
    applied: Iterable[str] = (),
    visible: Iterable[str] = (),
) -> frozenset[str]:
    """Return the options another document of the same design uses.

    ``choices`` are the visible choices (its ``output_format`` is replaced by the
    document's). ``applied`` options were used for the result shown and are kept as
    they are; the document may still refuse one, as the CLI would. ``visible`` options
    were set but did not apply to the result (their controls were disabled); each is
    added when it applies to ``document``. So Values only with E-series "None" gives a
    JSON document without standard values, never one with a substituted E24.
    """
    if document not in DOCUMENT_FORMATS:
        raise ValueError(f"Unknown document: {document}")
    reasons = inapplicable_options(replace(choices, output_format=DOCUMENT_FORMATS[document]))
    return frozenset(applied) | {option for option in visible if option not in reasons}
