# Codebase Summary

RF Filter Calculator is a Python CLI tool for calculating LC filter component values. Built with modern tooling (uv for package management) and comprehensive testing (344 tests).

## Project Statistics

- **Total Files**: 69 files
- **Total Lines of Code**: ~4,600 (excluding tests and docs)
- **Test Coverage**: 344 tests (~2,981 lines)
- **Documentation**: 8 files (~1,740 lines)

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
- `filter_wizard.py` - Main wizard orchestrator
- `bandpass_wizard.py` - Bandpass-specific prompts
- `interactive.py` - Interactive choice UI
- `prompts.py` - User input prompts and validation
- `__init__.py` - Module exports

### Shared Module (`filter_lib/shared/`)
Provides cross-cutting utilities:

| File | Purpose |
|------|---------|
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

**Test Files** (344 tests total):
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
| `docs/user-guide.md` | 379 | Complete CLI reference |
| `docs/filter-theory.md` | 214 | Educational background |
| `docs/testing.md` | 283 | Test suite guide |
| `docs/sample-output.md` | 325 | Example outputs |
| `docs/tips-and-best-practices.md` | 207 | Design guidance |
| `docs/caveats-and-known-issues.md` | 212 | Limitations and edge cases |

## Recent Major Changes

1. **uv Package Management** (commit 4da4f68): Switched from pip/venv to uv for consistent dependency management
2. **ASCII Art Fixes** (commit 4049ed7): Corrected spacing in topology diagrams
3. **Wizard Default Values** (commit 258fe6a): Fixed default value handling in interactive mode
4. **Simplified E-Series Display** (recent): Shows capacitor recommendations consistently (not topology-dependent)
