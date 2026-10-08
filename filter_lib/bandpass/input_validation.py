"""Validation and design-range warnings for public bandpass synthesis inputs."""

from .design_constants import (
    BANDPASS_EDGE_CALIBRATION_FBW_MAX,
    BANDPASS_LUMPED_MODEL_CAUTION_FBW,
)
from .numeric_validation import _is_positive_finite

# Shared with the wizard, which checks the same rules before calculating.
BANDWIDTH_NOT_BELOW_CENTER = "Bandwidth must be less than center frequency"
RESONATOR_COUNT_MESSAGE = "Number of resonators must be from 2 to 9"


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
        raise ValueError(BANDWIDTH_NOT_BELOW_CENTER)
    if not _is_positive_finite(z0):
        raise ValueError("Impedance must be positive and finite")
    if (
        isinstance(n_resonators, bool)
        or not isinstance(n_resonators, int)
        or not 2 <= n_resonators <= 9
    ):
        raise ValueError(RESONATOR_COUNT_MESSAGE)
    if filter_type not in ("butterworth", "chebyshev", "bessel"):
        raise ValueError("Filter type must be 'butterworth', 'chebyshev', or 'bessel'")
    if coupling == "shunt":
        raise ValueError(
            "Shunt-C coupling has been removed: capacitive bottom coupling cannot "
            "realize the designed response (simulation-verified). Use Top-C ('top')."
        )
    if coupling != "top":
        raise ValueError("Coupling must be 'top'")


def _percent(fraction: float) -> str:
    """Format a fraction as a percentage without trailing zeros (0.1 -> ``10%``)."""
    return f"{fraction * 100:g}%"


def fbw_untested_warning(fbw: float) -> str:
    """Caution for a fractional bandwidth above the range the Top-C design was tested for.

    Above that range the -3 dB edges are still placed and independently verified (a
    design whose edges miss is rejected), but the response shape is not confirmed.
    """
    return (
        f"Fractional bandwidth {fbw * 100:.1f}% is above the "
        f"{_percent(BANDPASS_EDGE_CALIBRATION_FBW_MAX)} this design method was tested up to. "
        "The -3 dB edges still match your request, but the response shape may differ from "
        "the ideal response shape; check it before building."
    )


def fbw_impractical_warning(fbw: float) -> str:
    """Advice for a fractional bandwidth too wide for a coupled-resonator design."""
    return (
        f"Fractional bandwidth {fbw * 100:.1f}% is above "
        f"{_percent(BANDPASS_LUMPED_MODEL_CAUTION_FBW)}, where a coupled-resonator design "
        "becomes impractical. Consider a high-pass filter followed by a low-pass filter "
        "instead."
    )


def _get_fbw_warnings(fbw: float) -> list[str]:
    """Return cautions beyond the tested and coupled-resonator bandwidth ranges."""
    warnings: list[str] = []
    if fbw > BANDPASS_EDGE_CALIBRATION_FBW_MAX:
        warnings.append(fbw_untested_warning(fbw))
    if fbw > BANDPASS_LUMPED_MODEL_CAUTION_FBW:
        warnings.append(fbw_impractical_warning(fbw))
    return warnings
