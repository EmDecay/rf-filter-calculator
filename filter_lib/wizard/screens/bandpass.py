"""Bandpass filter input screen."""
from textual.app import ComposeResult
from textual.screen import Screen
from textual.widgets import Button, Footer, Static, Input, RadioSet, RadioButton
from textual.containers import VerticalScroll, Vertical, Horizontal
from textual.validation import Number
from textual import on

from ..state import FilterState
from ..radio_button_helpers import get_selected_radio
from ..filter_screen_navigation_mixin import FilterScreenNavigationMixin


class BandpassScreen(FilterScreenNavigationMixin, Screen):
    """Screen for configuring bandpass filter parameters."""

    BINDINGS = [
        ("escape", "back", "Back"),
    ]
    RADIO_SET_FLOW = ["filter-type", "coupling"]
    FIRST_INPUT_ID = "frequency"

    def compose(self) -> ComposeResult:
        yield Static("Band-Pass Filter Design", classes="header")
        with VerticalScroll(classes="content"):
            # Response Type
            with Vertical(classes="form-section"):
                yield Static("Response Type", classes="form-section-title")
                with RadioSet(id="filter-type"):
                    yield RadioButton(
                        "Butterworth - Maximally flat passband",
                        value=True, id="butterworth"
                    )
                    yield RadioButton(
                        "Chebyshev - Sharper cutoff, passband ripple",
                        id="chebyshev"
                    )

            # Coupling
            with Vertical(classes="form-section"):
                yield Static("Coupling Topology", classes="form-section-title")
                with RadioSet(id="coupling"):
                    yield RadioButton(
                        "Top-C (Series) - Better for wider bandwidth",
                        value=True, id="top"
                    )
                    yield RadioButton(
                        "Shunt-C (Parallel) - Better for narrow < 10%",
                        id="shunt"
                    )

            # Frequency Parameters
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

            # Other Parameters
            with Vertical(classes="form-section"):
                yield Static("Parameters", classes="form-section-title")
                yield Static("Impedance (Ω):")
                yield Input(
                    value="50",
                    id="impedance",
                    validators=[Number(minimum=1, maximum=10000)],
                )
                yield Static("Resonators (2-9):")
                yield Input(
                    value="5",
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

            # Buttons
            with Horizontal(classes="button-row"):
                yield Button("Next", id="calculate-btn", variant="primary")
                yield Button("Reset", id="reset-btn")

        yield Footer()

    def on_mount(self) -> None:
        """Focus on filter type selection and hide ripple section initially."""
        self.query_one("#filter-type", RadioSet).focus()
        self.query_one("#ripple-section").display = False

    @on(RadioSet.Changed, "#filter-type")
    def _on_filter_type_changed(self, event: RadioSet.Changed) -> None:
        """Show/hide ripple section based on filter type."""
        ripple_section = self.query_one("#ripple-section")
        ripple_section.display = event.pressed.id == "chebyshev"

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
            self.query_one("#calculate-btn", Button).focus()

    @on(Input.Submitted, "#ripple")
    def _on_ripple_submitted(self, event: Input.Submitted) -> None:
        """Auto-advance to calculate button after ripple entry."""
        self.query_one("#calculate-btn", Button).focus()

    def action_back(self) -> None:
        """Go back to welcome screen."""
        self.app.pop_screen()

    @on(Input.Changed, "#frequency")
    @on(Input.Changed, "#bandwidth")
    def _update_fbw_display(self) -> None:
        """Update fractional bandwidth display when frequency or bandwidth changes."""
        from filter_lib.shared.parsing import parse_frequency

        freq_input = self.query_one("#frequency", Input)
        bw_input = self.query_one("#bandwidth", Input)
        fbw_display = self.query_one("#fbw-display", Static)

        try:
            f0 = parse_frequency(freq_input.value)
            bw = parse_frequency(bw_input.value)
            fbw = (bw / f0) * 100
            if fbw > 40:
                fbw_display.update(f"Fractional BW: {fbw:.2f}% ⚠ Wide bandwidth")
                fbw_display.remove_class("fbw-display")
                fbw_display.add_class("fbw-warning")
            else:
                fbw_display.update(f"Fractional BW: {fbw:.2f}% ✓")
                fbw_display.remove_class("fbw-warning")
                fbw_display.add_class("fbw-display")
        except (ValueError, ZeroDivisionError):
            fbw_display.update("")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle button presses."""
        if event.button.id == "calculate-btn":
            self._calculate()
        elif event.button.id == "reset-btn":
            self._reset_form()

    def _calculate(self) -> None:
        """Validate inputs and proceed to output options."""
        from filter_lib.shared.parsing import parse_frequency

        # Get input widgets
        freq_input = self.query_one("#frequency", Input)
        bw_input = self.query_one("#bandwidth", Input)
        impedance_input = self.query_one("#impedance", Input)
        resonators_input = self.query_one("#resonators", Input)
        ripple_input = self.query_one("#ripple", Input)

        # Validate center frequency (use placeholder as default if empty)
        freq_value = freq_input.value.strip() or freq_input.placeholder
        try:
            f0 = parse_frequency(freq_value)
        except ValueError as e:
            self.notify(f"Invalid center frequency: {e}", severity="error")
            freq_input.focus()
            return

        # Validate bandwidth (use placeholder as default if empty)
        bw_value = bw_input.value.strip() or bw_input.placeholder
        try:
            bw = parse_frequency(bw_value)
        except ValueError as e:
            self.notify(f"Invalid bandwidth: {e}", severity="error")
            bw_input.focus()
            return

        # Validate impedance
        try:
            impedance = float(impedance_input.value)
            if impedance <= 0:
                raise ValueError("must be positive")
        except ValueError as e:
            self.notify(f"Invalid impedance: {e}", severity="error")
            impedance_input.focus()
            return

        # Validate resonators
        try:
            resonators = int(resonators_input.value)
            if not 2 <= resonators <= 9:
                raise ValueError("must be 2-9")
        except ValueError as e:
            self.notify(f"Invalid resonators: {e}", severity="error")
            resonators_input.focus()
            return

        # Get filter type and coupling
        filter_type = get_selected_radio(self, "filter-type")
        coupling = get_selected_radio(self, "coupling")

        # Chebyshev requires odd number of resonators
        if filter_type == "chebyshev" and resonators % 2 == 0:
            self.notify(
                "Chebyshev bandpass requires odd number of resonators",
                severity="warning"
            )
            resonators_input.focus()
            return

        # Get ripple for Chebyshev
        ripple = None
        if filter_type == "chebyshev":
            try:
                ripple = float(ripple_input.value)
                if ripple <= 0:
                    raise ValueError("must be positive")
            except ValueError as e:
                self.notify(f"Invalid ripple: {e}", severity="error")
                ripple_input.focus()
                return

        # Update state
        state: FilterState = self.app.filter_state
        state.category = "bandpass"
        state.filter_type = filter_type
        state.topology = coupling  # top or shunt
        state.frequency_hz = f0
        state.bandwidth_hz = bw
        state.impedance = impedance
        state.order = resonators
        state.ripple_db = ripple if ripple else 0.5

        # Navigate to output options
        from .output_options import OutputOptionsScreen
        self.app.push_screen(OutputOptionsScreen())

    def _reset_form(self) -> None:
        """Reset form to defaults."""
        self.query_one("#frequency", Input).value = ""
        self.query_one("#bandwidth", Input).value = ""
        self.query_one("#impedance", Input).value = "50"
        self.query_one("#resonators", Input).value = "5"
        self.query_one("#ripple", Input).value = "0.5"
        self.query_one("#fbw-display", Static).update("")
        self.query_one("#frequency", Input).focus()
