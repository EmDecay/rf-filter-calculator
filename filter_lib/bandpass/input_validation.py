"""Validation and design-range warnings for public bandpass synthesis inputs."""

from .design_constants import (
    BANDPASS_EDGE_CALIBRATION_FBW_MAX,
    BANDPASS_LUMPED_MODEL_CAUTION_FBW,
)
from .numeric_validation import _is_positive_finite


def _validate_inputs(
    f0: float,
    bw: float,
    z0: float,
    n_resonators: int,
    filter_type: str,
    coupling: str,
) -> None:
    """Validate core bandpass inputs before any synthesis work."""
    if not _is_positive_finite(f0):
        raise ValueError("Center frequency must be positive and finite")
    if not _is_positive_finite(bw):
        raise ValueError("Bandwidth must be positive and finite")
    if bw >= f0:
        raise ValueError("Bandwidth must be less than center frequency")
    if not _is_positive_finite(z0):
        raise ValueError("Impedance must be positive and finite")
    if (
        isinstance(n_resonators, bool)
        or not isinstance(n_resonators, int)
        or not 2 <= n_resonators <= 9
    ):
        raise ValueError("Number of resonators must be an integer between 2 and 9")
    if filter_type not in ("butterworth", "chebyshev", "bessel"):
        raise ValueError("Filter type must be 'butterworth', 'chebyshev', or 'bessel'")
    if coupling == "shunt":
        raise ValueError(
            "Shunt-C coupling has been removed: capacitive bottom coupling cannot "
            "realize the designed response (simulation-verified). Use Top-C ('top')."
        )
    if coupling != "top":
        raise ValueError("Coupling must be 'top'")


def _get_fbw_warnings(fbw: float) -> list[str]:
    """Return cautions beyond the edge study and lumped-model ranges."""
    warnings: list[str] = []
    if fbw > BANDPASS_EDGE_CALIBRATION_FBW_MAX:
        warnings.append(
            f"FBW {fbw * 100:.1f}% exceeds the studied edge-calibration range "
            "(<=10%) for Top-C; calibrated edges do not establish prototype-shape accuracy"
        )
    if fbw > BANDPASS_LUMPED_MODEL_CAUTION_FBW:
        warnings.append(f"FBW {fbw * 100:.1f}% exceeds 40%; consider transmission-line design")
    return warnings
