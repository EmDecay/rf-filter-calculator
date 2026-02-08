"""Shared state dataclasses for the Textual wizard."""

from dataclasses import dataclass, field


@dataclass
class FilterState:
    """Holds all wizard state across screens."""

    # Filter selection
    category: str = ""  # lowpass, highpass, bandpass
    filter_type: str = "butterworth"
    topology: str = "pi"  # pi, t for lowpass/highpass; top, shunt for bandpass

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
    show_plot: bool = True
    export_format: str | None = None
    raw_units: bool = False
    quiet: bool = False

    # Calculated results (populated after calculation)
    result: dict = field(default_factory=dict)
    output_text: str = ""
