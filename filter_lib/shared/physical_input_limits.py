"""Accepted ranges for component-loss and evaluation-port inputs.

The ranges reject only values no lumped filter can contain, and leave headroom for
unusual but deliberate choices:

- Component Q: below about 1 a part is more resistor than reactor, and the lossiest real
  filter parts (ferrite beads) sit near 0.5; the best lumped inductors and capacitors reach
  about 1e4. Omitting Q models a lossless part.
- Evaluation ports: a port resistance is meaningful relative to the design impedance.
  1e-6 to 1e6 times it covers an ideal-voltage-source drive and a 10 Mohm probe load on a
  50 ohm filter. Beyond that ratio a high-impedance port needs the exact high-precision
  solver: a 9-resonator bandpass analysis takes several times longer at 1e7 and over a
  minute from 1e8.
"""

import sys
from decimal import Decimal

from .numeric import is_finite_real

MIN_COMPONENT_Q = 0.01
MAX_COMPONENT_Q = 1e9
PORT_RESISTANCE_RATIO_LIMIT = 1e6

# A boundary resistance typed as a decimal ("3.3M" against a 3.3 ohm design) must pass
# even though binary64 rounds the ratio a unit away from exactly 1e6.
_RATIO_SLACK = 1e-12


def require_component_q(value: object, name: str) -> int | float:
    """Return a component or resonator Q inside the accepted range, else raise ValueError."""
    if not is_finite_real(value) or not MIN_COMPONENT_Q <= value <= MAX_COMPONENT_Q:
        raise ValueError(f"{name} must be finite and in [{MIN_COMPONENT_Q:g}, {MAX_COMPONENT_Q:g}]")
    return value


def require_port_resistance(value: float, design_impedance: float, label: str) -> float:
    """Return a positive port resistance within the accepted ratio of the design impedance.

    Both arguments are positive finite values validated by their owners. A ratio that
    overflows or underflows binary64 is outside the range by construction.
    """
    ratio = value / design_impedance
    limit = PORT_RESISTANCE_RATIO_LIMIT
    if (1 - _RATIO_SLACK) / limit <= ratio <= limit * (1 + _RATIO_SLACK):
        return value
    impedance = Decimal(repr(design_impedance))
    exact_limit = Decimal(repr(limit))
    raise ValueError(
        f"{label} {value:.3g} ohm is outside the supported range "
        f"{_format_bound(impedance / exact_limit)} to {_format_bound(impedance * exact_limit)} "
        f"ohm ({1 / limit:g} to {limit:g} times the {design_impedance:.4g} ohm design impedance)"
    )


def _format_bound(bound: Decimal) -> str:
    """Format a range bound like a float, even where binary64 would print "inf" or "0"."""
    as_float = float(bound)
    if sys.float_info.min <= as_float <= sys.float_info.max:
        return f"{as_float:.3g}"
    return format(bound.normalize(), ".3g")
