# Textual Wizard Patterns

This project uses independent Textual screens, not a `ContentSwitcher`:

```text
Welcome (Choose a filter) → one filter form → Output options → Results
```

Forward navigation calls `push_screen()`. Escape and Back call `pop_screen()`. The optional
frequency plot is rendered in Results and does not create a fifth screen.

## Shared State

One `FilterState` lives at `FilterWizardApp.filter_state`. Screens read or update
`self.app.filter_state`; it is a dataclass, not a widget, and must not be found with
`query_one()`.

Parameter screens store validated design inputs (band-pass also stores the band edges and
Qu/QL/QC). Output options stores every control's *visible* value: format (Values only is
`output_format="quiet"`), E-series, `allow_sub_pf`, toroid detail
(`best`/`full`/`compact`/`none`), plot, raw, response sidecar, and build-simulation controls,
including ones that are disabled. `DesignInputsMixin` (`state_design_inputs.py`) turns those
into the result's `DesignRequest`/`RenderOptions` with `applied_options()` and into each saved
file's with `document_options()`. Results receives a snapshot and publishes a detached
`CalculationOutcome` only after the calculation succeeds.

## Navigation and Validation

- Validate the current screen before pushing the next screen.
- Map an error back to the most relevant widget, notify the user, and focus that widget.
- Enter advances through each screen's `FOCUS_FLOW` (the web form's order), skipping disabled
  or hidden controls and never ticking a box (Space ticks); Tab/Shift+Tab remain available.
- Escape goes back. `Q` on Results or Ctrl+C exits.
- Options and labels match the web form; `tests/test_wizard_web_alignment.py` compares them.

### Options that cannot apply

Output combinations are never refused on **Show results**. Each change to Format, E-series, Raw
units, the build box, or Toroid windings asks the shared rule,
`filter_lib.design.option_applicability.inapplicable_options`, which controls cannot apply. Those
are disabled and the rule's one-line reason is shown in the `#reason-<option>` Static under them.
The result treats a disabled control as unset, the same as leaving out the CLI flag, so Values
only with E24 just works. The band-pass screen checks Qu/QL/QC (`loss_q`) again on
`on_screen_resume`, because the format is chosen on the next screen.

Saved JSON and CSV use `document_options`, the same mapping the web downloads use: a disabled
control's visible value is applied to each file that can show it (Values only + None gives a
JSON file equal to `--format json --no-match`). When the saved JSON needs a design the result did
not run (a disabled build, or Qu with CSV or Values only), Results calculates it only when that
JSON is saved, in a separate thread worker (group `json-design`, notice "Preparing the JSON
file…"), and caches it in `FilterState.json_design`. The result shown never runs a disabled
build. Build fields the result does not use are not validated on Show results; a parse error is
kept in `FilterState.build_input_error` and reported if the saved JSON uses the build. Disabled
radio choices use `EnabledRadioSet`, so Space/Enter on a stale highlight cannot press them.
Extend the shared rule for a new option; never add a wizard-only check.

## Background Calculation

Results starts one exclusive thread worker from `FilterState.calculation_copy()`. The live state
has a monotonically increasing calculation revision:

1. changing inputs invalidates the prior result;
2. mounting Results begins a pending revision and captures a snapshot;
3. a worker event is accepted only if the screen, worker, revision, and pending state all match;
4. unmount cancels the worker and invalidates that pending revision;
5. export stays disabled until a complete successful result is published.

This prevents a canceled or stale calculation from overwriting a newer design.

Textual cannot interrupt a thread worker, so cancellation is cooperative. The worker passes
`should_cancel` (a check of the worker's `is_cancelled`) through `filter_lib.design` to the build
analysis, which polls it before each tolerance case and raises `BuildAnalysisCancelled`. Quit, Esc, and Design another
therefore stop a long build simulation after at most one more circuit measurement,
instead of leaving the thread running until it finishes. The worker runs with
`exit_on_error=False`: an unexpected exception is rendered as "Calculation failed: …" on
Results and does not exit the app.

## Export

The Results screen offers Design another, Export, and Quit. Export reveals *Save as* Text (as
shown), JSON (full design), or CSV (components) plus Save/Cancel, and shows the folder files are
saved in. A build simulation can be saved as text or JSON; the CSV choice is disabled with its
reason (`CSV_WITH_BUILD_MESSAGE`, "CSV cannot include the build simulation. Save as Text or
JSON.") because the nested results have no lossy flattening contract, and with
`LOSS_Q_NOT_SHOWN_MESSAGE` when the result used resonator Q. An optional response JSON/CSV
sidecar is written beside the component file; it is the ideal response and leaves out Qu/QL/QC
(equal to `--plot-data` without them). Files use UTF-8 and CSV-safe newline handling.

## Where Logic Belongs

- Screen modules: widgets, focus flow, notifications, and navigation.
- `bandpass_form.py`: BP form parsing and field-specific errors.
- `build_options.py`: build-field labels, help, parsing (blank = `BuildConfig()` default), and
  `BuildConfig` mapping.
- `state_design_inputs.py`: which options apply (via the shared rule) and the `DesignRequest`
  and `RenderOptions` for the result and each saved document.
- `filter_screen_navigation_mixin.py`: the generic Enter flow (`FOCUS_FLOW`, `_is_shown`).
- `filter_type_calculators.py`: map state to a `DesignRequest` and render with
  `filter_lib.design`.
- `calculation_handler.py`: detached orchestration, optional build simulation, and success/error
  outcomes.
- `export_formatting.py`: component and response files, rendered by `filter_lib.design`.
- `state.py`: state, snapshots, revisions, and publication invariants.

Business calculations, rendering, and machine schemas belong in `filter_lib.design` and the
shared calculator modules, never in a screen, so the CLI, wizard, and web UI cannot drift.

## Testing

Use both focused unit tests and Textual pilot tests:

- mocked widgets for parsing, focus mapping, and button handlers;
- `App.run_test()` for mounted navigation, worker completion/cancel, and export lifecycle,
  including the disabled-with-reason output journeys (`test_wizard_output_option_journeys.py`);
- stale-worker and failed-calculation regressions;
- parity tests showing wizard build settings create the same shared `BuildConfig` behavior.

Do not rely on manual TUI checks as the only evidence for a public workflow.
