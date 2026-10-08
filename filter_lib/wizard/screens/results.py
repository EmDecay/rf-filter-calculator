"""Results screen displaying calculated filter values."""

from functools import partial

from textual.app import ComposeResult
from textual.containers import Container, Horizontal, Vertical, VerticalScroll
from textual.screen import Screen
from textual.widgets import Button, Footer, RadioButton, RadioSet, Static
from textual.worker import Worker, get_current_worker

from ..calculation_handler import calculate_and_format
from ..export_formatting import export_folder, prepare_export_payloads
from ..radio_button_helpers import EnabledRadioSet
from ..state import (
    CSV_DOCUMENT,
    INTERNAL_NO_BUILD_MESSAGE,
    INTERNAL_NO_RESULT_MESSAGE,
    CalculationOutcome,
    FilterState,
)

NOTHING_TO_EXPORT_MESSAGE = (
    "Nothing to export yet. Wait for the result, or fix the error and try again."
)
EXPORT_FOLDER_FALLBACK = "Files are saved in the current folder."
# A saved JSON that uses a build or resonator Q the result shown did not is calculated
# on Save, in the background; these are the notices around that.
PREPARING_JSON_MESSAGE = "Preparing the JSON file…"
JSON_NOT_SAVED_PREFIX = "JSON file not saved: "


def export_folder_text() -> str:
    """Name the folder exports go to, without letting a lookup failure hide the results.

    The folder lookup fails when the working folder was deleted after the wizard
    started; the results must still display, so fall back to a generic line.
    """
    try:
        return f"Files are saved in: {export_folder()}"
    except ValueError:
        return EXPORT_FOLDER_FALLBACK


def save_failure_message(filepath: str, error: OSError) -> str:
    """Describe a failed write in plain words, without Python's ``[Errno N]`` prefix."""
    reason = error.strerror or str(error) or "the file could not be written"
    return f"Could not save {filepath}: {reason}. Check that the folder exists and is writable."


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
        # The background calculation of a saved JSON's own design (see _save_export).
        self._json_worker: Worker | None = None
        self._json_revision: int | None = None

    def compose(self) -> ComposeResult:
        yield Static("Results", classes="header")
        yield Static("Enter: select · ↑/↓: choose · Esc: back · Q: quit", classes="nav-hint")
        with Container(classes="content"):
            with VerticalScroll(classes="results-container"):
                yield Static("Calculating...", id="results-text", classes="results-text")

            # Export section (hidden by default)
            with Vertical(id="export-section", classes="form-section"):
                yield Static("Save as", classes="form-section-title")
                with EnabledRadioSet(id="export-format"):
                    yield RadioButton("Text (as shown)", value=True, id="export-txt")
                    yield RadioButton("JSON (full design)", id="export-json")
                    yield RadioButton("CSV (components)", id="export-csv")
                # Why CSV is disabled for this result (the build simulation or resonator Q).
                yield Static("", id="export-csv-reason", classes="option-reason")
                yield Static(export_folder_text(), id="export-folder")
                with Horizontal(classes="button-row"):
                    yield Button("Save", id="save-btn", variant="primary")
                    yield Button("Cancel", id="cancel-export-btn")

            with Horizontal(classes="button-row"):
                yield Button("Design another", id="another-btn", variant="primary")
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
        # remount stacking a second calculation. exit_on_error=False keeps an
        # unexpected worker exception on this screen as a rendered failure
        # (the ERROR branch below) instead of exiting the whole app.
        self._active_worker = self.run_worker(
            partial(self._calculate, snapshot),
            exclusive=True,
            thread=True,
            exit_on_error=False,
        )

    def on_unmount(self) -> None:
        """Cancel the worker and prevent late events from publishing output.

        Cancelling also sets the flag the worker thread polls, so the thread stops
        rather than finishing a long analysis after its screen is gone.
        """
        self._accept_worker_events = False
        for worker in (self._active_worker, self._json_worker):
            if worker is not None:
                worker.cancel()
        if self._calculation_revision is not None:
            self.app.filter_state.cancel_calculation(self._calculation_revision)

    def _preselect_export_format(self) -> None:
        """Pre-select the result's own format and disable CSV, with why, when it cannot apply."""
        state: FilterState = self.app.filter_state
        csv_refusal = state.document_refusal(CSV_DOCUMENT)
        target_id = {"json": "export-json", "csv": "export-csv"}.get(
            state.shown_format, "export-txt"
        )
        if csv_refusal and target_id == "export-csv":
            target_id = "export-txt"
        try:
            radio_set = self.query_one("#export-format", RadioSet)
            for button in radio_set.query(RadioButton):
                button.disabled = bool(csv_refusal) and button.id == "export-csv"
                button.value = button.id == target_id
            reason = self.query_one("#export-csv-reason", Static)
            reason.update(csv_refusal or "")
            reason.display = bool(csv_refusal)
        except (AttributeError, LookupError):
            # Widget not mounted yet — safe to skip; default radio value stands.
            pass

    def _calculate(self, snapshot: FilterState) -> CalculationOutcome:
        """Perform filter calculation using only the captured state snapshot.

        Runs in the worker thread. Textual cannot interrupt a thread, so the
        calculation polls this worker's cancellation flag, which is set when the
        screen unmounts (Esc, Design another) or the app exits; a long build
        simulation then stops within one circuit measurement.
        """
        worker = get_current_worker()
        return calculate_and_format(snapshot, should_cancel=lambda: worker.is_cancelled)

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
        if event.worker is self._json_worker and event.worker is not None:
            self._on_json_worker_changed(event)
            return
        if not self._is_current_worker_event(event):
            return

        if event.state.name == "SUCCESS":
            outcome = event.worker.result
            if not isinstance(outcome, CalculationOutcome):
                self._show_calculation_error(INTERNAL_NO_RESULT_MESSAGE)
                return
            if not outcome.succeeded:
                self._show_calculation_error(outcome.error or INTERNAL_NO_RESULT_MESSAGE)
                return

            state: FilterState = self.app.filter_state
            if state.runs_build and outcome.build_analysis is None:
                self._show_calculation_error(INTERNAL_NO_BUILD_MESSAGE)
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
        plot-data export format on the Output Options screen. A JSON file that uses a
        build or resonator Q the result shown did not is calculated first, in the
        background, as the web does when its JSON is downloaded.
        """
        state: FilterState = self.app.filter_state
        if not self._guard_current_result(state):
            self._hide_export_options()
            return

        radio_set = self.query_one("#export-format", RadioSet)
        format_id = radio_set.pressed_button.id if radio_set.pressed_button else "export-txt"
        own_design = state.json_needs_own_design() and state.json_design is None
        if format_id == "export-json" and own_design:
            self._prepare_json_then_save(state)
            return
        self._write_export(state, format_id)

    def _write_export(
        self, state: FilterState, format_id: str, *, include_component: bool = True
    ) -> None:
        """Format the requested files, then write each one and say which were saved."""
        # Generate every requested payload before opening any file. A stale or
        # malformed result therefore cannot leave a partial/error-text export.
        try:
            files = prepare_export_payloads(state, format_id, include_component=include_component)
        except (KeyError, TypeError, ValueError) as e:
            self.notify(f"Cannot export: {e}", severity="error")
            self._hide_export_options()
            return

        saved: list[str] = []
        for filepath, file_content in files:
            try:
                with open(filepath, "w", encoding="utf-8", newline="") as f:
                    f.write(file_content)
                saved.append(filepath)
            except OSError as e:
                self.notify(save_failure_message(filepath, e), severity="error")

        if saved:
            self.notify(f"Saved to {' and '.join(saved)}", severity="information")

        self._hide_export_options()

    # -- A saved JSON with its own design ---------------------------------------------

    def _prepare_json_then_save(self, state: FilterState) -> None:
        """Calculate the saved JSON's own design in a worker, then save the files."""
        if self._json_worker is not None and self._json_worker.is_running:
            self.notify(PREPARING_JSON_MESSAGE)
            return
        self._hide_export_options()
        try:
            # Cheap: builds and checks the request; the design itself runs in the worker.
            request = state.json_design_request()
        except ValueError as error:
            self._json_not_saved(state, str(error))
            return
        self.notify(PREPARING_JSON_MESSAGE)
        self._json_revision = state.calculation_revision
        # Its own group, so it never cancels (or is cancelled by) the result's worker.
        self._json_worker = self.run_worker(
            partial(self._calculate_json_design, request),
            group="json-design",
            thread=True,
            exit_on_error=False,
        )

    def _calculate_json_design(self, request):
        """Run in the worker thread; stops when the screen goes away (see on_unmount)."""
        from filter_lib.design import design

        worker = get_current_worker()
        return design(request, should_cancel=lambda: worker.is_cancelled)

    def _on_json_worker_changed(self, event: Worker.StateChanged) -> None:
        """Save the JSON once its design is ready, or say why it was not saved."""
        if not self._accept_worker_events:
            return
        if event.state.name not in ("SUCCESS", "ERROR"):
            return
        state: FilterState = self.app.filter_state
        # The files belong to the result the Save was for; nothing else is written.
        if state.calculation_revision != self._json_revision:
            return
        if not self._guard_current_result(state):
            return
        if event.state.name == "SUCCESS":
            state.json_design = event.worker.result
            self._write_export(state, "export-json")
        else:
            error = event.worker.error
            self._json_not_saved(state, str(error).strip() or type(error).__name__)

    def _json_not_saved(self, state: FilterState, message: str) -> None:
        """Report why the JSON was not saved; the response data file is still saved."""
        self.notify(f"{JSON_NOT_SAVED_PREFIX}{message}", severity="error")
        if state.export_format in ("json", "csv"):
            self._write_export(state, "export-json", include_component=False)

    def _has_current_result(self, state: FilterState | None = None) -> bool:
        """Return whether the rendered text and state are the same success."""
        current = state or self.app.filter_state
        return current.is_exportable and self._result_text == current.output_text

    def _guard_current_result(self, state: FilterState | None = None) -> bool:
        """Notify and reject missing, failed, pending, or stale output."""
        if self._has_current_result(state):
            return True
        self.notify(NOTHING_TO_EXPORT_MESSAGE, severity="warning")
        return False

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
