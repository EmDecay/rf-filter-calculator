"""Validation functions for filter wizard inputs."""


def validate_order(value: str) -> int:
    """Validate filter order (2-9).

    Args:
        value: String representation of order number

    Returns:
        Validated order as integer

    Raises:
        ValueError: If order is not between 2 and 9
    """
    n = int(value)
    if not 2 <= n <= 9:
        raise ValueError("Order must be 2-9")
    return n


def validate_ripple(value: str) -> float:
    """Validate Chebyshev ripple value.

    Args:
        value: String representation of ripple in dB

    Returns:
        Validated ripple as float

    Raises:
        ValueError: If ripple is not a valid option
    """
    r = float(value)
    if r <= 0:
        raise ValueError("Ripple must be positive")
    if r > 3.0:
        raise ValueError("Ripple typically should be <= 3.0 dB")
    return r
