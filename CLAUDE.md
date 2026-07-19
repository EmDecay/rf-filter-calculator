# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

```bash
# Install dependencies (runtime only)
uv sync

# Install with dev tools (pytest, ruff)
uv sync --group dev

# Run the tool
uv run filter-calc lowpass butterworth pi 10MHz -n 5
uv run filter-calc lp bw pi 10MHz --format json     # short aliases (lp/hp/bp); json/csv output
uv run filter-calc bp bw top -f 10MHz -b 500kHz --sim-build --format json
uv run filter-calc lp bw pi 10MHz --format spice --spice-realization nominal-build
uv run filter-calc                  # starts interactive wizard

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

Python 3.10+ CLI tool for calculating LC filter component values. Entry point is `filter_lib.cli:main` (registered as `filter-calc` script). No arguments launches a Textual TUI wizard.

### Package layout (`filter_lib/`)

- **`cli/`** — argparse subcommands (`lowpass_cmd`, `highpass_cmd`, `bandpass_cmd`, `wizard_cmd`). Each has `setup_parser()` and `run()`.
- **`lowpass/`**, **`highpass/`** — Thin wrappers over shared base. Each has `calculations.py`, `transfer.py`, `display.py`.
- **`bandpass/`** — Coupled resonator design. Has its own calculation, transfer, display, formatters, diagrams, and g-value modules.
- **`wizard/`** — Textual TUI. `app.py` drives screens in `screens/` (welcome → filter config → output options → results). `state.py` holds the `FilterState` dataclass shared across screens.
- **`shared/`** — Core logic shared across filter types:
  - `lp_hp_base_calculations.py` — Strategy pattern: LP and HP share calculation code, differing only in component formulas (`cap_formula`/`ind_formula` callables) and ordering.
  - `eseries.py` — E12/E24/E96 capacitor selection. A single part is selected within 1%; a parallel pair is selected only when it improves absolute error by at least 0.5 percentage points. Values below 1 pF require an explicit expert override. E-series names describe value density, not part tolerance.
  - `plotting.py` + `plot_*.py` — ASCII frequency response, zoom pairs, threshold analysis (split per GH-7); response-data export lives in `response_export.py`.
  - `parsing.py` — Flexible frequency/impedance parsing (`10MHz`, `10M`, `10e6`, etc.). Impedance also accepts k/M suffixes.
  - `constants.py` — Bessel g-value lookup tables. Chebyshev g-values computed by formula (see `chebyshev_g_calculator.py`).
  - `chebyshev_g_calculator.py` — Arbitrary Chebyshev ripple (0, 3.0] dB support via formula-based g-value computation (exact dB→neper conversion: 40/ln(10)).
  - `nodal_solver.py`, `netlist_simulation.py`, and `netlist_builders.py` — Named passive circuits, scale-safe AC nodal analysis, transducer power gain, and response landmarks.
  - `response_export.py` — Unified --plot-data schema for LP/HP/BP (replaces divergent implementations).
  - `build_*.py`, `component_realization.py`, and `nominal_realization.py` — calculated-versus-nominal build realization, finite-Q loss, unequal-port transducer gain, deterministic tolerance corners, and optional seeded screening. `--sim-matched` is a deprecated facade over this implementation; use `--sim-build`.
  - `lp_hp_display.py` — Single LP/HP table renderer used by CLI and wizard.
  - `toroid_*.py` + `toroid_core_data.json` — Primary-sourced integer-turn and winding-capacity screening. Only T25-6, T50-2, and T68-2 currently qualify for automatic selection. The output explicitly does not assess RF Q, core loss, SRF, saturation, thermal rise, or power handling.

Full module map: `docs/codebase-summary.md`.

### Key design patterns

- **LP/HP duality**: Lowpass and highpass use the same base calculation functions with different formulas injected (LP: `C=g/(Z*ω)`, `L=g*Z/ω`; HP: inverse). Topology (Pi/T) controls shunt vs series placement.
- **Filter-type alias canonicalization**: `shared/cli_aliases.py::FILTER_TYPE_ALIASES` is the single source of truth (`bw/b`→butterworth, `ch/c`→chebyshev, `bs`→bessel). Any new dispatch code must consult it rather than re-implement — see `shared/transfer_response_dispatch.py::_canonicalize_filter_type`.
- **Filter results**: LP/HP calculation functions return `(capacitors, inductors, order)`. Bandpass returns calibrated component values plus `synthesis_validation`, `response_validation_status`, Q-model metadata, and warnings. `q_min`/`q_safety` are compatibility heuristics, not stability or build-selection criteria. Build JSON keeps requested target, calculated response, selected nominal parts or explicit exact fallbacks, tolerance cases, and the effective loss model separate.
- **Bandpass -3 dB edges**: True edges come from solving `(f²-f0²)/(BW·f) = ±1`, not `f0 ± bw/2`. Source of truth: `bandpass.calculations.compute_bandpass_3db_edges` (uses `f_low = f0²/f_high` to dodge catastrophic cancellation for wide BW).
- **Chebyshev BP 3 dB semantics**: `bw` is the true requested −3 dB bandwidth. The raw Top-C design is calibrated against a circuit sweep rather than relying only on a prototype scaling equation. Source modules are `bandpass/top_c_calibration.py`, `response_verification.py`, and `ideal_response.py`.
- **Chebyshev constraints**: LP, HP, and BP require odd order (3/5/7/9) for equal terminations and `0 < ripple <= 3.0 dB` across CLI, wizard, and public synthesis APIs.
- **Bandpass end-coupling**: External Q is realized by series end capacitors. Tank inductance or tank impedance can be chosen independently from the equal design terminations. Shunt/bottom coupling is unsupported.
- **Bandpass validation**: Top-C is the only coupling topology. The maintained 128-cell matrix spans 1%, 2%, 5%, and 10% FBW: 106 cells are validated, 17 return `outside_validated_envelope`, and 5 known-unrealizable cells are rejected. Do not replace per-design status with a blanket ≤10% claim.
- **Toroid candidates**: Default table output shows the best qualified candidate, `--toroid-full` shows up to three, JSON includes up to three, and CSV carries the best available candidate. A requested detail count is not a guarantee that enough qualified cores exist.

## Ruff config

Target: py310, line-length 100, rules: E/F/I/UP/B. Ignores: E501 (formatter handles), B905 (zip without strict=). Tests ignore E501.

## Validation convention

Public numeric inputs reject booleans, wrong types, NaN/infinity, and arbitrary-size integers
outside binary64 before checking the application-specific sign or range. Use
`filter_lib.shared.numeric.is_finite_real` or the shared `require_*` validators; do not call bare
`math.isfinite` on untrusted public input because it can leak `TypeError` or `OverflowError`.
Invalid public input must raise a clear `ValueError`. Exact integer inputs likewise reject
booleans and floats.

## CI

GitHub Actions (`.github/workflows/ci.yml`) runs Ruff, coverage-gated tests on Python 3.10–3.13, source/wheel builds, archive inspection, and installed-wheel smoke tests on push/PR to `main`.

## Testing wizard screens

Wizard Textual screens are testable without a running app: mock widgets with `Mock(spec=RadioSet)`, override `type(screen).app` via `property`, then call the screen method directly. Pattern lives in `tests/test_wizard_screens_regressions.py`.

## Testing CLI subcommands

CLI tests build `argparse.Namespace` directly via `_lp_args()/_hp_args()/_bp_args()` helpers in `tests/test_cli_and_helpers.py` — pass overrides as kwargs to exercise validation branches without re-parsing argv. To exercise `setup_parser()` wiring, instantiate a plain `argparse.ArgumentParser()` and call `setup_parser(parser)` then `parser.parse_args([...])`.

## Netlist-Simulation Testing

Bandpass acceptance lives in `tests/test_netlist_simulation.py`. It checks requested skirts, connected/outer −3 dB regions, passband and stopband shape, ripple, and explicit unsupported cells. The harness builds the prescribed circuit and solves it with the stdlib AC nodal-analysis implementation; no external SPICE installation is required for these tests.

## Patching lazy imports

`wizard/interactive.py::run_wizard` imports `FilterWizardApp` lazily inside the function body. To mock it, patch at the definition site: `patch("filter_lib.wizard.app.FilterWizardApp")` — not at `filter_lib.wizard.interactive.FilterWizardApp` (the name doesn't exist until the function runs).
