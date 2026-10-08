"""Highpass filter input screen."""

from textual import on
from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical, VerticalScroll
from textual.screen import Screen
from textual.types import NoActiveAppError
from textual.validation import Integer
from textual.widgets import Button, Footer, Input, RadioButton, RadioSet, Static

from ...shared.cli_aliases import COMPONENT_COUNT_MESSAGE, chebyshev_odd_count_message
from ..design_field_validation import (
    COUNT_LABELS,
    CUTOFF_LABELS,
    RIPPLE_LABEL,
    RippleValidator,
    parse_ripple_db,
)
from ..filter_screen_navigation_mixin import FilterScreenNavigationMixin
from ..radio_button_helpers import get_selected_radio
from ..state import FilterState


class HighpassScreen(FilterScreenNavigationMixin, Screen):
    """Screen for configuring highpass filter parameters.

    On "Next" it validates the form, writes the shared FilterState, and
    pushes the output-options screen. Kept deliberately parallel to
    LowpassScreen — changes here usually belong there too.
    """

    BINDINGS = [
        ("escape", "back", "Back"),
    ]
    # Enter moves through the form in the web form's order; ripple shows for Chebyshev.
    FOCUS_FLOW = (
        "filter-type",
        "topology",
        "ripple",
        "frequency",
        "order",
        "impedance",
        "next-btn",
    )

    def compose(self) -> ComposeResult:
        yield Static("High-Pass Filter Design", classes="header")
        yield Static("Enter: next · ↑/↓: choose · Esc: back", classes="nav-hint")
        with VerticalScroll(classes="content"):
            with Vertical(classes="form-section"):
                yield Static("Response and topology", classes="form-section-title")
                yield Static("Response", classes="field-label")
                with RadioSet(id="filter-type"):
                    yield RadioButton(
                        "Butterworth - Maximally flat passband", value=True, id="butterworth"
                    )
                    yield RadioButton("Chebyshev - Sharper cutoff, passband ripple", id="chebyshev")
                    yield RadioButton(
                        "Bessel - Gentle cutoff; the high-pass form does not keep flat group delay",
                        id="bessel",
                    )
                # Pi is listed first, as on the web, but T is the default here (low-pass
                # defaults to Pi): for the same order, the high-pass T needs fewer
                # inductors than the shunt-L Pi, which is the usual builder's preference.
                yield Static("Topology", classes="field-label")
                with RadioSet(id="topology"):
                    yield RadioButton("Pi (shunt first) - L, then alternating C/L", id="pi")
                    yield RadioButton(
                        "T (series first) - C, then alternating L/C",
                        value=True,
                        id="t",
                    )
                with Vertical(id="ripple-section"):
                    yield Static(RIPPLE_LABEL)
                    yield Input(
                        value="0.5",
                        id="ripple",
                        validators=[RippleValidator()],
                    )

            with Vertical(classes="form-section"):
                yield Static("Frequency and size", classes="form-section-title")
                yield Static(CUTOFF_LABELS[False], id="frequency-label")
                yield Input(
                    placeholder="10MHz",
                    id="frequency",
                )
                yield Static(COUNT_LABELS[False], id="order-label")
                yield Input(
                    value="3",
                    id="order",
                    validators=[Integer(minimum=2, maximum=9)],
                )
                yield Static("Impedance, equal source and load (e.g. 50, 50ohm, 1k):")
                yield Input(
                    value="50",
                    placeholder="50 or 50ohm",
                    id="impedance",
                )

            with Horizontal(classes="button-row"):
                yield Button("Next", id="next-btn", variant="primary")
                yield Button("Reset", id="reset-btn")

        yield Footer()

    def on_mount(self) -> None:
        """Focus on filter type selection and hide ripple section initially."""
        self.query_one("#filter-type", RadioSet).focus()
        self.query_one("#ripple-section").display = False

    def _is_shown(self, widget_id: str) -> bool:
        """The ripple field takes focus only while Chebyshev shows it."""
        if widget_id == "ripple":
            return bool(self.query_one("#ripple-section").display)
        return True

    @on(RadioSet.Changed, "#filter-type")
    def _on_filter_type_changed(self, event: RadioSet.Changed) -> None:
        """Show/hide ripple section and odd-order hint based on filter type."""
        self._invalidate_previous_result()
        is_chebyshev = event.pressed.id == "chebyshev"
        self.query_one("#ripple-section").display = is_chebyshev
        self.query_one("#order-label", Static).update(COUNT_LABELS[is_chebyshev])
        self.query_one("#frequency-label", Static).update(CUTOFF_LABELS[is_chebyshev])

    @on(Input.Changed, "#frequency")
    @on(Input.Changed, "#impedance")
    @on(Input.Changed, "#order")
    @on(Input.Changed, "#ripple")
    def _on_design_input_changed(self, event: Input.Changed) -> None:
        """Invalidate prior output as soon as a design value changes."""
        self._invalidate_previous_result()

    @on(RadioSet.Changed, "#topology")
    def _on_topology_changed(self, event: RadioSet.Changed) -> None:
        """Invalidate prior output when the ladder orientation changes."""
        self._invalidate_previous_result()

    def _invalidate_previous_result(self) -> None:
        """Clear stale output when mounted; tolerate calls on an unmounted screen."""
        try:
            state = self.app.filter_state
        except NoActiveAppError:
            return
        if isinstance(state, FilterState):
            state.invalidate_calculation()

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
        """Validate inputs and proceed to output options.

        Re-checks ranges the Input validators already cover: validators only
        style the field red — they don't block the Next button. On any
        failure, notify and refocus the offending field instead of advancing.
        """
        from filter_lib.shared.parsing import parse_frequency, parse_impedance

        freq_input = self.query_one("#frequency", Input)
        impedance_input = self.query_one("#impedance", Input)
        order_input = self.query_one("#order", Input)
        ripple_input = self.query_one("#ripple", Input)

        # Empty frequency falls back to the placeholder so a user can
        # Enter straight through the suggested defaults.
        freq_value = freq_input.value.strip() or freq_input.placeholder
        try:
            freq_hz = parse_frequency(freq_value, label="Cutoff frequency")
        except ValueError as e:
            self.notify(str(e), severity="error")
            freq_input.focus()
            return

        # Validate impedance (same suffixed forms as the CLI: 50, 50ohm, 1k)
        try:
            impedance = parse_impedance(impedance_input.value.strip() or "50")
        except ValueError as e:
            self.notify(str(e), severity="error")
            impedance_input.focus()
            return

        try:
            order = int(order_input.value)
        except ValueError:
            order = 0
        if not 2 <= order <= 9:
            self.notify(COMPONENT_COUNT_MESSAGE, severity="error")
            order_input.focus()
            return

        filter_type = get_selected_radio(self, "filter-type")
        topology = get_selected_radio(self, "topology")

        # Chebyshev LP/HP requires odd order for equal source/load terminations
        if filter_type == "chebyshev" and order % 2 == 0:
            self.notify(chebyshev_odd_count_message("components"), severity="warning")
            order_input.focus()
            return

        # Ripple applies to Chebyshev only. CLI, wizard and public synthesis all
        # require 0 < ripple <= 3.0 dB; the ripple field's validator applies the same rule.
        ripple = None
        if filter_type == "chebyshev":
            try:
                ripple = parse_ripple_db(ripple_input.value)
            except ValueError as e:
                self.notify(str(e), severity="error")
                ripple_input.focus()
                return

        state: FilterState = self.app.filter_state
        state.invalidate_calculation()
        state.category = "highpass"
        state.filter_type = filter_type
        state.topology = topology
        state.frequency_hz = freq_hz
        state.impedance = impedance
        state.order = order
        # Non-Chebyshev paths never read ripple_db; storing the default keeps
        # a stale value from an earlier Chebyshev pass from lingering.
        state.ripple_db = ripple if ripple else 0.5

        from .output_options import OutputOptionsScreen

        self.app.push_screen(OutputOptionsScreen())

    def _reset_form(self) -> None:
        """Reset form to defaults."""
        self.query_one("#frequency", Input).value = ""
        self.query_one("#impedance", Input).value = "50"
        self.query_one("#order", Input).value = "3"
        self.query_one("#ripple", Input).value = "0.5"
        self.query_one("#frequency", Input).focus()
