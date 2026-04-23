# Codebase Summary

**Last Updated**: April 2, 2026

RF Filter Calculator is a Python CLI tool for calculating LC filter component values. Built with modern tooling (uv, ruff, GitHub Actions CI) and comprehensive testing (826+ tests).

## Project Statistics

- **Total Files**: 93+ files
- **Total Lines of Code**: ~8,200 LOC (2,200+ core lib + 5,900+ tests + ~350 CLI entry)
- **Test Coverage**: 826 tests, 78% coverage (~0.5s runtime)
- **Documentation**: 13 files (~2,300+ LOC)
- **Core Library**: 42+ modules in filter_lib/, organized by filter type + shared utilities

## Architecture Overview

The project uses a **modular architecture** organized by filter type and function:

```
rf-filter-calculator/
├── filter-calc.py          # Main CLI entry point (333 lines)
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

### Main Entry Point (`filter-calc.py`)
- Command parsing and routing
- Default wizard invocation
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
- `transfer.py` - Frequency response transfer function
- `__init__.py` - Module exports

### Wizard Module (`filter_lib/wizard/`)
**Architecture**: Textual TUI (Terminal User Interface) with modular screen-based navigation

**Core Infrastructure**:
- `app.py` (47 LOC) - FilterWizardApp (Textual App, manages screen stack)
- `state.py` (33 LOC) - FilterState dataclass (centralized mutable state shared across screens)
- `interactive.py` (15 LOC) - Entry point, exports `run_wizard()` function
- `calculation_handler.py` (35 LOC) - Calculation orchestration, reduced from 355 LOC via extraction
- `filter_type_calculators.py` (185 LOC) - Calculation logic for LP/HP/BP (Feb 2026)
- `formatting_helpers.py` (155 LOC) - Wizard-specific formatting helpers (Feb 2026)
- `screen_navigation_mixin.py` (46 LOC) - Screen navigation mixin (Feb 2026)
- `radio_button_helpers.py` (19 LOC) - Radio button widget utilities (Feb 2026)
- `filter_type_calculators.py` (261 LOC) - Calculation logic for LP/HP/BP (Apr 2026, expanded)
- `validation.py` (39 LOC) - Input validators (frequency, impedance, order, ripple)
- `styles.tcss` (192 LOC) - Textual CSS styling for all screens

**Screens** (`screens/` directory):
- `welcome.py` (56 LOC) - Filter category selection (lowpass/highpass/bandpass)
- `lowpass.py` (229 LOC) - Lowpass filter parameters form
- `highpass.py` (228 LOC) - Highpass filter parameters form
- `bandpass.py` (292 LOC) - Bandpass filter parameters form
- `output_options.py` (146 LOC) - Output format, E-series, export settings
- `results.py` (175 LOC) - Results display with async worker for calculations
- `__init__.py` - Screen exports

**Widgets** (`widgets/` directory):
- `__init__.py` - Placeholder for custom Textual widgets (future extensions)

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
| `filter_result.py` | Result data structure wrapper |
| `formatting.py` | Number formatting for user display |
| `parsing.py` | Input validation and normalization |
| `plotting.py` | **Facade** — re-exports plotting functions for backward compat |
| `plot_ascii_renderers.py` | **NEW (Apr 2026)** - ASCII plot rendering with configurable `db_floor` |
| `plot_zoom_pairs.py` | **NEW (Apr 2026)** - Zoomed passband plot pairs (full + zoomed side-by-side) |
| `plot_threshold_analysis.py` | **NEW (Apr 2026)** - dB crossing detection + summary table formatting |
| `plot_data_export.py` | **NEW (Apr 2026)** - JSON/CSV data export functions |
| `transfer_response_dispatch.py` | **NEW (Apr 2026)** - Shared factory for response-function closures |
| `topology_diagrams.py` | ASCII circuit topology diagrams |
| `toroid_core_data.json` | **NEW (Apr 2026)** - Vendored 43-core iron-powder T-series database |
| `toroid_core_data.py` | **NEW (Apr 2026)** - `ToroidCore` dataclass + lookup helpers |
| `toroid_inductance.py` | **NEW (Apr 2026)** - L↔N math, rounding, tolerance range, `solve_winding` |
| `toroid_wire.py` | **NEW (Apr 2026)** - AWG, Pythagorean wire length, DCR, `MechanicalFit` |
| `toroid_selection.py` | **NEW (Apr 2026)** - Freq-range gate + ranking → top-3 `ToroidRecommendation` |
| `toroid_display.py` | **NEW (Apr 2026)** - Full/compact text, JSON builder, CSV columns |
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

### Bandpass (Coupled Resonator)
- **Response types**: Butterworth, Chebyshev (even-only), Bessel
- **Coupling types**: Top-coupled (series) or Shunt-coupled (parallel)
- **Resonators**: 2-9 tanks
- **Design method**: Normalized g-values per Matthaei/Young/Jones
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

**Matching Strategies**:
1. **Single value**: Nearest E-series standard
2. **Parallel combination**: Two values in parallel for better accuracy
   - Capacitors: C_total = C1 + C2 (series addition)
   - Inductors: L_total = L1×L2/(L1+L2) (harmonic mean)

## Test Coverage

**Test Files** (826 tests total):
- `test_bandpass_calculations.py` - Coupled resonator design tests
- `test_bandpass_modules.py` - Bandpass display and formatting
- `test_chebyshev_calculator.py` - Chebyshev g-value calculations
- `test_cli_and_helpers.py` - CLI parsing and option handling
- `test_display_modules.py` - Display formatting (table, JSON, CSV)
- `test_eseries_matching.py` - Component matching algorithms
- `test_highpass_calculations.py` - Highpass filter calculations
- `test_lowpass_calculations.py` - Lowpass filter calculations
- `test_parsing_validation.py` - Input validation and parsing
- `test_topology_calculations.py` - Topology-specific calculations
- `test_transfer_functions.py` - Transfer function accuracy (49+ tests)
- `test_wizard_state.py` - FilterState dataclass validation
- `test_wizard_topology_diagrams.py` - Wizard topology diagram rendering
- `test_wizard_unit.py` - Wizard module unit tests (Feb 2026)
- `test_plotting_edge_cases.py` - ASCII plot rendering edge cases (Feb 2026)
- `test_plot_threshold_analysis.py` - dB threshold detection and table formatting (Apr 2026, 41 tests)
- `test_plot_zoomed.py` - Zoomed passband plot and zoom range computation (Apr 2026, 42 tests)
- `test_transfer_response_dispatch.py` - Response function factory (Apr 2026, 26 tests)
- `test_toroid_core_data.py` - **NEW (Apr 2026)** Iron-powder core database (12 tests)
- `test_toroid_inductance.py` - **NEW (Apr 2026)** L↔N math + T68-2 regression (16 tests)
- `test_toroid_wire.py` - **NEW (Apr 2026)** AWG, wire length, DCR, fit (16 tests)
- `test_toroid_selection.py` - **NEW (Apr 2026)** Ranking algorithm (12 tests)
- `test_toroid_display.py` - **NEW (Apr 2026)** Text/JSON/CSV formatters (12 tests)
- `test_toroid_integration.py` - **NEW (Apr 2026)** End-to-end LP/HP/BP × flags (19 tests)
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

1. **Result Dictionary Pattern**: All calculations return dict with keys:
   - `filter_type`, `freq_hz`, `impedance`, `order`, `ripple`
   - `capacitors`, `inductors` (lists of float values in Farads/Henries)
   - `topology` (Pi/T for LP/HP, top/shunt for BP)

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
- Click: CLI framework
- Rich: Terminal formatting and interactive UI

**Development** (dev group):
- pytest: Testing framework
- pytest-cov: Coverage reporting

## File Size Management

All code files respect 200-line limit for optimal context:
- Main entry: 333 lines (entry point exception)
- CLI commands: 60-80 lines each
- Calculation modules: 80-120 lines each
- Display modules: 50-90 lines each
- Shared utilities: 50-150 lines each

## Documentation Files

| File | Lines | Purpose |
|------|-------|---------|
| `README.md` (root) | 284 | Project overview and quick start |
| `docs/README.md` | 50 | Documentation index |
| `docs/quick-start.md` | 70 | 5-minute getting started |
| `docs/user-guide.md` | 485 | Complete CLI and wizard reference |
| `docs/filter-theory.md` | 214 | Educational background on filter types |
| `docs/testing.md` | 283 | Test suite guide |
| `docs/sample-output.md` | 325 | Example outputs and formats |
| `docs/code-standards.md` | 355 | Code structure and patterns |
| `docs/system-architecture.md` | 726 | Component architecture and layers |
| `docs/project-overview-pdr.md` | 508 | PDR and functional requirements |
| `docs/codebase-summary.md` | 238+ | Architecture overview (this file) |
| `docs/tips-and-best-practices.md` | 207 | Design guidance |
| `docs/caveats-and-known-issues.md` | 212 | Limitations and edge cases |
| `docs/textual-wizard-patterns.md` | 69 | Textual TUI screen vs ContentSwitcher patterns |

## Recent Major Changes

1. **Graph Enhancements: dB Threshold Table + Zoomed Passband** (Apr 2, 2026):
   - Split monolithic `plotting.py` (345 LOC) into 5 focused modules (facade pattern):
     - `plot_ascii_renderers.py` (276 LOC) — plot rendering with configurable `db_floor` for zooming
     - `plot_zoom_pairs.py` (133 LOC) — zoomed passband plot pairs (full + zoomed side-by-side)
     - `plot_threshold_analysis.py` (148 LOC) — dB crossing detection for -3, -10, -20 dB levels
     - `plot_data_export.py` (54 LOC) — JSON/CSV export functions
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
   - Capacitor-only E-series matching (inductor E-series removed)

5. **Package Management** (commit 4da4f68): Switched from pip/venv to uv
6. **Bug Fixes** (Jan-Feb 2026): ASCII topology spacing, HPF capacitor formula, wizard defaults, E-series export

**Quality Metrics** (as of Apr 2, 2026):
- 826 tests, 78% coverage
- 67 files ruff-formatted
- 8,200+ total LOC
- GitHub Actions CI enforcing lint → format → test on all PRs
- Graph enhancements (GH-7) complete with threshold tables + zoomed plots
