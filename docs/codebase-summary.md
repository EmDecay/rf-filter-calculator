# Codebase Summary

**Last updated:** July 19, 2026
**Version:** 2.1.0

RF Filter Calculator is a Python 3.10+ command-line and Textual TUI application for
synthesizing lowpass, highpass, and coupled-resonator bandpass LC filters. The current
design explicitly separates calculated values, selected physical parts, estimated loss,
and simulated build behavior.

## Current status

- More than 2,000 collected pytest cases
- 90% minimum coverage enforced in CI
- Ruff lint and format gates
- Full test matrix on Python 3.10–3.13
- Wheel and source-distribution inspection plus installed-wheel smoke test
- One runtime dependency: Textual

## Entry points

- Installed command: `filter-calc` → `filter_lib.cli:main`
- Source shim: `filter-calc.py`
- No arguments: launches `filter_lib.wizard.FilterWizardApp`
- Version: dynamically read from `filter_lib.__version__`

## Package layout

```text
filter_lib/
├── cli/            argparse setup, category handlers, mode validation
├── lowpass/        LP public calculations, transfer, and display facades
├── highpass/       HP public calculations, transfer, and display facades
├── bandpass/       calibrated Top-C synthesis and independent verification
├── shared/         realization, solver, build analysis, outputs, parsing, plots
└── wizard/         Textual screens, state, calculation workers, exports
```

### Lowpass and highpass

LP/HP public calculation functions return `(capacitors, inductors, order)`. Shared
strategy modules provide prototype scaling and analytic magnitude responses. Supported
topologies are Pi and T; supported response types are Butterworth, Chebyshev, and Bessel.

Chebyshev g-values are computed from formula for ripple in `(0, 3]` dB. With equal source
and load terminations, Chebyshev order must be odd. The LP/HP cutoff is its ripple-band
edge, while the −3 dB crossing lies beyond it.

### Bandpass

Bandpass supports Top-C series coupling only. The engine:

1. computes the prototype and initial coupling values;
2. calibrates tank frequency and synthesis fractional bandwidth against a passive nodal
   circuit;
3. independently verifies both −3 dB skirts and response shape;
4. returns requested, internal-synthesis, Q-model, and validation metadata.

The 128-cell support study is encoded in tests, but every generated design carries its
own `response_validation_status`. Bessel's flat-delay property applies only to the
lowpass prototype; transformed HP/BP phase is not claimed without external verification.

## Physical-part realization

`shared/eseries.py` supports E12, E24, and E96 capacitor preferred values. The series name
describes density, not tolerance. Default policy selects one part within 1%, otherwise a
parallel pair only when it improves absolute error by at least 0.5 percentage points. A
target below 1 pF reports expert action instead of silently selecting a part.

Inductors are not E-series matched. The optional toroid screen uses only primary-sourced
T25-6, T50-2, and T68-2 entries. Other vendored legacy records remain inspectable but are
not eligible for automatic recommendation. The screen checks frequency guidance,
integer-turn error, `A_L` tolerance, and winding capacity; it does not assess RF Q, SRF,
core loss, saturation, thermal rise, or power.

## Realized-build analysis

`--sim-build` creates a named nominal circuit from selected capacitors, screened integer
turn windings where available, and explicit exact-value fallbacks. Optional inputs add:

- independently specified source and load resistances;
- capacitor and inductor tolerance bounds;
- inductor/capacitor Q at an explicit loss-reference frequency;
- deterministic corners;
- repeatable seeded bounded samples;
- selectable analysis-grid size.

The AC nodal solver reports transducer power gain and uses scale-normalized log-polar
admittances. LP/HP output reports a category-appropriate cutoff; BP reports lower and
upper edges, center, and bandwidth. Screening results are engineering cases, not yield,
probability, guaranteed worst case, or measured performance.

`--sim-matched` is retained as a deprecated compatibility alias for the simpler nominal
comparison. New integrations should use `--sim-build`.

## Output surfaces

| Surface | Notes |
|---|---|
| Table | Human-oriented circuit, values, policy decisions, warnings, plots, optional build block |
| JSON | Strict finite JSON with explicit requested/calculated/nominal/simulated semantics |
| CSV | Quoted rectangular component rows; best eligible toroid only |
| SPICE | Generic exact or nominal-build passive deck from the shared named circuit |
| Plot data | Shared JSON/CSV response schema; analytic LP/HP, nodal BP |
| Wizard save | Component export plus independent optional response-data sidecar |

Unsupported option/output combinations are rejected rather than silently ignored.
Examples include E-series flags with raw/quiet/plot-data/exact-SPICE output and toroid
detail flags outside table mode.

## Important shared modules

### Input and output

- `parsing.py` — frequency, impedance, and inductance parsing
- `cli_argument_parsers.py`, `cli_*_validation.py` — reusable CLI contracts
- `formatting.py` — finite SI/scientific rendering
- `strict_json.py` — non-finite-tree rejection and JSON serialization
- `display_common.py`, `lp_hp_display.py` — common table/JSON/CSV presentation
- `response_export.py` — standalone response schema

### Mathematics and circuits

- `lp_hp_base_calculations.py` — shared ladder denormalization
- `chebyshev_g_calculator.py` — formula-based prototypes
- `numeric.py` — log-domain finite-result helpers
- `circuit_model.py`, `circuit_builders.py` — named passive networks
- `branch_admittance.py`, `nodal_solver.py` — stable AC solver
- `response_measurement.py` — cutoff/passband measurements

### Realization and analysis

- `component_realization.py`, `nominal_realization.py`
- `toroid_core_data.py`, `toroid_inductance.py`, `toroid_selection.py`, `toroid_wire.py`
- `build_loss_models.py`, `tolerance_screening.py`, `build_analysis.py`
- `build_output*.py`, `spice_export.py`

## Wizard structure

The wizard uses independent Textual screens:

```text
Welcome → Lowpass/Highpass/Bandpass form → Output Options → Results
```

`FilterState` is the single state owner. Calculation workers publish through revisioned
outcomes so an older/cancelled worker cannot replace a newer result. Results are not
exportable while pending or after failure. Component format selection and response-data
sidecar selection are separate.

## Package and repository files

- `pyproject.toml` — setuptools build, dynamic version, dependency and tool settings
- `uv.lock` — locked resolution
- `.github/workflows/ci.yml` — quality, Python matrix, packaging/smoke jobs
- `filter_lib/shared/toroid_core_data.json` — packaged toroid data
- `filter_lib/wizard/styles.tcss` — packaged wizard stylesheet
- `tests/wheel_smoke.py` — isolated installed-wheel smoke check
- `plans/` — ignored implementation work records when a broad change needs a plan

## Engineering boundaries

- Numerical representability is not physical buildability.
- Ideal responses omit layout, package parasitics, transmission-line effects, and
  component self-resonance.
- Q-based loss uses a stated-frequency constant series-resistance model.
- Toroid results are screened winding candidates, not RF/power suitability claims.
- Generic SPICE decks need simulator- and component-model-specific refinement for final
  hardware prediction.
- A VNA measurement of the assembled filter remains the acceptance test.

See [system-architecture.md](system-architecture.md) for data flow,
[testing.md](testing.md) for gates, and
[caveats-and-known-issues.md](caveats-and-known-issues.md) for practical limitations.
