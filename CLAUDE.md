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
  - `eseries.py` — E12/E24/E96 standard capacitor value matching with parallel combinations. Inductors are shown raw (no E-series matching).
  - `plotting.py` + `plot_*.py` — ASCII frequency response, zoom pairs, threshold analysis (split per GH-7); response-data export lives in `response_export.py`.
  - `parsing.py` — Flexible frequency/impedance parsing (`10MHz`, `10M`, `10e6`, etc.). Impedance also accepts k/M suffixes.
  - `constants.py` — Bessel g-value lookup tables. Chebyshev g-values computed by formula (see `chebyshev_g_calculator.py`).
  - `chebyshev_g_calculator.py` — Arbitrary Chebyshev ripple (0, 3.0] dB support via formula-based g-value computation (exact dB→neper conversion: 40/ln(10)).
  - `netlist_simulation.py` + `netlist_builders.py` — Bandpass netlist frequency sweep and component synthesis for simulation-proven response validation.
  - `response_export.py` — Unified --plot-data schema for LP/HP/BP (replaces divergent implementations).
  - `lp_hp_display.py` — Single LP/HP table renderer used by CLI and wizard.
  - `toroid_*.py` + `toroid_core_data.json` — Amidon core recommendations: given an inductance + frequency, suggests core/turns/wire gauge/DC resistance (GH-6). On by default; --no-toroids to suppress, --toroid-full to show top-3 in table (JSON always top-3; CSV rows carry the best match only).

Full module map: `docs/codebase-summary.md`.

### Key design patterns

- **LP/HP duality**: Lowpass and highpass use the same base calculation functions with different formulas injected (LP: `C=g/(Z*ω)`, `L=g*Z/ω`; HP: inverse). Topology (Pi/T) controls shunt vs series placement.
- **Filter-type alias canonicalization**: `shared/cli_aliases.py::FILTER_TYPE_ALIASES` is the single source of truth (`bw/b`→butterworth, `ch/c`→chebyshev, `bs`→bessel). Any new dispatch code must consult it rather than re-implement — see `shared/transfer_response_dispatch.py::_canonicalize_filter_type`.
- **Filter results**: LP/HP calculation functions return a tuple `(capacitors, inductors, order)`; display layers combine it with frequency/impedance/topology metadata. Bandpass `calculate_bandpass_filter()` returns a dict with synthesis and coupling fields (`f0`, `bw`, `fbw`, `n_resonators`, `g_values`, `qe_in`/`qe_out`, `L_resonant`/`C_resonant`, `c_coupling`, `c_tank`, `c_end_in`/`c_end_out`, `q_min`, `warnings`).
- **Bandpass -3 dB edges**: True edges come from solving `(f²-f0²)/(BW·f) = ±1`, not `f0 ± bw/2`. Source of truth: `bandpass.calculations.compute_bandpass_3db_edges` (uses `f_low = f0²/f_high` to dodge catastrophic cancellation for wide BW).
- **Chebyshev BP 3 dB semantics**: `bw` is the user's true -3 dB BW in both synthesis and plotting. For Chebyshev only, fbw is scaled down by `delta_3dB = cosh(acosh(1/ε)/n)` in `calculate_bandpass_filter`, and `magnitude_chebyshev` scales its deviation up by the same factor. Butterworth/Bessel prototypes already land at -3 dB when delta=1, so no scaling. Source of truth: `bandpass/transfer.py::chebyshev_3db_deviation`.
- **Chebyshev constraints**: LP, HP, and BP all require odd order (3/5/7/9) for equal source/load terminations — enforced in `shared/lp_hp_base_calculations.py` and `cli/bandpass_cmd.py`. Ripple is formula-computed for arbitrary values (no lookup tables); the 3.0 dB cap is enforced by the wizard (all filter types) and the bandpass CLI, while the LP/HP CLI validates only ripple > 0 (no upper bound).
- **Bandpass end-coupling**: External Q at port realized by series end-coupling capacitors Ce_in/Ce_out. Each Ce transforms the termination: Rp = Qe·ω0·L. Source of truth: `bandpass/calculations.py::calculate_end_coupling`. Shunt/bottom coupling removed — simulation showed it cannot realize the designed passband.
- **Bandpass netlist-simulation**: Top-C series coupling is the only coupling topology. Plots and --plot-data are netlist-simulated from the synthesized circuit (`netlist_frequency_sweep`), not idealized prototypes. Simulation-proven support capped at ≤10% fractional bandwidth (warning above threshold).
- **Toroid recommendations**: On by default, showing top-1 core per inductor in table output. --no-toroids suppresses entirely; --toroid-full shows top-3 in table (JSON/CSV always include top-3). Selection ranks cores by fit, computes turns from A_L, checks wire OD against window area.

## Ruff config

Target: py310, line-length 100, rules: E/F/I/UP/B. Ignores: E501 (formatter handles), B905 (zip without strict=). Tests ignore E501.

## Validation convention

Public float parameters reject NaN and inf alongside non-positive: `if not math.isfinite(x) or x <= 0: raise ValueError("X must be positive and finite")`. Keep the "must be positive" substring so existing regex tests match. Applies to cutoff/freq/BW/impedance/q_safety/ripple_db.

## CI

GitHub Actions (`.github/workflows/ci.yml`): lint → format check → pytest with coverage. Runs on push/PR to main, Python 3.13, ubuntu-latest.

## Testing wizard screens

Wizard Textual screens are testable without a running app: mock widgets with `Mock(spec=RadioSet)`, override `type(screen).app` via `property`, then call the screen method directly. Pattern lives in `tests/test_wizard_screens_regressions.py`.

## Testing CLI subcommands

CLI tests build `argparse.Namespace` directly via `_lp_args()/_hp_args()/_bp_args()` helpers in `tests/test_cli_and_helpers.py` — pass overrides as kwargs to exercise validation branches without re-parsing argv. To exercise `setup_parser()` wiring, instantiate a plain `argparse.ArgumentParser()` and call `setup_parser(parser)` then `parser.parse_args([...])`.

## Netlist-Simulation Testing

Bandpass synthesis is gated by simulation validation. To add a new simulation-gated acceptance case (e.g., a new ripple/FBW/order combination), parametrize it in the acceptance matrix at `tests/test_netlist_simulation.py` (measured -3 dB bandwidth within 3% of design, center frequency within 0.5%). Cases must land within ≤10% FBW (the simulation-proven range). The harness builds the prescribed circuit via `shared/netlist_builders.py` and solves it with the stdlib AC nodal-analysis solver in `shared/netlist_simulation.py` — no external SPICE dependency.

## Patching lazy imports

`wizard/interactive.py::run_wizard` imports `FilterWizardApp` lazily inside the function body. To mock it, patch at the definition site: `patch("filter_lib.wizard.app.FilterWizardApp")` — not at `filter_lib.wizard.interactive.FilterWizardApp` (the name doesn't exist until the function runs).
