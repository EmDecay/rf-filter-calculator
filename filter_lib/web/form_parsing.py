"""Turn a submitted design form into the shared request, render options, and build config.

Field names mirror the CLI flags (``frequency``, ``impedance``, ``components`` or
``resonators``, ``ripple``, ``bandwidth``, ``f_low``, ``f_high``, ``qu``, ``ql``,
``qc``, ``resonator_impedance``, ``resonator_inductance``, ``eseries``,
``allow_sub_pf``, ``raw``, ``plot``, ``sim_build``, ``build_*``, ``toroid_build``). Units are parsed with the CLI's parsers and
labels (so a value the CLI would reject gets the CLI's message), defaults come from the
CLI's constants, and all cross-field rules are left to ``DesignRequest`` and
``RenderOptions`` so the web reports the CLI's messages. Messages only the form can
produce (a blank required field, a non-number) name the field's visible label.
"""

from __future__ import annotations

from dataclasses import dataclass, replace

from ..bandpass.input_validation import RESONATOR_COUNT_MESSAGE
from ..design import DesignRequest, RenderOptions, band_from_edges
from ..design.design_request import CATEGORIES
from ..design.option_applicability import (
    ALLOW_SUB_PF,
    BUILD,
    LOSS_Q,
    RAW_UNITS,
    TEXT_PLOT,
    TOROID_DETAIL,
    OutputChoices,
    option_reason,
    require_applicable,
)
from ..design.render_options import BUILD_NEEDS_ESERIES_MESSAGE
from ..shared.build_types import BuildConfig
from ..shared.cli_aliases import (
    DEFAULT_COMPONENTS,
    DEFAULT_ESERIES,
    DEFAULT_IMPEDANCE,
    DEFAULT_RESONATORS,
    DEFAULT_RIPPLE_DB,
    RIPPLE_RANGE_MESSAGE,
    resolve_filter_type,
)
from ..shared.cli_argument_parsers import require_count
from ..shared.cli_helpers import FILTER_TYPE_CHOICES, validate_filter_args
from ..shared.parsing import parse_frequency, parse_impedance, parse_inductance
from .build_form_parsing import BUILD_FIELD_DEFAULTS, parse_build_config
from .form_values import FormData, choice, flag, float_or, int_or, optional_float, required, text

FILTER_TYPES = tuple(FILTER_TYPE_CHOICES)
OUTPUT_FORMATS = ("table", "quiet", "json", "csv")
ESERIES_CHOICES = ("E12", "E24", "E96", "none")
TOROID_CHOICES = ("best", "full", "compact", "none")
BAND_SPECS = ("center", "edges")


@dataclass(frozen=True)
class DesignForm:
    """Everything one submission asks for.

    ``request.build`` is set only when the build simulation was requested;
    ``spice_config`` is the configuration the chosen-parts SPICE deck uses: the
    submitted build controls when that section is enabled, the defaults otherwise.
    """

    request: DesignRequest
    options: RenderOptions
    spice_config: BuildConfig
    svg_plot: bool

    def option_choices(self) -> OutputChoices:
        """The submitted choices, as the shared applicability rule judges them."""
        options = self.options
        return OutputChoices(
            output_format=options.output_format,
            eseries=options.eseries,
            raw=options.raw,
            build=self.request.build is not None,
            include_toroids=options.include_toroids,
        )

    def require_applicable_options(self) -> None:
        """Refuse a ticked option the submitted output cannot apply, as the CLI does.

        The page disables such controls, so only a hand-made request (or a browser
        without JavaScript) reaches this. The E-series is not checked: the form always
        sends one, so the server cannot tell a choice from the default. Resonator Q is
        refused with the shared message naming only the Q values sent.
        """
        options = self.options
        selected = (
            (RAW_UNITS, options.raw),
            (TEXT_PLOT, options.show_plot),
            (TOROID_DETAIL, options.toroid_full or options.toroid_compact),
            (ALLOW_SUB_PF, self.request.allow_sub_pf),
            (BUILD, self.request.build is not None),
        )
        choices = self.option_choices()
        require_applicable(choices, [option for option, ticked in selected if ticked])
        if option_reason(choices, LOSS_Q) is not None:
            self.request.reject_loss_q()


# Example designs prefilled on a fresh page: the README examples, the same values the
# wizard uses (10 MHz low-pass Pi and high-pass T; the 20 m band for band-pass). The
# band edges are the -3 dB edges of 14.175 MHz / 350 kHz, rounded to the band limits.
EXAMPLE_FIELDS = {
    "lowpass": {"topology": "pi", "frequency": "10MHz"},
    "highpass": {"topology": "t", "frequency": "10MHz"},
    "bandpass": {
        "coupling": "top",
        "band_spec": "center",
        "frequency": "14.175MHz",
        "bandwidth": "350kHz",
        "f_low": "14MHz",
        "f_high": "14.35MHz",
    },
}


def form_defaults(category: str) -> dict[str, str]:
    """Field values for a fresh form, using the CLI's defaults and help examples.

    Checkbox names map to ``"on"`` when checked by default; the web shows the
    response plot by default, a deliberate choice of this surface. The build fields
    are filled with the CLI's defaults, and the toroid-winding build box is ticked,
    as the CLI simulates the windings unless ``--no-toroid-build`` is given.
    """
    order_field = (
        {"resonators": str(DEFAULT_RESONATORS)}
        if category == "bandpass"
        else {"components": str(DEFAULT_COMPONENTS)}
    )
    return {
        "filter_type": "butterworth",
        "impedance": DEFAULT_IMPEDANCE,
        "ripple": f"{DEFAULT_RIPPLE_DB:g}",
        "eseries": DEFAULT_ESERIES,
        "toroids": "best",
        "output_format": "table",
        "svg_plot": "on",
        **BUILD_FIELD_DEFAULTS,
        **order_field,
        **EXAMPLE_FIELDS[require_category(category)],
    }


def require_category(category: str) -> str:
    if category not in CATEGORIES:
        raise ValueError("Unknown filter category")
    return category


def _render_options(form: FormData) -> RenderOptions:
    eseries = choice(form, "eseries", ESERIES_CHOICES, DEFAULT_ESERIES, "Standard capacitor values")
    toroids = choice(form, "toroids", TOROID_CHOICES, "best", "Toroid detail")
    return RenderOptions(
        output_format=choice(form, "output_format", OUTPUT_FORMATS, "table", "Output format"),
        raw=flag(form, "raw"),
        eseries=None if eseries == "none" else eseries,
        show_plot=flag(form, "plot"),
        include_toroids=toroids != "none",
        toroid_compact=toroids == "compact",
        toroid_full=toroids == "full",
    )


def _ladder_request(category: str, form: FormData, filter_type: str) -> DesignRequest:
    frequency_hz = parse_frequency(required(form, "frequency", "Cutoff frequency"))
    impedance = parse_impedance(text(form, "impedance", DEFAULT_IMPEDANCE))
    components = int_or(form, "components", "Number of components", DEFAULT_COMPONENTS)
    validate_filter_args(frequency_hz, impedance, components)
    return DesignRequest(
        category=category,
        filter_type=filter_type,
        topology=choice(form, "topology", ("pi", "t"), "pi", "Topology"),
        frequency_hz=frequency_hz,
        impedance=impedance,
        order=components,
        ripple_db=_ripple(form, filter_type),
        allow_sub_pf=flag(form, "allow_sub_pf"),
    )


def _ripple(form: FormData, filter_type: str) -> float:
    """Read ripple only for Chebyshev; other types hide the field and ignore it."""
    if resolve_filter_type(filter_type) != "chebyshev":
        return DEFAULT_RIPPLE_DB
    try:
        return float_or(form, "ripple", "Passband ripple", DEFAULT_RIPPLE_DB)
    except ValueError:
        # Text that is not a number gets the same range message as any other bad ripple.
        raise ValueError(RIPPLE_RANGE_MESSAGE) from None


def _bandpass_band(form: FormData) -> tuple[float, float, float | None, float | None]:
    """Return center, bandwidth, and the requested edges when given by edges."""
    if choice(form, "band_spec", BAND_SPECS, "center", "Band specification") == "edges":
        f_low = parse_frequency(
            required(form, "f_low", "Lower edge"), label="Lower cutoff frequency"
        )
        f_high = parse_frequency(
            required(form, "f_high", "Upper edge"), label="Upper cutoff frequency"
        )
        return (*band_from_edges(f_low, f_high), f_low, f_high)
    f0 = parse_frequency(required(form, "frequency", "Center frequency"), label="Center frequency")
    bw = parse_frequency(required(form, "bandwidth", "Bandwidth"), label="Bandwidth")
    return f0, bw, None, None


def _bandpass_request(form: FormData, filter_type: str) -> DesignRequest:
    f0, bw, f_low, f_high = _bandpass_band(form)
    impedance = parse_impedance(text(form, "impedance", DEFAULT_IMPEDANCE))
    # The range is checked before the Chebyshev odd-count rule, in the CLI's order.
    resonators = require_count(
        int_or(form, "resonators", "Number of resonators", DEFAULT_RESONATORS),
        RESONATOR_COUNT_MESSAGE,
    )
    tank_impedance = text(form, "resonator_impedance")
    tank_inductance = text(form, "resonator_inductance")
    return DesignRequest(
        category="bandpass",
        filter_type=filter_type,
        topology=choice(form, "coupling", ("top",), "top", "Coupling"),
        frequency_hz=f0,
        impedance=impedance,
        order=resonators,
        ripple_db=_ripple(form, filter_type),
        bandwidth_hz=bw,
        requested_f_low_hz=f_low,
        requested_f_high_hz=f_high,
        qu=optional_float(form, "qu", "Qu"),
        ql=optional_float(form, "ql", "QL"),
        qc=optional_float(form, "qc", "QC"),
        resonator_impedance=(
            parse_impedance(tank_impedance, label="Resonator impedance") if tank_impedance else None
        ),
        resonator_inductance=(
            parse_inductance(tank_inductance, label="Resonator inductance")
            if tank_inductance
            else None
        ),
        allow_sub_pf=flag(form, "allow_sub_pf"),
    )


def parse_design_form(category: str, form: FormData) -> DesignForm:
    """Validate a submission for ``category`` and return what it asks for."""
    require_category(category)
    filter_type = choice(form, "filter_type", FILTER_TYPES, "butterworth", "Response")
    if category == "bandpass":
        request = _bandpass_request(form, filter_type)
    else:
        request = _ladder_request(category, form, filter_type)
    options = _render_options(form)
    if request.allow_sub_pf:
        # Checked here, not only when rendering, so every download gives the same answer.
        options.validate_for_sub_pf()

    eseries = options.eseries or DEFAULT_ESERIES
    if flag(form, "sim_build"):
        # The build needs standard values; whether the chosen output can show it is
        # checked by each route against the document it actually produces.
        if options.eseries is None:
            raise ValueError(BUILD_NEEDS_ESERIES_MESSAGE)
        build_config = parse_build_config(
            form,
            eseries,
            use_toroids=options.include_toroids,
            resonator_q_supplied=any(q is not None for q in (request.qu, request.ql, request.qc)),
        )
        request = replace(request, build=build_config)
    else:
        # Build fields are ignored unless the build section is enabled; the deck then
        # uses the CLI's defaults for the chosen E-series and toroid setting.
        build_config = BuildConfig(eseries=eseries, use_toroid_candidates=options.include_toroids)
    return DesignForm(
        request=request,
        options=options,
        spice_config=build_config,
        svg_plot=flag(form, "svg_plot"),
    )
