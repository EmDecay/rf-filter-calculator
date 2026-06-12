"""Lowpass filter input screen."""

from textual import on
from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical, VerticalScroll
from textual.screen import Screen
from textual.validation import Number
from textual.widgets import Button, Footer, Input, RadioButton, RadioSet, Static

from ..filter_screen_navigation_mixin import FilterScreenNavigationMixin
from ..radio_button_helpers import get_selected_radio
from ..state import FilterState


class LowpassScreen(FilterScreenNavigationMixin, Screen):
    """Screen for configuring lowpass filter parameters."""

    BINDINGS = [
        ("escape", "back", "Back"),
    ]
    RADIO_SET_FLOW = ["filter-type", "topology"]
    FIRST_INPUT_ID = "frequency"

    def compose(self) -> ComposeResult:
        yield Static("Low-Pass Filter Design", classes="header")
        yield Static("Enter: next · ↑/↓: choose · Esc: back", classes="nav-hint")
        with VerticalScroll(classes="content"):
            with Vertical(classes="form-section"):
                yield Static("Response Type", classes="form-section-title")
                with RadioSet(id="filter-type"):
                    yield RadioButton(
                        "Butterworth - Maximally flat passband", value=True, id="butterworth"
                    )
                    yield RadioButton("Chebyshev - Sharper cutoff, passband ripple", id="chebyshev")
                    yield RadioButton("Bessel - Best transient response", id="bessel")

            with Vertical(classes="form-section"):
                yield Static("Topology", classes="form-section-title")
                with RadioSet(id="topology"):
                    yield RadioButton("Pi (C-L-C) - Shunt C first", value=True, id="pi")
                    yield RadioButton("T (L-C-L) - Series L first", id="t")

            with Vertical(classes="form-section"):
                yield Static("Parameters", classes="form-section-title")
                yield Static("Cutoff Frequency (e.g., 10MHz, 14.2M, 7100kHz):")
                yield Input(
                    placeholder="10MHz",
                    id="frequency",
                )
                yield Static("Impedance (e.g., 50, 50ohm, 1k):")
                yield Input(
                    value="50",
                    placeholder="50 or 50ohm",
                    id="impedance",
                )
                yield Static("Order (2-9 components):", id="order-label")
                yield Input(
                    value="3",
                    id="order",
                    validators=[Number(minimum=2, maximum=9)],
                )
                with Vertical(id="ripple-section"):
                    yield Static("Ripple (dB):")
                    yield Input(
                        value="0.5",
                        id="ripple",
                        validators=[Number(minimum=0.01, maximum=3.0)],
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
        """Show/hide ripple section and odd-order hint based on filter type."""
        is_chebyshev = event.pressed.id == "chebyshev"
        self.query_one("#ripple-section").display = is_chebyshev
        order_label = self.query_one("#order-label", Static)
        if is_chebyshev:
            order_label.update("Order (Chebyshev: odd only — 3, 5, 7, 9):")
        else:
            order_label.update("Order (2-9 components):")

    @on(Input.Submitted, "#frequency")
    def _on_frequency_submitted(self, event: Input.Submitted) -> None:
        """Auto-advance to impedance input after frequency entry."""
        self.query_one("#impedance", Input).focus()

    @on(Input.Submitted, "#impedance")
    def _on_impedance_submitted(self, event: Input.Submitted) -> None:
        """Auto-advance to order input after impedance entry."""
        self.query_one("#order", Input).focus()

    @on(Input.Submitted, "#order")
    def _on_order_submitted(self, event: Input.Submitted) -> None:
        """Auto-advance to ripple or button after order entry."""
        if self.query_one("#ripple-section").display:
            self.query_one("#ripple", Input).focus()
        else:
            self.query_one("#next-btn", Button).focus()

    @on(Input.Submitted, "#ripple")
    def _on_ripple_submitted(self, event: Input.Submitted) -> None:
        """Auto-advance to calculate button after ripple entry."""
        self.query_one("#next-btn", Button).focus()

    def action_back(self) -> None:
        """Go back to welcome screen."""
        self.app.pop_screen()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle button presses."""
        if event.button.id == "next-btn":
            self._validate_and_continue()
        elif event.button.id == "reset-btn":
            self._reset_form()

    def _validate_and_continue(self) -> None:
        """Validate inputs and proceed to output options."""
        from filter_lib.shared.parsing import parse_frequency, parse_impedance

        # Get values
        freq_input = self.query_one("#frequency", Input)
        impedance_input = self.query_one("#impedance", Input)
        order_input = self.query_one("#order", Input)
        ripple_input = self.query_one("#ripple", Input)

        # Validate frequency (use placeholder as default if empty)
        freq_value = freq_input.value.strip() or freq_input.placeholder
        try:
            freq_hz = parse_frequency(freq_value)
        except ValueError as e:
            self.notify(f"Invalid frequency: {e}", severity="error")
            freq_input.focus()
            return

        # Validate impedance (same suffixed forms as the CLI: 50, 50ohm, 1k)
        try:
            impedance = parse_impedance(impedance_input.value.strip() or "50")
        except ValueError as e:
            self.notify(f"Invalid impedance: {e}", severity="error")
            impedance_input.focus()
            return

        # Validate order
        try:
            order = int(order_input.value)
            if not 2 <= order <= 9:
                raise ValueError("must be 2-9")
        except ValueError as e:
            self.notify(f"Invalid order: {e}", severity="error")
            order_input.focus()
            return

        # Get filter type and topology
        filter_type = get_selected_radio(self, "filter-type")
        topology = get_selected_radio(self, "topology")

        # Chebyshev LP/HP requires odd order for equal source/load terminations
        if filter_type == "chebyshev" and order % 2 == 0:
            self.notify(
                "Chebyshev lowpass requires odd order (3, 5, 7, or 9)",
                severity="warning",
            )
            order_input.focus()
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
        state.category = "lowpass"
        state.filter_type = filter_type
        state.topology = topology
        state.frequency_hz = freq_hz
        state.impedance = impedance
        state.order = order
        state.ripple_db = ripple if ripple else 0.5

        # Navigate to output options
        from .output_options import OutputOptionsScreen

        self.app.push_screen(OutputOptionsScreen())

    def _reset_form(self) -> None:
        """Reset form to defaults."""
        self.query_one("#frequency", Input).value = ""
        self.query_one("#impedance", Input).value = "50"
        self.query_one("#order", Input).value = "3"
        self.query_one("#ripple", Input).value = "0.5"
        self.query_one("#frequency", Input).focus()
