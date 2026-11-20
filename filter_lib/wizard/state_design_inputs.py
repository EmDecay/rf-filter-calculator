"""What the wizard's result and saved files use, by the shared applicability rule.

``FilterState`` holds every control's visible value; this mixin turns those values into
the shared ``DesignRequest`` and ``RenderOptions`` for the result shown and for each
saved document. A control the rule (``filter_lib.design.option_applicability``) disables
is left out of the result, as the CLI does without the flag, and reaches each saved
document it applies to (``document_options``, the web downloads' mapping).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from filter_lib.design.option_applicability import (
    ALLOW_SUB_PF,
    BUILD,
    CAPACITOR_GRADE,
    CAPACITOR_TOLERANCE,
    ESERIES,
    LOSS_Q,
    LOSS_Q_NOT_SHOWN_MESSAGE,
    OPTIONS,
    RAW_UNITS,
    RESPONSE_DOCUMENTS,
    STRAY_CAPACITANCE,
    TEXT_PLOT,
    TOROID_BUILD,
    TOROID_DETAIL,
    OutputChoices,
    document_options,
    document_reason,
    inapplicable_options,
)
from filter_lib.shared.build_types import BuildConfig
from filter_lib.shared.cli_aliases import DEFAULT_ESERIES
from filter_lib.shared.eseries import DEFAULT_STRAY_CAPACITANCE_F

if TYPE_CHECKING:
    from filter_lib.design import DesignRequest, DesignResult, RenderOptions

# Saved CSV refuses a build simulation that was shown (the CSV has no place for it).
CSV_WITH_BUILD_MESSAGE = "CSV cannot include the build simulation. Save as Text or JSON."
# Other documents a result can be saved as (``DOCUMENT_FORMATS`` keys).
JSON_DOCUMENT = "json"
CSV_DOCUMENT = "csv"
# The response data file (``--plot-data``) is one of the shared ``RESPONSE_DOCUMENTS``.


class DesignInputsMixin:
    """Option rules and shared design inputs for ``FilterState`` (see the module)."""

    # -- Which options apply (the shared rule) --------------------------------------

    @property
    def shown_format(self) -> str:
        """The output format of the result: table, quiet (Values only), json, or csv."""
        if self.output_format == "table" and self.quiet:
            return "quiet"
        return self.output_format

    @property
    def include_toroids(self) -> bool:
        """False when Toroid windings is None (CLI --no-toroids)."""
        return self.toroid_detail != "none"

    @property
    def has_resonator_q(self) -> bool:
        """Whether a resonator Q (Qu, inductor Q, or capacitor Q) is entered (band-pass only)."""
        return self.category == "bandpass" and any(
            value is not None for value in (self.qu, self.ql, self.qc)
        )

    def option_choices(self) -> OutputChoices:
        """The choices the shared rule judges, as shown."""
        return OutputChoices(
            output_format=self.shown_format,
            eseries=None if self.eseries == "none" else self.eseries,
            raw=self.raw_units,
            build=self.build_analysis_enabled,
            include_toroids=self.include_toroids,
        )

    def option_reasons(self) -> dict[str, str]:
        """``{option: reason}`` for each option the shown output cannot apply."""
        return inapplicable_options(self.option_choices())

    def set_options(self) -> frozenset[str]:
        """The options the user set. A standard-values choice is always set."""
        chosen = {
            ESERIES: True,
            ALLOW_SUB_PF: self.allow_sub_pf,
            CAPACITOR_GRADE: self.capacitor_grade != "standard",
            CAPACITOR_TOLERANCE: bool(self.capacitor_tolerance_text.strip()),
            STRAY_CAPACITANCE: bool(self.stray_capacitance_text.strip()),
            TOROID_DETAIL: self.toroid_detail in ("full", "compact"),
            TEXT_PLOT: self.show_plot,
            RAW_UNITS: self.raw_units,
            BUILD: self.build_analysis_enabled,
            TOROID_BUILD: not self.build_use_toroid_candidates,
            LOSS_Q: self.has_resonator_q,
        }
        return frozenset(option for option in OPTIONS if chosen[option])

    def applied_options(self) -> frozenset[str]:
        """The options the result uses: those set, less those the rule disables."""
        return self.set_options().difference(self.option_reasons())

    def document_options(self, document: str) -> frozenset[str]:
        """The options a saved ``document`` (``DOCUMENT_FORMATS`` key) uses.

        A saved JSON or CSV keeps the options the result used (a CSV may then refuse
        one, see ``document_refusal``). The response data file is the ideal response,
        like the web's response downloads: every option is judged by that document's
        rule alone, so resonator Q and the build are left out of it, never refused.
        """
        applied = self.applied_options()
        if document in RESPONSE_DOCUMENTS:
            applied = frozenset()
        return document_options(
            self.option_choices(),
            document,
            applied=applied,
            visible=self.set_options().difference(applied),
        )

    @property
    def runs_build(self) -> bool:
        """Whether the result shown includes the build simulation."""
        return BUILD in self.applied_options()

    def document_refusal(self, document: str) -> str | None:
        """Why ``document`` cannot be saved for the result shown, or ``None``.

        Only a CSV refuses: it has no place for a build simulation or for resonator Q
        that the result used (the CLI refuses those flags there too). A disabled control
        never blocks a document.
        """
        if document != CSV_DOCUMENT:
            return None
        applied = self.applied_options()
        if BUILD in applied:
            return CSV_WITH_BUILD_MESSAGE
        if LOSS_Q in applied and document_reason(document, LOSS_Q) is not None:
            # A refusal, in the CLI's words: the result used the values.
            return LOSS_Q_NOT_SHOWN_MESSAGE
        return None

    # -- Shared design inputs ----------------------------------------------------------

    def _eseries_for(self, options: frozenset[str]) -> str | None:
        """The standard values used: the choice when it applies, else the CLI default."""
        if ESERIES not in options:
            return DEFAULT_ESERIES
        return None if self.eseries == "none" else self.eseries

    def make_build_config(self, options: frozenset[str] | None = None) -> BuildConfig:
        """Return the shared engine configuration for the current controls."""
        options = self.applied_options() if options is None else options
        return BuildConfig(
            inductor_tolerance_pct=self.build_inductor_tolerance_pct,
            inductor_q=self.build_inductor_q,
            capacitor_q=self.build_capacitor_q,
            source_resistance_ohm=self.build_source_resistance_ohm,
            load_resistance_ohm=self.build_load_resistance_ohm,
            reference_frequency_hz=self.build_reference_frequency_hz,
            sample_count=self.build_sample_count,
            seed=self.build_seed,
            grid_points=self.build_grid_points,
            # --no-toroids also leaves the windings out of the build (CLI rule).
            use_toroid_candidates=self.include_toroids and self.build_use_toroid_candidates,
        )

    def _design_request(self, options: frozenset[str], include_build: bool) -> DesignRequest:
        from filter_lib.design import DesignRequest

        bandpass = self.category == "bandpass"
        resonator_q = bandpass and LOSS_Q in options
        return DesignRequest(
            category=self.category,
            filter_type=self.filter_type,
            topology=self.topology,
            frequency_hz=self.frequency_hz,
            impedance=self.impedance,
            order=self.order,
            ripple_db=self.ripple_db,
            bandwidth_hz=self.bandwidth_hz if bandpass else None,
            requested_f_low_hz=self.requested_f_low_hz if bandpass else None,
            requested_f_high_hz=self.requested_f_high_hz if bandpass else None,
            qu=self.qu if resonator_q else None,
            ql=self.ql if resonator_q else None,
            qc=self.qc if resonator_q else None,
            resonator_impedance=self.resonator_impedance if bandpass else None,
            resonator_inductance=self.resonator_inductance if bandpass else None,
            eseries=self._eseries_for(options),
            allow_sub_pf=ALLOW_SUB_PF in options,
            capacitor_grade=self.capacitor_grade if CAPACITOR_GRADE in options else "standard",
            capacitor_tolerance_pct=(
                self.capacitor_tolerance_pct if CAPACITOR_TOLERANCE in options else None
            ),
            stray_capacitance_f=(
                self.stray_capacitance_f
                if STRAY_CAPACITANCE in options
                else DEFAULT_STRAY_CAPACITANCE_F
            ),
            # The wizard has no SPICE output, so the build settings matter only to a build.
            realization=self.make_build_config(options) if include_build else None,
            run_build_analysis=include_build,
        )

    def to_design_request(self) -> DesignRequest:
        """Return the shared design request for the result shown.

        ``order`` carries the component count for ladders and the resonator count for
        bandpass; ``topology`` carries the coupling id for bandpass. The build
        simulation is part of the request when the result shows it.
        """
        return self._design_request(self.applied_options(), include_build=self.runs_build)

    def document_request(self, document: str) -> DesignRequest:
        """The design request of a saved ``document`` (``DOCUMENT_FORMATS`` key).

        Only a saved JSON can carry the build. A build the result did not use was not
        checked when the result was shown; if its fields could not be read, the saved
        JSON reports why here.
        """
        options = self.document_options(document)
        include_build = document == JSON_DOCUMENT and BUILD in options
        if include_build and self.build_input_error is not None:
            raise ValueError(self.build_input_error)
        typed = {CAPACITOR_TOLERANCE, STRAY_CAPACITANCE} & options
        if typed and self.capacitor_input_error is not None:
            raise ValueError(self.capacitor_input_error)
        return self._design_request(options, include_build=include_build)

    def needs_own_design(self, document: str) -> bool:
        """Whether a saved ``document`` needs a design the result shown cannot give.

        The result is reused only for an equal request (same inputs and the same build);
        any other document is designed when it is saved, unless that was already done.
        """
        outcome = self.design_outcome
        shown = outcome.request if outcome is not None else self.to_design_request()
        request = self.document_request(document)
        if request == shown:
            return False
        stored = self.document_designs.get(document)
        return stored is None or stored.request != request

    def to_render_options(self) -> RenderOptions:
        """Return the shared render options for the result shown.

        Unlike the CLI, the wizard ends its table without a blank line and adds a line
        telling the ideal design above from the build simulation below.
        """
        from filter_lib.design import RenderOptions

        applied = self.applied_options()
        detail = self.toroid_detail if TOROID_DETAIL in applied else "best"
        return RenderOptions(
            output_format=self.shown_format,
            raw=RAW_UNITS in applied,
            show_plot=TEXT_PLOT in applied,
            include_toroids=self.include_toroids,
            toroid_compact=detail == "compact",
            toroid_full=detail == "full",
            trailing_blank=False,
            build_target_note=True,
        )

    def document_render_options(self, document: str) -> RenderOptions:
        """Render options of a saved JSON or CSV document (``--format json``/``csv``)."""
        from filter_lib.design import RenderOptions

        return RenderOptions(output_format=document, include_toroids=self.include_toroids)

    def design_result(self, document: str | None = None) -> DesignResult:
        """Return the shared ``DesignResult`` of the result shown, or of a saved document.

        A document reuses the result shown when its request is equal; otherwise it uses
        its own design, which the results screen calculates on Save.
        """
        from .state import INTERNAL_NO_RESULT_MESSAGE

        outcome = self.design_outcome
        if outcome is None:
            raise ValueError(INTERNAL_NO_RESULT_MESSAGE)
        if document is None:
            return outcome
        request = self.document_request(document)
        if request == outcome.request:
            return outcome
        stored = self.document_designs.get(document)
        if stored is None or stored.request != request:
            raise ValueError(INTERNAL_NO_RESULT_MESSAGE)
        return stored
