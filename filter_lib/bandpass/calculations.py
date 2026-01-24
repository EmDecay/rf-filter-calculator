"""Coupled resonator bandpass filter calculations.

Contains coupling coefficient formulas and component value calculations
for Top-C and Shunt-C topologies.

References:
- Matthaei, Young, Jones "Microwave Filters, Impedance-Matching Networks..."
- Zverev "Handbook of Filter Synthesis" (1967)
- Cohn "Direct-Coupled-Resonator Filters" (1957)
"""

from __future__ import annotations
import math
from typing import Any

from .g_values import get_g_values

# Type alias for filter result dict
FilterResult = dict[str, Any]


def calculate_coupling_coefficients(g_values: list[float], fbw: float) -> list[float]:
    """Calculate inter-resonator coupling coefficients.

    Formula: k[i,i+1] = FBW / sqrt(g[i] * g[i+1])

    Args:
        g_values: Prototype g-values [g1, g2, ..., gn]
        fbw: Fractional bandwidth (BW/f0)

    Returns:
        List of coupling coefficients [k12, k23, ..., k_{n-1,n}]
    """
    return [fbw / math.sqrt(g_values[i] * g_values[i + 1])
            for i in range(len(g_values) - 1)]


def calculate_external_q(g_values: list[float], fbw: float) -> tuple[float, float]:
    """Calculate external Q factors for input/output coupling.

    Args:
        g_values: Prototype g-values [g1, g2, ..., gn]
        fbw: Fractional bandwidth

    Returns:
        Tuple (Qe_in, Qe_out)
    """
    return g_values[0] / fbw, g_values[-1] / fbw


def calculate_resonator_components(f0: float, z0: float) -> tuple[float, float]:
    """Calculate parallel LC tank components for center frequency.

    Args:
        f0: Center frequency in Hz
        z0: System impedance in Ohms

    Returns:
        Tuple (L in Henries, C in Farads)
    """
    omega0 = 2 * math.pi * f0
    return z0 / omega0, 1 / (omega0 * z0)


def calculate_coupling_capacitors(k_values: list[float], c_resonant: float) -> list[float]:
    """Calculate coupling capacitors for both Top-C and Shunt-C.

    Formula: Cs[i] = k[i] * C_resonant

    Args:
        k_values: Coupling coefficients [k12, k23, ...]
        c_resonant: Resonator capacitance in Farads

    Returns:
        List of coupling capacitors [Cs12, Cs23, ...] in Farads
    """
    return [k * c_resonant for k in k_values]


def calculate_tank_capacitors(n_resonators: int, c_resonant: float,
                               c_coupling: list[float]) -> list[float]:
    """Calculate compensated tank capacitors.

    Tank capacitors are reduced to account for coupling capacitor effects.
    Formula: Cp[i] = C_resonant - Cs[i-1] - Cs[i]

    Args:
        n_resonators: Number of resonators
        c_resonant: Base resonant capacitance in Farads
        c_coupling: Coupling capacitors [Cs12, Cs23, ...]

    Returns:
        List of tank capacitors [Cp1, Cp2, ..., Cpn] in Farads
    """
    tank_caps: list[float] = []
    for i in range(n_resonators):
        compensation = 0.0
        if i > 0:
            compensation += c_coupling[i - 1]
        if i < n_resonators - 1:
            compensation += c_coupling[i]
        tank_caps.append(c_resonant - compensation)
    return tank_caps


def calculate_min_q(f0: float, bw: float, safety_factor: float = 2.0) -> float:
    """Calculate minimum component Q requirement.

    Args:
        f0: Center frequency in Hz
        bw: Bandwidth in Hz
        safety_factor: Design margin multiplier (default 2.0)

    Returns:
        Minimum required component Q
    """
    return (f0 / bw) * safety_factor


def _validate_inputs(f0: float, bw: float, z0: float, n_resonators: int,
                     filter_type: str, coupling: str) -> None:
    """Validate input parameters for bandpass filter calculation."""
    if f0 <= 0:
        raise ValueError("Center frequency must be positive")
    if bw <= 0:
        raise ValueError("Bandwidth must be positive")
    if bw >= f0:
        raise ValueError("Bandwidth must be less than center frequency")
    if z0 <= 0:
        raise ValueError("Impedance must be positive")
    if not 2 <= n_resonators <= 9:
        raise ValueError("Number of resonators must be between 2 and 9")
    if filter_type not in ('butterworth', 'chebyshev', 'bessel'):
        raise ValueError("Filter type must be 'butterworth', 'chebyshev', or 'bessel'")
    if coupling not in ('top', 'shunt'):
        raise ValueError("Coupling must be 'top' or 'shunt'")


def _get_fbw_warnings(fbw: float, coupling: str) -> list[str]:
    """Generate FBW-related warnings."""
    warnings: list[str] = []
    if coupling == 'shunt' and fbw > 0.10:
        warnings.append(f"FBW {fbw*100:.1f}% exceeds 10% limit for Shunt-C; consider Top-C topology")
    if fbw > 0.40:
        warnings.append(f"FBW {fbw*100:.1f}% exceeds 40%; consider transmission-line design")
    return warnings


def calculate_bandpass_filter(f0: float, bw: float, z0: float, n_resonators: int,
                               filter_type: str, coupling: str,
                               ripple_db: float = 0.5,
                               q_safety: float = 2.0) -> FilterResult:
    """Calculate complete bandpass filter component values.

    Args:
        f0: Center frequency in Hz
        bw: 3dB bandwidth in Hz
        z0: System impedance in Ohms
        n_resonators: Number of resonators (2-9)
        filter_type: 'butterworth', 'chebyshev', or 'bessel'
        coupling: 'top' (series) or 'shunt' (parallel)
        ripple_db: Chebyshev ripple (0.1, 0.5, or 1.0 dB)
        q_safety: Q safety factor multiplier

    Returns:
        Dict containing all filter parameters and component values

    Raises:
        ValueError: If invalid parameters provided
    """
    _validate_inputs(f0, bw, z0, n_resonators, filter_type, coupling)

    fbw = bw / f0
    warnings = _get_fbw_warnings(fbw, coupling)

    # Get prototype g-values
    g_values = get_g_values(filter_type, n_resonators, ripple_db)

    # Calculate coupling and external Q
    k_values = calculate_coupling_coefficients(g_values, fbw)
    qe_in, qe_out = calculate_external_q(g_values, fbw)

    # Calculate resonator components
    L_resonant, C_resonant = calculate_resonator_components(f0, z0)

    # Calculate coupling and tank capacitors
    c_coupling = calculate_coupling_capacitors(k_values, C_resonant)
    c_tank = calculate_tank_capacitors(n_resonators, C_resonant, c_coupling)

    # Check for negative tank capacitors
    negative_caps = [(i + 1, ct) for i, ct in enumerate(c_tank) if ct <= 0]
    if negative_caps:
        cap_list = ", ".join([f"Cp{i}" for i, _ in negative_caps])
        raise ValueError(
            f"Bandwidth too wide: tank capacitors {cap_list} would be negative. "
            f"Reduce bandwidth or use fewer resonators."
        )

    return {
        'f0': f0,
        'f_low': f0 - bw / 2,
        'f_high': f0 + bw / 2,
        'bw': bw,
        'fbw': fbw,
        'z0': z0,
        'n_resonators': n_resonators,
        'filter_type': filter_type,
        'coupling': coupling,
        'ripple_db': ripple_db if filter_type == 'chebyshev' else None,
        'q_safety': q_safety,
        'g_values': g_values,
        'k_values': k_values,
        'qe_in': qe_in,
        'qe_out': qe_out,
        'L_resonant': L_resonant,
        'C_resonant': C_resonant,
        'c_coupling': c_coupling,
        'c_tank': c_tank,
        'q_min': calculate_min_q(f0, bw, q_safety),
        'warnings': warnings,
    }
