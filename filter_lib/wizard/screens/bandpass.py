"""Bandpass filter input screen, with the web form's sections and fields."""

from textual import on
from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical, VerticalScroll
from textual.screen import Screen
from textual.types import NoActiveAppError
from textual.validation import Integer
from textual.widgets import Button, Footer, Input, RadioButton, RadioSet, Static

from ...design.option_applicability import LOSS_Q
from ..bandpass_form import (
    BandpassFormError,
    BandpassFormValues,
    edge_bandwidth_feedback,
    fractional_bandwidth_feedback,
    parse_bandpass_form,
)
from ..design_field_validation import RESONATOR_COUNT_LABELS, RIPPLE_LABEL, RippleValidator
from ..filter_screen_navigation_mixin import FilterScreenNavigationMixin
from ..radio_button_helpers import get_selected_radio
from ..state import FilterState

# Example band shown as placeholders (blank = these), as on the web form: the 20 m
# band, 14.175 MHz / 350 kHz, whose -3 dB edges round to 14 MHz / 14.35 MHz.
CENTER_EXAMPLE = "14.175MHz"
BANDWIDTH_EXAMPLE = "350kHz"
F_LOW_EXAMPLE = "14MHz"
F_HIGH_EXAMPLE = "14.35MHz"
RESONATOR_Q_IDS = ("qu", "ql", "qc")
RESONATOR_QU_HELP = (
    "Unloaded Q of each resonator, inductor and capacitor losses together. Adds a loss "
    "estimate and is used by the build simulation."
)
RESONATOR_Q_NOTE = (
    "Or enter QL and QC instead of Qu; they combine as 1/Qu = 1/QL + 1/QC. QC applies to "
    "the resonator capacitors only. Each Q is 0.01 to 1e9."
)


class BandpassScreen(FilterScreenNavigationMixin, Screen):
    """Screen for configuring bandpass filter parameters.

    On "Next" it validates the form, writes the shared FilterState, and
    pushes the output-options screen. Differs from LP/HP in taking a band (center
    and width, or the -3 dB edges, with live fractional-BW feedback), a resonator
    count, and optional resonator size and Q.
    """

    BINDINGS = [
        ("escape", "back", "Back"),
    ]
    FOCUS_FLOW = (
        "filter-type",
        "coupling",
        "ripple",
        "band-spec",
        "frequency",
        "bandwidth",
        "f-low",
        "f-high",
        "resonators",
        "impedance",
        "resonator-impedance",
        "resonator-inductance",
        *RESONATOR_Q_IDS,
        "next-btn",
    )

    def compose(self) -> ComposeResult:
        yield Static("Band-Pass Filter Design", classes="header")
        yield Static("Enter: next · ↑/↓: choose · Esc: back", classes="nav-hint")
        with VerticalScroll(classes="content"):
            with Vertical(classes="form-section"):
                yield Static("Response and coupling", classes="form-section-title")
                yield Static("Response", classes="field-label")
                with RadioSet(id="filter-type"):
                    yield RadioButton(
                        "Butterworth - Maximally flat passband", value=True, id="butterworth"
                    )
                    yield RadioButton("Chebyshev - Sharper cutoff, passband ripple", id="chebyshev")
                    yield RadioButton(
                        "Bessel - Gentle skirts; the band-pass form does not keep flat group delay",
                        id="bessel",
                    )
                # Single-option RadioSet on purpose: Top-C is the only coupling
                # that survived simulation validation (shunt coupling was
                # removed), but keeping the RadioSet preserves the Enter-through
                # navigation flow and leaves room for future topologies.
                yield Static("Coupling", classes="field-label")
                with RadioSet(id="coupling"):
                    yield RadioButton(
                        "Top-C - series capacitors couple the resonators", value=True, id="top"
                    )
                with Vertical(id="ripple-section"):
                    yield Static(RIPPLE_LABEL)
                    yield Input(
                        value="0.5",
                        id="ripple",
                        validators=[RippleValidator()],
                    )

            with Vertical(classes="form-section"):
                yield Static("Passband", classes="form-section-title")
                yield Static("Specify the band by", classes="field-label")
                with RadioSet(id="band-spec"):
                    yield RadioButton("Center and width", value=True, id="center")
                    yield RadioButton("Band edges", id="edges")
                with Vertical(id="center-fields"):
                    yield Static(
                        f"Center frequency (e.g. {CENTER_EXAMPLE}; blank = {CENTER_EXAMPLE}):"
                    )
                    yield Input(placeholder=CENTER_EXAMPLE, id="frequency")
                    yield Static(
                        "Bandwidth between the -3 dB edges, less than the center frequency "
                        f"(e.g. {BANDWIDTH_EXAMPLE}; blank = {BANDWIDTH_EXAMPLE}):"
                    )
                    yield Input(placeholder=BANDWIDTH_EXAMPLE, id="bandwidth")
                with Vertical(id="edge-fields"):
                    yield Static(
                        f"Lower edge, -3 dB (e.g. {F_LOW_EXAMPLE}; blank = {F_LOW_EXAMPLE}):"
                    )
                    yield Input(placeholder=F_LOW_EXAMPLE, id="f-low")
                    yield Static(
                        f"Upper edge, -3 dB (e.g. {F_HIGH_EXAMPLE}; blank = {F_HIGH_EXAMPLE}):"
                    )
                    yield Input(placeholder=F_HIGH_EXAMPLE, id="f-high")
                yield Static("", id="fbw-display", classes="fbw-display")
                yield Static(RESONATOR_COUNT_LABELS[False], id="resonators-label")
                yield Input(
                    value="3",
                    id="resonators",
                    validators=[Integer(minimum=2, maximum=9)],
                )
                yield Static("Impedance, equal source and load (e.g. 50, 50ohm, 1k):")
                yield Input(
                    value="50",
                    placeholder="50 or 50ohm",
                    id="impedance",
                )

            with Vertical(classes="form-section"):
                yield Static("Resonators and losses (optional)", classes="form-section-title")
                yield Static(
                    "Each resonator is an L-C tank. Set its impedance or its inductance, "
                    "not both; leave both blank to use the impedance above."
                )
                yield Static("Resonator impedance sqrt(L/C) (e.g. 75ohm):")
                yield Input(placeholder="blank = impedance above", id="resonator-impedance")
                yield Static("Resonator inductance (e.g. 1uH):")
                yield Input(
                    placeholder="blank = from the resonator impedance", id="resonator-inductance"
                )
                yield Static("Resonator Qu", classes="field-label")
                yield Input(id="qu")
                yield Static(RESONATOR_QU_HELP, classes="field-help")
                yield Static("Inductor QL", classes="field-label")
                yield Input(id="ql")
                yield Static("Capacitor QC", classes="field-label")
                yield Input(id="qc")
                yield Static(RESONATOR_Q_NOTE, classes="field-help")
                reason = Static("", id="reason-loss_q", classes="option-reason")
                reason.display = False
                yield reason

            with Horizontal(classes="button-row"):
                yield Button("Next", id="next-btn", variant="primary")
                yield Button("Reset", id="reset-btn")

        yield Footer()

    def on_mount(self) -> None:
        """Focus on filter type selection; hide ripple and the band-edge fields."""
        self.query_one("#filter-type", RadioSet).focus()
        self.query_one("#ripple-section").display = False
        self.query_one("#edge-fields").display = False
        self._refresh_resonator_q()

    def on_screen_resume(self) -> None:
        """Coming back from Output options: the chosen format may leave out resonator Q."""
        self._refresh_resonator_q()

    def _refresh_resonator_q(self) -> None:
        """Disable Qu/QL/QC, with the shared rule's reason, when the output cannot use them.

        The output format is chosen on the next screen, so this reflects the choice made
        there; values stay in place and still reach a saved JSON file.
        """
        try:
            state = self.app.filter_state
        except NoActiveAppError:
            return
        if not isinstance(state, FilterState):
            return
        reason = state.option_reasons().get(LOSS_Q)
        for field_id in RESONATOR_Q_IDS:
            self.query_one(f"#{field_id}", Input).disabled = reason is not None
        static = self.query_one("#reason-loss_q", Static)
        static.update(reason or "")
        static.display = reason is not None

    def _band_by_edges(self) -> bool:
        return get_selected_radio(self, "band-spec") == "edges"

    def _is_shown(self, widget_id: str) -> bool:
        """Skip hidden or disabled fields: ripple, the other band entry, disabled Q."""
        if widget_id == "ripple":
            return bool(self.query_one("#ripple-section").display)
        if widget_id in ("frequency", "bandwidth"):
            return not self._band_by_edges()
        if widget_id in ("f-low", "f-high"):
            return self._band_by_edges()
        if widget_id in RESONATOR_Q_IDS:
            return self.query_one(f"#{widget_id}", Input).disabled is not True
        return True

    @on(RadioSet.Changed, "#filter-type")
    def _on_filter_type_changed(self, event: RadioSet.Changed) -> None:
        """Show/hide ripple section and odd-count hint based on filter type."""
        self._invalidate_previous_result()
        is_chebyshev = event.pressed.id == "chebyshev"
        self.query_one("#ripple-section").display = is_chebyshev
        self.query_one("#resonators-label", Static).update(RESONATOR_COUNT_LABELS[is_chebyshev])

    @on(RadioSet.Changed, "#band-spec")
    def _on_band_spec_changed(self, event: RadioSet.Changed) -> None:
        """Show the center/width fields or the band-edge fields."""
        edges = event.pressed.id == "edges"
        self.query_one("#center-fields").display = not edges
        self.query_one("#edge-fields").display = edges
        self._update_fbw_display()

    def action_back(self) -> None:
        """Go back to welcome screen."""
        self.app.pop_screen()

    @on(Input.Changed, "#frequency")
    @on(Input.Changed, "#bandwidth")
    @on(Input.Changed, "#f-low")
    @on(Input.Changed, "#f-high")
    def _update_fbw_display(self) -> None:
        """Update fractional bandwidth display when the band changes.

        Live feedback says whether the fractional bandwidth is inside the range the
        design method was tested for; the result's Response check line stays the
        final word.
        """
        self._invalidate_previous_result()

        fbw_display = self.query_one("#fbw-display", Static)
        if self._band_by_edges():
            feedback = edge_bandwidth_feedback(
                self.query_one("#f-low", Input).value, self.query_one("#f-high", Input).value
            )
        else:
            feedback = fractional_bandwidth_feedback(
                self.query_one("#frequency", Input).value,
                self.query_one("#bandwidth", Input).value,
            )
        if feedback is None:
            fbw_display.update("")
            return
        text, class_name = feedback
        for old_class in ("fbw-display", "fbw-warning", "fbw-danger"):
            fbw_display.remove_class(old_class)
        fbw_display.update(text)
        fbw_display.add_class(class_name)

    @on(Input.Changed, "#impedance")
    @on(Input.Changed, "#resonators")
    @on(Input.Changed, "#ripple")
    @on(Input.Changed, "#resonator-impedance")
    @on(Input.Changed, "#resonator-inductance")
    @on(Input.Changed, "#qu")
    @on(Input.Changed, "#ql")
    @on(Input.Changed, "#qc")
    def _on_design_input_changed(self, event: Input.Changed) -> None:
        """Invalidate prior output as soon as any non-FBW input changes."""
        self._invalidate_previous_result()

    @on(RadioSet.Changed, "#coupling")
    def _on_coupling_changed(self, event: RadioSet.Changed) -> None:
        """Invalidate prior output when coupling selection changes."""
        self._invalidate_previous_result()

    def _invalidate_previous_result(self) -> None:
        """Clear stale output when mounted; tolerate calls on an unmounted screen."""
        try:
            state = self.app.filter_state
        except NoActiveAppError:
            return
        if isinstance(state, FilterState):
            state.invalidate_calculation()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle button presses."""
        if event.button.id == "next-btn":
            self._validate_and_continue()
        elif event.button.id == "reset-btn":
            self._reset_form()

    def _value(self, field_id: str, blank: str = "") -> str:
        """The stripped field text, or ``blank`` when it is empty."""
        return self.query_one(f"#{field_id}", Input).value.strip() or blank

    def _validate_and_continue(self) -> None:
        """Validate inputs and proceed to output options.

        Re-checks ranges the Input validators already cover: validators only
        style the field red — they don't block the Next button. On any
        failure, notify and refocus the offending field instead of advancing.
        """
        try:
            design = parse_bandpass_form(
                BandpassFormValues(
                    frequency=self._value("frequency", CENTER_EXAMPLE),
                    bandwidth=self._value("bandwidth", BANDWIDTH_EXAMPLE),
                    impedance=self._value("impedance", "50"),
                    resonators=self.query_one("#resonators", Input).value,
                    ripple=self.query_one("#ripple", Input).value,
                    resonator_impedance=self._value("resonator-impedance"),
                    resonator_inductance=self._value("resonator-inductance"),
                    filter_type=get_selected_radio(self, "filter-type"),
                    coupling=get_selected_radio(self, "coupling"),
                    band_spec="edges" if self._band_by_edges() else "center",
                    f_low=self._value("f-low", F_LOW_EXAMPLE),
                    f_high=self._value("f-high", F_HIGH_EXAMPLE),
                    qu=self._value("qu"),
                    ql=self._value("ql"),
                    qc=self._value("qc"),
                )
            )
        except BandpassFormError as error:
            self.notify(str(error), severity=error.severity)
            self.query_one(f"#{error.field_id}", Input).focus()
            return

        state: FilterState = self.app.filter_state
        state.invalidate_calculation()
        state.category = "bandpass"
        state.filter_type = design.filter_type
        # FilterState reuses the topology field for the bandpass coupling id
        # ("top"); order likewise carries the resonator count.
        state.topology = design.coupling
        state.frequency_hz = design.frequency_hz
        state.bandwidth_hz = design.bandwidth_hz
        state.requested_f_low_hz = design.requested_f_low_hz
        state.requested_f_high_hz = design.requested_f_high_hz
        state.impedance = design.impedance
        state.order = design.resonators
        state.ripple_db = design.ripple_db
        state.resonator_impedance = design.resonator_impedance
        state.resonator_inductance = design.resonator_inductance
        state.qu, state.ql, state.qc = design.qu, design.ql, design.qc

        from .output_options import OutputOptionsScreen

        self.app.push_screen(OutputOptionsScreen())

    def _reset_form(self) -> None:
        """Reset form to defaults."""
        for field_id in (
            "frequency",
            "bandwidth",
            "f-low",
            "f-high",
            "resonator-impedance",
            "resonator-inductance",
            *RESONATOR_Q_IDS,
        ):
            self.query_one(f"#{field_id}", Input).value = ""
        self.query_one("#impedance", Input).value = "50"
        self.query_one("#resonators", Input).value = "3"
        self.query_one("#ripple", Input).value = "0.5"
        self.query_one("#fbw-display", Static).update("")
        self.query_one("#center", RadioButton).value = True
        self.query_one("#center-fields").display = True
        self.query_one("#edge-fields").display = False
        self.query_one("#frequency", Input).focus()
