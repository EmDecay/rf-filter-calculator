"""Wire gauge, length, DC resistance, and max-turns fit check for toroids.

Uses VK3CPU Pythagorean wire-length formula, NOT the 'simple' form in the
research doc (see plan Accuracy Contract sec 7). Bare copper diameter is used
for DC resistance; insulated (enamel) diameter is used for mechanical fit.
"""

import math
from dataclasses import dataclass

from .toroid_core_data import ToroidCore

_COPPER_RESISTIVITY_OHM_M = 1.68e-8  # 20 C
_ENAMEL_FACTOR = 1.07  # bare copper -> insulated diameter
_WINDING_FILL_FACTOR = 0.9  # realistic single-layer coverage

_DEFAULT_AWG_BY_FAMILY: dict[str, int] = {
    "T25": 26,
    "T30": 24,
    "T37": 24,
    "T44": 22,
    "T50": 22,
    "T68": 20,
    "T80": 20,
    "T94": 18,
    "T106": 18,
    "T130": 16,
    "T157": 16,
    "T184": 16,
    "T200": 14,
    "T225": 14,
}


def awg_to_diameter_mm(awg: int) -> float:
    """Bare copper diameter from AWG (standard 0.127 * 92^((36-AWG)/39) formula)."""
    if not 0 <= awg <= 50:
        raise ValueError(f"AWG out of range [0, 50]: {awg}")
    return 0.127 * (92 ** ((36 - awg) / 39))


def default_awg_for_core(core: ToroidCore) -> int:
    """Canonical default AWG for the core's family."""
    family = core.family
    if family not in _DEFAULT_AWG_BY_FAMILY:
        raise ValueError(f"No default AWG known for family {family!r}")
    return _DEFAULT_AWG_BY_FAMILY[family]


def max_turns(core: ToroidCore, awg: int) -> int:
    """Max single-layer turns that fit through the inner diameter.

    Applies enamel factor (1.07 x diameter) and winding fill factor (0.9).
    """
    d_insulated = awg_to_diameter_mm(awg) * _ENAMEL_FACTOR
    inner_circumference = math.pi * core.id_mm
    theoretical = inner_circumference / d_insulated
    return max(1, int(theoretical * _WINDING_FILL_FACTOR))


def wire_length_mm(core: ToroidCore, n: int, awg: int) -> float:
    """Pythagorean (VK3CPU) wire-length including wire-radius contribution."""
    if n <= 0:
        raise ValueError("n must be positive")
    r_wire = awg_to_diameter_mm(awg) / 2.0
    axial = math.pi * (core.od_mm + core.id_mm) / 2.0
    cross = n * (4.0 * r_wire + 2.0 * core.height_mm + core.od_mm - core.id_mm)
    return math.sqrt(axial**2 + cross**2)


def dc_resistance_ohms(length_mm: float, awg: int) -> float:
    """DC resistance of bare copper wire at 20 C."""
    if length_mm < 0:
        raise ValueError("length_mm must be non-negative")
    d_m = awg_to_diameter_mm(awg) * 1e-3
    area_m2 = math.pi * (d_m / 2.0) ** 2
    length_m = length_mm * 1e-3
    return _COPPER_RESISTIVITY_OHM_M * length_m / area_m2


@dataclass(frozen=True)
class MechanicalFit:
    """Wire-fit result for a core + turn-count + AWG combination."""

    awg: int
    wire_diameter_mm: float
    n_max: int
    fits: bool
    wire_length_mm: float
    wire_length_m: float
    dc_resistance_ohm: float


def fit_wire(core: ToroidCore, n_turns: int, awg: int | None = None) -> MechanicalFit:
    """One-shot: pick AWG (default for family), check fit, compute length + DCR."""
    gauge = awg if awg is not None else default_awg_for_core(core)
    n_cap = max_turns(core, gauge)
    fits = n_turns <= n_cap
    length_mm = wire_length_mm(core, n_turns, gauge)
    return MechanicalFit(
        awg=gauge,
        wire_diameter_mm=awg_to_diameter_mm(gauge),
        n_max=n_cap,
        fits=fits,
        wire_length_mm=length_mm,
        wire_length_m=length_mm * 1e-3,
        dc_resistance_ohm=dc_resistance_ohms(length_mm, gauge),
    )
