"""Coupled resonator bandpass filter calculations.

Contains coupling coefficient formulas and component value calculations
for Top-C (series capacitive) coupled resonator filters.

References:
- Matthaei, Young, Jones "Microwave Filters, Impedance-Matching Networks..."
- Zverev "Handbook of Filter Synthesis" (1967)
- Cohn "Direct-Coupled-Resonator Filters" (1957)
"""

import math
from typing import Any

from .g_values import get_g_values

# Type alias for filter result dict
BandpassResult = dict[str, Any]


def calculate_coupling_coefficients(g_values: list[float], fbw: float) -> list[float]:
    """Calculate inter-resonator coupling coefficients.

    Formula: k[i,i+1] = FBW / sqrt(g[i] * g[i+1])

    Args:
        g_values: Prototype g-values [g1, g2, ..., gn]
        fbw: Fractional bandwidth (BW/f0)

    Returns:
        List of coupling coefficients [k12, k23, ..., k_{n-1,n}]
    """
    return [fbw / math.sqrt(g_values[i] * g_values[i + 1]) for i in range(len(g_values) - 1)]


def calculate_external_q(g_values: list[float], fbw: float) -> tuple[float, float]:
    """Calculate external Q factors for input/output coupling.

    Assumes equal source/load terminations, so g0 = g_{n+1} = 1 and:
    Qe_in = g1/FBW, Qe_out = gn/FBW.

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
    """Calculate Top-C inter-resonator coupling capacitors.

    Formula: Cs[i] = k[i] * C_resonant

    Args:
        k_values: Coupling coefficients [k12, k23, ...]
        c_resonant: Resonator capacitance in Farads

    Returns:
        List of coupling capacitors [Cs12, Cs23, ...] in Farads
    """
    return [k * c_resonant for k in k_values]


def calculate_tank_capacitors(
    n_resonators: int, c_resonant: float, c_coupling: list[float]
) -> list[float]:
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


def calculate_end_coupling(
    qe: float, omega0: float, l_resonant: float, z0: float
) -> tuple[float, float]:
    """Series end-coupling capacitor that realizes an external Q at a resistive port.

    The end resonator must see a parallel resistance Rp = Qe·ω0·L to be loaded
    to its designed external Q. A series capacitor acts as an impedance
    transformer stepping the port resistance up: Rp = Z0·(1 + q²) with
    transformation Q given by q = 1/(ω0·Z0·Ce).

    Returns:
        Tuple (Ce, ΔC): the series end capacitor and its series-equivalent
        capacitance ΔC = Ce·q²/(1+q²) that appears across the tank and must
        be subtracted from the end tank capacitor to keep it on frequency.

    Raises:
        ValueError: when Rp <= Z0 (no real transformation Q exists).
    """
    rp = qe * omega0 * l_resonant
    if rp <= z0:
        raise ValueError(
            "Fractional bandwidth too wide to realize input/output coupling at "
            "this impedance; reduce bandwidth or order"
        )
    q = math.sqrt(rp / z0 - 1)
    ce = 1 / (omega0 * z0 * q)
    delta_c = ce * q * q / (1 + q * q)
    return ce, delta_c


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


def compute_bandpass_3db_edges(f0: float, bw: float) -> tuple[float, float]:
    """Return the exact -3 dB edges of the narrowband bandpass transfer function.

    The transfer function uses the frequency deviation delta = (f^2 - f0^2) / (BW*f);
    |H|^2 hits 0.5 when delta = ±1, which solves two quadratics in f.

    Upper: f^2 - BW*f - f0^2 = 0 → f = (BW + sqrt(BW^2 + 4*f0^2)) / 2
    Lower: f^2 + BW*f - f0^2 = 0 → f = (-BW + sqrt(BW^2 + 4*f0^2)) / 2

    These edges satisfy f_high - f_low = BW and f0 = sqrt(f_low * f_high)
    (geometric centering), which differs from the arithmetic shortcut f0 ± BW/2
    for wider fractional bandwidths.
    """
    if not math.isfinite(f0) or f0 <= 0:
        raise ValueError("f0 must be positive and finite")
    if not math.isfinite(bw) or bw <= 0:
        raise ValueError("bw must be positive and finite")
    disc = math.sqrt(bw * bw + 4.0 * f0 * f0)
    f_high = (bw + disc) / 2.0
    # Use the geometric invariant f_low * f_high = f0^2 to avoid catastrophic
    # cancellation in (-bw + disc) when bw >> 2*f0.
    f_low = (f0 * f0) / f_high
    return f_low, f_high


def _validate_inputs(
    f0: float, bw: float, z0: float, n_resonators: int, filter_type: str, coupling: str
) -> None:
    """Validate input parameters for bandpass filter calculation.

    Rejects NaN and inf explicitly — the ``<= 0`` checks would otherwise let
    NaN slip past and produce downstream garbage component values.
    """
    if not math.isfinite(f0) or f0 <= 0:
        raise ValueError("Center frequency must be positive and finite")
    if not math.isfinite(bw) or bw <= 0:
        raise ValueError("Bandwidth must be positive and finite")
    if bw >= f0:
        raise ValueError("Bandwidth must be less than center frequency")
    if not math.isfinite(z0) or z0 <= 0:
        raise ValueError("Impedance must be positive and finite")
    if not 2 <= n_resonators <= 9:
        raise ValueError("Number of resonators must be between 2 and 9")
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
    """Generate FBW-related warnings."""
    warnings: list[str] = []
    if fbw > 0.10:
        warnings.append(
            f"FBW {fbw * 100:.1f}% exceeds the simulation-validated range (<=10%) for "
            "Top-C; verify the design before building"
        )
    if fbw > 0.40:
        warnings.append(f"FBW {fbw * 100:.1f}% exceeds 40%; consider transmission-line design")
    return warnings


def calculate_bandpass_filter(
    f0: float,
    bw: float,
    z0: float,
    n_resonators: int,
    filter_type: str,
    coupling: str,
    ripple_db: float = 0.5,
    q_safety: float = 2.0,
) -> BandpassResult:
    """Calculate complete bandpass filter component values.

    Args:
        f0: Center frequency in Hz
        bw: 3dB bandwidth in Hz
        z0: System impedance in Ohms
        n_resonators: Number of resonators (2-9)
        filter_type: 'butterworth', 'chebyshev', or 'bessel'
        coupling: 'top' (series capacitive coupling; the only supported kind)
        ripple_db: Chebyshev passband ripple in dB, in (0, 3.0]
        q_safety: Q safety factor multiplier

    Returns:
        Dict containing all filter parameters and component values

    Raises:
        ValueError: If invalid parameters provided
    """
    _validate_inputs(f0, bw, z0, n_resonators, filter_type, coupling)
    if not math.isfinite(q_safety) or q_safety <= 0:
        raise ValueError("q_safety must be positive and finite")
    if filter_type == "chebyshev":
        if not math.isfinite(ripple_db) or ripple_db <= 0:
            raise ValueError("ripple_db must be positive and finite for Chebyshev")
        if ripple_db > 3.0:
            raise ValueError("ripple_db must be at most 3.0 dB for Chebyshev")

    fbw = bw / f0
    warnings = _get_fbw_warnings(fbw)

    # Get prototype g-values
    g_values = get_g_values(filter_type, n_resonators, ripple_db)

    # Cohn synthesis treats fbw as the prototype passband-edge fractional BW
    # (|delta| = 1). For Butterworth and Bessel that is also the -3 dB BW, so no
    # rescaling is needed. For Chebyshev, |delta| = 1 is the ripple edge, which
    # is narrower than the -3 dB BW — scale fbw down by delta_3dB so the
    # synthesized filter's *true* -3 dB BW equals the user-supplied ``bw``.
    fbw_synth = fbw
    if filter_type == "chebyshev":
        from .transfer import chebyshev_3db_deviation

        fbw_synth = fbw / chebyshev_3db_deviation(n_resonators, ripple_db)

    # Calculate coupling and external Q
    k_values = calculate_coupling_coefficients(g_values, fbw_synth)
    qe_in, qe_out = calculate_external_q(g_values, fbw_synth)

    # Calculate resonator components
    L_resonant, C_resonant = calculate_resonator_components(f0, z0)

    # Calculate coupling and tank capacitors
    c_coupling = calculate_coupling_capacitors(k_values, C_resonant)
    c_tank = calculate_tank_capacitors(n_resonators, C_resonant, c_coupling)

    # Realize the external Q with series end-coupling capacitors. Without
    # them the source/load load the end tanks far too heavily and the built
    # filter misses the designed bandwidth by an order of magnitude.
    omega0 = 2 * math.pi * f0
    c_end_in, delta_c_in = calculate_end_coupling(qe_in, omega0, L_resonant, z0)
    c_end_out, delta_c_out = calculate_end_coupling(qe_out, omega0, L_resonant, z0)
    # The end caps' series-equivalent capacitance appears across the end
    # tanks; absorb it so the tanks stay resonant at f0.
    c_tank[0] -= delta_c_in
    c_tank[-1] -= delta_c_out

    # Check for negative tank capacitors
    negative_caps = [(i + 1, ct) for i, ct in enumerate(c_tank) if ct <= 0]
    if negative_caps:
        cap_list = ", ".join([f"Cp{i}" for i, _ in negative_caps])
        raise ValueError(
            f"Bandwidth too wide: tank capacitors {cap_list} would be negative. "
            f"Reduce bandwidth or use fewer resonators."
        )

    f_low, f_high = compute_bandpass_3db_edges(f0, bw)

    return {
        "f0": f0,
        "f_low": f_low,
        "f_high": f_high,
        "bw": bw,
        "fbw": fbw,
        "z0": z0,
        "n_resonators": n_resonators,
        "filter_type": filter_type,
        "coupling": coupling,
        "ripple_db": ripple_db if filter_type == "chebyshev" else None,
        "q_safety": q_safety,
        "g_values": g_values,
        "k_values": k_values,
        "qe_in": qe_in,
        "qe_out": qe_out,
        "L_resonant": L_resonant,
        "C_resonant": C_resonant,
        "c_coupling": c_coupling,
        "c_tank": c_tank,
        "c_end_in": c_end_in,
        "c_end_out": c_end_out,
        "q_min": calculate_min_q(f0, bw, q_safety),
        "warnings": warnings,
    }
