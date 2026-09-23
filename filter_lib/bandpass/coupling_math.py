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


def require_end_coupling_resonator(
    g_values: list[float],
    fbw: float,
    z0: float,
    f0: float,
    resonator_impedance: float | None,
    resonator_inductance: float | None,
) -> None:
    """Name a supplied tank impedance or inductance too low for series end coupling.

    A series end capacitor can only step the termination up, so it needs
    ``Rp = Qe * X > Z0`` with ``Qe = g_end / FBW`` and tank reactance ``X``. With the
    default tank (``X = Z0``) that is a bandwidth-and-order limit, reported during
    synthesis; a supplied tank adds the lower bound ``X > Z0 * FBW / g_end`` checked here.
    ``fbw`` is the initial synthesis bandwidth where calibration starts. A tank below the
    bound already fails that first synthesis, so this check changes only the message; the
    calibrated bandwidth moves the exact limit slightly, hence "about".
    """
    if resonator_impedance is None and resonator_inductance is None:
        return
    g = _positive_values(g_values, "g_values")
    log_omega0 = math.log(2 * math.pi) + math.log(_positive_finite(f0, "f0"))
    log_minimum_reactance = (
        math.log(_positive_finite(z0, "z0"))
        + math.log(_positive_finite(fbw, "fbw"))
        - math.log(min(g[0], g[-1]))
    )
    if resonator_inductance is not None:
        log_reactance = log_omega0 + math.log(resonator_inductance)
        supplied = f"Resonator inductance {resonator_inductance:.3g} H"
        minimum = f"{_format_from_log(log_minimum_reactance - log_omega0)} H"
    else:
        log_reactance = math.log(resonator_impedance)
        supplied = f"Resonator impedance {resonator_impedance:.3g} ohm"
        minimum = f"{_format_from_log(log_minimum_reactance)} ohm"
    if log_reactance > log_minimum_reactance:
        return
    raise ValueError(
        f"{supplied} is too low to realize the input/output coupling to the {z0:.3g} ohm "
        f"terminations at this bandwidth and order; it must exceed about {minimum} "
        "(necessary, not sufficient: a wide enough bandwidth fails at any tank value)"
    )


def _format_from_log(log_value: float) -> str:
    """Format ``exp(log_value)`` to three significant digits, even beyond binary64."""
    try:
        value = math.exp(log_value)
    except OverflowError:
        value = math.inf
    if 0 < value < math.inf:
        return f"{value:.3g}"
    exponent = math.floor(log_value / math.log(10.0))
    mantissa = math.exp(log_value - exponent * math.log(10.0))
    if mantissa >= 9.995:
        mantissa, exponent = mantissa / 10.0, exponent + 1
    return f"{mantissa:.3g}e{exponent:+03d}"


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
            "this impedance; reduce bandwidth or order, or raise the resonator impedance"
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
