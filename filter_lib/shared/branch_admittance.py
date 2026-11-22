"""Validation and admittance conversion for passive solver branches."""

import math

from .circuit_model import Branch
from .numeric import is_finite_real, require_positive_finite

_LOG_TWO_PI = math.log(2 * math.pi)


def normalise_branch(branch: Branch) -> tuple[int, int, str, float, float, float]:
    """Validate and expand a four-, five- or six-field branch.

    The optional fifth field is a series resistance and the sixth a capacitor's series
    inductance (a trimmer's), both zero when left out.
    """
    if not isinstance(branch, (tuple, list)):
        raise ValueError("Branch must be a tuple or list")
    series_resistance = series_inductance = 0.0
    if len(branch) == 4:
        n1, n2, kind, value = branch
    elif len(branch) == 5:
        n1, n2, kind, value, series_resistance = branch
    elif len(branch) == 6:
        n1, n2, kind, value, series_resistance, series_inductance = branch
    else:
        raise ValueError(
            "Branch must contain four fields plus optional series resistance and inductance"
        )
    if not isinstance(kind, str) or kind not in {"C", "L", "R"}:
        raise ValueError(f"Unknown branch kind {kind!r}: use 'C', 'L', or 'R'")
    require_positive_finite(value, "branch value")
    if not is_finite_real(series_resistance) or series_resistance < 0:
        raise ValueError("branch series resistance must be finite and non-negative")
    if kind == "R" and series_resistance:
        raise ValueError("resistor branches cannot specify a series resistance")
    if not is_finite_real(series_inductance) or series_inductance < 0:
        raise ValueError("branch series inductance must be finite and non-negative")
    if kind != "C" and series_inductance:
        raise ValueError("only capacitor branches can specify a series inductance")
    return n1, n2, kind, value, series_resistance, series_inductance


def branch_log_terms(
    value: float, series_resistance: float, series_inductance: float = 0.0
) -> tuple[float, float | None, float | None]:
    """Frequency-independent logarithms of a branch checked by ``normalise_branch``.

    Returns ``(log(value), log(series_resistance), log(series_inductance))``; a lossless
    branch has ``None`` as its loss term, and a branch without series inductance ``None``
    as its last. Computing these once per circuit leaves only the per-frequency admittance
    arithmetic in a sweep.
    """
    return (
        math.log(value),
        math.log(series_resistance) if series_resistance else None,
        math.log(series_inductance) if series_inductance else None,
    )


def log_angular_frequency(frequency: float) -> float:
    """Return ``log(2*pi*frequency)`` without materializing angular frequency."""
    return _LOG_TWO_PI + math.log(frequency)


def branch_admittance_from_logs(
    kind: str,
    log_value: float,
    log_omega: float,
    log_series_resistance: float | None,
    log_series_inductance: float | None = None,
) -> tuple[float, complex]:
    """Represent a validated branch admittance as ``(log(abs(Y)), unit_phase)``.

    Inputs come from ``normalise_branch``/``branch_log_terms`` and a finite positive
    frequency, so this per-frequency kernel does no validation of its own.
    """
    if kind == "R":
        return -log_value, 1 + 0j
    if log_series_inductance is not None:
        return _series_lc_admittance(
            log_value, log_omega, log_series_resistance, log_series_inductance
        )

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


def _series_lc_admittance(
    log_capacitance: float,
    log_omega: float,
    log_series_resistance: float | None,
    log_series_inductance: float,
) -> tuple[float, complex]:
    """A capacitor in series with its inductance (and resistance), as ``(log|Y|, unit)``.

    Its reactance is ``omega L - 1/(omega C)``; every term is scaled by the largest before
    the difference is taken, so the kernel stays finite wherever its terms are.
    """
    log_inductive = log_omega + log_series_inductance
    log_capacitive = -log_omega - log_capacitance
    logs = [log_inductive, log_capacitive]
    if log_series_resistance is not None:
        logs.append(log_series_resistance)
    log_scale = max(logs)
    reactance_scaled = math.exp(log_inductive - log_scale) - math.exp(log_capacitive - log_scale)
    resistance_scaled = (
        0.0 if log_series_resistance is None else math.exp(log_series_resistance - log_scale)
    )
    impedance_scaled = math.hypot(resistance_scaled, reactance_scaled)
    if impedance_scaled == 0:
        # A lossless branch exactly at its series resonance is a short. Its reactance is
        # then the difference's rounding residue: one unit in the last place of the terms.
        reactance_scaled = math.ulp(1.0)
        impedance_scaled = reactance_scaled
    unit = complex(resistance_scaled, -reactance_scaled) / impedance_scaled
    return -(log_scale + math.log(impedance_scaled)), unit
