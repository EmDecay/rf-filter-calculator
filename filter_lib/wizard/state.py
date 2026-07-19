"""Shared state dataclasses for the Textual wizard."""

from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Literal

if TYPE_CHECKING:
    from filter_lib.shared.build_simulation import BuildAnalysisResult, BuildConfig

CalculationStatus = Literal["idle", "pending", "success", "error"]


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
class FilterState:
    """Holds all wizard state across screens.

    A single instance lives on `FilterWizardApp.filter_state`; each screen
    mutates it in place as the user advances, so going back and re-submitting
    simply overwrites the relevant fields. "Design Another" on the results
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

    # Common parameters
    impedance: float = 50.0
    order: int = 3  # num_components for LP/HP, resonators for BP
    ripple_db: float = 0.5
    # Optional band-pass tank constraint. At most one may be populated.
    resonator_impedance: float | None = None
    resonator_inductance: float | None = None

    # Output options
    eseries: str = "E24"
    output_format: str = "table"
    # Wizard shows the plot by default — deliberate divergence from the CLI's
    # opt-in --plot; the guided flow is the showcase experience.
    show_plot: bool = True
    export_format: str | None = None
    raw_units: bool = False
    quiet: bool = False

    # Optional realized-build analysis. It is deliberately off by default;
    # these values map one-to-one onto shared.build_simulation.BuildConfig.
    build_analysis_enabled: bool = False
    build_capacitor_tolerance_pct: float = 5.0
    build_inductor_tolerance_pct: float = 10.0
    build_inductor_q: float | None = None
    build_capacitor_q: float | None = None
    build_resonator_q: float | None = None
    build_source_resistance_ohm: float | None = None
    build_load_resistance_ohm: float | None = None
    build_sample_count: int = 0
    build_seed: int = 0
    build_grid_points: int = 601
    build_use_toroid_candidates: bool = True

    # Calculated results. filter_type_calculators stashes the raw result dict
    # here so the results screen's export paths can re-format (JSON/CSV/
    # response data) without recalculating. Empty dict means calculation
    # hasn't run or failed — exports must check before using it.
    result: dict = field(default_factory=dict)
    output_text: str = ""
    calculation_status: CalculationStatus = "idle"
    calculation_error: str | None = None
    build_analysis: BuildAnalysisResult | None = None
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
            and (not self.build_analysis_enabled or self.build_analysis is not None)
        )

    def _clear_calculation(self, status: CalculationStatus) -> None:
        self.result = {}
        self.output_text = ""
        self.calculation_status = status
        self.calculation_error = None
        self.build_analysis = None

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
            self.publish_error(revision, "Calculation returned no usable result")
            return False
        self.output_text = output_text
        self.result = deepcopy(result)
        self.build_analysis = deepcopy(build_analysis)
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
        self.calculation_status = "error"
        self.calculation_error = error
        return True

    def make_build_config(self) -> BuildConfig:
        """Return the shared engine configuration for the current controls."""
        from filter_lib.shared.build_simulation import BuildConfig

        return BuildConfig(
            eseries=self.eseries,
            capacitor_tolerance_pct=self.build_capacitor_tolerance_pct,
            inductor_tolerance_pct=self.build_inductor_tolerance_pct,
            inductor_q=self.build_inductor_q,
            capacitor_q=self.build_capacitor_q,
            resonator_q=self.build_resonator_q,
            source_resistance_ohm=self.build_source_resistance_ohm,
            load_resistance_ohm=self.build_load_resistance_ohm,
            sample_count=self.build_sample_count,
            seed=self.build_seed,
            grid_points=self.build_grid_points,
            use_toroid_candidates=self.build_use_toroid_candidates,
        )

    def cancel_calculation(self, revision: int) -> bool:
        """Clear a pending calculation when its screen is removed."""
        if revision != self.calculation_revision or self.calculation_status != "pending":
            return False
        self._clear_calculation("idle")
        return True
