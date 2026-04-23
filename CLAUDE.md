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

# Linting
uv run ruff check .                 # lint
uv run ruff format --check .        # format check
uv run ruff format .                # auto-format
```

## Architecture

Python 3.10+ CLI tool for calculating LC filter component values. Entry point is `filter_lib.cli:main` (registered as `filter-calc` script). No arguments launches a Textual TUI wizard.

### Package layout (`filter_lib/`)

- **`cli/`** — argparse subcommands (`lowpass_cmd`, `highpass_cmd`, `bandpass_cmd`, `wizard_cmd`). Each has `setup_parser()` and `run()`.
- **`lowpass/`**, **`highpass/`** — Thin wrappers over shared base. Each has `calculations.py`, `transfer.py`, `display.py`.
- **`bandpass/`** — Coupled resonator design. Has its own calculation, transfer, display, formatters, diagrams, and g-value modules.
- **`wizard/`** — Textual TUI. `app.py` drives screens in `screens/` (welcome → filter config → output options → results). `state.py` holds `WizardState` dataclass shared across screens.
- **`shared/`** — Core logic shared across filter types:
  - `lp_hp_base_calculations.py` — Strategy pattern: LP and HP share calculation code, differing only in component formulas (`cap_formula`/`ind_formula` callables) and ordering.
  - `eseries.py` — E12/E24/E96 standard capacitor value matching with parallel combinations. Inductors are shown raw (no E-series matching).
  - `plotting.py` + `plot_*.py` — ASCII frequency response, zoom pairs, threshold analysis, data export (split per GH-7).
  - `parsing.py` — Flexible frequency/impedance parsing (`10MHz`, `10M`, `10e6`, etc.).
  - `constants.py` — Bessel and Chebyshev g-value lookup tables.
  - `filter_result.py` — `FilterResult` dataclass standardizing return types.
  - `toroid_*.py` + `toroid_core_data.json` — Amidon core recommendations: given an inductance + frequency, suggests core/turns/wire gauge/DC resistance (GH-6).

Full module map: `docs/codebase-summary.md`.

### Key design patterns

- **LP/HP duality**: Lowpass and highpass use the same base calculation functions with different formulas injected (LP: `C=g/(Z*ω)`, `L=g*Z/ω`; HP: inverse). Topology (Pi/T) controls shunt vs series placement.
- **Filter results**: All calculation functions return dicts with `capacitors`, `inductors`, `order`, `topology`, etc. Bandpass results have additional coupling fields (`c_tank`, `c_coupling`, `qe_in`, `qe_out`).
- **Chebyshev constraints**: Bandpass only supports odd resonator counts (3,5,7,9) for equal terminations. Ripple limited to 0.1, 0.5, 1.0 dB in wizard mode.
- **Toroid recommendations**: Opt-in via `--toroid` flag (see `cli/toroid_flags.py`); selection ranks cores by fit, computes turns from A_L, checks wire OD against window area.

## Ruff config

Target: py310, line-length 100, rules: E/F/I/UP/B. Ignores: E501 (formatter handles), B905 (zip without strict=). Tests ignore E501.

## CI

GitHub Actions (`.github/workflows/ci.yml`): lint → format check → pytest with coverage. Runs on push/PR to main, Python 3.13, ubuntu-latest.
