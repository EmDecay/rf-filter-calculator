"""Wire gauge, length, DC resistance, and max-turns fit check for toroids.

Wire length per turn uses the Pythagorean form, which combines the mean
circumferential advance with the per-turn cross-section perimeter; a
perimeter-only estimate underestimates length because each turn also travels
around the core. Bare copper diameter is used for DC resistance; insulated
(enamel) diameter is used for mechanical fit.
"""

import math
from dataclasses import dataclass

from .numeric import is_finite_real, require_nonnegative_finite, require_positive_finite
from .toroid_core_data import ToroidCore, _require_toroid_core

# IACS annealed copper at 20 C (1/58 ohm·mm²/m), the basis of standard AWG resistance tables.
_COPPER_RESISTIVITY_OHM_M = 1.724e-8
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
    """Bare copper diameter in mm from AWG (standard 0.127 * 92^((36-AWG)/39) formula).

    Raises:
        ValueError: If awg is outside [0, 50].
    """
    if isinstance(awg, bool) or not isinstance(awg, int) or not 0 <= awg <= 50:
        raise ValueError(f"AWG out of range [0, 50]: {awg}")
    return 0.127 * (92 ** ((36 - awg) / 39))


def default_awg_for_core(core: ToroidCore) -> int:
    """Canonical default AWG for the core's family."""
    core = _require_toroid_core(core)
    family = core.family
    if family not in _DEFAULT_AWG_BY_FAMILY:
        raise ValueError(f"No default AWG known for family {family!r}")
    return _DEFAULT_AWG_BY_FAMILY[family]


def max_turns(core: ToroidCore, awg: int) -> int:
    """Maximum turns from a manufacturer table, else a geometry estimate.

    A published full-winding limit is authoritative.  The fallback is only a
    single-layer estimate and callers must retain that uncertainty.
    """
    core = _require_toroid_core(core)
    awg_to_diameter_mm(awg)
    published = core.winding_spec_for_awg(awg)
    if published is not None:
        return published.full_winding_turns
    d_insulated = awg_to_diameter_mm(awg) * _ENAMEL_FACTOR
    inner_circumference = math.pi * core.id_mm
    theoretical = inner_circumference / d_insulated
    return max(1, int(theoretical * _WINDING_FILL_FACTOR))


def wire_length_mm(
    core: ToroidCore, n: int, awg: int, wire_diameter_mm: float | None = None
) -> float:
    """Pythagorean (VK3CPU) wire-length including wire-radius contribution.

    Each turn wraps the rectangular core cross-section with the wire
    centerline offset outward by the wire radius r: the two straight runs per
    side are unchanged, and the four quarter-circle corner arcs of radius r
    sum to one full circle, adding 2πr per turn. The Pythagorean combination
    with the mean circumferential advance accounts for the helical path.

    ``wire_diameter_mm`` is the reported (for example datasheet) diameter; the
    AWG formula diameter is used when it is not supplied.
    """
    core = _require_toroid_core(core)
    _require_turn_count(n, "n")
    formula_diameter_mm = awg_to_diameter_mm(awg)
    if wire_diameter_mm is None:
        wire_diameter_mm = formula_diameter_mm
    r_wire = require_positive_finite(wire_diameter_mm, "wire_diameter_mm") / 2.0
    axial = math.pi * (core.od_mm + core.id_mm) / 2.0
    cross = n * (2.0 * math.pi * r_wire + 2.0 * core.height_mm + core.od_mm - core.id_mm)
    try:
        length = math.sqrt(axial**2 + cross**2)
    except OverflowError:
        length = math.inf
    if not math.isfinite(length):
        raise ValueError("wire length is outside the finite numeric range")
    return length


def _require_turn_count(turns: object, label: str) -> int:
    """Require a positive integer turn count that converts to a finite binary64 value."""
    if isinstance(turns, bool) or not isinstance(turns, int) or turns <= 0:
        raise ValueError(f"{label} must be a positive integer")
    if not is_finite_real(turns):
        raise ValueError(f"{label} is outside the finite numeric range")
    return turns


def dc_resistance_ohms(length_mm: float, awg: int) -> float:
    """DC resistance of bare copper wire at 20 C."""
    require_nonnegative_finite(length_mm, "length_mm")
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
    dc_resistance_ohm: float
    capacity_status: str = "estimated"
    capacity_source_id: str | None = None
    winding_style: str = "estimated_single_layer"
    dcr_method: str = "geometry_estimate"
    single_layer_capacity: int | None = None
    full_winding_capacity: int | None = None


def _published_winding_choice(core: ToroidCore, n_turns: int, awg: int | None):
    """Return a published table row and winding status, when available."""
    if awg is not None:
        row = core.winding_spec_for_awg(awg)
        if row is None:
            return None
        if n_turns <= row.single_layer_turns:
            return row, "manufacturer_single_layer", "single_layer"
        if n_turns <= row.full_winding_turns:
            return row, "manufacturer_full_winding", "full_winding"
        return row, "manufacturer_exceeded", "beyond_published_capacity"

    if not core.winding_table:
        return None
    single_layer = sorted(
        (row for row in core.winding_table if n_turns <= row.single_layer_turns),
        key=lambda row: row.awg,
    )
    if single_layer:
        return single_layer[0], "manufacturer_single_layer", "single_layer"
    full_winding = sorted(
        (row for row in core.winding_table if n_turns <= row.full_winding_turns),
        key=lambda row: row.awg,
    )
    if full_winding:
        return full_winding[0], "manufacturer_full_winding", "full_winding"
    thinnest = max(core.winding_table, key=lambda row: row.awg)
    return thinnest, "manufacturer_exceeded", "beyond_published_capacity"


def fit_wire(core: ToroidCore, n_turns: int, awg: int | None = None) -> MechanicalFit:
    """Choose wire, report sourced/estimated capacity, and estimate length/DCR.

    With a manufacturer table, the thickest single-layer wire that fits is
    preferred, then the thickest full-winding option.  Without a table, the
    legacy geometric capacity is retained but explicitly labeled estimated.
    """
    core = _require_toroid_core(core)
    _require_turn_count(n_turns, "n_turns")
    if awg is not None:
        awg_to_diameter_mm(awg)
    published_choice = _published_winding_choice(core, n_turns, awg)
    if published_choice is not None:
        row, capacity_status, winding_style = published_choice
        gauge = row.awg
        n_cap = row.full_winding_turns
        fits = capacity_status != "manufacturer_exceeded"
        reference_turns = (
            row.single_layer_turns
            if capacity_status == "manufacturer_single_layer"
            else row.full_winding_turns
        )
        reference_dcr = (
            row.single_layer_dcr_ohm
            if capacity_status == "manufacturer_single_layer"
            else row.full_winding_dcr_ohm
        )
        dcr = reference_dcr * n_turns / reference_turns
        capacity_source_id = core.winding_source_id
        dcr_method = "manufacturer_table_scaled_by_turn_count"
        single_layer_capacity = row.single_layer_turns
        full_winding_capacity = row.full_winding_turns
        diameter_mm = row.wire_diameter_mm
    else:
        gauge = awg if awg is not None else default_awg_for_core(core)
        n_cap = max_turns(core, gauge)
        fits = n_turns <= n_cap
        capacity_status = "estimated"
        winding_style = "estimated_single_layer"
        capacity_source_id = None
        dcr_method = "geometry_estimate"
        single_layer_capacity = n_cap
        full_winding_capacity = None
        diameter_mm = awg_to_diameter_mm(gauge)

    length_mm = wire_length_mm(core, n_turns, gauge, wire_diameter_mm=diameter_mm)
    if published_choice is None:
        dcr = dc_resistance_ohms(length_mm, gauge)
    return MechanicalFit(
        awg=gauge,
        wire_diameter_mm=diameter_mm,
        n_max=n_cap,
        fits=fits,
        wire_length_mm=length_mm,
        dc_resistance_ohm=dcr,
        capacity_status=capacity_status,
        capacity_source_id=capacity_source_id,
        winding_style=winding_style,
        dcr_method=dcr_method,
        single_layer_capacity=single_layer_capacity,
        full_winding_capacity=full_winding_capacity,
    )
