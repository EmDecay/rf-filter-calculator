# Codebase Summary

**Last updated:** October 8, 2026
**Version:** 2.3.0

RF Filter Calculator is a Python 3.10+ command-line, Textual TUI, and local web application for
synthesizing lowpass, highpass, and coupled-resonator bandpass LC filters. The current
design explicitly separates calculated values, selected physical parts, estimated loss,
and simulated build behavior.

## Current status

- More than 4,500 collected pytest cases
- 90% minimum coverage enforced in CI
- Ruff lint and format gates
- Full test matrix on Python 3.10–3.13
- Wheel and source-distribution inspection plus installed-wheel smoke test
- One required runtime dependency, Textual; the optional `web` extra adds FastAPI, uvicorn,
  Jinja2, and python-multipart for the browser UI

## Entry points

- Installed command: `filter-calc` → `filter_lib.cli:main`
- Source shim: `filter-calc.py`
- No arguments: launches `filter_lib.wizard.FilterWizardApp`
- `filter-calc web`: `filter_lib/cli/web_cmd.py` serves `filter_lib.web.create_app` with
  uvicorn
- Version: dynamically read from `filter_lib.__version__`

## Package layout

```text
filter_lib/
├── cli/            argparse setup, category handlers, mode validation, web launcher
├── design/         shared request → synthesis/build analysis → render/export path
├── lowpass/        LP public calculations, transfer, and display facades
├── highpass/       HP public calculations, transfer, and display facades
├── bandpass/       calibrated Top-C synthesis and independent verification
├── shared/         realization, solver, build analysis, outputs, parsing, plots
├── wizard/         Textual screens, state, calculation workers, exports
└── web/            FastAPI app, form parsing, bounded execution, SVG plot, templates
```

### Design service

`filter_lib/design/` is the orchestration every surface calls; see
[system-architecture.md](system-architecture.md#shared-design-service) for why.

- `design_request.py` — `DesignRequest` (including `allow_sub_pf`) and the cross-field rules
  every surface enforces
- `design_service.py` — `design()`, `synthesize()`, `with_build_analysis()`, and
  `apply_sub_pf_policy` (combines the request and `BuildConfig` sub-pF switches)
- `render_options.py`, `render.py` — `RenderOptions` and `render_lines` for table, quiet,
  JSON, and CSV; shared surface messages such as `BUILD_NEEDS_ESERIES_MESSAGE`
- `export.py` — `export_spice`, `export_response_data`, and `response_series`
- `option_applicability.py` — the one rule for which output and build options apply to a set of
  choices (`inapplicable_options`, `option_reason`, `require_applicable`) and which a
  download or saved file uses (`document_options`, `DOCUMENT_FORMATS`, `document_reason`,
  `RESPONSE_DOCUMENTS`), with the reasons the wizard and web show next to a disabled control
- `q_reference_frequency.py` — label, help, and parser for the build simulation's
  "Frequency at which the Q values apply", shared by the wizard and web

The CLI maps its flags in `cli/design_output_args.py`; the wizard maps `FilterState` in
`FilterState.to_design_request` and `to_render_options` (`wizard/state_design_inputs.py`).

### Web UI

- `app.py` — app factory, lifespan-owned calculation pool, error handlers, headers
- `form_parsing.py`, `build_form_parsing.py`, `form_values.py` — form fields to request,
  options, and build configuration; refuses an option the shared rule disables
- `option_states.py` — the shared applicability rule tabulated for the page's script
- `download_inputs.py` — `download_fields`: the result's snapshot plus each disabled
  control's visible value that applies to the download
- `execution.py` — bounded pool with timeout and cancellation
- `request_guard.py` — same-origin and Host check applied to every request
- `routes_pages.py`, `routes_design.py`, `routes_export.py` — page, design, and download
  routes
- `svg_plot.py` — SVG response chart
- `templates/`, `static/` — Jinja2 partials, tokens and stylesheet, vendored HTMX with its
  license

### Lowpass and highpass

Lowpass calculation functions return `(capacitors, inductors, order)` and highpass ones
`(inductors, capacitors, order)`. Shared
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

`shared/eseries.py` supports E12, E24, and E96 standard capacitor values. The series name
gives values per decade, not tolerance. Each capacitor gets one choice: a single part within
1%, otherwise a parallel pair only when it is at least 0.5 percentage points closer. Below
1 pF no part is chosen unless `DesignRequest.allow_sub_pf` (`--allow-sub-pf`, wizard/web
**Allow capacitors below 1 pF**) is set; the warning names that option.

Inductors are not E-series matched. Toroid winding suggestions use only primary-sourced
T25-6, T50-2, and T68-2 entries. Other vendored legacy records remain inspectable but are
not eligible for automatic suggestion. Selection checks frequency guidance, whole-turn
error within the `A_L` tolerance, and winding capacity; it does not check RF Q, SRF, core
loss, saturation, heating, or power.

## Build simulation

`--sim-build` (user-facing name: build simulation) creates a named circuit from the chosen
parts: standard capacitors, whole-turn toroid windings where available, and explicit
exact-value fallbacks ("calculated value used"). Optional inputs add:

- separate simulation source and load resistances;
- capacitor and inductor tolerances;
- inductor/capacitor Q at the frequency where the Q values apply;
- fixed tolerance cases (all low, all high, each part low and high alone);
- repeatable extra random tolerance cases;
- the initial number of frequency points, with bounded automatic measurement refinement.

The AC nodal solver reports transducer power gain and uses scale-normalized log-polar
admittances. LP/HP output reports a category-appropriate cutoff; BP reports lower and
upper edges, center, and bandwidth. Tolerance cases show spread; they are not yield,
probability, guaranteed worst case, or measured performance. Bandpass text uses the table
part names via `circuit_display_names.py`; SPICE and JSON keep `CT1`/`LT1`/`CK1`/`CIN`/`COUT`.

Response accuracy owners are [build_response.py](../filter_lib/shared/build_response.py),
[response_refinement.py](../filter_lib/shared/response_refinement.py), and
[model_diagnostics.py](../filter_lib/bandpass/model_diagnostics.py). The
[user guide](user-guide.md#interpreting-response-measurements) explains convergence, region
selection and model-comparison limits; [accuracy tests](../tests/test_response_accuracy.py)
provide independent circuit evidence.

`--sim-matched` is retained as a deprecated compatibility alias for the simpler
ideal-versus-chosen-parts comparison. New integrations should use `--sim-build`.

## Output surfaces

| Surface | Notes |
|---|---|
| Table | Human-oriented circuit, values, standard-value choices, warnings, plots, optional build-simulation block |
| JSON | Strict finite JSON with explicit requested/calculated/nominal/simulated semantics |
| CSV | Quoted rectangular component rows; best toroid suggestion only |
| SPICE | Generic deck (`exact` calculated values or `nominal-build` chosen parts) from the shared named circuit; BP decks add a `* names:` map |
| Plot data | Shared JSON/CSV response schema; analytic LP/HP, nodal BP |
| Wizard save | Component export plus independent optional response-data sidecar |
| Web UI | The CLI's text in the page, optional SVG response graph, and downloads byte-identical to the CLI |

Unsupported option/output combinations are rejected by the CLI rather than silently ignored.
Examples include E-series flags (and `--allow-sub-pf`) with raw/quiet/plot-data/exact-SPICE
output and toroid detail flags outside table mode. The wizard and web disable the matching
controls, with the reason, from `design/option_applicability.py`.

## Important shared modules

### Input and output

- `parsing.py` — frequency, impedance, and inductance parsing
- `cli_argument_parsers.py`, `cli_*_validation.py` — reusable CLI contracts
- `formatting.py` — finite SI/scientific rendering
- `strict_json.py` — non-finite-tree rejection and JSON serialization
- `display_common.py`, `lp_hp_display.py` — common table/JSON/CSV presentation
- `display_helpers.py` — shared `SECTION_RULE`, E-series section heading/note, and `Use:` rows
- `toroid_display.py` — toroid winding suggestion text/JSON/CSV; the table section shared by
  CLI and wizard
- `circuit_display_names.py` — maps bandpass circuit names to table names (CT1→Cp1, CK1→Cs12,
  CIN→Ce_in) for readable text and the SPICE `* names:` comment
- `response_export.py` — standalone response schema

### Mathematics and circuits

- `lp_hp_base_calculations.py` — shared ladder denormalization
- `chebyshev_g_calculator.py` — formula-based prototypes
- `numeric.py` — log-domain finite-result helpers
- `physical_input_limits.py` — accepted component-Q and port-resistance ranges, with the
  reasons for them
- `circuit_model.py`, `circuit_builders.py` — named passive networks
- `branch_admittance.py`, `nodal_solver.py`, `decimal_nodal_solver.py` — stable AC solver
  and its high-precision fallback
- `response_measurement.py` — cutoff/passband measurements

### Realization and analysis

- `component_realization.py`, `nominal_realization.py`
- `toroid_core_data.py`, `toroid_inductance.py`, `toroid_selection.py`, `toroid_wire.py`
- `build_loss_models.py`, `tolerance_screening.py`, `build_analysis.py`
- `build_output*.py`, `spice_export.py`

## Wizard structure

The wizard uses independent Textual screens:

```text
Welcome → Lowpass/Highpass/Bandpass form → Output options → Results
```

`FilterState` is the single state owner and holds each control's visible value;
`state_design_inputs.py` (`DesignInputsMixin`) decides from the shared rule what the result and
each saved file use. Calculation workers publish through revisioned outcomes so an
older/cancelled worker cannot replace a newer result. Results are not exportable while pending
or after failure. Component format selection and response-data sidecar selection are separate.

## Package and repository files

- `pyproject.toml` — setuptools build, dynamic version, dependency and tool settings
- `uv.lock` — locked resolution
- `.github/workflows/ci.yml` — quality, Python matrix, core-install, packaging/smoke jobs
- `filter_lib/shared/toroid_core_data.json` — packaged toroid data
- `filter_lib/wizard/styles.tcss` — packaged wizard stylesheet
- `filter_lib/web/templates/`, `filter_lib/web/static/` — packaged web templates and assets
- `tests/wheel_smoke.py` — isolated installed-wheel smoke check
- `plans/` — ignored implementation work records when a broad change needs a plan

## Engineering boundaries

- Numerical representability is not physical buildability.
- Ideal responses omit layout, package parasitics, transmission-line effects, and
  component self-resonance.
- Q-based loss uses a stated-frequency constant series-resistance model.
- Toroid results are winding suggestions, not RF/power suitability claims.
- Generic SPICE decks need simulator- and component-model-specific refinement for final
  hardware prediction.
- A VNA measurement of the assembled filter remains the acceptance test.

See [system-architecture.md](system-architecture.md) for data flow,
[testing.md](testing.md) for gates, and
[caveats-and-known-issues.md](caveats-and-known-issues.md) for practical limitations.
