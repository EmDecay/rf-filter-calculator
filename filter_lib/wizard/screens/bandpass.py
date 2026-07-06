"""Bandpass filter input screen."""

import math

from textual import on
from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical, VerticalScroll
from textual.screen import Screen
from textual.validation import Number
from textual.widgets import Button, Footer, Input, RadioButton, RadioSet, Static

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
                    yield RadioButton("Bessel - Best transient response", id="bessel")

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

    def action_back(self) -> None:
        """Go back to welcome screen."""
        self.app.pop_screen()

    @on(Input.Changed, "#frequency")
    @on(Input.Changed, "#bandwidth")
    def _update_fbw_display(self) -> None:
        """Update fractional bandwidth display when frequency or bandwidth changes.

        Live feedback so the user sees an over-wide design before committing;
        the synthesis itself warns again above the simulation-proven FBW.
        """
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
            # Half-typed values are normal while editing — blank the readout
            # rather than flashing errors on every keystroke.
            fbw_display.update("")

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
        from filter_lib.shared.parsing import parse_frequency, parse_impedance

        freq_input = self.query_one("#frequency", Input)
        bw_input = self.query_one("#bandwidth", Input)
        impedance_input = self.query_one("#impedance", Input)
        resonators_input = self.query_one("#resonators", Input)
        ripple_input = self.query_one("#ripple", Input)

        # Empty frequency/bandwidth fall back to their placeholders so a user
        # can Enter straight through the suggested defaults.
        freq_value = freq_input.value.strip() or freq_input.placeholder
        try:
            f0 = parse_frequency(freq_value)
        except ValueError as e:
            self.notify(f"Invalid center frequency: {e}", severity="error")
            freq_input.focus()
            return

        bw_value = bw_input.value.strip() or bw_input.placeholder
        try:
            bw = parse_frequency(bw_value)
        except ValueError as e:
            self.notify(f"Invalid bandwidth: {e}", severity="error")
            bw_input.focus()
            return

        # Validate impedance (same suffixed forms as the CLI: 50, 50ohm, 1k)
        try:
            impedance = parse_impedance(impedance_input.value.strip() or "50")
        except ValueError as e:
            self.notify(f"Invalid impedance: {e}", severity="error")
            impedance_input.focus()
            return

        try:
            resonators = int(resonators_input.value)
            if not 2 <= resonators <= 9:
                raise ValueError("must be 2-9")
        except ValueError as e:
            self.notify(f"Invalid resonators: {e}", severity="error")
            resonators_input.focus()
            return

        filter_type = get_selected_radio(self, "filter-type")
        coupling = get_selected_radio(self, "coupling")

        # Chebyshev requires an odd resonator count for equal source/load
        # terminations (same constraint as the LP/HP odd-order rule).
        if filter_type == "chebyshev" and resonators % 2 == 0:
            self.notify("Chebyshev bandpass requires odd number of resonators", severity="warning")
            resonators_input.focus()
            return

        # Ripple applies to Chebyshev only; the 3.0 dB cap matches the
        # bandpass CLI's validation.
        ripple = None
        if filter_type == "chebyshev":
            try:
                ripple = float(ripple_input.value)
                if not math.isfinite(ripple):
                    raise ValueError("must be finite")
                if ripple <= 0:
                    raise ValueError("must be positive")
                if ripple > 3.0:
                    raise ValueError("must be <= 3.0 dB")
            except ValueError as e:
                self.notify(f"Invalid ripple: {e}", severity="error")
                ripple_input.focus()
                return

        state: FilterState = self.app.filter_state
        state.category = "bandpass"
        state.filter_type = filter_type
        # FilterState reuses the topology field for the bandpass coupling id
        # ("top"); order likewise carries the resonator count.
        state.topology = coupling
        state.frequency_hz = f0
        state.bandwidth_hz = bw
        state.impedance = impedance
        state.order = resonators
        # Non-Chebyshev paths never read ripple_db; storing the default keeps
        # a stale value from an earlier Chebyshev pass from lingering.
        state.ripple_db = ripple if ripple else 0.5

        from .output_options import OutputOptionsScreen

        self.app.push_screen(OutputOptionsScreen())

    def _reset_form(self) -> None:
        """Reset form to defaults."""
        self.query_one("#frequency", Input).value = ""
        self.query_one("#bandwidth", Input).value = ""
        self.query_one("#impedance", Input).value = "50"
        self.query_one("#resonators", Input).value = "3"
        self.query_one("#ripple", Input).value = "0.5"
        self.query_one("#fbw-display", Static).update("")
        self.query_one("#frequency", Input).focus()
