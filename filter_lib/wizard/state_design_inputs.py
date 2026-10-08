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
    ESERIES,
    LOSS_Q,
    LOSS_Q_NOT_SHOWN_MESSAGE,
    OPTIONS,
    RAW_UNITS,
    RESPONSE_DOCUMENTS,
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

if TYPE_CHECKING:
    from filter_lib.design import DesignRequest, DesignResult, RenderOptions

# Saved CSV refuses a build simulation that was shown (the CSV has no place for it).
CSV_WITH_BUILD_MESSAGE = "CSV cannot include the build simulation. Save as Text or JSON."
# Other documents a result can be saved as (``DOCUMENT_FORMATS`` keys).
JSON_DOCUMENT = "json"
CSV_DOCUMENT = "csv"
# The response data file (``--plot-data``) is one of the shared ``RESPONSE_DOCUMENTS``.
# Options that change the calculated design, not only how it is written out.
_DESIGN_OPTIONS = frozenset({BUILD, LOSS_Q})


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
        """Whether Qu, QL, or QC is entered (band-pass only)."""
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

    def json_needs_own_design(self) -> bool:
        """Whether the saved JSON uses a build or resonator Q the result shown did not."""
        extra = self.document_options(JSON_DOCUMENT).difference(self.applied_options())
        return bool(extra & _DESIGN_OPTIONS)

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
            eseries=self._eseries_for(options) or DEFAULT_ESERIES,
            capacitor_tolerance_pct=self.build_capacitor_tolerance_pct,
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
            build=self.make_build_config(options) if include_build else None,
            allow_sub_pf=ALLOW_SUB_PF in options,
        )

    def to_design_request(self, include_build: bool) -> DesignRequest:
        """Return the shared design request for the result shown.

        ``order`` carries the component count for ladders and the resonator count for
        bandpass; ``topology`` carries the coupling id for bandpass. The build
        configuration is attached only when ``include_build`` is true.
        """
        return self._design_request(self.applied_options(), include_build)

    def json_design_request(self) -> DesignRequest:
        """The design request of the saved JSON, with its build when it uses one.

        A build the result did not use was not checked when the result was shown; if
        its fields could not be read, the saved JSON reports why here.
        """
        options = self.document_options(JSON_DOCUMENT)
        include_build = BUILD in options
        if include_build and self.build_input_error is not None:
            raise ValueError(self.build_input_error)
        return self._design_request(options, include_build=include_build)

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
            eseries=self._eseries_for(applied),
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

        return RenderOptions(
            output_format=document,
            eseries=self._eseries_for(self.document_options(document)),
            include_toroids=self.include_toroids,
        )

    def design_result(self, document: str | None = None) -> DesignResult:
        """Return the stored calculation as a shared ``DesignResult``.

        With ``document``, the result as that saved document uses it: the separately
        calculated design when the JSON needs one, otherwise the stored result with the
        document's sub-pF choice (the build only where the document carries it).
        """
        from filter_lib.design import DesignResult

        if document is None:
            options = self.applied_options()
        else:
            if document == JSON_DOCUMENT and self.json_needs_own_design():
                if self.json_design is None:
                    from .state import INTERNAL_NO_RESULT_MESSAGE

                    raise ValueError(INTERNAL_NO_RESULT_MESSAGE)
                return self.json_design
            options = self.document_options(document)
        return DesignResult(
            category=self.category,
            result=self.result,
            build_analysis=self.build_analysis if BUILD in options else None,
            allow_sub_pf=ALLOW_SUB_PF in options,
        )
