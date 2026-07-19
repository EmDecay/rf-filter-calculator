"""Coupling and compensated-capacitor math for Top-C bandpass filters."""

import math

from ..shared.numeric import is_finite_real, positive_float_from_log, positive_geometric_mean


def _positive_finite(value: object, name: str) -> float:
    if not is_finite_real(value) or value <= 0:
        raise ValueError(f"{name} must be positive and finite")
    return float(value)


def _positive_values(values: list[float], name: str, *, minimum_length: int = 1) -> list[float]:
    if not isinstance(values, list) or len(values) < minimum_length:
        raise ValueError(f"{name} must be a list with at least {minimum_length} value(s)")
    return [_positive_finite(value, f"{name}[{index}]") for index, value in enumerate(values)]


def _require_positive_finite_results(values: list[float], label: str) -> list[float]:
    if not all(math.isfinite(value) and value > 0 for value in values):
        raise ValueError(f"derived {label} must be positive and finite")
    return values


def calculate_coupling_coefficients(g_values: list[float], fbw: float) -> list[float]:
    """Return Cohn inter-resonator couplings ``FBW/sqrt(g[i]*g[i+1])``."""
    g = _positive_values(g_values, "g_values", minimum_length=2)
    bandwidth = _positive_finite(fbw, "fbw")
    values = [
        bandwidth / positive_geometric_mean(g[index], g[index + 1]) for index in range(len(g) - 1)
    ]
    return _require_positive_finite_results(values, "coupling coefficients")


def calculate_external_q(g_values: list[float], fbw: float) -> tuple[float, float]:
    """Return equal-termination input and output external Q values."""
    g = _positive_values(g_values, "g_values")
    bandwidth = _positive_finite(fbw, "fbw")
    values = _require_positive_finite_results(
        [g[0] / bandwidth, g[-1] / bandwidth], "external Q values"
    )
    return values[0], values[1]


def calculate_coupling_capacitors(k_values: list[float], c_resonant: float) -> list[float]:
    """Return first-order Top-C series coupling capacitors ``Cs = k*C``."""
    coefficients = _positive_values(k_values, "k_values", minimum_length=0)
    resonant_capacitance = _positive_finite(c_resonant, "c_resonant")
    return _require_positive_finite_results(
        [coefficient * resonant_capacitance for coefficient in coefficients],
        "coupling capacitances",
    )


def calculate_tank_capacitors(
    n_resonators: int, c_resonant: float, c_coupling: list[float]
) -> list[float]:
    """Compensate each tank for the coupling capacitors attached to it."""
    if not isinstance(n_resonators, int) or isinstance(n_resonators, bool) or n_resonators < 1:
        raise ValueError("n_resonators must be an integer >= 1")
    resonant_capacitance = _positive_finite(c_resonant, "c_resonant")
    coupling = _positive_values(c_coupling, "c_coupling", minimum_length=0)
    if len(coupling) != n_resonators - 1:
        raise ValueError("c_coupling must contain exactly n_resonators - 1 values")

    tank_caps: list[float] = []
    for index in range(n_resonators):
        compensation = 0.0
        if index > 0:
            compensation += coupling[index - 1]
        if index < n_resonators - 1:
            compensation += coupling[index]
        tank_caps.append(resonant_capacitance - compensation)
    if not all(math.isfinite(value) and value > 0 for value in tank_caps):
        raise ValueError(
            "Bandwidth too wide to realize: derived tank capacitances must be positive and finite"
        )
    return tank_caps


def calculate_end_coupling(
    qe: float, omega0: float, l_resonant: float, z0: float
) -> tuple[float, float]:
    """Return a series port capacitor and its end-tank compensation.

    The series RC branch must transform the port resistance to
    ``Rp = Qe*omega0*L``. Its quality factor is
    ``sqrt(Rp/z0 - 1)``, which determines both the series capacitor and the
    equivalent shunt capacitance that must be removed from the end tank.

    Raises:
        ValueError: If the requested external Q cannot step the port resistance up.
    """
    angular_frequency = _positive_finite(omega0, "omega0")
    return _calculate_end_coupling_from_log_omega(qe, math.log(angular_frequency), l_resonant, z0)


def _calculate_end_coupling_at_frequency(
    qe: float, frequency: float, l_resonant: float, z0: float
) -> tuple[float, float]:
    """Frequency-domain variant that need not materialize ``2*pi*f``."""
    center_frequency = _positive_finite(frequency, "frequency")
    log_omega = math.log(2 * math.pi) + math.log(center_frequency)
    return _calculate_end_coupling_from_log_omega(qe, log_omega, l_resonant, z0)


def _calculate_end_coupling_from_log_omega(
    qe: float, log_omega: float, l_resonant: float, z0: float
) -> tuple[float, float]:
    external_q = _positive_finite(qe, "qe")
    resonant_inductance = _positive_finite(l_resonant, "l_resonant")
    impedance = _positive_finite(z0, "z0")
    log_resistance_ratio = (
        math.log(external_q) + log_omega + math.log(resonant_inductance) - math.log(impedance)
    )
    # Exact equality can leave a one-ULP positive log after cancellation.
    # Keep that roundoff on the physically infeasible Rp=Z0 boundary.
    if log_resistance_ratio <= 4 * math.ulp(1.0):
        raise ValueError(
            "Fractional bandwidth too wide to realize input/output coupling at "
            "this impedance; reduce bandwidth or order"
        )
    if log_resistance_ratio < math.log(2.0):
        log_q = 0.5 * math.log(math.expm1(log_resistance_ratio))
    else:
        log_q = 0.5 * (log_resistance_ratio + math.log1p(-math.exp(-log_resistance_ratio)))
    log_coupling = -log_omega - math.log(impedance) - log_q
    coupling_capacitance = positive_float_from_log(log_coupling, "derived end-coupling capacitance")
    inverse_q_squared_log = -2 * log_q
    if inverse_q_squared_log > 0:
        log_compensation_factor = inverse_q_squared_log + math.log1p(
            math.exp(-inverse_q_squared_log)
        )
    else:
        log_compensation_factor = math.log1p(math.exp(inverse_q_squared_log))
    compensation = positive_float_from_log(
        log_coupling - log_compensation_factor,
        "derived end-tank compensation capacitance",
    )
    values = _require_positive_finite_results(
        [coupling_capacitance, compensation], "end-coupling capacitances"
    )
    return values[0], values[1]
