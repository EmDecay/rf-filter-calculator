# Codebase Summary

**Last Updated**: July 6, 2026

RF Filter Calculator is a Python CLI tool for calculating LC filter component values. Built with modern tooling (uv, ruff, GitHub Actions CI) and comprehensive testing (1274 tests, 95% coverage).

## Project Statistics

- **Total Lines of Code**: ~20,700 LOC (~7,950 core lib + ~12,700 tests)
- **Test Coverage**: 1274 tests, 95% coverage (~3s runtime)
- **Documentation**: 14 files (~4,600 LOC)
- **Core Library**: 66 modules in filter_lib/, organized by filter type + shared utilities

## Architecture Overview

The project uses a **modular architecture** organized by filter type and function:

```
rf-filter-calculator/
├── filter-calc.py          # Thin shim (15 lines) → filter_lib.cli:main
├── filter_lib/             # Core library
│   ├── cli/                # Command handlers (4 subcommands)
│   ├── lowpass/            # Pi/T topology calculations
│   ├── highpass/           # Pi/T topology calculations
│   ├── bandpass/           # Coupled resonator design
│   ├── wizard/             # Interactive design mode
│   └── shared/             # Common utilities
└── tests/                  # Test suite (pytest)
```

## Core Components

### Main Entry Point (`filter_lib/cli/__init__.py:main`)
- Registered as the `filter-calc` script in pyproject.toml; `filter-calc.py` at the repo root is a 15-line shim that calls the same `main()`
- Command parsing and routing (argparse subcommands)
- Default wizard invocation when run with no arguments
- Error handling and user feedback

### CLI Module (`filter_lib/cli/`)
- `bandpass_cmd.py` - Bandpass filter command handler
- `highpass_cmd.py` - Highpass filter command handler
- `lowpass_cmd.py` - Lowpass filter command handler
- `wizard_cmd.py` - Interactive wizard coordinator
- `toroid_flags.py` - **NEW (Apr 2026)** Shared `--no-toroids` and `--toroid-compact` flags

### Lowpass Module (`filter_lib/lowpass/`)
- `calculations.py` - Component value calculations for Pi/T topologies
- `display.py` - Output formatting (table, JSON, CSV)
- `transfer.py` - Frequency response transfer function
- `__init__.py` - Module exports

### Highpass Module (`filter_lib/highpass/`)
- `calculations.py` - Component value calculations (topologies reversed vs lowpass)
- `display.py` - Output formatting
- `transfer.py` - Frequency response transfer function
- `__init__.py` - Module exports

### Bandpass Module (`filter_lib/bandpass/`)
- `calculations.py` - Coupled resonator design
- `diagrams.py` - Topology visualization
- `display.py` - Output formatting
- `formatters.py` - Component value formatting
- `g_values.py` - Normalized component value tables
- `transfer.py` - Frequency response transfer function; includes `chebyshev_3db_deviation()` helper for true -3dB BW semantics in Chebyshev BP (Apr 2026)
- `__init__.py` - Module exports

### Wizard Module (`filter_lib/wizard/`)
**Architecture**: Textual TUI (Terminal User Interface) with modular screen-based navigation

**Core Infrastructure**:
- `app.py` (49 LOC) - FilterWizardApp (Textual App, manages screen stack)
- `state.py` (36 LOC) - FilterState dataclass (centralized mutable state shared across screens)
- `interactive.py` (15 LOC) - Entry point, exports `run_wizard()` function
- `calculation_handler.py` (34 LOC) - Calculation orchestration, reduced from 355 LOC via extraction
- `filter_type_calculators.py` (202 LOC) - Calculation logic for LP/HP/BP
- `formatting_helpers.py` (115 LOC) - Wizard-specific formatting helpers
- `filter_screen_navigation_mixin.py` (43 LOC) - Screen navigation mixin
- `radio_button_helpers.py` (20 LOC) - Radio button widget utilities
- `styles.tcss` (197 LOC) - Textual CSS styling for all screens

**Screens** (`screens/` directory):
- `welcome.py` (58 LOC) - Filter category selection (lowpass/highpass/bandpass)
- `lowpass.py` (215 LOC) - Lowpass filter parameters form
- `highpass.py` (216 LOC) - Highpass filter parameters form
- `bandpass.py` (270 LOC) - Bandpass filter parameters form
- `output_options.py` (146 LOC) - Output format, E-series, export settings
- `results.py` (279 LOC) - Results display with async worker for calculations
- `__init__.py` - Screen exports

**Key Design Pattern**: Each screen is independent, receives/updates shared FilterState. Results screen uses background worker thread to prevent UI blocking during calculations.

### Shared Module (`filter_lib/shared/`)
Provides cross-cutting utilities:

| File | Purpose |
|------|---------|
| `lp_hp_base_calculations.py` | Strategy pattern for LP/HP calculations |
| `lp_hp_base_transfer_functions.py` | Shared transfer function logic for LP/HP |
| `chebyshev_g_calculator.py` | Normalized g-values for Chebyshev filters |
| `cli_aliases.py` | Filter type and topology aliases |
| `cli_helpers.py` | Common CLI parsing utilities |
| `constants.py` | Physical constants and defaults |
| `display_common.py` | Shared display formatting functions |
| `display_helpers.py` | E-series matching and formatting helpers |
| `eseries.py` | E12/E24/E96 standard component values |
| `formatting.py` | Number formatting for user display |
| `parsing.py` | Input validation and normalization |
| `plotting.py` | **Facade** — re-exports plotting functions for backward compat |
| `plot_ascii_renderers.py` | **NEW (Apr 2026)** - ASCII plot rendering with configurable `db_floor` |
| `plot_zoom_pairs.py` | **NEW (Apr 2026)** - Zoomed passband plot pairs (full + zoomed side-by-side) |
| `plot_threshold_analysis.py` | **NEW (Apr 2026)** - dB crossing detection + summary table formatting |
| `response_export.py` | Unified JSON/CSV response export (single schema for LP/HP/BP) |
| `transfer_response_dispatch.py` | Shared factory for response-function closures |
| `topology_diagrams.py` | ASCII circuit topology diagrams |
| `netlist_simulation.py` | Pure-stdlib nodal-analysis solver and simulation-validated bandpass response |
| `netlist_builders.py` | Internal circuit branch-list construction from filter synthesis |
| `lp_hp_display.py` | Unified LP/HP table renderer (CLI and wizard) |
| `matched_simulation.py` | **NEW (Jul 2026)** - E-series matched capacitor re-simulation (inductors exact) |
| `toroid_core_data.json` | Vendored 43-core iron-powder T-series database |
| `toroid_core_data.py` | `ToroidCore` dataclass + lookup helpers |
| `toroid_inductance.py` | L↔N math, rounding, tolerance range, `solve_winding` |
| `toroid_wire.py` | AWG, Pythagorean wire length, DCR, `MechanicalFit` |
| `toroid_selection.py` | Freq-range gate + ranking → top-3 `ToroidRecommendation` |
| `toroid_display.py` | Full/compact text, JSON builder, CSV columns |
| `transfer_functions.py` | Transfer function calculations |

## Filter Types Supported

### Lowpass (Pi/T Topology)
- **Response types**: Butterworth, Chebyshev, Bessel
- **Orders**: 2-9 components
- **Default topology**: Pi (shunt C - series L pattern)
- **Calculations**: `filter_lib/lowpass/calculations.py`

### Highpass (Pi/T Topology)
- **Response types**: Butterworth, Chebyshev, Bessel
- **Orders**: 2-9 components
- **Default topology**: T (series C - shunt L pattern)
- **Topologies reversed** vs lowpass: Pi has shunt L, T has series C
- **Calculations**: `filter_lib/highpass/calculations.py`

### Bandpass (Coupled Resonator, Top-C Series Coupling Only)
- **Response types**: Butterworth, Chebyshev, Bessel
- **Coupling**: Top-coupled series capacitors only (Ce_in/Ce_out for external Q, Cs12/Cs23 inter-resonator). Shunt coupling removed (simulation showed non-realizable passband).
- **Resonators**: 2-9 tanks
- **Design method**: Normalized g-values per Matthaei/Young/Jones; external Q realized by end-coupling capacitors
- **Validation**: Built-in nodal-analysis netlist sweep for ≤10% fractional BW (simulation-proven tolerance ±3% magnitude, ±0.5% f₀)
- **Calculations**: `filter_lib/bandpass/calculations.py`

## Output Formats

| Format | Handler | Use Case |
|--------|---------|----------|
| Table (default) | `display.py:display_results()` | Interactive use, human-readable |
| JSON | `display_common.py:format_json_result()` | Programmatic automation |
| CSV | `display_common.py:format_csv_result()` | Spreadsheet import |
| Quiet | `display_common.py:format_quiet_result()` | Scripting, minimal output |

## Component Matching

**E-Series Matching** (`filter_lib/shared/eseries.py`):
- E12: 12 values per decade (±10% tolerance)
- E24: 24 values per decade (±5% tolerance) - default
- E96: 96 values per decade (±1% tolerance)

**Matching Strategies** (capacitors only — inductors are shown raw, to be wound to value):
1. **Single value**: Nearest E-series standard
2. **Parallel combination**: Two standard capacitors in parallel for better accuracy (C_total = C1 + C2)

## Test Coverage

**Test Files** (1274 tests total across 32 modules, 95% coverage — see `docs/testing.md` for per-file counts):
- `test_bandpass_calculations.py` - Coupled resonator design, end-coupling, -3 dB edges
- `test_bandpass_modules.py` - Bandpass g-values, display, and formatting
- `test_chebyshev_calculator.py` - Chebyshev g-value calculations
- `test_cli_and_helpers.py` - CLI parsing and option handling (Namespace builder helpers)
- `test_cli_coverage_gaps.py` - CLI main(), setup_parser, validation error paths
- `test_codex_review_fixes.py` - Chebyshev BP 3dB semantics, wizard HP harmonic parallel, NaN/inf validation
- `test_display_modules.py` - Display formatting (table, JSON, CSV)
- `test_eseries_matching.py` - Component matching algorithms (capacitors only)
- `test_highpass_calculations.py` - Highpass filter calculations
- `test_lowpass_calculations.py` - Lowpass filter calculations
- `test_lp_hp_display_golden.py` - Golden snapshots of LP/HP table, JSON, CSV output
- `test_netlist_simulation.py` - AC nodal-analysis solver + bandpass simulation acceptance matrix
- `test_parsing_validation.py` - Input validation and parsing
- `test_plot_threshold_analysis.py` - dB threshold detection and table formatting
- `test_plot_zoomed.py` - Zoomed passband plot and zoom range computation
- `test_plotting_edge_cases.py` - ASCII plot rendering edge cases
- `test_topology_calculations.py` - Topology-specific calculations
- `test_toroid_core_data.py` - Iron-powder core database
- `test_toroid_display.py` - Text/JSON/CSV formatters
- `test_toroid_inductance.py` - L↔N math + T68-2 regression
- `test_toroid_integration.py` - End-to-end LP/HP/BP × flags
- `test_toroid_selection.py` - Ranking algorithm
- `test_toroid_wire.py` - AWG, wire length, DCR, fit
- `test_transfer_and_shared_edges.py` - HP transfer dispatch, E-series edges, toroid validation
- `test_transfer_functions.py` - Transfer function accuracy
- `test_transfer_response_dispatch.py` - Response function factory
- `test_wizard_event_handlers_and_final_edges.py` - Input handlers, filter type changes, csv export
- `test_wizard_screens_coverage.py` - Screen navigation via Mock pattern
- `test_wizard_screens_regressions.py` - Wizard screen regressions via Mock pattern
- `test_wizard_state.py` - FilterState dataclass validation
- `test_wizard_topology_diagrams.py` - Wizard topology diagram rendering
- `test_wizard_unit.py` - Wizard module unit tests
- `conftest.py` - Shared pytest fixtures and configuration

## Development Workflow

### Setup
```bash
uv sync                    # Install dependencies
uv sync --group dev        # Include pytest
```

### Testing
```bash
uv run pytest tests/ -v    # Run all tests
uv run pytest tests/ --cov=filter_lib  # With coverage
```

### Running
```bash
uv run filter-calc                     # Interactive wizard
uv run filter-calc lp bw pi 10MHz -n 5  # CLI command
```

## Key Design Patterns

1. **Calculation Return Shapes**:
   - LP/HP: calculation functions return a tuple `(capacitors, inductors, order)` (lists of float values in Farads/Henries); display layers combine it with frequency/impedance/topology metadata
   - Bandpass: `calculate_bandpass_filter()` returns a dict with `f0`, `f_low`/`f_high`, `bw`, `fbw`, `fbw_synth`, `z0`, `n_resonators`, `g_values`, `qe_in`/`qe_out`, `L_resonant`/`C_resonant`, `c_coupling`, `c_tank`, `c_end_in`/`c_end_out`, `q_min`, `il_estimates` (dict mapping Qu values to dB), `warnings`

2. **Primary Component Concept**: Identifies which component type should show E-series recommendations:
   - Lowpass Pi: Capacitors (shunt positions)
   - Lowpass T: Inductors (series positions)
   - Highpass T: Capacitors (series positions)
   - Highpass Pi: Inductors (shunt positions)
   - Bandpass: Always capacitors

3. **Display Module Pattern**: Each filter type has `display.py` with:
   - `display_results()` - Main table output
   - `format_json()`, `format_csv()`, `format_quiet()` - Alt formats
   - `_primary_component()` - Topology-aware identification

4. **Shared Utilities Pattern**: Common functions centralized in `shared/` module to reduce duplication across filter types

## Dependencies

**Runtime** (via `uv`):
- Textual: TUI framework for the interactive wizard (CLI itself is stdlib argparse)

**Development** (dev group):
- pytest: Testing framework
- pytest-cov: Coverage reporting
- ruff: Linting and formatting

## File Size Management

Most code files stay near the 200-line guideline for optimal context:
- Main entry shim: 15 lines (`filter-calc.py`)
- CLI commands: ~100-220 lines each
- Calculation modules: 70-330 lines (`bandpass/calculations.py` is the largest)
- Display modules: 60-250 lines each
- Shared utilities: 30-380 lines each (`lp_hp_base_calculations.py` is the largest)

## Documentation Files

| File | Lines | Purpose |
|------|-------|---------|
| `README.md` (root) | ~290 | Project overview and quick start |
| `docs/README.md` | ~50 | Documentation index |
| `docs/quick-start.md` | ~75 | 5-minute getting started |
| `docs/user-guide.md` | ~570 | Complete CLI and wizard reference |
| `docs/filter-theory.md` | ~240 | Educational background on filter types |
| `docs/testing.md` | ~425 | Test suite guide |
| `docs/sample-output.md` | ~385 | Example outputs and formats |
| `docs/code-standards.md` | ~560 | Code structure and patterns |
| `docs/system-architecture.md` | ~775 | Component architecture and layers |
| `docs/project-overview-pdr.md` | ~535 | PDR and functional requirements |
| `docs/codebase-summary.md` | ~345 | Architecture overview (this file) |
| `docs/tips-and-best-practices.md` | ~200 | Design guidance |
| `docs/caveats-and-known-issues.md` | ~225 | Limitations and edge cases |
| `docs/project-changelog.md` | ~145 | Release and change history |
| `docs/textual-wizard-patterns.md` | ~70 | Textual TUI screen vs ContentSwitcher patterns |

## Recent Major Changes

0. **v2.0.0 Remediation Release** (Jun 2026):
   - Bandpass external Q realized by series end-coupling capacitors (Ce_in/Ce_out); shunt-C coupling removed (simulation showed non-realizable passband)
   - Bandpass plots and `--plot-data` are netlist-simulated from the synthesized circuit (`shared/netlist_simulation.py` + `netlist_builders.py`), with simulation-proven support capped at ≤10% fractional BW
   - Chebyshev g-values computed by formula for arbitrary ripple in (0, 3.0] dB (`shared/chebyshev_g_calculator.py`)
   - E-series matching now capacitors-only (inductors shown raw, to be wound)
   - Unified `--plot-data` export schema for LP/HP/BP (`shared/response_export.py`)
   - LP/HP display consolidated into single shared renderer (`shared/lp_hp_display.py`) with golden-snapshot tests
   - Coordinated CLI cleanup (breaking changes) and wizard input parsing aligned with the CLI
   - Test count: 1046 → 1227

1. **Graph Enhancements: dB Threshold Table + Zoomed Passband** (Apr 2, 2026):
   - Split monolithic `plotting.py` (345 LOC) into 5 focused modules (facade pattern):
     - `plot_ascii_renderers.py` (276 LOC) — plot rendering with configurable `db_floor` for zooming
     - `plot_zoom_pairs.py` (133 LOC) — zoomed passband plot pairs (full + zoomed side-by-side)
     - `plot_threshold_analysis.py` (148 LOC) — dB crossing detection for -3, -10, -20 dB levels
     - response-data export now lives in `shared/response_export.py` (unified schema)
     - `transfer_response_dispatch.py` (58 LOC) — shared factory for response-fn closures
   - **Features**:
     - dB Threshold Summary Table: Shows frequencies at -3, -10, -20 dB with direction indicators
     - Zoomed Passband Graph: 0 to -6dB detail view alongside full-range plot (adaptive for Chebyshev)
     - 2× frequency resolution in zoomed plots for smoother curves
   - Integrated into all output paths (automatic with `--plot`)
   - Added 93 new tests: 41 threshold analysis + 42 zoomed plot + 26 dispatch tests
   - Test count: 639 → 732 tests
   - Closed GitHub issue #7

2. **Ruff Linting & GitHub Actions CI** (Feb 2026, commit cc4e9c1):
   - Added ruff>=0.8 to dev dependencies
   - Config: target py310, line-length 100, rules E/F/I/UP/B (E501, B905 ignored)
   - GitHub Actions CI workflow: lint → format check → pytest+coverage on all pushes/PRs
   - 67 files reformatted by ruff format (E731 lambdas→defs, f-string upgrades, cleanup)
   - Test suite expanded from 344 to 556 tests during major refactor

2. **Wizard Refactoring** (commit 69938ca, Feb 2026): Modularized calculation_handler.py (355 → 35 LOC)
   - Extracted filter_type_calculators.py (185 LOC) - LP/HP/BP calculation routing
   - Extracted formatting_helpers.py (155 LOC) - wizard-specific display formatting
   - Added filter_screen_navigation_mixin.py (46 LOC) - reusable screen navigation
   - Added radio_button_helpers.py (19 LOC) - radio button widget utilities

3. **Shared Module Expansion** (Feb 2026): Added lp_hp_base_*.py modules
   - lp_hp_base_calculations.py (342 LOC) - Strategy pattern for LP/HP duality
   - lp_hp_base_transfer_functions.py (164 LOC) - Shared transfer function logic

4. **Textual TUI Wizard Migration** (commit 69938ca, Feb 2026):
   - Screen-based architecture (welcome → params → output options → results)
   - Async calculation with worker thread to prevent UI blocking
   - Centralized FilterState for state management across screens

5. **Package Management** (commit 4da4f68): Switched from pip/venv to uv
6. **Bug Fixes** (Jan-Feb 2026): ASCII topology spacing, HPF capacitor formula, wizard defaults, E-series export

**Quality Metrics** (as of Jul 6, 2026):
- 1274 tests, 95% coverage
- ~20,700 total LOC
- GitHub Actions CI enforcing lint → format → test on all PRs
- Graph enhancements (GH-7) complete with threshold tables + zoomed plots
- Wizard screens 67-85% covered via Mock(spec=...) + property override pattern
- CLI validation error paths fully tested (negative/NaN/inf frequency, impedance, ripple rejection)
- Bandpass synthesis validated by built-in netlist simulation (±3% BW, ±0.5% f₀ acceptance)
