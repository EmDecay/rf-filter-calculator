"""Validation and admittance conversion for passive solver branches."""

import math

from .circuit_model import Branch
from .numeric import is_finite_real, positive_float_from_log

_LOG_TWO_PI = math.log(2 * math.pi)


def is_finite_number(value: object) -> bool:
    """Return whether ``value`` is a finite real number but not a boolean."""
    return is_finite_real(value)


def normalise_branch(branch: Branch) -> tuple[int, int, str, float, float]:
    """Validate and expand a legacy four- or five-field branch."""
    if not isinstance(branch, (tuple, list)):
        raise ValueError("Branch must be a tuple or list")
    if len(branch) == 4:
        n1, n2, kind, value = branch
        series_resistance = 0.0
    elif len(branch) == 5:
        n1, n2, kind, value, series_resistance = branch
    else:
        raise ValueError("Branch must contain four fields plus optional series resistance")
    if not isinstance(kind, str) or kind not in {"C", "L", "R"}:
        raise ValueError(f"Unknown branch kind {kind!r}: use 'C', 'L', or 'R'")
    if not is_finite_number(value) or value <= 0:
        raise ValueError("branch value must be positive and finite")
    if not is_finite_number(series_resistance) or series_resistance < 0:
        raise ValueError("branch series resistance must be finite and non-negative")
    if kind == "R" and series_resistance:
        raise ValueError("resistor branches cannot specify a series resistance")
    return n1, n2, kind, value, series_resistance


def branch_admittance(
    kind: str, value: float, omega: float, series_resistance: float = 0.0
) -> complex:
    """Return the finite complex admittance of one passive branch."""
    if not is_finite_number(omega) or omega <= 0:
        raise ValueError("omega must be positive and finite")
    log_magnitude, unit = _branch_admittance_from_log_omega(
        kind, value, math.log(omega), series_resistance
    )
    magnitude = positive_float_from_log(log_magnitude, "branch admittance")
    return unit * magnitude


def _branch_admittance_at_frequency(
    kind: str, value: float, frequency: float, series_resistance: float = 0.0
) -> tuple[float, complex]:
    """Return log magnitude and phase without materializing angular frequency."""
    if not is_finite_number(frequency) or frequency <= 0:
        raise ValueError("frequency must be positive and finite")
    return _branch_admittance_from_log_omega(
        kind, value, _LOG_TWO_PI + math.log(frequency), series_resistance
    )


def _branch_admittance_from_log_omega(
    kind: str, value: float, log_omega: float, series_resistance: float
) -> tuple[float, complex]:
    """Represent an admittance as ``(log(abs(Y)), unit_phase)``."""
    if not isinstance(kind, str) or kind not in {"C", "L", "R"}:
        raise ValueError(f"Unknown branch kind {kind!r}: use 'C', 'L', or 'R'")
    if not is_finite_number(value) or value <= 0:
        raise ValueError("branch value must be positive and finite")
    if not is_finite_number(series_resistance) or series_resistance < 0:
        raise ValueError("branch series resistance must be finite and non-negative")
    if kind == "R":
        if series_resistance:
            raise ValueError("resistor branches cannot specify a series resistance")
        return -math.log(value), 1 + 0j

    log_reactance = log_omega + math.log(value) if kind == "L" else -log_omega - math.log(value)
    reactance_sign = 1.0 if kind == "L" else -1.0
    if series_resistance == 0:
        return -log_reactance, complex(0.0, -reactance_sign)

    log_resistance = math.log(series_resistance)
    log_scale = max(log_resistance, log_reactance)
    resistance_scaled = math.exp(log_resistance - log_scale)
    reactance_scaled = math.exp(log_reactance - log_scale)
    impedance_scaled = math.hypot(resistance_scaled, reactance_scaled)
    log_impedance = log_scale + math.log(impedance_scaled)
    unit = complex(resistance_scaled, -reactance_sign * reactance_scaled) / impedance_scaled
    return -log_impedance, unit
