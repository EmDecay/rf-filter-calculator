"""Shared state dataclasses for the Textual wizard.

``FilterState`` holds what the user sees: every control's value, including a control the
shared rule (``filter_lib.design.option_applicability``) disables for the chosen output.
The result follows that rule as if a disabled control were unset, which is what leaving
out the CLI flag means. A saved JSON or CSV file or the response data file is another
document of the same design: like the web's downloads, it uses each visible value that
applies to it (``document_options``).
"""

from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Literal

from filter_lib.shared.build_types import BuildConfig
from filter_lib.shared.cli_aliases import DEFAULT_ESERIES

from .state_design_inputs import (
    CSV_DOCUMENT,
    CSV_WITH_BUILD_MESSAGE,
    JSON_DOCUMENT,
    DesignInputsMixin,
)

if TYPE_CHECKING:
    from filter_lib.design import DesignResult
    from filter_lib.shared.build_simulation import BuildAnalysisResult

__all__ = [
    "CALCULATION_STOPPED_MESSAGE",
    "CSV_DOCUMENT",
    "CSV_WITH_BUILD_MESSAGE",
    "INTERNAL_NO_BUILD_MESSAGE",
    "INTERNAL_NO_RESULT_MESSAGE",
    "JSON_DOCUMENT",
    "CalculationOutcome",
    "CalculationStatus",
    "FilterState",
    "ToroidDetail",
]

CalculationStatus = Literal["idle", "pending", "success", "error"]

# Guards for outcomes a working calculation never produces; seeing one is a bug.
INTERNAL_NO_RESULT_MESSAGE = (
    "Internal error: the calculation returned no result. Please report this."
)
INTERNAL_NO_BUILD_MESSAGE = (
    "Internal error: the calculation returned no build simulation. Please report this."
)
CALCULATION_STOPPED_MESSAGE = "Calculation stopped"
# "Best, detailed" (CLI default) · "Up to 3, detailed" (--toroid-full) ·
# "Best, one line" (--toroid-compact) · "None" (--no-toroids).
ToroidDetail = Literal["best", "full", "compact", "none"]
_BUILD_DEFAULTS = BuildConfig()


@dataclass(frozen=True)
class CalculationOutcome:
    """Detached result returned by a wizard calculation worker."""

    status: Literal["success", "error"]
    output_text: str = ""
    result: dict = field(default_factory=dict)
    error: str | None = None
    build_analysis: BuildAnalysisResult | None = None

    @property
    def succeeded(self) -> bool:
        """Return whether this contains a usable calculation result."""
        return self.status == "success" and bool(self.output_text.strip()) and bool(self.result)


@dataclass
class FilterState(DesignInputsMixin):
    """Holds all wizard state across screens.

    A single instance lives on `FilterWizardApp.filter_state`; each screen
    mutates it in place as the user advances, so going back and re-submitting
    simply overwrites the relevant fields. "Design another" on the results
    screen replaces the whole instance to restore these defaults.
    """

    # Filter selection
    category: str = ""  # lowpass, highpass, bandpass
    # Fields are deliberately overloaded across filter categories so LP/HP/BP
    # screens can share one state object (see per-field notes below).
    filter_type: str = "butterworth"
    topology: str = "pi"  # pi, t for lowpass/highpass; top for bandpass

    # Frequency parameters
    frequency_hz: float = 0.0  # cutoff for LP/HP, center for BP
    bandwidth_hz: float = 0.0  # bandpass only
    # Band-pass band given by its -3 dB edges ("Band edges"); ``frequency_hz`` and
    # ``bandwidth_hz`` then hold the center and width derived from them.
    requested_f_low_hz: float | None = None
    requested_f_high_hz: float | None = None

    # Common parameters
    impedance: float = 50.0
    order: int = 3  # num_components for LP/HP, resonators for BP
    ripple_db: float = 0.5
    # Optional band-pass tank constraint. At most one may be populated.
    resonator_impedance: float | None = None
    resonator_inductance: float | None = None
    # Band-pass resonator Q (CLI --qu/--ql/--qc): Qu, or QL and/or QC.
    qu: float | None = None
    ql: float | None = None
    qc: float | None = None

    # Output options, as shown (see the module docstring for disabled controls).
    eseries: str = DEFAULT_ESERIES  # E12, E24, E96, or "none"
    # "Allow capacitors below 1 pF" (CLI --allow-sub-pf).
    allow_sub_pf: bool = False
    # "table", "quiet" (Values only), "json", or "csv".
    output_format: str = "table"
    # Text plot in the table (CLI --plot), off by default as in the CLI and web.
    show_plot: bool = False
    # Response data file saved with the results: None, "json", or "csv".
    export_format: str | None = None
    raw_units: bool = False
    # Earlier name for Values only; ``output_format="quiet"`` is the same choice.
    quiet: bool = False
    # Toroid windings: "best" (CLI default), "full", "compact", or "none".
    # JSON always carries up to three candidates and CSV the best one.
    toroid_detail: ToroidDetail = "best"

    # Optional build simulation, off by default; the other values are the CLI's
    # defaults (``BuildConfig``) and map one-to-one onto it.
    build_analysis_enabled: bool = False
    build_capacitor_tolerance_pct: float = _BUILD_DEFAULTS.capacitor_tolerance_pct
    build_inductor_tolerance_pct: float = _BUILD_DEFAULTS.inductor_tolerance_pct
    build_inductor_q: float | None = None
    build_capacitor_q: float | None = None
    build_reference_frequency_hz: float | None = None
    build_source_resistance_ohm: float | None = None
    build_load_resistance_ohm: float | None = None
    build_sample_count: int = _BUILD_DEFAULTS.sample_count
    build_seed: int = _BUILD_DEFAULTS.seed
    build_grid_points: int = _BUILD_DEFAULTS.grid_points
    # "Simulate inductors as the suggested toroid windings" (unticked = --no-toroid-build).
    build_use_toroid_candidates: bool = True
    # The build fields as typed ({input id: text}), shown again when the output screen
    # reopens, so values survive unticking the build and going Back.
    build_field_text: dict[str, str] = field(default_factory=dict)
    # Why the typed build fields cannot be used, when the result did not need them (the
    # build was unticked or disabled). A saved JSON that uses the build reports it.
    build_input_error: str | None = None

    # Calculated results. filter_type_calculators stashes the raw result dict
    # here so the results screen's export paths can re-format (JSON/CSV/
    # response data) without recalculating. Empty dict means calculation
    # hasn't run or failed — exports must check before using it.
    result: dict = field(default_factory=dict)
    output_text: str = ""
    calculation_status: CalculationStatus = "idle"
    calculation_error: str | None = None
    build_analysis: BuildAnalysisResult | None = None
    # The design of the saved JSON when it uses a build or resonator Q the result shown
    # did not (``json_needs_own_design``). Calculated only when that JSON is saved.
    json_design: DesignResult | None = None
    # Incremented before every calculation and whenever design inputs change.
    # Worker results publish only when their captured revision is still current.
    calculation_revision: int = 0

    @property
    def is_exportable(self) -> bool:
        """Return whether the current revision has a usable successful result."""
        return (
            self.calculation_status == "success"
            and bool(self.result)
            and bool(self.output_text.strip())
            and (not self.runs_build or self.build_analysis is not None)
        )

    def _clear_calculation(self, status: CalculationStatus) -> None:
        self.result = {}
        self.output_text = ""
        self.calculation_status = status
        self.calculation_error = None
        self.build_analysis = None
        self.json_design = None

    def invalidate_calculation(self) -> None:
        """Synchronously invalidate output after any design input change."""
        self.calculation_revision += 1
        self._clear_calculation("idle")

    def begin_calculation(self) -> int:
        """Clear prior output, mark pending, and return the new revision."""
        self.calculation_revision += 1
        self._clear_calculation("pending")
        return self.calculation_revision

    def calculation_copy(self) -> FilterState:
        """Return an independent snapshot safe for a background worker."""
        return deepcopy(self)

    def publish_success(
        self,
        revision: int,
        output_text: str,
        result: dict,
        build_analysis: BuildAnalysisResult | None = None,
    ) -> bool:
        """Publish a successful outcome if its revision is still current."""
        if revision != self.calculation_revision or self.calculation_status != "pending":
            return False
        if not output_text.strip() or not result:
            self.publish_error(revision, INTERNAL_NO_RESULT_MESSAGE)
            return False
        self.output_text = output_text
        self.result = deepcopy(result)
        self.build_analysis = deepcopy(build_analysis)
        self.json_design = None
        self.calculation_status = "success"
        self.calculation_error = None
        return True

    def publish_error(self, revision: int, error: str) -> bool:
        """Publish a failed outcome if its revision is still current."""
        if revision != self.calculation_revision or self.calculation_status != "pending":
            return False
        self.result = {}
        self.output_text = ""
        self.build_analysis = None
        self.json_design = None
        self.calculation_status = "error"
        self.calculation_error = error
        return True

    def cancel_calculation(self, revision: int) -> bool:
        """Clear a pending calculation when its screen is removed."""
        if revision != self.calculation_revision or self.calculation_status != "pending":
            return False
        self._clear_calculation("idle")
        return True
