"""Validation and admittance conversion for passive solver branches."""

import math

from .circuit_model import Branch
from .numeric import is_finite_real

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


def branch_log_terms(value: float, series_resistance: float) -> tuple[float, float | None]:
    """Frequency-independent logarithms of a branch checked by ``normalise_branch``.

    Returns ``(log(value), log(series_resistance))``; a lossless branch has ``None``
    as its loss term. Computing these once per circuit leaves only the per-frequency
    admittance arithmetic in a sweep.
    """
    return math.log(value), math.log(series_resistance) if series_resistance else None


def log_angular_frequency(frequency: float) -> float:
    """Return ``log(2*pi*frequency)`` without materializing angular frequency."""
    return _LOG_TWO_PI + math.log(frequency)


def branch_admittance_from_logs(
    kind: str, log_value: float, log_omega: float, log_series_resistance: float | None
) -> tuple[float, complex]:
    """Represent a validated branch admittance as ``(log(abs(Y)), unit_phase)``.

    Inputs come from ``normalise_branch``/``branch_log_terms`` and a finite positive
    frequency, so this per-frequency kernel does no validation of its own.
    """
    if kind == "R":
        return -log_value, 1 + 0j

    log_reactance = log_omega + log_value if kind == "L" else -log_omega - log_value
    reactance_sign = 1.0 if kind == "L" else -1.0
    if log_series_resistance is None:
        return -log_reactance, complex(0.0, -reactance_sign)

    log_scale = max(log_series_resistance, log_reactance)
    resistance_scaled = math.exp(log_series_resistance - log_scale)
    reactance_scaled = math.exp(log_reactance - log_scale)
    impedance_scaled = math.hypot(resistance_scaled, reactance_scaled)
    log_impedance = log_scale + math.log(impedance_scaled)
    unit = complex(resistance_scaled, -reactance_sign * reactance_scaled) / impedance_scaled
    return -log_impedance, unit
