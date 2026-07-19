"""Pure parsing and live feedback for the wizard band-pass form."""

from __future__ import annotations

import math
from dataclasses import dataclass

from filter_lib.bandpass.calculations import (
    BANDPASS_EDGE_CALIBRATION_FBW_MAX,
    BANDPASS_LUMPED_MODEL_CAUTION_FBW,
)
from filter_lib.shared.parsing import parse_frequency, parse_impedance, parse_inductance


class BandpassFormError(ValueError):
    """A user-facing validation failure tied to one form input."""

    def __init__(self, message: str, field_id: str, severity: str = "error") -> None:
        super().__init__(message)
        self.field_id = field_id
        self.severity = severity


@dataclass(frozen=True)
class BandpassFormValues:
    """Raw band-pass form values, including placeholder fallbacks."""

    frequency: str
    bandwidth: str
    impedance: str
    resonators: str
    ripple: str
    resonator_impedance: str
    resonator_inductance: str
    filter_type: str
    coupling: str


@dataclass(frozen=True)
class ParsedBandpassDesign:
    """Validated values ready to persist into ``FilterState``."""

    frequency_hz: float
    bandwidth_hz: float
    impedance: float
    resonators: int
    ripple_db: float
    resonator_impedance: float | None
    resonator_inductance: float | None
    filter_type: str
    coupling: str


def parse_bandpass_form(values: BandpassFormValues) -> ParsedBandpassDesign:
    """Validate the band-pass form without depending on Textual widgets."""
    try:
        frequency_hz = parse_frequency(values.frequency)
    except ValueError as error:
        raise BandpassFormError(f"Invalid center frequency: {error}", "frequency") from error

    try:
        bandwidth_hz = parse_frequency(values.bandwidth)
    except ValueError as error:
        raise BandpassFormError(f"Invalid bandwidth: {error}", "bandwidth") from error
    if bandwidth_hz >= frequency_hz:
        raise BandpassFormError("Bandwidth must be less than center frequency", "bandwidth")

    try:
        impedance = parse_impedance(values.impedance)
    except ValueError as error:
        raise BandpassFormError(f"Invalid impedance: {error}", "impedance") from error

    if values.resonator_impedance and values.resonator_inductance:
        raise BandpassFormError(
            "Choose only one advanced tank setting: impedance or fixed inductance",
            "resonator-inductance",
        )

    resonator_impedance = None
    if values.resonator_impedance:
        try:
            resonator_impedance = parse_impedance(values.resonator_impedance)
        except ValueError as error:
            raise BandpassFormError(
                f"Invalid tank impedance: {error}", "resonator-impedance"
            ) from error

    resonator_inductance = None
    if values.resonator_inductance:
        try:
            resonator_inductance = parse_inductance(values.resonator_inductance)
        except ValueError as error:
            raise BandpassFormError(
                f"Invalid tank inductance: {error}", "resonator-inductance"
            ) from error

    try:
        resonators = int(values.resonators)
        if not 2 <= resonators <= 9:
            raise ValueError("must be 2-9")
    except ValueError as error:
        raise BandpassFormError(f"Invalid resonators: {error}", "resonators") from error

    if values.filter_type == "chebyshev" and resonators % 2 == 0:
        raise BandpassFormError(
            "With equal source/load terminations, Chebyshev bandpass requires an odd "
            "number of resonators",
            "resonators",
            "warning",
        )

    ripple_db = 0.5
    if values.filter_type == "chebyshev":
        try:
            ripple_db = float(values.ripple)
            if not math.isfinite(ripple_db):
                raise ValueError("must be finite")
            if ripple_db <= 0:
                raise ValueError("must be positive")
            if ripple_db > 3.0:
                raise ValueError("must be <= 3.0 dB")
        except ValueError as error:
            raise BandpassFormError(f"Invalid ripple: {error}", "ripple") from error

    return ParsedBandpassDesign(
        frequency_hz=frequency_hz,
        bandwidth_hz=bandwidth_hz,
        impedance=impedance,
        resonators=resonators,
        ripple_db=ripple_db,
        resonator_impedance=resonator_impedance,
        resonator_inductance=resonator_inductance,
        filter_type=values.filter_type,
        coupling=values.coupling,
    )


def fractional_bandwidth_feedback(
    frequency_text: str, bandwidth_text: str
) -> tuple[str, str] | None:
    """Return live feedback text and style, or ``None`` for partial input."""
    try:
        fractional_bw = parse_frequency(bandwidth_text) / parse_frequency(frequency_text)
    except (ValueError, ZeroDivisionError):
        return None

    percent = fractional_bw * 100
    if fractional_bw > BANDPASS_LUMPED_MODEL_CAUTION_FBW:
        return (
            f"Fractional BW: {percent:.2f}% · Lumped-model caution: consider a "
            "transmission-line design; final response validation runs after calculation.",
            "fbw-danger",
        )
    if fractional_bw > BANDPASS_EDGE_CALIBRATION_FBW_MAX:
        return (
            f"Fractional BW: {percent:.2f}% · Outside studied edge-calibration "
            "range; final response validation runs after calculation.",
            "fbw-warning",
        )
    return (
        f"Fractional BW: {percent:.2f}% · Within studied edge-calibration "
        "range; final response validation runs after calculation.",
        "fbw-display",
    )
