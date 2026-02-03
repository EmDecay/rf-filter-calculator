"""Output options screen for configuring display format."""
from textual.app import ComposeResult
from textual.screen import Screen
from textual.widgets import Button, Footer, Static, RadioSet, RadioButton, SelectionList
from textual.widgets.selection_list import Selection
from textual.containers import VerticalScroll, Vertical, Horizontal
from textual import on

from ..state import FilterState


class OutputOptionsScreen(Screen):
    """Screen for selecting output format options."""

    BINDINGS = [
        ("escape", "back", "Back"),
    ]

    def compose(self) -> ComposeResult:
        yield Static("Output Options", classes="header")
        with VerticalScroll(classes="content"):
            # E-Series Selection
            with Vertical(classes="form-section"):
                yield Static("Component Matching", classes="form-section-title")
                with RadioSet(id="eseries"):
                    yield RadioButton(
                        "E24 - Standard tolerance (default)",
                        value=True, id="E24"
                    )
                    yield RadioButton("E12 - Fewer values, looser tolerance", id="E12")
                    yield RadioButton("E96 - More values, tighter tolerance", id="E96")
                    yield RadioButton("None - Calculated values only", id="none")

            # Output Format
            with Vertical(classes="form-section"):
                yield Static("Output Format", classes="form-section-title")
                with RadioSet(id="format"):
                    yield RadioButton("Table - Pretty display", value=True, id="table")
                    yield RadioButton("JSON - Machine readable", id="json")
                    yield RadioButton("CSV - Spreadsheet compatible", id="csv")

            # Additional Options - use SelectionList for arrow key navigation
            with Vertical(classes="form-section"):
                yield Static("Additional Options", classes="form-section-title")
                yield SelectionList[str](
                    Selection("Raw units (Farads/Henries instead of pF/µH)", "raw", False),
                    Selection("Quiet mode (minimal output)", "quiet", False),
                    Selection("Show frequency response plot", "plot", True),
                    id="options-list",
                )

            # Export Format
            with Vertical(classes="form-section"):
                yield Static("Export Plot Data", classes="form-section-title")
                with RadioSet(id="export"):
                    yield RadioButton("No export", value=True, id="no-export")
                    yield RadioButton("JSON file", id="export-json")
                    yield RadioButton("CSV file", id="export-csv")

            # Buttons
            with Horizontal(classes="button-row"):
                yield Button("Show Results", id="results-btn", variant="primary")
                yield Button("Back", id="back-btn")

        yield Footer()

    def on_mount(self) -> None:
        """Focus on E-series selection when screen mounts."""
        self.query_one("#eseries", RadioSet).focus()

    def on_key(self, event) -> None:
        """Handle Enter key to advance from RadioSet and SelectionList."""
        if event.key == "enter":
            try:
                eseries_set = self.query_one("#eseries", RadioSet)
                format_set = self.query_one("#format", RadioSet)
                options_list = self.query_one("#options-list", SelectionList)
                export_set = self.query_one("#export", RadioSet)

                if eseries_set.has_focus:
                    format_set.focus()
                    event.prevent_default()
                    event.stop()
                elif format_set.has_focus:
                    options_list.focus()
                    event.prevent_default()
                    event.stop()
                elif options_list.has_focus:
                    export_set.focus()
                    event.prevent_default()
                    event.stop()
                elif export_set.has_focus:
                    self.query_one("#results-btn", Button).focus()
                    event.prevent_default()
                    event.stop()
            except Exception:
                pass

    def action_back(self) -> None:
        """Go back to filter input screen."""
        self.app.pop_screen()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle button presses."""
        if event.button.id == "results-btn":
            self._show_results()
        elif event.button.id == "back-btn":
            self.app.pop_screen()

    def _get_selected_radio(self, radio_set_id: str) -> str:
        """Get the ID of the selected radio button in a RadioSet."""
        radio_set = self.query_one(f"#{radio_set_id}", RadioSet)
        if radio_set.pressed_button:
            return radio_set.pressed_button.id
        return ""

    def _show_results(self) -> None:
        """Save options and navigate to results screen."""
        state: FilterState = self.app.filter_state

        # Get E-series selection
        eseries = self._get_selected_radio("eseries")
        state.eseries = eseries if eseries != "none" else "E24"

        # Get output format
        state.output_format = self._get_selected_radio("format")

        # Get options from SelectionList
        options_list = self.query_one("#options-list", SelectionList)
        selected = options_list.selected
        state.raw_units = "raw" in selected
        state.quiet = "quiet" in selected
        state.show_plot = "plot" in selected

        # Get export format
        export = self._get_selected_radio("export")
        if export == "export-json":
            state.export_format = "json"
        elif export == "export-csv":
            state.export_format = "csv"
        else:
            state.export_format = None

        # Navigate to results
        from .results import ResultsScreen
        self.app.push_screen(ResultsScreen())
