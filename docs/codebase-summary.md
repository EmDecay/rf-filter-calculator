# Codebase Summary

RF Filter Calculator is a Python CLI tool for calculating LC filter component values. Built with modern tooling (uv for package management) and comprehensive testing (344 tests).

## Project Statistics

- **Total Files**: 91 files
- **Total Lines of Code**: ~5,000 (excluding tests and docs)
- **Test Coverage**: 344+ tests (~2,981+ lines)
- **Documentation**: 13 files (~2,200+ lines)

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
- `filter_type_calculators.py` (185 LOC) - **NEW** - Separated calculation logic for LP/HP/BP
- `formatting_helpers.py` (155 LOC) - **NEW** - Wizard-specific formatting and helpers
- `filter_screen_navigation_mixin.py` (46 LOC) - **NEW** - Screen navigation mixin for DRY code
- `radio_button_helpers.py` (19 LOC) - **NEW** - Radio button widget utilities
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
| `lp_hp_base_calculations.py` | **NEW** - Strategy pattern for LP/HP calculations |
| `lp_hp_base_transfer_functions.py` | **NEW** - Shared transfer function logic for LP/HP |
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
| `plotting.py` | ASCII frequency response plots |
| `topology_diagrams.py` | ASCII circuit topology diagrams |
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

**Test Files** (344+ tests total):
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
- `test_transfer_functions.py` - Transfer function accuracy
- `test_wizard_state.py` - FilterState dataclass validation
- `test_wizard_topology_diagrams.py` - Wizard topology diagram rendering
- `conftest.py` - Shared pytest fixtures and configuration
- `test_wizard_unit.py` - **NEW** - Wizard module unit tests
- `test_plotting_edge_cases.py` - **NEW** - Edge cases for plotting

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

1. **Wizard Refactoring** (commit 69938ca): Modularized calculation_handler.py (355 LOC → 35 LOC)
   - Extracted filter_type_calculators.py (185 LOC) - type-specific calculation logic
   - Extracted formatting_helpers.py (155 LOC) - wizard display formatting
   - Added filter_screen_navigation_mixin.py - DRY screen navigation
   - Added radio_button_helpers.py - shared radio button utilities

2. **Shared Module Expansion**: Added lp_hp_base_*.py modules
   - lp_hp_base_calculations.py (342 LOC) - Strategy pattern for LP/HP
   - lp_hp_base_transfer_functions.py (164 LOC) - Shared transfer functions

3. **Textual TUI Wizard Migration** (commit 79291e5): Textual screen-based architecture
   - Modular screen components (welcome, filter config, output options, results)
   - Async calculation handling with worker thread
   - Centralized FilterState for state management
   - Removed inductor E-series recommendations (capacitors only)

4. **uv Package Management** (commit 4da4f68): Switched from pip/venv to uv
5. **ASCII Art Fixes** (commit 4049ed7): Corrected spacing in topology diagrams
6. **Wizard Default Values** (commit 258fe6a): Fixed default value handling in interactive mode
