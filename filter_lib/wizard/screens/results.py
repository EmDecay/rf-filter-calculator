"""Results screen displaying calculated filter values."""

from functools import partial

from textual.app import ComposeResult
from textual.containers import Container, Horizontal, Vertical, VerticalScroll
from textual.screen import Screen
from textual.widgets import Button, Footer, RadioButton, RadioSet, Static
from textual.worker import Worker

from ..calculation_handler import calculate_and_format
from ..export_formatting import (
    format_component_csv,
    format_component_json,
    format_response_export,
    prepare_export_payloads,
)
from ..state import CalculationOutcome, FilterState


class ResultsScreen(Screen):
    """Final wizard screen with background calculation and guarded export."""

    BINDINGS = [
        ("escape", "back", "Back"),
        ("q", "quit", "Quit"),
    ]

    def __init__(self) -> None:
        super().__init__()
        self._result_text = ""
        self._active_worker: Worker | None = None
        self._calculation_revision: int | None = None
        self._accept_worker_events = False

    def compose(self) -> ComposeResult:
        yield Static("Filter Results", classes="header")
        yield Static("Enter: select · ↑/↓: choose · Esc: back · Q: quit", classes="nav-hint")
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
                yield Button("Export", id="export-btn", disabled=True)
                yield Button("Quit", id="quit-btn")

        yield Footer()

    def on_mount(self) -> None:
        """Start calculation when screen mounts."""
        # Export UI is opt-in via the Export button.
        self.query_one("#export-section").display = False
        self._preselect_export_format()
        state: FilterState = self.app.filter_state
        # Clear old output before the worker is scheduled. This prevents an
        # earlier success from remaining exportable during a recalculation.
        self._calculation_revision = state.begin_calculation()
        snapshot = state.calculation_copy()
        self._result_text = ""
        self._accept_worker_events = True
        self.query_one("#export-btn", Button).disabled = True
        # thread=True keeps the event loop free (bandpass runs a netlist
        # sweep, which is not instant); exclusive=True guards against a
        # remount stacking a second calculation.
        self._active_worker = self.run_worker(
            partial(self._calculate, snapshot),
            exclusive=True,
            thread=True,
        )

    def on_unmount(self) -> None:
        """Cancel the worker and prevent late events from publishing output."""
        self._accept_worker_events = False
        if self._active_worker is not None:
            self._active_worker.cancel()
        if self._calculation_revision is not None:
            self.app.filter_state.cancel_calculation(self._calculation_revision)

    def _preselect_export_format(self) -> None:
        """Pre-select the valid component export format for the current result."""
        state: FilterState = self.app.filter_state
        build_enabled = state.build_analysis_enabled or state.build_analysis is not None
        target_id = {"json": "export-json", "csv": "export-csv"}.get(
            state.output_format, "export-txt"
        )
        if build_enabled and target_id == "export-csv":
            target_id = "export-txt"
        try:
            radio_set = self.query_one("#export-format", RadioSet)
            for button in radio_set.query(RadioButton):
                button.disabled = build_enabled and button.id == "export-csv"
                button.value = button.id == target_id
        except (AttributeError, LookupError):
            # Widget not mounted yet — safe to skip; default radio value stands.
            pass

    def _calculate(self, snapshot: FilterState) -> CalculationOutcome:
        """Perform filter calculation using only the captured state snapshot."""
        return calculate_and_format(snapshot)

    def _is_current_worker_event(self, event: Worker.StateChanged) -> bool:
        """Return whether an event still belongs to this mounted revision."""
        state: FilterState = self.app.filter_state
        return (
            self._accept_worker_events
            and event.worker is self._active_worker
            and self._calculation_revision is not None
            and state.calculation_revision == self._calculation_revision
            and state.calculation_status == "pending"
        )

    def _show_calculation_error(self, message: str) -> None:
        """Publish and render a calculation error for the current revision."""
        if self._calculation_revision is None:
            return
        state: FilterState = self.app.filter_state
        if not state.publish_error(self._calculation_revision, message):
            return
        self._result_text = ""
        self.query_one("#export-btn", Button).disabled = True
        self.query_one("#results-text", Static).update(
            f"Calculation failed: {message}\n\nPress Esc to go back."
        )

    def on_worker_state_changed(self, event: Worker.StateChanged) -> None:
        """Handle worker state changes."""
        if not self._is_current_worker_event(event):
            return

        if event.state.name == "SUCCESS":
            outcome = event.worker.result
            if not isinstance(outcome, CalculationOutcome):
                self._show_calculation_error("Calculation returned an invalid outcome")
                return
            if not outcome.succeeded:
                self._show_calculation_error(outcome.error or "Calculation returned no result")
                return

            state: FilterState = self.app.filter_state
            if state.build_analysis_enabled and outcome.build_analysis is None:
                self._show_calculation_error("Calculation returned no realized-build analysis")
                return
            if not state.publish_success(
                self._calculation_revision,
                outcome.output_text,
                outcome.result,
                outcome.build_analysis,
            ):
                return
            self._result_text = state.output_text
            self.query_one("#results-text", Static).update(self._result_text)
            self.query_one("#export-btn", Button).disabled = False
        elif event.state.name == "ERROR":
            error = event.worker.error
            self._show_calculation_error(str(error).strip() or type(error).__name__)

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
        if not self._guard_current_result():
            return
        self.query_one("#export-section").display = True
        self.query_one("#export-format", RadioSet).focus()

    def _hide_export_options(self) -> None:
        """Hide the export format selection."""
        self.query_one("#export-section").display = False

    def _save_export(self) -> None:
        """Save the results file, plus a response-data file when selected.

        The component file format comes from this screen's radio selection;
        a second ``…-response.{ext}`` file is written when the user picked a
        plot-data export format on the Output Options screen.
        """
        state: FilterState = self.app.filter_state
        if not self._guard_current_result(state):
            self._hide_export_options()
            return

        radio_set = self.query_one("#export-format", RadioSet)
        format_id = radio_set.pressed_button.id if radio_set.pressed_button else "export-txt"

        # Generate every requested payload before opening any file. A stale or
        # malformed result therefore cannot leave a partial/error-text export.
        try:
            files = prepare_export_payloads(state, format_id)
        except (KeyError, TypeError, ValueError) as e:
            self.notify(f"Cannot export current result: {e}", severity="error")
            self._hide_export_options()
            return

        saved: list[str] = []
        for filepath, file_content in files:
            try:
                with open(filepath, "w", encoding="utf-8", newline="") as f:
                    f.write(file_content)
                saved.append(filepath)
            except OSError as e:
                self.notify(f"Error saving {filepath}: {e}", severity="error")

        if saved:
            self.notify(f"Saved to {' and '.join(saved)}", severity="information")

        self._hide_export_options()

    def _has_current_result(self, state: FilterState | None = None) -> bool:
        """Return whether the rendered text and state are the same success."""
        current = state or self.app.filter_state
        return current.is_exportable and self._result_text == current.output_text

    def _guard_current_result(self, state: FilterState | None = None) -> bool:
        """Notify and reject missing, failed, pending, or stale output."""
        if self._has_current_result(state):
            return True
        self.notify("No current successful calculation is available to export", severity="warning")
        return False

    def _require_current_result(self, state: FilterState) -> None:
        """Raise when a formatter is called without the current success."""
        if not self._has_current_result(state):
            raise ValueError("no current successful calculation")

    def _get_response_export(self, state: FilterState, fmt: str) -> str:
        """Generate frequency-response data in the unified export schema."""
        self._require_current_result(state)
        return format_response_export(state, fmt)

    def _get_json_export(self, state: FilterState) -> str:
        """Get JSON export using existing formatters."""
        self._require_current_result(state)
        return format_component_json(state)

    def _get_csv_export(self, state: FilterState) -> str:
        """Get CSV export using existing formatters."""
        self._require_current_result(state)
        return format_component_csv(state)

    def _design_another(self) -> None:
        """Start a new design."""
        from .welcome import WelcomeScreen

        # Replace (not mutate) the state so every field returns to its
        # dataclass default — nothing from the previous design can leak.
        self.app.filter_state = FilterState()
        # Unwind to the base default screen, then push a fresh WelcomeScreen:
        # rebuilding from scratch guarantees no stale widget state on the
        # old screens.
        while len(self.app.screen_stack) > 1:
            self.app.pop_screen()
        self.app.push_screen(WelcomeScreen())
