"""Output options screen for configuring display format."""

from textual import on
from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical, VerticalScroll
from textual.screen import Screen
from textual.widgets import (
    Button,
    Checkbox,
    Footer,
    Input,
    RadioButton,
    RadioSet,
    SelectionList,
    Static,
)
from textual.widgets.selection_list import Selection

from ..build_options import (
    BUILD_INPUT_FLOW,
    BuildOptionValues,
    apply_build_config,
    build_error_input_id,
    build_option_issue,
    has_custom_build_controls,
    output_option_issue,
    parse_build_config,
)
from ..radio_button_helpers import get_selected_radio
from ..state import FilterState


class OutputOptionsScreen(Screen):
    """Configure output, with resonator-only loss controls limited to band-pass."""

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
                    yield RadioButton(
                        "E24 - 24 preferred values per decade (default)", value=True, id="E24"
                    )
                    yield RadioButton("E12 - 12 preferred values per decade", id="E12")
                    yield RadioButton("E96 - 96 preferred values per decade", id="E96")
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

            with Vertical(classes="form-section"):
                yield Static("Realized-Build Analysis (optional)", classes="form-section-title")
                yield Checkbox(
                    "Analyze nominal parts and bounded tolerances (simulation, not a measurement)",
                    id="build-analysis-enabled",
                )
                with Vertical(id="build-analysis-options"):
                    yield Static(
                        "Evaluation loads affect simulated transducer gain only; synthesis "
                        "remains at the equal source/load impedance selected earlier."
                    )
                    yield Static("Evaluation source resistance (blank = synthesized impedance):")
                    yield Input(id="build-source-resistance")
                    yield Static("Evaluation load resistance (blank = synthesized impedance):")
                    yield Input(id="build-load-resistance")
                    yield Static("Capacitor tolerance bound (%):")
                    yield Input(value="5", id="build-capacitor-tolerance")
                    yield Static("Inductor tolerance bound (%):")
                    yield Input(value="10", id="build-inductor-tolerance")
                    yield Static("Inductor Q at design frequency (optional):")
                    yield Input(id="build-inductor-q")
                    yield Static("Capacitor Q at design frequency (optional):")
                    yield Input(id="build-capacitor-q")
                    yield Static(
                        "Complete resonator Q (optional; do not combine with L/C Q):",
                        id="build-resonator-q-label",
                    )
                    yield Input(id="build-resonator-q")
                    yield Static("Additional seeded screening samples (0-10000):")
                    yield Input(value="0", id="build-sample-count")
                    yield Static("Screening seed (integer):")
                    yield Input(value="0", id="build-seed")
                    yield Static("Analysis frequency points (51-5001):")
                    yield Input(value="601", id="build-grid-points")
                    yield Checkbox(
                        "Use screened integer-turn toroid candidates when available",
                        value=True,
                        id="build-use-toroids",
                    )

            with Horizontal(classes="button-row"):
                yield Button("Show Results", id="results-btn", variant="primary")
                yield Button("Back", id="back-btn")

        yield Footer()

    def on_mount(self) -> None:
        """Focus on E-series selection when screen mounts."""
        self.query_one("#eseries", RadioSet).focus()
        self.query_one("#build-analysis-options").display = False
        show_resonator_q = self.app.filter_state.category == "bandpass"
        self.query_one("#build-resonator-q-label").display = show_resonator_q
        resonator_q = self.query_one("#build-resonator-q", Input)
        resonator_q.display = show_resonator_q
        resonator_q.value = resonator_q.value if show_resonator_q else ""

    @on(Checkbox.Changed, "#build-analysis-enabled")
    def _on_build_analysis_changed(self, event: Checkbox.Changed) -> None:
        """Reveal advanced controls only after the user opts in."""
        self.query_one("#build-analysis-options").display = event.value
        if event.value:
            self.query_one("#build-source-resistance", Input).focus()

    @on(Input.Submitted)
    def _on_build_input_submitted(self, event: Input.Submitted) -> None:
        """Advance through the optional controls without trapping keyboard users."""
        input_id = event.input.id
        if input_id not in BUILD_INPUT_FLOW:
            return
        flow = BUILD_INPUT_FLOW
        if self.app.filter_state.category != "bandpass":
            flow = tuple(item for item in flow if item != "build-resonator-q")
        index = flow.index(input_id)
        if index + 1 < len(flow):
            self.query_one(f"#{flow[index + 1]}", Input).focus()
        else:
            self.query_one("#build-use-toroids", Checkbox).focus()

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
        state.invalidate_calculation()

        # The literal id "none" (as opposed to an empty selection) means the
        # user explicitly disabled E-series matching; empty falls back to E24.
        eseries = get_selected_radio(self, "eseries")
        eseries = eseries or "E24"
        output_format = get_selected_radio(self, "format") or "table"

        options_list = self.query_one("#options-list", SelectionList)
        selected = options_list.selected
        raw = "raw" in selected
        quiet = "quiet" in selected
        show_plot = "plot" in selected
        build_enabled = self.query_one("#build-analysis-enabled", Checkbox).value

        issue = output_option_issue(
            output_format=output_format,
            raw=raw,
            quiet=quiet,
            show_plot=show_plot,
            eseries=eseries,
            build_enabled=build_enabled,
        )
        if issue is not None:
            self.notify(issue.message, severity="error")
            self.query_one(issue.focus_selector).focus()
            return

        issue = build_option_issue(
            enabled=build_enabled,
            output_format=output_format,
            quiet=quiet,
            eseries=eseries,
        )
        if issue is not None:
            self.notify(issue.message, severity="error")
            self.query_one(issue.focus_selector).focus()
            return

        build_config = self._parse_build_config(eseries if eseries != "none" else "E24")
        if build_config is None:
            return
        issue = build_option_issue(
            enabled=build_enabled,
            output_format=output_format,
            quiet=quiet,
            eseries=eseries,
            has_custom_controls=has_custom_build_controls(build_config),
        )
        if issue is not None:
            self.notify(issue.message, severity="error")
            self.query_one(issue.focus_selector).focus()
            return

        state.eseries = eseries
        state.output_format = output_format
        state.raw_units = raw
        state.quiet = quiet
        state.show_plot = show_plot
        apply_build_config(state, build_enabled, build_config)

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

    def _parse_build_config(self, eseries: str):
        """Parse every build control and validate it through ``BuildConfig``."""

        def text(selector: str) -> str:
            return self.query_one(selector, Input).value.strip()

        try:
            return parse_build_config(
                eseries,
                BuildOptionValues(
                    source_resistance=text("#build-source-resistance"),
                    load_resistance=text("#build-load-resistance"),
                    capacitor_tolerance=text("#build-capacitor-tolerance"),
                    inductor_tolerance=text("#build-inductor-tolerance"),
                    inductor_q=text("#build-inductor-q"),
                    capacitor_q=text("#build-capacitor-q"),
                    resonator_q=text("#build-resonator-q"),
                    sample_count=text("#build-sample-count"),
                    seed=text("#build-seed"),
                    grid_points=text("#build-grid-points"),
                    use_toroid_candidates=self.query_one("#build-use-toroids", Checkbox).value,
                ),
            )
        except ValueError as error:
            self.notify(f"Invalid realized-build setting: {error}", severity="error")
            input_id = build_error_input_id(str(error))
            if input_id is not None:
                self.query_one(f"#{input_id}", Input).focus()
            return None
