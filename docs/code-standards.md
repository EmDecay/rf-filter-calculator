# Code Standards and Architecture Guidelines

**Last updated:** October 7, 2026

This document records the conventions that matter for the current calculator. Follow the
repository-level `CLAUDE.md`, then these project-specific rules and nearby code patterns.

## Priorities

1. Correct electrical behavior and truthful limitations.
2. Simple, readable code with explicit contracts.
3. Compatibility unless a deliberate release changes a public contract.
4. Performance only where measurement shows it matters.

Do not make a numerical test pass by weakening an engineering invariant, hiding a failure,
or substituting a mock result for real circuit behavior.

## Python Style

- Python modules and functions use `snake_case`; classes use `PascalCase`; constants use
  `UPPER_SNAKE_CASE`.
- Use Python 3.10 syntax, including `T | None` and `A | B` rather than legacy
  `Optional[T]`/`Union[A, B]` spellings.
- Ruff is authoritative: target `py310`, line length 100, rules `E`, `F`, `I`, `UP`, and
  `B`, with the exceptions recorded in `pyproject.toml`.
- Keep imports in standard-library, third-party, then local groups.
- Comments explain invariants, units, limitations, or non-obvious choices—not the syntax.
- Public functions need useful type hints and docstrings. Document units at the boundary.

Run:

```bash
uv run ruff check .
uv run ruff format --check .
```

## Calculation Contracts

LP/HP calculation functions return a tuple whose first two items follow the category: lowpass
returns capacitors first, highpass returns inductors first (the LP→HP transform swaps the
component roles):

```python
capacitors, inductors, order = lowpass.calculate_butterworth(
    cutoff_hz, impedance, num_components, topology
)
inductors, capacitors, order = highpass.calculate_butterworth(
    cutoff_hz, impedance, num_components, topology
)
```

`filter_lib.design` assembles the ladder result dictionaries for every surface (CLI, wizard,
and web UI). Bandpass synthesis returns a
dictionary because it carries calibrated component values, requested/internal parameters,
Q-model metadata, warnings, and per-design validation evidence.

Keep these meanings distinct:

- LP/HP Chebyshev cutoff is the ripple-band edge.
- Butterworth/Bessel LP/HP cutoff is the −3 dB point.
- Bandpass bandwidth is the true requested −3 dB skirt-to-skirt bandwidth.
- Equal source/load termination is a synthesis assumption. Separate build-analysis ports
  change evaluation, not synthesis.
- `q_min` is a compatibility heuristic. It is not a build guarantee.

## Numeric Validation

Public numeric boundaries reject booleans, wrong types, NaN/infinity, arbitrary-size integers
outside binary64, and invalid signs with a stable `ValueError`. Do not use bare
`math.isfinite(value)` as a type check: booleans pass it, strings leak `TypeError`, and very large
Python integers leak `OverflowError`.

Use a shared validator or finite-real predicate:

```python
from filter_lib.shared.numeric import is_finite_real

if not is_finite_real(value) or value <= 0:
    raise ValueError("value must be positive and finite")
```

For a simple positive or non-negative boundary, prefer `require_positive_finite` or
`require_nonnegative_finite` so the error contract stays consistent.

Integer inputs require an exact non-boolean `int`; do not silently truncate floats. Validate
arrays element-by-element before zipping or serializing them. A public invalid-input path must
not leak `TypeError`, `OverflowError`, `ZeroDivisionError`, or non-standard JSON.

For multiplicative formulas, avoid rejecting valid final values because an intermediate
overflows or underflows. Prefer log-domain scaling, cancellation-resistant identities, or
decimal parsing when unit suffixes compensate for an extreme textual exponent. Reject the
request cleanly when the final result is not positive finite binary64.

## Filter and Circuit Architecture

The maintained boundaries are:

- `filter_lib/lowpass/` and `filter_lib/highpass/`: public calculation/display/response
  adapters over shared prototype logic.
- `filter_lib/bandpass/`: Top-C synthesis, calibration, independent shape verification,
  ideal response, and display adapters.
- `filter_lib/shared/`: parsing, prototypes, E-series policy, named circuits, nodal solving,
  realization, loss/tolerance analysis, export, plotting, and toroid screening.
- `filter_lib/design/`: the one request → synthesis → render/export path that every surface
  calls; cross-surface input rules live in `DesignRequest` and `RenderOptions`.
- `filter_lib/cli/`: argument definitions and thin command orchestration.
- `filter_lib/wizard/`: Textual screens, shared state, calculation workers, and export.
- `filter_lib/web/`: the optional FastAPI web UI: form parsing, bounded execution, request
  guard, SVG plot, and templates. Imported only by `filter-calc web`.

Keep calibrated synthesis separate from validation. The bandpass calibration sweep may place
the skirts; `response_verification.py` independently checks skirts, connected regions, shape,
and near-stopband samples. Do not replace `response_validation_status` with a
blanket support claim.

Preserve the separation between synthesis acceptance and reporting accuracy. Harmonic samples
and approximation comparisons are informational. Measurement changes need independent circuit
references, convergence evidence, and explicit unresolved/region semantics; see
[accuracy regressions](../tests/test_response_accuracy.py).

Named circuits are the common physical contract for the build simulation and SPICE. A chosen
parallel capacitor remains two branches. A part that is unavailable or refused by the selection
rule is an explicit exact fallback with warnings (shown as "calculated value used"), never a
fabricated physical part. Bandpass SPICE element names (`CT1`, `LT1`, `CK1`, `CIN`, `COUT`) stay
as they are; human-readable text maps them to the table names with
`shared/circuit_display_names.py::display_component_name`, and decks carry a `* names:` comment.

## E-Series Policy

E12/E24/E96 names describe how many standard values there are per decade, not tolerance.
Automatic standard-value selection applies to capacitors only:

- keep a single part when absolute error is at most 1%;
- select a two-part parallel combination only when it improves absolute error by at least
  0.5 percentage points;
- below 1 pF, choose nothing unless `DesignRequest.allow_sub_pf` is set (CLI `--allow-sub-pf`,
  wizard/web **Allow capacitors below 1 pF**); the warning names that option.

Surfaces set `allow_sub_pf` on `DesignRequest` only; `design()` copies it to the result and
applies it to every `MatchPolicy`. A Python caller's explicit `BuildConfig.match_policy`
opt-in is combined with it (either one allows sub-pF parts), never overwritten. Table, JSON, CSV, wizard, web UI, nominal realization, and SPICE must
agree on the selected result. Inductors remain calculated/wound values or toroid winding
suggestions.

## Toroid Data and Claims

Automatic screening uses only exact parts marked primary-source verified in
`toroid_core_data.json`. Legacy records remain inspectable but are not auto-selected. Preserve
source IDs and field provenance whenever data changes.

Toroid selection may evaluate material-frequency guidance, whole turns, nominal error,
published winding capacity, wire length, and DC resistance. Output calls the result a
"suggestion" and must not present it as a prediction of RF Q, SRF, core loss, saturation,
heating, or power handling (`toroid_selection.NOT_ASSESSED_WARNING`).

## Build Simulation and SPICE

`BuildConfig`, nominal realization, and tolerance screening are public contracts (shown to users
as the build simulation, the chosen parts, and the tolerance cases):

- chosen parts and exact fallbacks remain auditable;
- Q is converted to constant series resistance at a stated reference frequency;
- a custom loss reference without an effective Q is rejected;
- fixed tolerance cases and seeded extra random cases are not measurements, probabilities,
  yields, or guaranteed worst cases;
- all reported gain is transducer power gain with explicit source/load ports.

Generic SPICE export has two realizations: `exact` and `nominal_build` (the CLI default). The
printed `vm(load)` trace is load voltage, not gain in dB; deck comments state the transducer
gain expression.

## User-Facing Text

Help, errors, output, wizard, and web text use one plain term per concept: build simulation,
ideal values, chosen parts, parts used, calculated value used, tolerance cases, extra random
tolerance cases, toroid winding suggestions, response check, part losses (Q), resonator Qu,
simulation source/load resistance, frequency points, values only, and standard capacitor
values. Do not reintroduce "realized", "nominal build", "screened candidate", "expert
override", "tolerance corners", or "validated envelope" in human-readable text. JSON keys,
JSON enum values, CSV columns, flag names, and choice values (`nominal-build`, `exact`) are
machine contracts and keep their names. A plainer CLI spelling is an additive alias resolved at
parse time (`--spice-realization calculated`/`chosen-parts` via
`shared/cli_aliases.py::SPICE_REALIZATION_ALIASES`), so validation and output only ever see the
canonical value.

A rule enforced on more than one surface has one message constant or helper; import it instead
of restating the text. Examples: `design/render_options.py` (`BUILD_NEEDS_ESERIES_MESSAGE`,
`BUILD_NEEDS_TABLE_OR_JSON_MESSAGE`, `BUILD_NOT_WITH_VALUES_ONLY_MESSAGE`,
`SUB_PF_NEEDS_ESERIES_MESSAGE`, `shows_design_warnings`), `shared/eseries.py`
(`SUB_PF_OPTION_LABEL`, `SUB_PF_CLI_FLAG`, `sub_pf_warning`), `shared/cli_aliases.py`
(`RIPPLE_RANGE_MESSAGE`, `COMPONENT_COUNT_MESSAGE`, `chebyshev_odd_count_message`),
`bandpass/input_validation.py` (`RESONATOR_COUNT_MESSAGE`, `BANDWIDTH_NOT_BELOW_CENTER`,
`fbw_untested_warning`, `fbw_impractical_warning`), `bandpass/resonator_math.py`
(`TANK_SETTING_CONFLICT_MESSAGE`), `shared/build_types.py`
(`RESONATOR_AND_COMPONENT_Q_MESSAGE`), `shared/cli_helpers.py`
(`SIM_MATCHED_DEPRECATION_WARNING`), `shared/cli_argument_parsers.py` (`require_count`, used
with the count messages by all three subcommands and the web), `design/option_applicability.py`
(the disabled-control reasons, such as `TEXT_PLOT_NEEDS_TABLE_MESSAGE` and
`LOSS_Q_NOT_SHOWN_MESSAGE`), `design/q_reference_frequency.py` (`Q_FREQUENCY_LABEL`,
`Q_FREQUENCY_HELP`), and `wizard/state_design_inputs.py` (`CSV_WITH_BUILD_MESSAGE`). Error text
names fields in words, never as snake_case.

Whether a wizard or web control applies to the chosen output is decided only by
`design/option_applicability.py`, which restates the CLI's accept/refuse rules and is tested
against them. Extend that rule for a new option or combination; do not add a check, a disabled
state, or a reason text in one interface.
Caveats print once where they apply; JSON and CSV keep every warning entry.

## Machine-Readable Output

- JSON must pass strict serialization with no `NaN`/`Infinity` extension values.
- CSV must be rectangular and use the `csv` module for fields that can contain delimiters.
- Response exports require positive finite frequency values and finite real dB values.
- Requested synthesis targets, calculated response, chosen parts, tolerance cases,
  effective loss, and limitations stay in separate fields.
- When explicit bandpass edges are supplied, `requested_parameters` and build `target` retain
  those parsed values and record `frequency_specification = edge_frequencies`.

## Wizard Architecture

The wizard uses independent Textual `Screen` classes and `push_screen`/`pop_screen`:

```text
Welcome → LP/HP/BP form → Output options → Results
```

`FilterWizardApp.filter_state` owns the one `FilterState` instance. Screens access
`self.app.filter_state`; `FilterState` is data, not a DOM widget, so do not query it with
`query_one`.

Current responsibilities:

- `bandpass_form.py`: BP form parsing and focus/error mapping.
- `build_options.py`: build-field labels, help, parsing, and `BuildConfig` mapping.
- `state_design_inputs.py`: which controls apply (from the shared rule), and the
  `DesignRequest`/`RenderOptions` for the result and for each saved file
  (`document_options`).
- `filter_type_calculators.py`: builds the `DesignRequest` from state and renders through
  `filter_lib.design`.
- `calculation_handler.py`: detached calculation, optional build analysis through
  `filter_lib.design`, and outcome construction.
- `export_formatting.py`: component and response export payloads, rendered by
  `filter_lib.design`.
- `screens/results.py`: background worker lifecycle, revision guard, and save UI.

Every design mutation invalidates prior output. A Results worker calculates from a deep-copied
snapshot and may publish only to the same pending revision. Unmount cancels the worker and
invalidates its result; long work must poll a cancellation check, because a thread worker
cannot be interrupted from outside (see `design(..., should_cancel=...)`, which forwards the
check to the build analysis). Export is enabled only after a complete successful outcome; the
build simulation must be present when requested.

Output options never refuses a combination on submit: controls that cannot apply are disabled
with the shared rule's reason, and the result treats them as unset (the CLI without that flag).
`FilterState` keeps their visible values for the saved files that can use them. A plot is
rendered inside Results; it is not an extra screen.

## File Boundaries

Split a file when doing so creates a real responsibility boundary or makes an invariant easier
to test. Avoid line-count-only refactors. Prefer focused modules for synthesis, verification,
realization, serialization, and UI parsing rather than large cross-layer routers.

## Testing

Run the narrowest relevant test first, then the broad release gates when shared contracts
change. Install the `web` extra first (`uv sync --group dev --extra web`), or the web tests
skip and the coverage gate counts `filter_lib/web/` as uncovered:

```bash
uv run pytest -q tests/test_relevant_module.py
uv run pytest -m runtime_budget
uv run pytest -m "not runtime_budget" --cov=filter_lib --cov-report=term-missing --cov-fail-under=90
uv run ruff check .
uv run ruff format --check .
uv lock --check
uv build
```

Important regression layers include:

- hand/reference calculation fixtures and topology duality;
- the 128-cell independent bandpass acceptance matrix;
- analytic and Decimal-fallback nodal-solver cases;
- strict JSON, rectangular CSV, build, and generic SPICE contracts;
- toroid provenance and winding math;
- Textual unit tests and real `run_test()` pilot flows;
- source archive, wheel contents, and installed-wheel smoke tests;
- Python 3.10 through 3.13.

Do not hide a failing gate or reduce coverage to land a change.

## Documentation

Update documentation only when behavior, setup, architecture, public contracts, or maintainer
decisions change. Verify commands execute as written, schema examples use real field names, and
claims match the final test/build evidence. Historical changelog entries remain historical;
new reality belongs in the newest release entry and current reference documents.
