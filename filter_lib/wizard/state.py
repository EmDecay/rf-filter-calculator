"""Shared state dataclasses for the Textual wizard."""

from dataclasses import dataclass, field


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

    # Output options
    eseries: str = "E24"
    output_format: str = "table"
    # Wizard shows the plot by default — deliberate divergence from the CLI's
    # opt-in --plot; the guided flow is the showcase experience.
    show_plot: bool = True
    export_format: str | None = None
    raw_units: bool = False
    quiet: bool = False

    # Calculated results. filter_type_calculators stashes the raw result dict
    # here so the results screen's export paths can re-format (JSON/CSV/
    # response data) without recalculating. Empty dict means calculation
    # hasn't run or failed — exports must check before using it.
    result: dict = field(default_factory=dict)
    output_text: str = ""
