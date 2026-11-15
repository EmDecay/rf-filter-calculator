"""Lowpass filter input screen."""

from .ladder import LadderScreen


class LowpassScreen(LadderScreen):
    """Screen for configuring lowpass filter parameters."""

    CATEGORY = "lowpass"
    HEADER = "Low-Pass Filter Design"
    BESSEL_LABEL = "Bessel - Maximally flat group delay, gentle cutoff"
    PI_LABEL = "Pi (shunt first) - C, then alternating L/C"
    T_LABEL = "T (series first) - L, then alternating C/L"
    DEFAULT_TOPOLOGY = "pi"
