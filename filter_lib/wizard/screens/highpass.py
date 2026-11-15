"""Highpass filter input screen."""

from .ladder import LadderScreen


class HighpassScreen(LadderScreen):
    """Screen for configuring highpass filter parameters."""

    CATEGORY = "highpass"
    HEADER = "High-Pass Filter Design"
    BESSEL_LABEL = "Bessel - Gentle cutoff; the high-pass form does not keep flat group delay"
    PI_LABEL = "Pi (shunt first) - L, then alternating C/L"
    T_LABEL = "T (series first) - C, then alternating L/C"
    # Pi is listed first, as on the web, but T is the default here (low-pass
    # defaults to Pi): for the same order, the high-pass T needs fewer
    # inductors than the shunt-L Pi, which is the usual builder's preference.
    DEFAULT_TOPOLOGY = "t"
