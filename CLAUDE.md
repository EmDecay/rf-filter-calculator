# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

```bash
# Install dependencies (runtime only)
uv sync

# Install with dev tools (pytest, ruff); add --extra web for the browser UI and its tests
uv sync --group dev --extra web

# Run the tool
uv run filter-calc lowpass butterworth pi 10MHz -n 5
uv run filter-calc lp bw pi 10MHz --format json     # short aliases (lp/hp/bp); json/csv output
uv run filter-calc bp bw top -f 10MHz -b 500kHz --sim-build --format json
uv run filter-calc lp bw pi 10MHz --format spice --spice-realization nominal-build
uv run filter-calc                  # starts interactive wizard
uv run filter-calc web              # browser UI on 127.0.0.1:8765 (needs the optional web dependencies: --extra web)

# Tests
uv run pytest tests/ -v             # all tests
uv run pytest tests/test_lowpass_calculations.py -v   # single file
uv run pytest tests/ -k "test_butterworth"            # by name pattern
uv run pytest tests/ --cov=filter_lib --cov-report=term-missing  # with coverage
uv run pytest tests/ --cov=filter_lib --cov-report=json:/tmp/rf-cov.json  # JSON for gap analysis

# Linting
uv run ruff check .                 # lint
uv run ruff format --check .        # format check
uv run ruff format .                # auto-format
```

## Reports

`plans/` is gitignored — session reports written to `plans/reports/` are local-only and won't show up in `git status`.

## Architecture

Python 3.10+ CLI tool for calculating LC filter component values. Entry point is `filter_lib.cli:main` (registered as `filter-calc` script). No arguments launches a Textual TUI wizard; `filter-calc web` serves a FastAPI + HTMX browser UI from the optional `web` extra.

### Package layout (`filter_lib/`)

- **`cli/`** — argparse subcommands (`lowpass_cmd`, `highpass_cmd`, `bandpass_cmd`, `wizard_cmd`, `web_cmd`). Each has `setup_parser()` and `run()`. LP/HP share `ladder_command.py`. `web_cmd` imports FastAPI/uvicorn only inside `run()`; keep it that way so the core install never needs the extra.
- **`design/`** — the only orchestration path: `DesignRequest` → `design()` → `render_lines` / `export_spice` / `export_response_data`. CLI, wizard, and web all call it. `option_applicability.py` is the shared rule for which output/build options apply (see below); `q_reference_frequency.py` holds the Q-frequency label/help/parser both UIs use.
- **`web/`** — FastAPI app (`create_app`), form parsing, bounded `CalculationRunner`, SVG plot, Jinja2 templates, vendored HTMX. Output shown or downloaded must stay byte-identical to the CLI. `option_states.py` tabulates the applicability rule for `static/app.js` (never restate the rule in JS); downloads post the result's snapshot form and `download_inputs.py::download_fields` adds the `visible.<name>` values that apply. The build toroid box is `toroid_build` (ticked by default); `no_toroid_build=on` is still accepted.
- **`lowpass/`**, **`highpass/`** — Thin wrappers over shared base. Each has `calculations.py`, `transfer.py`, `display.py`.
- **`bandpass/`** — Coupled resonator design. Has its own calculation, transfer, display, formatters, diagrams, and g-value modules. `display.py::format_table_lines` is the single BP table renderer for CLI and wizard; never add a wizard-side BP formatter.
- **`wizard/`** — Textual TUI. `app.py` drives screens in `screens/` (welcome → filter config → output options → results). `state.py` holds the `FilterState` dataclass shared across screens; it stores every control's visible value, and `state_design_inputs.py::DesignInputsMixin` builds the result from `applied_options()` and each saved file from `document_options()`. Labels, choice order, and defaults match the web form (`tests/test_wizard_web_alignment.py`).
- **`shared/`** — Core logic shared across filter types:
  - `lp_hp_base_calculations.py` — Strategy pattern: LP and HP share calculation code, differing only in component formulas (`cap_formula`/`ind_formula` callables) and ordering.
  - `eseries.py` — E12/E24/E96 capacitor selection. A single part is selected within 1%; a parallel pair is selected only when it improves absolute error by at least 0.5 percentage points. Below 1 pF no part is chosen unless `DesignRequest.allow_sub_pf` is set (CLI `--allow-sub-pf`, wizard/web "Allow capacitors below 1 pF" = `SUB_PF_OPTION_LABEL`); `design()` applies it to every `MatchPolicy` (OR-ed with an explicit `BuildConfig.match_policy.allow_sub_pf`, never overwritten), so table, CSV, JSON, build simulation, and chosen-parts SPICE agree. E-series names describe values per decade, not part tolerance.
  - `plotting.py` + `plot_*.py` — ASCII frequency response, zoom pairs, threshold analysis (split per GH-7); response-data export lives in `response_export.py`.
  - `parsing.py` — Flexible frequency/impedance parsing (`10MHz`, `10M`, `10e6`, etc.). Impedance also accepts k/M suffixes.
  - `constants.py` — Bessel g-value lookup tables. Chebyshev g-values computed by formula (see `chebyshev_g_calculator.py`).
  - `chebyshev_g_calculator.py` — Arbitrary Chebyshev ripple (0, 3.0] dB support via formula-based g-value computation (exact dB→neper conversion: 40/ln(10)).
  - `nodal_solver.py`, `netlist_simulation.py`, and `netlist_builders.py` — Named passive circuits, scale-safe AC nodal analysis, transducer power gain, and response landmarks.
  - `response_export.py` — Unified --plot-data schema for LP/HP/BP (replaces divergent implementations).
  - `build_*.py`, `component_realization.py`, and `nominal_realization.py` — the build simulation (user-facing name): ideal values versus chosen parts, part losses (Q), separate simulation source/load resistance, fixed tolerance cases (all low, all high, each part alone), and optional seeded extra random cases. `circuit_display_names.py` maps bandpass circuit names (CT1/LT1/CK1/CIN/COUT) to table names (Cp1/L1/Cs12/Ce_in/Ce_out) for readable text and the SPICE `* names:` comment; SPICE element names and JSON stay unchanged. `--sim-matched` is a deprecated facade over this implementation; use `--sim-build`.
  - `lp_hp_display.py` — Single LP/HP table renderer used by CLI and wizard.
  - `toroid_*.py` + `toroid_core_data.json` — Primary-sourced integer-turn and winding-capacity screening. Only T25-6, T50-2, and T68-2 currently qualify for automatic suggestions. The output explicitly does not check RF Q, core loss, SRF, saturation, heating, or power handling (`toroid_selection.NOT_ASSESSED_WARNING`).

Full module map: `docs/codebase-summary.md`.

### Key design patterns

- **One orchestration path**: new surfaces and inputs go through `filter_lib.design`; never call `calculate_*`, category `format_*`, or `analyze_build` from `cli/`, `wizard/`, or `web/`. A rule every surface must enforce belongs in `DesignRequest` or `RenderOptions`, with the message copied verbatim from the CLI.
- **Shared user-facing text**: one message constant or helper per rule; import it, never restate it (e.g. `design/render_options.py` `BUILD_NEEDS_ESERIES_MESSAGE`/`SUB_PF_NEEDS_ESERIES_MESSAGE`/`shows_design_warnings`, `shared/cli_aliases.py` `RIPPLE_RANGE_MESSAGE`/`COMPONENT_COUNT_MESSAGE`/`chebyshev_odd_count_message`, `bandpass/input_validation.py` `RESONATOR_COUNT_MESSAGE`/`fbw_untested_warning`/`fbw_impractical_warning`; full list in `docs/code-standards.md#user-facing-text`). Use plain terms (build simulation, chosen parts, toroid winding suggestions, response check, tolerance cases); never "realized", "nominal build", "screened", "expert override". JSON keys/enums, CSV columns, flags, and choice values (`nominal-build`) keep their names. Errors name fields in words, not snake_case.
- **Option applicability**: whether a wizard or web control applies to the chosen output is decided only by `design/option_applicability.py` (`inapplicable_options`, `require_applicable`, `document_options`). Both UIs disable such a control with the rule's reason and treat it as unset (= CLI flag left out); the web server refuses it in hand-made requests. A disabled build never runs for the wizard's result: a saved JSON that uses it is calculated on Save in its own worker, like the web's JSON download. The rule mirrors the CLI validators and is tested against every combination. Extend that rule for a new option; never add a UI-specific check or reason.
- **CLI spellings**: `-f/--frequency/--freq` on all three subcommands (`FREQUENCY_FLAGS`); `-n` is range-checked in `run()` with `require_count` and the shared count message (exit 1), not argparse choices; `--spice-realization calculated|chosen-parts` resolve to `exact|nominal-build` at parse time via `shared/cli_aliases.py::SPICE_REALIZATION_ALIASES`.
- **LP/HP duality**: Lowpass and highpass use the same base calculation functions with different formulas injected (LP: `C=g/(Z*ω)`, `L=g*Z/ω`; HP: inverse). Topology (Pi/T) controls shunt vs series placement.
- **Filter-type alias canonicalization**: `shared/cli_aliases.py::FILTER_TYPE_ALIASES` is the single source of truth (`bw/b`→butterworth, `ch/c`→chebyshev, `bs`→bessel). Any new dispatch code must consult it rather than re-implement — see `shared/transfer_response_dispatch.py::_canonicalize_filter_type`.
- **Filter results**: lowpass calculation functions return `(capacitors, inductors, order)`; highpass ones return `(inductors, capacitors, order)`. `filter_lib.design` builds the result dict from either. Bandpass returns calibrated component values plus `synthesis_validation`, `response_validation_status`, Q-model metadata, and warnings. `q_min`/`q_safety` are compatibility heuristics, not stability or build-selection criteria. Build JSON keeps requested target, calculated response, chosen parts or explicit exact fallbacks, tolerance cases, and the effective loss model separate.
- **Bandpass -3 dB edges**: True edges come from solving `(f²-f0²)/(BW·f) = ±1`, not `f0 ± bw/2`. Source of truth: `bandpass.calculations.compute_bandpass_3db_edges` (uses `f_low = f0²/f_high` to dodge catastrophic cancellation for wide BW).
- **Chebyshev BP 3 dB semantics**: `bw` is the true requested −3 dB bandwidth. The raw Top-C design is calibrated against a circuit sweep rather than relying only on a prototype scaling equation. Source modules are `bandpass/top_c_calibration.py`, `bandpass/response_verification.py`, and `bandpass/ideal_response.py`.
- **Chebyshev constraints**: LP, HP, and BP require odd order (3/5/7/9) for equal terminations and `0 < ripple <= 3.0 dB` across CLI, wizard, and public synthesis APIs.
- **Bandpass end-coupling**: External Q is set by series end capacitors. Tank inductance or tank impedance can be chosen independently from the equal design terminations. Shunt/bottom coupling is unsupported.
- **Bandpass validation**: Top-C is the only coupling topology. The maintained 128-cell matrix spans 1%, 2%, 5%, and 10% FBW: 106 cells are validated, 17 return `outside_validated_envelope` (table: `Response Check: Not confirmed`), and 5 known-unrealizable cells are rejected. Do not replace per-design status with a blanket ≤10% claim. Calibration solver failures surface as one plain `calibration_failure_message` with the solver reason on `__cause__`. Bandpass design warnings print once: inside the table for table output, on stderr otherwise (`shows_design_warnings`).
- **Toroid winding suggestions**: Default table output shows the best suggestion, `--toroid-full` shows up to three, JSON includes up to three, and CSV carries the best available one. A requested detail count is not a guarantee that enough qualified cores exist. The wizard and web offer "Best, detailed" (default), "Up to 3, detailed" (`--toroid-full`), "Best, one line" (`--toroid-compact`), and "None" (`--no-toroids`); `FilterState.toroid_detail` is `best`/`full`/`compact`/`none` and the web field `toroids` uses the same values. The CLI and wizard share `shared/toroid_display.py::format_winding_candidate_section`.

## Ruff config

Target: py310, line-length 100, rules: E/F/I/UP/B. Ignores: E501 (formatter handles), B905 (zip without strict=). Tests ignore E501.

## Validation convention

Public numeric inputs reject booleans, wrong types, NaN/infinity, and arbitrary-size integers
outside binary64 before checking the application-specific sign or range. Use
`filter_lib.shared.numeric.is_finite_real` or the shared `require_*` validators; do not call bare
`math.isfinite` on untrusted public input because it can leak `TypeError` or `OverflowError`.
Invalid public input must raise a clear `ValueError`. Exact integer inputs likewise reject
booleans and floats.

Component-Q and source/load-resistance ranges are owned by `shared/physical_input_limits.py`. A new Q or port input must call `require_component_q` or `require_port_resistance`; never restate the range elsewhere.

## CI

GitHub Actions (`.github/workflows/ci.yml`) runs Ruff, coverage-gated tests on Python 3.10–3.13 with the `web` extra, a core-install job without it (web tests skip; `filter-calc web` must print the install hint), source/wheel builds, archive inspection, and installed-wheel smoke tests on push/PR to `main`.

## Testing wizard screens

Wizard Textual screens are testable without a running app: mock widgets with `Mock(spec=RadioSet)`, install the stub app with `monkeypatch.setattr(type(screen), "app", property(...))` so the class-level override is undone after the test, then call the screen method directly. Pattern lives in `tests/test_wizard_design_screens.py::_mount`. Widget ids and focus chains are only proven by mounted `App.run_test()` journeys (`tests/test_wizard_design_screen_journeys.py`, `tests/test_wizard_output_option_journeys.py`); keep those few and use them where compose/event-loop behavior matters.

## Testing CLI subcommands

CLI tests build `argparse.Namespace` directly via `_lp_args()/_hp_args()/_bp_args()` helpers in `tests/test_cli_and_helpers.py` — pass overrides as kwargs to exercise validation branches without re-parsing argv. To exercise `setup_parser()` wiring, instantiate a plain `argparse.ArgumentParser()` and call `setup_parser(parser)` then `parser.parse_args([...])`.

Every line starting with `uv run filter-calc` in `README.md` or `docs/*.md` is executed by `tests/test_cli_documented_examples.py`. A doc example must run exactly as written; write syntax templates with `<...>` or `[...]` placeholders so they are skipped. `wizard`/`w`/`web` lines are skipped because they never return. Top-level `--help` examples are also executed (`tests/test_cli_help_accuracy.py`), so do not add a `web` example there.

## Testing the web UI

Web tests start with `pytest.importorskip("fastapi")` and use `tests/web_helpers.py::web_client(**settings)`, which runs the app lifespan so the calculation pool is joined on exit. A raw `TestClient` needs `base_url=BASE_URL`: the request guard refuses the default `testserver` host on a loopback bind. Compare against live CLI output via `tests/cli_parity_helpers.py` (`cli_stdout`, `cli_error_message`), never fixtures. A fake slow analysis must be bounded so a cancellation regression fails instead of hanging.

## Netlist-Simulation Testing

Bandpass acceptance lives in `tests/test_netlist_simulation.py`. It checks requested skirts, connected/outer −3 dB regions, passband and stopband shape, ripple, and explicit unsupported cells. The harness builds the prescribed circuit and solves it with the stdlib AC nodal-analysis implementation; no external SPICE installation is required for these tests.

## Patching lazy imports

`wizard/interactive.py::run_wizard` imports `FilterWizardApp` lazily inside the function body. To mock it, patch at the definition site: `patch("filter_lib.wizard.app.FilterWizardApp")` — not at `filter_lib.wizard.interactive.FilterWizardApp` (the name doesn't exist until the function runs).
