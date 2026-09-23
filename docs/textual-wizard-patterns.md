# Textual Wizard Patterns

This project uses independent Textual screens, not a `ContentSwitcher`:

```text
Welcome → one filter form → Output Options → Results
```

Forward navigation calls `push_screen()`. Escape and Back call `pop_screen()`. The optional
frequency plot is rendered in Results and does not create a fifth screen.

## Shared State

One `FilterState` lives at `FilterWizardApp.filter_state`. Screens read or update
`self.app.filter_state`; it is a dataclass, not a widget, and must not be found with
`query_one()`.

Parameter screens store validated design inputs. Output Options stores component-output,
toroid-detail, response-sidecar, and optional build-analysis controls. Results receives a
snapshot and publishes a detached `CalculationOutcome` only after the calculation succeeds.

## Navigation and Validation

- Validate the current screen before pushing the next screen.
- Map an error back to the most relevant widget, notify the user, and focus that widget.
- Enter advances through the documented field flow; Tab/Shift+Tab remain available.
- Escape goes back. `Q` on Results or Ctrl+C exits.
- Output choices that would hide selected data are rejected rather than silently ignored.

Toroid Winding Detail always has a selection (Full by default), so it is labelled as a
table-output choice instead of being rejected for JSON or CSV. Those formats keep their own
candidate contracts: JSON carries up to three candidates and CSV the best one.

The raw-table/E-series combination is normally rejected because raw rows hide preferred-value
selection. It is allowed when realized-build analysis is enabled, because the E-series still
drives the visible nominal-build analysis. Quiet mode cannot hide build analysis.

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
`should_cancel` (a check of `get_current_worker().is_cancelled`) to `analyze_build`, which polls
it before each screening case and raises `BuildAnalysisCancelled`. Quit, Esc, and Design Another
therefore stop a long realized-build analysis after at most one more circuit measurement,
instead of leaving the thread running until it finishes. The worker runs with
`exit_on_error=False`: an unexpected exception is rendered as "Calculation failed: …" on
Results and does not exit the app.

## Export

The Results screen offers Design Another, Export, and Quit. Export reveals Text, JSON, or CSV
component choices plus Save/Cancel. Build analysis can be saved as text or JSON; CSV is disabled
because the nested analysis has no lossy flattening contract. An optional response JSON/CSV
sidecar is written beside the component file. Files use UTF-8 and CSV-safe newline handling.

## Where Logic Belongs

- Screen modules: widgets, focus flow, notifications, and navigation.
- `bandpass_form.py`: BP form parsing and field-specific errors.
- `build_options.py`: output/build compatibility and `BuildConfig` mapping.
- `filter_type_calculators.py`: category calculation and primary rendering.
- `calculation_handler.py`: detached orchestration and success/error outcomes.
- `export_formatting.py`: component and response serialization.
- `state.py`: state, snapshots, revisions, and publication invariants.

Business calculations and machine schemas belong in shared calculator modules so CLI and wizard
cannot drift.

## Testing

Use both focused unit tests and Textual pilot tests:

- mocked widgets for parsing, focus mapping, and button handlers;
- `App.run_test()` for mounted navigation, worker completion/cancel, and export lifecycle;
- stale-worker and failed-calculation regressions;
- parity tests showing wizard build settings create the same shared `BuildConfig` behavior.

Do not rely on manual TUI checks as the only evidence for a public workflow.
