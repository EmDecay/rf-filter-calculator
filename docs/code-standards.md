# Code Standards and Architecture Guidelines

**Last updated:** July 19, 2026

This document records the conventions that matter for the current calculator. Follow the
repository-level `AGENTS.md`, then these project-specific rules and nearby code patterns.

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

LP/HP calculation functions return a tuple:

```python
capacitors, inductors, order = calculate_butterworth(
    cutoff_hz, impedance, num_components, topology
)
```

The CLI and wizard assemble the user-facing result dictionaries. Bandpass synthesis returns a
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
- `filter_lib/cli/`: argument definitions and thin command orchestration.
- `filter_lib/wizard/`: Textual screens, shared state, calculation orchestration, and export.

Keep calibrated synthesis separate from validation. The bandpass calibration sweep may place
the skirts; `response_verification.py` independently checks skirts, connected regions, shape,
and representative stopband samples. Do not replace `response_validation_status` with a
blanket support claim.

Named circuits are the common physical contract for build analysis and SPICE. A selected
parallel capacitor remains two branches. An unavailable or policy-refused nominal part is an
explicit exact fallback with warnings, never a fabricated physical part.

## E-Series Policy

E12/E24/E96 names describe preferred-value density, not tolerance. Automatic preferred-value
selection applies to capacitors only:

- keep a single part when absolute error is at most 1%;
- select a two-part parallel combination only when it improves absolute error by at least
  0.5 percentage points;
- below 1 pF, require explicit expert action rather than silently selecting a sub-pF value.

Table, JSON, CSV, wizard, nominal realization, and SPICE must agree on the selected policy
result. Inductors remain calculated/wound values or screened integer-turn toroid candidates.

## Toroid Data and Claims

Automatic screening uses only exact parts marked primary-source verified in
`toroid_core_data.json`. Legacy records remain inspectable but are not auto-selected. Preserve
source IDs and field provenance whenever data changes.

A candidate screen may evaluate material-frequency guidance, integer turns, nominal error,
published winding capacity, wire length, and DC resistance. It must not be labeled as a
prediction of RF Q, SRF, core loss, saturation, thermal rise, or power handling.

## Build Analysis and SPICE

`BuildConfig`, nominal realization, and tolerance screening are public contracts:

- selected nominal parts and exact fallbacks remain auditable;
- Q is converted to constant series resistance at a stated reference frequency;
- a custom loss reference without an effective Q is rejected;
- deterministic corners and seeded bounded samples are not measurements, probabilities,
  yields, or guaranteed worst cases;
- all reported gain is transducer power gain with explicit source/load ports.

Generic SPICE export has two realizations: `exact` and `nominal_build` (the CLI default). The
printed `vm(load)` trace is load voltage, not gain in dB; deck comments state the transducer
gain expression.

## Machine-Readable Output

- JSON must pass strict serialization with no `NaN`/`Infinity` extension values.
- CSV must be rectangular and use the `csv` module for fields that can contain delimiters.
- Response exports require positive finite frequency values and finite real dB values.
- Requested synthesis targets, calculated response, selected nominal build, tolerance cases,
  effective loss, and limitations stay in separate fields.
- When explicit bandpass edges are supplied, `requested_parameters` and build `target` retain
  those parsed values and record `frequency_specification = edge_frequencies`.

## Wizard Architecture

The wizard uses independent Textual `Screen` classes and `push_screen`/`pop_screen`:

```text
Welcome → LP/HP/BP form → Output Options → Results
```

`FilterWizardApp.filter_state` owns the one `FilterState` instance. Screens access
`self.app.filter_state`; `FilterState` is data, not a DOM widget, so do not query it with
`query_one`.

Current responsibilities:

- `bandpass_form.py`: BP form parsing and focus/error mapping.
- `build_options.py`: wizard/engine build-control mapping and compatibility checks.
- `filter_type_calculators.py`: category-specific calculation and primary formatting.
- `calculation_handler.py`: detached calculation orchestration and outcome construction.
- `export_formatting.py`: component and response export payloads.
- `screens/results.py`: background worker lifecycle, revision guard, and save UI.

Every design mutation invalidates prior output. A Results worker calculates from a deep-copied
snapshot and may publish only to the same pending revision. Unmount cancels the worker and
invalidates its result. Export is enabled only after a complete successful outcome; build
analysis must be present when requested.

The wizard allows raw table rows with an E-series only when realized-build analysis consumes
that series for nominal selection. Quiet mode remains incompatible with hidden build/match
results. A plot is rendered inside Results; it is not an extra screen.

## File Boundaries

Split a file when doing so creates a real responsibility boundary or makes an invariant easier
to test. Avoid line-count-only refactors. Prefer focused modules for synthesis, verification,
realization, serialization, and UI parsing rather than large cross-layer routers.

## Testing

Run the narrowest relevant test first, then the broad release gates when shared contracts
change:

```bash
uv run pytest -q tests/test_relevant_module.py
uv run pytest --cov=filter_lib --cov-report=term-missing --cov-fail-under=90
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
