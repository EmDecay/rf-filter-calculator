"""Results screen displaying calculated filter values."""

import os
from datetime import datetime

from textual.app import ComposeResult
from textual.containers import Container, Horizontal, Vertical, VerticalScroll
from textual.screen import Screen
from textual.widgets import Button, Footer, RadioButton, RadioSet, Static
from textual.worker import Worker

from ..calculation_handler import calculate_and_format
from ..state import FilterState


class ResultsScreen(Screen):
    """Screen displaying calculation results."""

    BINDINGS = [
        ("escape", "back", "Back"),
        ("q", "quit", "Quit"),
    ]

    def __init__(self) -> None:
        super().__init__()
        self._result_text = ""

    def compose(self) -> ComposeResult:
        yield Static("Filter Results", classes="header")
        with Container(classes="content"):
            with VerticalScroll(classes="results-container"):
                yield Static("Calculating...", id="results-text", classes="results-text")

            # Export section (hidden by default)
            with Vertical(id="export-section", classes="form-section"):
                yield Static("Export Format", classes="form-section-title")
                with RadioSet(id="export-format"):
                    yield RadioButton("Text (raw output)", value=True, id="export-txt")
                    yield RadioButton("JSON", id="export-json")
                    yield RadioButton("CSV", id="export-csv")
                with Horizontal(classes="button-row"):
                    yield Button("Save", id="save-btn", variant="primary")
                    yield Button("Cancel", id="cancel-export-btn")

            with Horizontal(classes="button-row"):
                yield Button("Design Another", id="another-btn", variant="primary")
                yield Button("Export", id="export-btn")
                yield Button("Quit", id="quit-btn")

        yield Footer()

    def on_mount(self) -> None:
        """Start calculation when screen mounts."""
        # Hide export section initially
        self.query_one("#export-section").display = False
        # Honour the export format the user picked on the Output Options screen.
        self._preselect_export_format()
        self.run_worker(self._calculate, exclusive=True, thread=True)

    def _preselect_export_format(self) -> None:
        """Pre-select the export-format radio that matches state.export_format.

        Setting ``value=True`` on the target RadioButton prompts the parent
        RadioSet to clear the other buttons automatically via its
        Changed-event handling.
        """
        state: FilterState = self.app.filter_state
        fmt = getattr(state, "export_format", None)
        target_id = {"json": "export-json", "csv": "export-csv"}.get(fmt, "export-txt")
        try:
            radio_set = self.query_one("#export-format", RadioSet)
            for button in radio_set.query(RadioButton):
                button.value = button.id == target_id
        except (AttributeError, LookupError):
            # Widget not mounted yet — safe to skip; default radio value stands.
            pass

    def _calculate(self) -> str:
        """Perform filter calculation and generate output text."""
        state: FilterState = self.app.filter_state
        return calculate_and_format(state)

    def on_worker_state_changed(self, event: Worker.StateChanged) -> None:
        """Handle worker state changes."""
        if event.state.name == "SUCCESS":
            self._result_text = event.worker.result
            self.query_one("#results-text", Static).update(self._result_text)

    def action_back(self) -> None:
        """Go back to output options."""
        self.app.pop_screen()

    def action_quit(self) -> None:
        """Exit the application."""
        self.app.exit()

    def on_key(self, event) -> None:
        """Handle Enter key to advance from export format selection."""
        if event.key == "enter":
            try:
                export_format = self.query_one("#export-format", RadioSet)
                if export_format.has_focus:
                    self._save_export()
                    event.prevent_default()
                    event.stop()
            except (AttributeError, LookupError):
                # Widget not yet mounted during init; safe to ignore
                pass

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle button presses."""
        if event.button.id == "another-btn":
            self._design_another()
        elif event.button.id == "export-btn":
            self._show_export_options()
        elif event.button.id == "save-btn":
            self._save_export()
        elif event.button.id == "cancel-export-btn":
            self._hide_export_options()
        elif event.button.id == "quit-btn":
            self.app.exit()

    def _show_export_options(self) -> None:
        """Show the export format selection."""
        self.query_one("#export-section").display = True
        self.query_one("#export-format", RadioSet).focus()

    def _hide_export_options(self) -> None:
        """Hide the export format selection."""
        self.query_one("#export-section").display = False

    def _save_export(self) -> None:
        """Save the results to a file in selected format."""
        state: FilterState = self.app.filter_state

        # Get selected format
        radio_set = self.query_one("#export-format", RadioSet)
        format_id = radio_set.pressed_button.id if radio_set.pressed_button else "export-txt"

        # Generate filename with timestamp
        timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        category = state.category or "filter"

        if format_id == "export-txt":
            filename = f"{category}-{timestamp}.txt"
            content = self._result_text
        elif format_id == "export-json":
            filename = f"{category}-{timestamp}.json"
            content = self._get_json_export(state)
        else:  # CSV
            filename = f"{category}-{timestamp}.csv"
            content = self._get_csv_export(state)

        # Save to current directory
        filepath = os.path.join(os.getcwd(), filename)
        try:
            with open(filepath, "w") as f:
                f.write(content)
            self.notify(f"Saved to {filename}", severity="information")
        except OSError as e:
            self.notify(f"Error saving: {e}", severity="error")

        self._hide_export_options()

    def _get_json_export(self, state: FilterState) -> str:
        """Get JSON export using existing formatters."""
        eseries = None if state.eseries == "none" else state.eseries

        if state.category == "lowpass":
            from filter_lib.lowpass.display import format_json

            return format_json(state.result, eseries=eseries)
        elif state.category == "highpass":
            from filter_lib.highpass.display import format_json

            return format_json(state.result, eseries=eseries)
        else:  # bandpass
            from filter_lib.bandpass.formatters import format_json

            return format_json(state.result, eseries=eseries)

    def _get_csv_export(self, state: FilterState) -> str:
        """Get CSV export using existing formatters."""
        eseries = None if state.eseries == "none" else state.eseries

        if state.category == "lowpass":
            from filter_lib.lowpass.display import format_csv

            return format_csv(state.result, eseries=eseries)
        elif state.category == "highpass":
            from filter_lib.highpass.display import format_csv

            return format_csv(state.result, eseries=eseries)
        else:  # bandpass
            from filter_lib.bandpass.formatters import format_csv

            return format_csv(state.result, eseries=eseries)

    def _design_another(self) -> None:
        """Start a new design."""
        from .welcome import WelcomeScreen

        self.app.filter_state = FilterState()
        # Pop all screens except the base default screen
        while len(self.app.screen_stack) > 1:
            self.app.pop_screen()
        # Push a fresh WelcomeScreen
        self.app.push_screen(WelcomeScreen())
