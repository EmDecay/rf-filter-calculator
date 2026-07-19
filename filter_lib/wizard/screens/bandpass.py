"""Bandpass filter input screen."""

from textual import on
from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical, VerticalScroll
from textual.screen import Screen
from textual.validation import Number
from textual.widgets import Button, Footer, Input, RadioButton, RadioSet, Static

from ..bandpass_form import (
    BandpassFormError,
    BandpassFormValues,
    fractional_bandwidth_feedback,
    parse_bandpass_form,
)
from ..filter_screen_navigation_mixin import FilterScreenNavigationMixin
from ..radio_button_helpers import get_selected_radio
from ..state import FilterState


class BandpassScreen(FilterScreenNavigationMixin, Screen):
    """Screen for configuring bandpass filter parameters.

    On "Next" it validates the form, writes the shared FilterState, and
    pushes the output-options screen. Differs from LP/HP in taking a
    bandwidth (with live fractional-BW feedback) and a resonator count
    instead of a component order.
    """

    BINDINGS = [
        ("escape", "back", "Back"),
    ]
    RADIO_SET_FLOW = ["filter-type", "coupling"]
    FIRST_INPUT_ID = "frequency"

    def compose(self) -> ComposeResult:
        yield Static("Band-Pass Filter Design", classes="header")
        yield Static("Enter: next · ↑/↓: choose · Esc: back", classes="nav-hint")
        with VerticalScroll(classes="content"):
            with Vertical(classes="form-section"):
                yield Static("Response Type", classes="form-section-title")
                with RadioSet(id="filter-type"):
                    yield RadioButton(
                        "Butterworth - Maximally flat passband", value=True, id="butterworth"
                    )
                    yield RadioButton("Chebyshev - Sharper cutoff, passband ripple", id="chebyshev")
                    yield RadioButton(
                        "Bessel - Band-pass transform does not preserve flat group delay",
                        id="bessel",
                    )

            # Single-option RadioSet on purpose: Top-C is the only coupling
            # that survived simulation validation (shunt coupling was
            # removed), but keeping the RadioSet preserves the Enter-through
            # navigation flow and leaves room for future topologies.
            with Vertical(classes="form-section"):
                yield Static("Coupling Topology", classes="form-section-title")
                with RadioSet(id="coupling"):
                    yield RadioButton(
                        "Top-C (Series) - capacitively coupled resonators", value=True, id="top"
                    )

            with Vertical(classes="form-section"):
                yield Static("Frequency", classes="form-section-title")
                yield Static("Center Frequency (e.g., 14.175MHz):")
                yield Input(
                    placeholder="14.175MHz",
                    id="frequency",
                )
                yield Static("Bandwidth (e.g., 350kHz):")
                yield Input(
                    placeholder="350kHz",
                    id="bandwidth",
                )
                yield Static("", id="fbw-display", classes="fbw-display")

            with Vertical(classes="form-section"):
                yield Static("Parameters", classes="form-section-title")
                yield Static("Impedance (e.g., 50, 50ohm, 1k):")
                yield Input(
                    value="50",
                    placeholder="50 or 50ohm",
                    id="impedance",
                )
                yield Static("Resonators (2-9):", id="resonators-label")
                yield Input(
                    value="3",
                    id="resonators",
                    validators=[Number(minimum=2, maximum=9)],
                )
                with Vertical(id="ripple-section"):
                    yield Static("Ripple (dB):")
                    yield Input(
                        value="0.5",
                        id="ripple",
                        validators=[Number(minimum=0.01, maximum=3.0)],
                    )

            with Vertical(classes="form-section"):
                yield Static("Advanced Tank Choice (optional)", classes="form-section-title")
                yield Static(
                    "Use one setting only; blank uses the port impedance for each resonator."
                )
                yield Static("Tank impedance (e.g., 75ohm):")
                yield Input(placeholder="blank = port impedance", id="resonator-impedance")
                yield Static("Fixed tank inductance (e.g., 1uH):")
                yield Input(
                    placeholder="blank = calculate from impedance", id="resonator-inductance"
                )

            with Horizontal(classes="button-row"):
                yield Button("Next", id="next-btn", variant="primary")
                yield Button("Reset", id="reset-btn")

        yield Footer()

    def on_mount(self) -> None:
        """Focus on filter type selection and hide ripple section initially."""
        self.query_one("#filter-type", RadioSet).focus()
        self.query_one("#ripple-section").display = False

    @on(RadioSet.Changed, "#filter-type")
    def _on_filter_type_changed(self, event: RadioSet.Changed) -> None:
        """Show/hide ripple section and odd-count hint based on filter type."""
        self._invalidate_previous_result()
        is_chebyshev = event.pressed.id == "chebyshev"
        self.query_one("#ripple-section").display = is_chebyshev
        resonators_label = self.query_one("#resonators-label", Static)
        if is_chebyshev:
            resonators_label.update("Resonators (Chebyshev: odd only — 3, 5, 7, 9):")
        else:
            resonators_label.update("Resonators (2-9):")

    @on(Input.Submitted, "#frequency")
    def _on_frequency_submitted(self, event: Input.Submitted) -> None:
        """Auto-advance to bandwidth input after frequency entry."""
        self.query_one("#bandwidth", Input).focus()

    @on(Input.Submitted, "#bandwidth")
    def _on_bandwidth_submitted(self, event: Input.Submitted) -> None:
        """Auto-advance to impedance input after bandwidth entry."""
        self.query_one("#impedance", Input).focus()

    @on(Input.Submitted, "#impedance")
    def _on_impedance_submitted(self, event: Input.Submitted) -> None:
        """Auto-advance to resonators input after impedance entry."""
        self.query_one("#resonators", Input).focus()

    @on(Input.Submitted, "#resonators")
    def _on_resonators_submitted(self, event: Input.Submitted) -> None:
        """Auto-advance to ripple or button after resonators entry."""
        if self.query_one("#ripple-section").display:
            self.query_one("#ripple", Input).focus()
        else:
            self.query_one("#next-btn", Button).focus()

    @on(Input.Submitted, "#ripple")
    def _on_ripple_submitted(self, event: Input.Submitted) -> None:
        """Auto-advance to calculate button after ripple entry."""
        self.query_one("#next-btn", Button).focus()

    @on(Input.Submitted, "#resonator-impedance")
    def _on_resonator_impedance_submitted(self, event: Input.Submitted) -> None:
        """Advance between optional tank fields when reached by Tab."""
        self.query_one("#resonator-inductance", Input).focus()

    @on(Input.Submitted, "#resonator-inductance")
    def _on_resonator_inductance_submitted(self, event: Input.Submitted) -> None:
        """Advance from the optional tank fields to Next."""
        self.query_one("#next-btn", Button).focus()

    def action_back(self) -> None:
        """Go back to welcome screen."""
        self.app.pop_screen()

    @on(Input.Changed, "#frequency")
    @on(Input.Changed, "#bandwidth")
    def _update_fbw_display(self) -> None:
        """Update fractional bandwidth display when frequency or bandwidth changes.

        Live feedback distinguishes the studied edge-calibration range from
        the final response validation, which remains authoritative.
        """
        self._invalidate_previous_result()

        freq_input = self.query_one("#frequency", Input)
        bw_input = self.query_one("#bandwidth", Input)
        fbw_display = self.query_one("#fbw-display", Static)

        feedback = fractional_bandwidth_feedback(freq_input.value, bw_input.value)
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
    def _on_design_input_changed(self, event: Input.Changed) -> None:
        """Invalidate prior output as soon as any non-FBW input changes."""
        self._invalidate_previous_result()

    @on(RadioSet.Changed, "#coupling")
    def _on_coupling_changed(self, event: RadioSet.Changed) -> None:
        """Invalidate prior output when coupling selection changes."""
        self._invalidate_previous_result()

    def _invalidate_previous_result(self) -> None:
        """Clear stale output when mounted; tolerate direct handler tests."""
        try:
            state = self.app.filter_state
        except (AttributeError, RuntimeError):
            return
        if isinstance(state, FilterState):
            state.invalidate_calculation()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle button presses."""
        if event.button.id == "next-btn":
            self._validate_and_continue()
        elif event.button.id == "reset-btn":
            self._reset_form()

    def _validate_and_continue(self) -> None:
        """Validate inputs and proceed to output options.

        Re-checks ranges the Input validators already cover: validators only
        style the field red — they don't block the Next button. On any
        failure, notify and refocus the offending field instead of advancing.
        """
        freq_input = self.query_one("#frequency", Input)
        bw_input = self.query_one("#bandwidth", Input)
        impedance_input = self.query_one("#impedance", Input)
        resonators_input = self.query_one("#resonators", Input)
        ripple_input = self.query_one("#ripple", Input)
        resonator_impedance_input = self.query_one("#resonator-impedance", Input)
        resonator_inductance_input = self.query_one("#resonator-inductance", Input)

        filter_type = get_selected_radio(self, "filter-type")
        coupling = get_selected_radio(self, "coupling")
        try:
            design = parse_bandpass_form(
                BandpassFormValues(
                    frequency=freq_input.value.strip() or freq_input.placeholder,
                    bandwidth=bw_input.value.strip() or bw_input.placeholder,
                    impedance=impedance_input.value.strip() or "50",
                    resonators=resonators_input.value,
                    ripple=ripple_input.value,
                    resonator_impedance=resonator_impedance_input.value.strip(),
                    resonator_inductance=resonator_inductance_input.value.strip(),
                    filter_type=filter_type,
                    coupling=coupling,
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
        state.impedance = design.impedance
        state.order = design.resonators
        state.ripple_db = design.ripple_db
        state.resonator_impedance = design.resonator_impedance
        state.resonator_inductance = design.resonator_inductance

        from .output_options import OutputOptionsScreen

        self.app.push_screen(OutputOptionsScreen())

    def _reset_form(self) -> None:
        """Reset form to defaults."""
        self.query_one("#frequency", Input).value = ""
        self.query_one("#bandwidth", Input).value = ""
        self.query_one("#impedance", Input).value = "50"
        self.query_one("#resonators", Input).value = "3"
        self.query_one("#ripple", Input).value = "0.5"
        self.query_one("#resonator-impedance", Input).value = ""
        self.query_one("#resonator-inductance", Input).value = ""
        self.query_one("#fbw-display", Static).update("")
        self.query_one("#frequency", Input).focus()
