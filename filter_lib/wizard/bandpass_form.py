"""Pure parsing and live feedback for the wizard band-pass form."""

from __future__ import annotations

from dataclasses import dataclass

from filter_lib.bandpass.calculations import (
    BANDPASS_EDGE_CALIBRATION_FBW_MAX,
    BANDPASS_LUMPED_MODEL_CAUTION_FBW,
)
from filter_lib.bandpass.input_validation import (
    BANDWIDTH_NOT_BELOW_CENTER,
    RESONATOR_COUNT_MESSAGE,
    fbw_impractical_warning,
    fbw_untested_warning,
)
from filter_lib.bandpass.resonator_math import TANK_SETTING_CONFLICT_MESSAGE, combine_resonator_q
from filter_lib.design import band_from_edges
from filter_lib.shared.cli_aliases import chebyshev_odd_count_message
from filter_lib.shared.parsing import parse_frequency, parse_impedance, parse_inductance
from filter_lib.shared.physical_input_limits import require_component_q

from .design_field_validation import parse_ripple_db

__all__ = [
    "BANDWIDTH_NOT_BELOW_CENTER",
    "BandpassFormError",
    "BandpassFormValues",
    "ParsedBandpassDesign",
    "edge_bandwidth_feedback",
    "fractional_bandwidth_feedback",
    "parse_bandpass_form",
]

# "Specify the band by": center and width, or the -3 dB band edges (CLI --fl/--fh).
BAND_SPECS = ("center", "edges")
# Resonator Q fields (CLI --qu/--ql/--qc): (field id, label used in messages).
RESONATOR_Q_FIELDS = (("qu", "Qu"), ("ql", "QL"), ("qc", "QC"))


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
    band_spec: str = "center"
    f_low: str = ""
    f_high: str = ""
    qu: str = ""
    ql: str = ""
    qc: str = ""


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
    requested_f_low_hz: float | None = None
    requested_f_high_hz: float | None = None
    qu: float | None = None
    ql: float | None = None
    qc: float | None = None


def _parse_band(values: BandpassFormValues) -> tuple[float, float, float | None, float | None]:
    """Return center, bandwidth, and the edges when the band is given by its edges.

    The center and width come from the edges exactly as the CLI's ``--fl/--fh`` do
    (``band_from_edges``), so the result restates the edges the user typed.
    """
    if values.band_spec == "edges":
        edges = []
        for text, label, field_id in (
            (values.f_low, "Lower cutoff frequency", "f-low"),
            (values.f_high, "Upper cutoff frequency", "f-high"),
        ):
            try:
                edges.append(parse_frequency(text, label=label))
            except ValueError as error:
                raise BandpassFormError(str(error), field_id) from error
        f_low, f_high = edges
        try:
            frequency_hz, bandwidth_hz = band_from_edges(f_low, f_high)
        except ValueError as error:
            raise BandpassFormError(str(error), "f-high") from error
        if bandwidth_hz >= frequency_hz:
            raise BandpassFormError(BANDWIDTH_NOT_BELOW_CENTER, "f-high")
        return frequency_hz, bandwidth_hz, f_low, f_high

    try:
        frequency_hz = parse_frequency(values.frequency, label="Center frequency")
    except ValueError as error:
        raise BandpassFormError(str(error), "frequency") from error
    try:
        bandwidth_hz = parse_frequency(values.bandwidth, label="Bandwidth")
    except ValueError as error:
        raise BandpassFormError(str(error), "bandwidth") from error
    if bandwidth_hz >= frequency_hz:
        raise BandpassFormError(BANDWIDTH_NOT_BELOW_CENTER, "bandwidth")
    return frequency_hz, bandwidth_hz, None, None


def _parse_resonator_q(values: BandpassFormValues) -> dict[str, float | None]:
    """Parse Qu, QL, and QC with the messages the web and the CLI give.

    Qu with QL or QC is refused first (the shared calculator's rule and message), then
    each value is checked against the shared Q range, naming its own field.
    """
    parsed: dict[str, float | None] = {}
    for field_id, label in RESONATOR_Q_FIELDS:
        text = getattr(values, field_id)
        if not text:
            parsed[field_id] = None
            continue
        try:
            parsed[field_id] = float(text)
        except ValueError as error:
            raise BandpassFormError(f"{label} must be a number", field_id) from error
    if parsed["qu"] is not None and (parsed["ql"] is not None or parsed["qc"] is not None):
        try:
            combine_resonator_q(**parsed)
        except ValueError as error:
            raise BandpassFormError(
                str(error), "ql" if parsed["ql"] is not None else "qc"
            ) from error
    for field_id, label in RESONATOR_Q_FIELDS:
        if parsed[field_id] is not None:
            try:
                require_component_q(parsed[field_id], label)
            except ValueError as error:
                raise BandpassFormError(str(error), field_id) from error
    return parsed


def parse_bandpass_form(values: BandpassFormValues) -> ParsedBandpassDesign:
    """Validate the band-pass form without depending on Textual widgets."""
    # The shared parsers name the field in their messages ("Invalid center frequency:
    # abc (use ...)", "Bandwidth must be positive: -5MHz"), so they are shown as-is.
    frequency_hz, bandwidth_hz, f_low_hz, f_high_hz = _parse_band(values)

    try:
        impedance = parse_impedance(values.impedance)
    except ValueError as error:
        raise BandpassFormError(str(error), "impedance") from error

    if values.resonator_impedance and values.resonator_inductance:
        raise BandpassFormError(TANK_SETTING_CONFLICT_MESSAGE, "resonator-inductance")

    resonator_impedance = None
    if values.resonator_impedance:
        try:
            resonator_impedance = parse_impedance(
                values.resonator_impedance, label="Resonator impedance"
            )
        except ValueError as error:
            raise BandpassFormError(str(error), "resonator-impedance") from error

    resonator_inductance = None
    if values.resonator_inductance:
        try:
            resonator_inductance = parse_inductance(
                values.resonator_inductance, label="Resonator inductance"
            )
        except ValueError as error:
            raise BandpassFormError(str(error), "resonator-inductance") from error

    try:
        resonators = int(values.resonators)
    except ValueError:
        resonators = 0
    if not 2 <= resonators <= 9:
        raise BandpassFormError(RESONATOR_COUNT_MESSAGE, "resonators")

    if values.filter_type == "chebyshev" and resonators % 2 == 0:
        raise BandpassFormError(chebyshev_odd_count_message("resonators"), "resonators", "warning")

    ripple_db = 0.5
    if values.filter_type == "chebyshev":
        try:
            ripple_db = parse_ripple_db(values.ripple)
        except ValueError as error:
            raise BandpassFormError(str(error), "ripple") from error

    resonator_q = _parse_resonator_q(values)

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
        requested_f_low_hz=f_low_hz,
        requested_f_high_hz=f_high_hz,
        **resonator_q,
    )


def fractional_bandwidth_feedback(
    frequency_text: str, bandwidth_text: str
) -> tuple[str, str] | None:
    """Return live feedback text and style, or ``None`` for partial input.

    A bandwidth at or above the center frequency is reported as the rejection Next
    will give, not as a percentage: with a subnormal center frequency the ratio can
    overflow to infinity, and no such design is accepted anyway.
    """
    try:
        frequency_hz = parse_frequency(frequency_text)
        bandwidth_hz = parse_frequency(bandwidth_text)
    except ValueError:
        return None
    return _band_feedback(frequency_hz, bandwidth_hz)


def edge_bandwidth_feedback(f_low_text: str, f_high_text: str) -> tuple[str, str] | None:
    """Return live feedback for a band given by its edges, or ``None`` for partial input.

    Edges in the wrong order get the rejection Next will give.
    """
    try:
        f_low = parse_frequency(f_low_text)
        f_high = parse_frequency(f_high_text)
    except ValueError:
        return None
    try:
        frequency_hz, bandwidth_hz = band_from_edges(f_low, f_high)
    except ValueError as error:
        return (str(error), "fbw-danger")
    return _band_feedback(frequency_hz, bandwidth_hz)


def _band_feedback(frequency_hz: float, bandwidth_hz: float) -> tuple[str, str]:
    if bandwidth_hz >= frequency_hz:
        return (BANDWIDTH_NOT_BELOW_CENTER, "fbw-danger")

    # Both values are positive and finite and bandwidth < center, so the ratio is
    # finite and at most 1; at extreme scales it can only underflow toward zero.
    # Above the tested range the hint is the design warning the result will carry.
    fractional_bw = bandwidth_hz / frequency_hz
    if fractional_bw > BANDPASS_LUMPED_MODEL_CAUTION_FBW:
        return (fbw_impractical_warning(fractional_bw), "fbw-danger")
    if fractional_bw > BANDPASS_EDGE_CALIBRATION_FBW_MAX:
        return (fbw_untested_warning(fractional_bw), "fbw-warning")
    return (
        f"Fractional bandwidth {fractional_bw * 100:.1f}% is within the "
        f"{BANDPASS_EDGE_CALIBRATION_FBW_MAX * 100:g}% this design method was tested up to. "
        "The Response check line in the result confirms the design.",
        "fbw-display",
    )
