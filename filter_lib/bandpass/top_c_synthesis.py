"""Raw, uncalibrated Top-C component synthesis."""

from typing import Any

from ..shared.numeric import is_finite_real
from .coupling_math import (
    _calculate_end_coupling_at_frequency,
    calculate_coupling_capacitors,
    calculate_coupling_coefficients,
    calculate_external_q,
    calculate_tank_capacitors,
)
from .resonator_math import _resolve_resonator_components

BandpassResult = dict[str, Any]


def _synthesize_top_c_raw(
    f_tank: float,
    fbw_synth: float,
    z0: float,
    n_resonators: int,
    g_values: list[float],
    resonator_impedance: float | None,
    resonator_inductance: float | None,
) -> BandpassResult:
    """Generate one uncompromised Top-C candidate without claiming its edges."""
    if not is_finite_real(fbw_synth) or fbw_synth <= 0:
        raise ValueError("fbw_synth must be positive and finite")

    k_values = calculate_coupling_coefficients(g_values, fbw_synth)
    qe_in, qe_out = calculate_external_q(g_values, fbw_synth)
    inductance, capacitance, resonator_z, selection = _resolve_resonator_components(
        f_tank, z0, resonator_impedance, resonator_inductance
    )
    c_coupling = calculate_coupling_capacitors(k_values, capacitance)
    c_tank = calculate_tank_capacitors(n_resonators, capacitance, c_coupling)

    c_end_in, delta_c_in = _calculate_end_coupling_at_frequency(qe_in, f_tank, inductance, z0)
    c_end_out, delta_c_out = _calculate_end_coupling_at_frequency(qe_out, f_tank, inductance, z0)
    c_tank[0] -= delta_c_in
    c_tank[-1] -= delta_c_out

    negative_caps = [index + 1 for index, value in enumerate(c_tank) if value <= 0]
    if negative_caps:
        cap_list = ", ".join(f"Cp{index}" for index in negative_caps)
        raise ValueError(
            f"Bandwidth too wide: tank capacitors {cap_list} would be negative. "
            "Reduce bandwidth, tank impedance, or resonator count."
        )

    return {
        "z0": z0,
        "n_resonators": n_resonators,
        "f_tank_hz": f_tank,
        "fbw_synth": fbw_synth,
        "g_values": g_values,
        "k_values": k_values,
        "qe_in": qe_in,
        "qe_out": qe_out,
        "L_resonant": inductance,
        "C_resonant": capacitance,
        "resonator_impedance": resonator_z,
        "resonator_selection": selection,
        "c_coupling": c_coupling,
        "c_tank": c_tank,
        "c_end_in": c_end_in,
        "c_end_out": c_end_out,
    }
