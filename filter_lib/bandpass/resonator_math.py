"""Resonator component selection, unloaded-Q math, and band-edge formulas."""

import math

from ..shared.numeric import positive_float_from_log
from .numeric_validation import _is_positive_finite

STANDARD_QU_VALUES: tuple[float, ...] = (100.0, 250.0)


def _resolve_resonator_components(
    f0: float,
    z0: float,
    resonator_impedance: float | None,
    resonator_inductance: float | None,
) -> tuple[float, float, float, str]:
    """Resolve tank L/C, actual reactance, and selection mode."""
    if not _is_positive_finite(f0):
        raise ValueError("f0 must be positive and finite")
    if not _is_positive_finite(z0):
        raise ValueError("z0 must be positive and finite")
    if resonator_impedance is not None and resonator_inductance is not None:
        raise ValueError("resonator_impedance and resonator_inductance are mutually exclusive")
    if resonator_impedance is not None and not _is_positive_finite(resonator_impedance):
        raise ValueError("resonator_impedance must be positive and finite")
    if resonator_inductance is not None and not _is_positive_finite(resonator_inductance):
        raise ValueError("resonator_inductance must be positive and finite")

    log_omega0 = math.log(2 * math.pi) + math.log(f0)
    if resonator_inductance is not None:
        inductance = resonator_inductance
        resonator_z = positive_float_from_log(
            log_omega0 + math.log(inductance), "resonator impedance"
        )
        capacitance = positive_float_from_log(
            -2 * log_omega0 - math.log(inductance), "resonator capacitance"
        )
        mode = "fixed_inductance"
    else:
        resonator_z = resonator_impedance if resonator_impedance is not None else z0
        inductance = positive_float_from_log(
            math.log(resonator_z) - log_omega0, "resonator inductance"
        )
        capacitance = positive_float_from_log(
            -log_omega0 - math.log(resonator_z), "resonator capacitance"
        )
        mode = "fixed_impedance" if resonator_impedance is not None else "system_impedance"
    if not all(_is_positive_finite(value) for value in (inductance, capacitance, resonator_z)):
        raise ValueError("Resonator choice does not produce finite positive component values")
    return inductance, capacitance, resonator_z, mode


def calculate_resonator_components(
    f0: float,
    z0: float,
    *,
    resonator_impedance: float | None = None,
    resonator_inductance: float | None = None,
) -> tuple[float, float]:
    """Return parallel tank L/C for the selected center frequency and impedance."""
    inductance, capacitance, _resonator_z, _mode = _resolve_resonator_components(
        f0, z0, resonator_impedance, resonator_inductance
    )
    return inductance, capacitance


def combine_resonator_q(
    qu: float | None = None,
    ql: float | None = None,
    qc: float | None = None,
) -> float | None:
    """Resolve complete unloaded Q directly or from reciprocal component losses."""
    if qu is not None and (ql is not None or qc is not None):
        raise ValueError("qu and separate ql/qc values are mutually exclusive")
    for name, value in (("Qu", qu), ("QL", ql), ("QC", qc)):
        if value is not None and not _is_positive_finite(value):
            raise ValueError(f"{name} must be positive and finite")
    if qu is not None:
        return qu
    if ql is None:
        return qc
    if qc is None:
        return ql
    smaller, larger = sorted((ql, qc))
    combined = smaller / (1.0 + smaller / larger)
    if combined <= 0:
        raise ValueError("Combined resonator Q is too small to represent")
    return combined


def estimate_insertion_loss(g_values: list[float], fbw_synth: float, qu: float) -> float:
    """Estimate Cohn midband dissipation loss for uniform resonator Q."""
    if not _is_positive_finite(fbw_synth):
        raise ValueError("fbw_synth must be positive and finite")
    if not _is_positive_finite(qu):
        raise ValueError("Qu must be positive and finite")
    if not g_values or any(not _is_positive_finite(value) for value in g_values):
        raise ValueError("g_values must contain positive finite values")
    largest = max(g_values)
    log_prototype_sum = math.log(largest) + math.log(
        math.fsum(value / largest for value in g_values)
    )
    return positive_float_from_log(
        math.log(4.343) + log_prototype_sum - math.log(fbw_synth) - math.log(qu),
        "Insertion-loss estimate",
    )


def calculate_min_q(f0: float, bw: float, safety_factor: float = 2.0) -> float:
    """Return the legacy unloaded-Q heuristic ``(f0/bw)*safety_factor``."""
    if not all(_is_positive_finite(value) for value in (f0, bw, safety_factor)):
        raise ValueError("Q heuristic inputs must be positive and finite")
    return positive_float_from_log(
        math.log(f0) - math.log(bw) + math.log(safety_factor), "Q heuristic"
    )


def compute_bandpass_3db_edges(f0: float, bw: float) -> tuple[float, float]:
    """Return exact geometrically centered -3 dB edges without cancellation."""
    if not _is_positive_finite(f0):
        raise ValueError("f0 must be positive and finite")
    if not _is_positive_finite(bw):
        raise ValueError("bw must be positive and finite")
    half_bw = bw / 2.0
    f_high = half_bw + math.hypot(half_bw, f0)
    f_low = f0 * (f0 / f_high)
    if not all(_is_positive_finite(value) for value in (f_low, f_high)):
        raise ValueError("f0 and bw must produce positive finite band edges")
    return f_low, f_high
