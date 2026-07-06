"""Output options screen for configuring display format."""

from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical, VerticalScroll
from textual.screen import Screen
from textual.widgets import Button, Footer, RadioButton, RadioSet, SelectionList, Static
from textual.widgets.selection_list import Selection

from ..radio_button_helpers import get_selected_radio
from ..state import FilterState


class OutputOptionsScreen(Screen):
    """Screen for selecting output format options.

    Shared by all three filter categories — it only writes the output-side
    FilterState fields, so it never needs to know which filter was designed.
    """

    BINDINGS = [
        ("escape", "back", "Back"),
    ]

    def compose(self) -> ComposeResult:
        yield Static("Output Options", classes="header")
        yield Static("Enter: next · ↑/↓: choose · Esc: back", classes="nav-hint")
        with VerticalScroll(classes="content"):
            with Vertical(classes="form-section"):
                yield Static("Component Matching", classes="form-section-title")
                with RadioSet(id="eseries"):
                    yield RadioButton("E24 - Standard tolerance (default)", value=True, id="E24")
                    yield RadioButton("E12 - Fewer values, looser tolerance", id="E12")
                    yield RadioButton("E96 - More values, tighter tolerance", id="E96")
                    yield RadioButton("None - Calculated values only", id="none")

            with Vertical(classes="form-section"):
                yield Static("Output Format", classes="form-section-title")
                with RadioSet(id="format"):
                    yield RadioButton("Table - Pretty display", value=True, id="table")
                    yield RadioButton("JSON - Machine readable", id="json")
                    yield RadioButton("CSV - Spreadsheet compatible", id="csv")

            # SelectionList rather than individual Checkboxes so arrow keys
            # walk the multi-select options the same way they walk the
            # RadioSets above — one consistent keyboard model per screen.
            with Vertical(classes="form-section"):
                yield Static("Additional Options", classes="form-section-title")
                yield SelectionList[str](
                    Selection("Raw units (Farads/Henries instead of pF/µH)", "raw", False),
                    Selection("Quiet mode (minimal output)", "quiet", False),
                    Selection("Show frequency response plot", "plot", True),
                    id="options-list",
                )

            with Vertical(classes="form-section"):
                yield Static("Export Plot Data", classes="form-section-title")
                with RadioSet(id="export"):
                    yield RadioButton("No export", value=True, id="no-export")
                    yield RadioButton(
                        "JSON file - frequency response saved alongside results on Save",
                        id="export-json",
                    )
                    yield RadioButton(
                        "CSV file - frequency response saved alongside results on Save",
                        id="export-csv",
                    )

            with Horizontal(classes="button-row"):
                yield Button("Show Results", id="results-btn", variant="primary")
                yield Button("Back", id="back-btn")

        yield Footer()

    def on_mount(self) -> None:
        """Focus on E-series selection when screen mounts."""
        self.query_one("#eseries", RadioSet).focus()

    def on_key(self, event) -> None:
        """Handle Enter key to advance from RadioSet and SelectionList.

        Hand-rolled Enter chain instead of FilterScreenNavigationMixin: the
        mixin only walks RadioSets, and this screen has a SelectionList in
        the middle of the flow.
        """
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
            except (AttributeError, LookupError):
                # Widget not yet mounted during init; safe to ignore
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

    def _show_results(self) -> None:
        """Save options and navigate to results screen."""
        state: FilterState = self.app.filter_state

        # The literal id "none" (as opposed to an empty selection) means the
        # user explicitly disabled E-series matching; empty falls back to E24.
        eseries = get_selected_radio(self, "eseries")
        state.eseries = eseries or "E24"

        state.output_format = get_selected_radio(self, "format")

        options_list = self.query_one("#options-list", SelectionList)
        selected = options_list.selected
        state.raw_units = "raw" in selected
        state.quiet = "quiet" in selected
        state.show_plot = "plot" in selected

        # None (not a string) signals "no response-data export"; the results
        # screen checks this when deciding whether to write a second file.
        export = get_selected_radio(self, "export")
        if export == "export-json":
            state.export_format = "json"
        elif export == "export-csv":
            state.export_format = "csv"
        else:
            state.export_format = None

        from .results import ResultsScreen

        self.app.push_screen(ResultsScreen())
