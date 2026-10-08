"""Output options screen: the web form's Output and Build simulation sections.

Fields, labels, defaults, and order follow the web form. A control the shared rule
(``filter_lib.design.option_applicability``) says cannot apply to the chosen output is
disabled live, with the rule's one-line reason under it; the result then leaves it out,
as the CLI does without the flag. Its visible value is kept for the saved files that can
use it (see ``FilterState``). Build fields the result does not use (the build unticked or
disabled) are not checked here; a saved JSON that uses them reports any problem.
"""

from __future__ import annotations

from textual import on
from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical, VerticalScroll
from textual.screen import Screen
from textual.widgets import Button, Checkbox, Footer, Input, RadioButton, RadioSet, Static

from ...design.option_applicability import (
    ALLOW_SUB_PF,
    BUILD,
    ESERIES,
    LOSS_Q,
    RAW_UNITS,
    TEXT_PLOT,
    TOROID_BUILD,
    TOROID_DETAIL,
)
from ...shared.cli_aliases import DEFAULT_ESERIES
from ...shared.eseries import SUB_PF_OPTION_LABEL
from ..build_options import (
    BUILD_FIELDS,
    BUILD_INPUT_FLOW,
    BUILD_OPTION_HELP,
    BUILD_OPTION_LABEL,
    BUILD_OPTION_PREFIX,
    TOROID_BUILD_HELP,
    TOROID_BUILD_LABEL,
    BuildOptionError,
    BuildOptionValues,
    apply_build_config,
    build_field_values,
    parse_build_config,
)
from ..radio_button_helpers import EnabledRadioSet, get_selected_radio
from ..state import FilterState

# (value, label) per choice, in the web form's order.
FORMAT_CHOICES = (
    ("table", "Table - formatted for reading"),
    ("quiet", "Values only - calculated values, no table"),
    ("json", "JSON - machine readable"),
    ("csv", "CSV - spreadsheet compatible"),
)
ESERIES_CHOICES = (
    ("E12", "E12 - 12 standard values per decade"),
    ("E24", "E24 - 24 standard values per decade (default)"),
    ("E96", "E96 - 96 standard values per decade"),
    ("none", "None - show calculated values only"),
)
TOROID_CHOICES = (
    ("best", "Best, detailed - the best core with wire length, DCR, and size (default)"),
    ("full", "Up to 3, detailed - up to three cores, each with wire length, DCR, and size"),
    ("compact", "Best, one line - turns, AWG, and inductance"),
    ("none", "None - no toroid windings in any output"),
)
RESPONSE_CHOICES = (
    ("no-export", None, "None"),
    ("export-json", "json", "JSON - also saved when you export the results"),
    ("export-csv", "csv", "CSV - also saved when you export the results"),
)
SUB_PF_HELP = (
    "Also choose standard values for capacitors below 1 pF. When off, no part is chosen "
    "below 1 pF and you choose one manually. Needs E12, E24, or E96."
)
TOROID_HELP = (
    "JSON lists up to three cores and CSV the best, whatever is chosen here. None also "
    "leaves the toroid windings out of JSON, CSV, and the build simulation."
)
TEXT_PLOT_LABEL = "Text plot in the table"
TEXT_PLOT_HELP = (
    "Adds a text chart of the ideal response and the −3, −10 and −20 dB frequencies to "
    "the table. Table format only."
)
RAW_UNITS_LABEL = "Raw units (F, H)"
RAW_UNITS_HELP = (
    "Unrounded values in farads and henries (scientific notation) instead of pF and µH. "
    "The table then leaves out the standard capacitor values."
)

# The widgets each option disables; the toroid detail disables only its two choices.
OPTION_WIDGETS = {
    ESERIES: ("#eseries",),
    ALLOW_SUB_PF: ("#allow-sub-pf",),
    TOROID_DETAIL: ("#toroid-full", "#toroid-compact"),
    TEXT_PLOT: ("#plot",),
    RAW_UNITS: ("#raw",),
    BUILD: ("#build-analysis-enabled",),
    TOROID_BUILD: ("#build-use-toroids",),
}
# Enter moves through the controls in the web form's order, skipping any that are
# disabled or hidden (the build fields show only while the build applies).
FOCUS_FLOW = (
    "#format",
    "#eseries",
    "#allow-sub-pf",
    "#toroid-detail",
    "#plot",
    "#raw",
    "#export",
    "#build-analysis-enabled",
    *(f"#{input_id}" for input_id in BUILD_INPUT_FLOW),
    "#build-use-toroids",
    "#results-btn",
)
BUILD_SECTION = frozenset(
    {*(f"#{input_id}" for input_id in BUILD_INPUT_FLOW), "#build-use-toroids"}
)
ENTER_ADVANCES = frozenset(FOCUS_FLOW) - BUILD_SECTION - {"#results-btn"} | {"#build-use-toroids"}


def reason_id(option: str) -> str:
    """The id of the Static that shows why ``option`` is disabled."""
    return f"#reason-{option}"


def _reason(option: str) -> Static:
    static = Static("", id=reason_id(option)[1:], classes="option-reason")
    static.display = False
    return static


def _radio_set(set_id: str, choices, selected: str, prefix: str = "") -> RadioSet:
    return EnabledRadioSet(
        *(
            RadioButton(label, value=value == selected, id=f"{prefix}{value}")
            for value, label in choices
        ),
        id=set_id,
    )


class OutputOptionsScreen(Screen):
    """Configure the output and the optional build simulation."""

    BINDINGS = [
        ("escape", "back", "Back"),
    ]

    def compose(self) -> ComposeResult:
        state: FilterState = self.app.filter_state
        values = build_field_values(state)
        yield Static("Output options", classes="header")
        yield Static("Enter: next · ↑/↓: choose · Space: tick · Esc: back", classes="nav-hint")
        with VerticalScroll(classes="content"):
            with Vertical(classes="form-section"):
                yield Static("Output", classes="form-section-title")
                yield Static("Format", classes="field-label")
                yield _radio_set("format", FORMAT_CHOICES, state.shown_format)
                yield _reason(LOSS_Q)

                yield Static("Standard capacitor values", classes="field-label")
                yield _radio_set("eseries", ESERIES_CHOICES, state.eseries)
                yield _reason(ESERIES)
                yield Checkbox(SUB_PF_OPTION_LABEL, state.allow_sub_pf, id="allow-sub-pf")
                yield Static(SUB_PF_HELP, classes="field-help")
                yield _reason(ALLOW_SUB_PF)

                yield Static("Toroid windings (table detail)", classes="field-label")
                yield _radio_set("toroid-detail", TOROID_CHOICES, state.toroid_detail, "toroid-")
                yield Static(TOROID_HELP, classes="field-help")
                yield _reason(TOROID_DETAIL)

                yield Checkbox(TEXT_PLOT_LABEL, state.show_plot, id="plot")
                yield Static(TEXT_PLOT_HELP, classes="field-help")
                yield _reason(TEXT_PLOT)
                yield Checkbox(RAW_UNITS_LABEL, state.raw_units, id="raw")
                yield Static(RAW_UNITS_HELP, classes="field-help")
                yield _reason(RAW_UNITS)

            with Vertical(classes="form-section"):
                yield Static("Response data file", classes="form-section-title")
                yield EnabledRadioSet(
                    *(
                        RadioButton(label, value=value == state.export_format, id=button_id)
                        for button_id, value, label in RESPONSE_CHOICES
                    ),
                    id="export",
                )

            with Vertical(classes="form-section"):
                yield Static("Build simulation (optional)", classes="form-section-title")
                yield Checkbox(
                    BUILD_OPTION_LABEL, state.build_analysis_enabled, id="build-analysis-enabled"
                )
                yield Static(BUILD_OPTION_HELP, classes="field-help")
                yield _reason(BUILD)
                with Vertical(id="build-analysis-options"):
                    for build_field in BUILD_FIELDS:
                        yield Static(build_field.label, classes="field-label")
                        yield Input(values[build_field.input_id], id=build_field.input_id)
                        yield Static(build_field.help, classes="field-help")
                    yield Checkbox(
                        TOROID_BUILD_LABEL,
                        state.build_use_toroid_candidates,
                        id="build-use-toroids",
                    )
                    yield Static(TOROID_BUILD_HELP, classes="field-help")
                    yield _reason(TOROID_BUILD)

            with Horizontal(classes="button-row"):
                yield Button("Show results", id="results-btn", variant="primary")
                yield Button("Back", id="back-btn")

        yield Footer()

    def on_mount(self) -> None:
        """Apply the shared rule to the initial choices and focus the first control."""
        for radio_set in self.query(RadioSet):
            # Start the arrow-key highlight on the chosen button, not the first one
            # (Textual highlights the first; the choices here come from the state).
            if radio_set.pressed_index >= 0 and hasattr(radio_set, "_selected"):
                radio_set._selected = radio_set.pressed_index
        self._refresh_options()
        self.query_one("#format", RadioSet).focus()

    # -- Live applicability -------------------------------------------------------

    def _store_choices(self, state: FilterState) -> None:
        """Copy the visible output choices into ``state`` (build fields are parsed later)."""
        output_format = get_selected_radio(self, "format") or "table"
        state.output_format = output_format
        state.quiet = output_format == "quiet"
        state.eseries = get_selected_radio(self, "eseries") or DEFAULT_ESERIES
        state.allow_sub_pf = self.query_one("#allow-sub-pf", Checkbox).value
        toroid = get_selected_radio(self, "toroid-detail").removeprefix("toroid-")
        state.toroid_detail = toroid if toroid in ("full", "compact", "none") else "best"
        state.show_plot = self.query_one("#plot", Checkbox).value
        state.raw_units = self.query_one("#raw", Checkbox).value
        # None (not a string) means "no response-data file".
        export = get_selected_radio(self, "export")
        state.export_format = {"export-json": "json", "export-csv": "csv"}.get(export)
        state.build_analysis_enabled = self.query_one("#build-analysis-enabled", Checkbox).value
        state.build_use_toroid_candidates = self.query_one("#build-use-toroids", Checkbox).value

    def _show_reason(self, selector: str, reason: str | None) -> None:
        static = self.query_one(selector, Static)
        static.update(reason or "")
        static.display = reason is not None

    def _refresh_options(self) -> None:
        """Disable each control the shared rule says cannot apply, and say why."""
        state: FilterState = self.app.filter_state
        self._store_choices(state)
        reasons = state.option_reasons()
        for option, selectors in OPTION_WIDGETS.items():
            for selector in selectors:
                self.query_one(selector).disabled = option in reasons
            self._show_reason(reason_id(option), reasons.get(option))
        # Resonator Q is entered on the band-pass screen; say here when it is left out.
        self._show_reason(reason_id(LOSS_Q), reasons.get(LOSS_Q) if state.has_resonator_q else None)
        # As on the web, the build fields show only while the build applies.
        self.query_one("#build-analysis-options").display = (
            state.build_analysis_enabled and BUILD not in reasons
        )

    @on(RadioSet.Changed)
    @on(Checkbox.Changed)
    def _on_choice_changed(self, event) -> None:
        """Re-apply the rule after any choice; reveal the build fields when ticked."""
        self._refresh_options()
        control = getattr(event, "checkbox", None)
        if control is not None and control.id == "build-analysis-enabled" and event.value:
            if self.query_one("#build-analysis-options").display:
                self.query_one(f"#{BUILD_INPUT_FLOW[0]}", Input).focus()

    # -- Keyboard flow --------------------------------------------------------------

    def _available(self, selector: str) -> bool:
        if self.query_one(selector).disabled is True:
            return False
        if selector in BUILD_SECTION:
            return bool(self.query_one("#build-analysis-options").display)
        return True

    def _focus_after(self, selector: str) -> None:
        """Focus the next control in the web form's order that can take focus."""
        for candidate in FOCUS_FLOW[FOCUS_FLOW.index(selector) + 1 :]:
            if self._available(candidate):
                self.query_one(candidate).focus()
                return

    @on(Input.Submitted)
    def _on_build_input_submitted(self, event: Input.Submitted) -> None:
        """Advance through the build fields without trapping keyboard users."""
        if event.input.id in BUILD_INPUT_FLOW:
            self._focus_after(f"#{event.input.id}")

    def on_key(self, event) -> None:
        """Enter on a choice or box advances to the next control; Space still ticks."""
        if event.key != "enter":
            return
        try:
            for selector in ENTER_ADVANCES:
                if self.query_one(selector).has_focus is True:
                    self._focus_after(selector)
                    event.prevent_default()
                    event.stop()
                    return
        except (AttributeError, LookupError):
            # Widget not yet mounted during init; safe to ignore
            pass

    # -- Buttons ------------------------------------------------------------------

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
        """Save the choices and open the results.

        Nothing here refuses a combination of choices: the shared rule has already
        disabled what cannot apply. Only the build fields' own values can be refused,
        and only when the result uses the build (its fields are then on screen).
        """
        state: FilterState = self.app.filter_state
        state.invalidate_calculation()
        self._store_choices(state)

        values = self._build_values()
        state.build_field_text = {
            input_id: self.query_one(f"#{input_id}", Input).value for input_id in BUILD_INPUT_FLOW
        }
        # The series here only validates; each output picks its own.
        eseries = DEFAULT_ESERIES if state.eseries == "none" else state.eseries
        try:
            build_config = parse_build_config(
                eseries,
                values,
                design_impedance=state.impedance,
                resonator_q_supplied=state.has_resonator_q,
            )
        except BuildOptionError as error:
            if state.runs_build:
                self.notify(f"{BUILD_OPTION_PREFIX}{error}", severity="error")
                if error.field_id is not None:
                    self.query_one(f"#{error.field_id}", Input).focus()
                return
            # Not used by the result: a saved JSON that uses the build reports it.
            state.build_input_error = f"{BUILD_OPTION_PREFIX}{error}"
            state.build_use_toroid_candidates = values.use_toroid_candidates
        else:
            state.build_input_error = None
            apply_build_config(state, state.build_analysis_enabled, build_config)

        from .results import ResultsScreen

        self.app.push_screen(ResultsScreen())

    def _build_values(self) -> BuildOptionValues:
        """The build fields as typed, in form order."""

        def text(input_id: str) -> str:
            return self.query_one(f"#{input_id}", Input).value.strip()

        return BuildOptionValues(
            capacitor_tolerance=text("build-capacitor-tolerance"),
            inductor_tolerance=text("build-inductor-tolerance"),
            inductor_q=text("build-inductor-q"),
            capacitor_q=text("build-capacitor-q"),
            reference_frequency=text("build-reference-frequency"),
            source_resistance=text("build-source-resistance"),
            load_resistance=text("build-load-resistance"),
            sample_count=text("build-sample-count"),
            seed=text("build-seed"),
            grid_points=text("build-grid-points"),
            use_toroid_candidates=self.query_one("#build-use-toroids", Checkbox).value,
        )
