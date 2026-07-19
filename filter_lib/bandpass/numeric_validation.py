"""Small numeric validators shared by bandpass calculation and response modules."""

from typing import Any

from ..shared.numeric import is_finite_real

MAX_CHEBYSHEV_RIPPLE_DB = 3.0


def _is_positive_finite(value: Any) -> bool:
    """Return whether a numeric public input is finite, positive, and not bool."""
    return is_finite_real(value) and value > 0


def _validate_order(order: int) -> None:
    """Require a positive integer order; bool is not an order."""
    if isinstance(order, bool) or not isinstance(order, int) or order <= 0:
        raise ValueError("order must be a positive integer")


def _validate_chebyshev_ripple(ripple_db: float) -> None:
    """Require ripple within the public Chebyshev bandpass support range."""
    if not _is_positive_finite(ripple_db):
        raise ValueError("ripple_db must be positive and finite for Chebyshev")
    if ripple_db > MAX_CHEBYSHEV_RIPPLE_DB:
        raise ValueError(
            f"ripple_db must be at most {MAX_CHEBYSHEV_RIPPLE_DB:.1f} dB for Chebyshev"
        )
