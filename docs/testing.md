# Testing Guide

Comprehensive test suite for the RF Filter Calculator.

---

## Running Tests

### Quick Start

```bash
# Run all tests
uv run pytest tests/

# Run with verbose output
uv run pytest tests/ -v

# Run specific test file
uv run pytest tests/test_lowpass_calculations.py

# Run with coverage report
uv run pytest tests/ --cov=filter_lib --cov-report=term-missing
```

### Requirements

Install with the dev dependency group:

```bash
uv sync --group dev
```

---

## Test Suite Overview

| Test File | Tests | Description |
|-----------|-------|-------------|
| `test_wizard_screens_coverage.py` | 102 | FilterScreenNavigationMixin, screen navigation, validation via Mock pattern |
| `test_cli_and_helpers.py` | 97 | CLI commands, plotting, and formatting helpers (includes `_lp_args`/`_hp_args`/`_bp_args` Namespace builders) |
| `test_plotting_edge_cases.py` | 81 | ASCII plot edge cases |
| `test_plot_zoomed.py` | 68 | Zoomed passband plot computation and rendering |
| `test_netlist_simulation.py` | 68 | AC nodal-analysis solver, netlist builders, bandpass simulation acceptance matrix |
| `test_plot_threshold_analysis.py` | 63 | dB threshold detection and summary tables |
| `test_transfer_functions.py` | 56 | Frequency response (shared + LPF/HPF/BPF) |
| `test_cli_coverage_gaps.py` | 52 | CLI main(), setup_parser wiring, CLI helpers, validation error paths |
| `test_transfer_response_dispatch.py` | 51 | Response function factory |
| `test_bandpass_modules.py` | 50 | Bandpass g-values, formatters, display, diagrams |
| `test_display_modules.py` | 49 | Output formatting (JSON/CSV/table/topology) |
| `test_wizard_unit.py` | 47 | Wizard module unit tests |
| `test_bandpass_calculations.py` | 47 | Coupled resonator calculations, end-coupling, -3 dB edges |
| `test_eseries_matching.py` | 40 | E12/E24/E96 component matching (capacitors only) |
| `test_codex_review_fixes.py` | 38 | Chebyshev BP 3dB semantics, wizard HP harmonic parallel, NaN/inf validation |
| `test_wizard_event_handlers_and_final_edges.py` | 33 | Input.Submitted handlers, _on_filter_type_changed, csv export, wizard entry |
| `test_lowpass_calculations.py` | 27 | Pi/T topology lowpass calculations |
| `test_chebyshev_calculator.py` | 27 | Chebyshev g-value computation |
| `test_transfer_and_shared_edges.py` | 25 | HP transfer alias dispatch, E-series edge cases, toroid validation |
| `test_toroid_integration.py` | 24 | End-to-end LP/HP/BP × flag matrix |
| `test_lp_hp_display_golden.py` | 24 | Golden snapshots of LP/HP rendered table, JSON, and CSV output |
| `test_highpass_calculations.py` | 21 | Pi/T topology highpass calculations |
| `test_toroid_inductance.py` | 20 | L↔N math + T68-2 unit-mismatch regression |
| `test_parsing_validation.py` | 20 | Input parsing and validation |
| `test_topology_calculations.py` | 19 | Pi/T topology formulas and component counts |
| `test_toroid_wire.py` | 18 | AWG, wire length, DCR, mechanical fit |
| `test_toroid_selection.py` | 12 | Freq-range gate + ranking algorithm |
| `test_toroid_display.py` | 12 | Full/compact text, JSON, CSV formatters |
| `test_toroid_core_data.py` | 12 | Iron-powder T-series core database |
| `test_wizard_topology_diagrams.py` | 11 | Wizard topology diagram rendering |
| `test_wizard_screens_regressions.py` | 11 | Wizard screen regressions via Mock pattern |
| `test_wizard_state.py` | 2 | FilterState dataclass |
| `conftest.py` | - | Shared pytest fixtures and configuration |

**Total: 1227 tests** (94% coverage)

**New Modules** (tested and integrated):
- `filter_lib/shared/lp_hp_base_calculations.py` - Shared LP/HP strategy calculations
- `filter_lib/shared/lp_hp_base_transfer_functions.py` - Shared LP/HP transfer functions
- `filter_lib/shared/plot_ascii_renderers.py` - ASCII plot rendering with db_floor
- `filter_lib/shared/plot_zoom_pairs.py` - Zoomed passband plot pairs
- `filter_lib/shared/plot_threshold_analysis.py` - dB threshold detection
- `filter_lib/shared/response_export.py` - unified JSON/CSV response export
- `filter_lib/shared/transfer_response_dispatch.py` - Response function factory
- `filter_lib/wizard/filter_type_calculators.py` - Wizard calculation logic
- `filter_lib/wizard/formatting_helpers.py` - Wizard formatting utilities
- `filter_lib/wizard/filter_screen_navigation_mixin.py` - Screen navigation mixin
- `filter_lib/shared/toroid_core_data.py` - 43-core iron-powder T-series database (Apr 2026)
- `filter_lib/shared/toroid_inductance.py` - Turns ↔ inductance math (Apr 2026)
- `filter_lib/shared/toroid_wire.py` - AWG, wire length, DCR, mechanical fit (Apr 2026)
- `filter_lib/shared/toroid_selection.py` - Top-3 recommendation ranking (Apr 2026)
- `filter_lib/shared/toroid_display.py` - Full/compact text, JSON, CSV formatters (Apr 2026)
- `filter_lib/cli/toroid_flags.py` - Shared `--no-toroids` / `--toroid-compact` flags (Apr 2026)
- `filter_lib/wizard/radio_button_helpers.py` - Radio button utilities
- `filter_lib/shared/netlist_simulation.py` - Stdlib AC nodal-analysis solver (Jun 2026)
- `filter_lib/shared/netlist_builders.py` - Component synthesis for simulation (Jun 2026)
- `filter_lib/shared/lp_hp_display.py` - Single LP/HP table renderer for CLI and wizard (Jun 2026)

---

## Test Categories

### Calculation Tests

Verify mathematical correctness of filter component calculations.

**Lowpass (Pi/T Topology)**
- Butterworth coefficient verification against Zverev formulas
- Chebyshev g-value computation for arbitrary ripple
- Bessel filter constants from Thomson filter theory
- Impedance and frequency scaling relationships
- Component count ranges (2-9 elements)

**Highpass (Pi/T Topology)**
- HPF derived from lowpass prototype via 1/g transformation
- T: series capacitors at odd positions, shunt inductors at even positions
- Pi: shunt inductors at odd positions, series capacitors at even positions
- Scaling verification across frequency/impedance ranges

**Bandpass (Coupled Resonator)**
- Coupling coefficient calculations
- External Q computations
- Resonator component sizing
- Tank and coupling capacitor values

### Validation Tests

Verify input validation and error handling.

```python
# Example: Negative impedance rejection
def test_negative_impedance_raises():
    with pytest.raises(ValueError, match="must be positive"):
        parse_impedance("-50ohm")

# Example: Zero frequency rejection
def test_zero_frequency_raises():
    with pytest.raises(ValueError, match="must be positive"):
        parse_frequency("0Hz")
```

**Validated Inputs:**
- Frequency: Must be positive and finite (NaN/inf rejected), supports suffixes (MHz, kHz, M, k, G)
- Impedance: Must be positive and finite (> 0)
- Component count: Must be 2-9
- Chebyshev ripple: Must be positive and finite; wizard and bandpass CLI additionally cap ripple at 3.0 dB (LP/HP CLI enforces only > 0)

### Display Tests

Verify output formatting for all export formats.

**JSON Output**
- Correct structure with filter_type, frequency, impedance
- Component arrays with proper naming (C1, L1, etc.)
- Ripple included for Chebyshev filters

**CSV Output**
- Header row starts `Component,Value,Unit,...` followed by E-series match columns (`NearestStdValue`, `ParallelStdValues`, ...) and toroid columns (`ToroidCore`, `ToroidTurns`, ...)
- Proper component ordering (capacitors first for lowpass)
- Engineering notation units (pF, nF, µH)

**Quiet Mode**
- Minimal output format
- Raw SI values when requested

---

## Coverage Report

### Fully Covered Modules (100%)

| Module | Description |
|--------|-------------|
| `filter_lib/lowpass/calculations.py` | Lowpass component formulas |
| `filter_lib/highpass/calculations.py` | Highpass component formulas |
| `filter_lib/bandpass/calculations.py` | Coupled-resonator and end-coupling formulas |
| `filter_lib/shared/chebyshev_g_calculator.py` | Chebyshev g-value math |
| `filter_lib/shared/constants.py` | Butterworth/Bessel constants |
| `filter_lib/shared/parsing.py` | Input parsing/validation |
| `filter_lib/shared/transfer_functions.py` | Transfer function entry points |

### Partially Covered Modules

| Module | Coverage | Notes |
|--------|----------|-------|
| `filter_lib/shared/display_common.py` | 99% | Core formatting tested |
| `filter_lib/shared/eseries.py` | 98% | Matching algorithms tested |
| `filter_lib/shared/lp_hp_base_calculations.py` | 99% | Strategy logic tested |
| `filter_lib/shared/lp_hp_base_transfer_functions.py` | 98% | Transfer functions tested |

### Wizard Screen Coverage (Mock-Based Testing)

| Module | Coverage | Testing Method |
|--------|----------|-----------------|
| `filter_lib/wizard/screens/lowpass.py` | 78% | Mock(spec=RadioSet/Input/...); `type(screen).app = property(...)` pattern |
| `filter_lib/wizard/screens/highpass.py` | 78% | Mock pattern + state injection |
| `filter_lib/wizard/screens/bandpass.py` | 80% | Mock pattern + validation error paths |
| `filter_lib/wizard/screens/welcome.py` | 76% | Mock pattern + category selection |
| `filter_lib/wizard/screens/output_options.py` | 67% | Mock pattern + option transitions |
| `filter_lib/wizard/screens/results.py` | 85% | Mock pattern + async worker testing |
| `filter_lib/wizard/app.py` | 57% | Screen stack, filter_state access (compose/on_mount uncovered) |

**Coverage Method**: Mock Textual widgets (RadioSet, Input, etc.) with spec enforcement. Override `type(screen).app` via property to inject mock FilterWizardApp. Call screen handler methods directly. Covers all validation paths, state updates, and navigation transitions.

**Deferred**: Full `compose()`/`on_mount` coverage (requires Textual pilot harness for widget mount/layout testing). Core calculation and event logic is fully tested.

---

## Mathematical Verification

### Butterworth Coefficients

Tests verify g-values match published Zverev formulas:

```
g_k = 2 * sin((2k-1) * π / (2n))
```

For n=3: g = [1.0, 2.0, 1.0]

### Chebyshev G-Values

Computed using closed-form expressions:

```python
epsilon = sqrt(10^(ripple_db/10) - 1)
gamma = sinh(asinh(1/epsilon) / n)
```

Tests verify against standard tables for 0.1, 0.5, 1.0, 3.0 dB ripple.

### Bessel Constants

Pre-computed from Thomson filter theory for maximally flat group delay. Verified for orders 2-9.

### Scaling Laws

Tests verify proper frequency and impedance scaling:

```
Lowpass:  C = g / (2π * f * Z0),   L = g * Z0 / (2π * f)
Highpass: C = 1 / (g * 2π * f * Z0), L = Z0 / (g * 2π * f)
```

---

## Testing CLI Subcommands

### Namespace Builder Pattern

CLI subcommands are tested by constructing `argparse.Namespace` objects directly, without re-parsing argv:

```python
# From tests/test_cli_and_helpers.py
from filter_lib.cli.lowpass_cmd import run as lowpass_run

def test_lowpass_cli_butterworth():
    """Test lowpass CLI command with Namespace builder."""
    args = _lp_args(filter_type="butterworth", components=5)
    lowpass_run(args)  # prints the result table
```

**Builders** (`_lp_args`, `_hp_args`, `_bp_args`) are helper functions in `tests/test_cli_and_helpers.py`. Each returns a properly configured Namespace with all required fields and defaults; pass overrides as kwargs to exercise validation branches.

### Direct setup_parser() Invocation

Parser setup can also be tested directly:

```python
def test_lowpass_parser_setup():
    """Verify lowpass subcommand parser configuration."""
    parser = argparse.ArgumentParser()
    lowpass_cmd.setup_parser(parser)
    # Verify parser has expected arguments
    args = parser.parse_args([...])
    assert args.filter_type is not None
```

---

## Coverage Reports

### Terminal Summary

```bash
uv run pytest tests/ --cov=filter_lib --cov-report=term-missing
```

### JSON Report (for CI/analysis)

```bash
uv run pytest tests/ --cov=filter_lib --cov-report=json:/tmp/rf-cov.json
```

Produces JSON with per-module coverage percentages for programmatic analysis.

---

## Adding New Tests

### Test Structure

```python
import pytest
from filter_lib.module import function_to_test

class TestFeatureName:
    """Tests for specific feature."""

    def test_basic_case(self):
        """Describe what this tests."""
        result = function_to_test(args)
        assert result == expected

    def test_edge_case(self):
        """Test boundary conditions."""
        with pytest.raises(ValueError):
            function_to_test(invalid_args)
```

### Fixtures

Common test data is provided via pytest fixtures:

```python
@pytest.fixture
def lowpass_result():
    """Sample lowpass filter result."""
    return {
        'filter_type': 'butterworth',
        'freq_hz': 10e6,
        'impedance': 50.0,
        'order': 5,
        'capacitors': [1e-10, 2e-10, 1e-10],
        'inductors': [1e-6, 1e-6],
        'ripple': None,
    }
```

### Naming Conventions

- Test files: `test_<module_name>.py`
- Test classes: `Test<FeatureName>`
- Test methods: `test_<specific_behavior>`

---

## Continuous Integration

### GitHub Actions CI Pipeline

Tests run automatically on every push and PR to `main` via `.github/workflows/ci.yml`:

**Pipeline stages:**
1. **Lint** - Ruff linting checks (errors fail fast)
2. **Format** - Ruff format verification
3. **Test** - Full pytest suite with coverage reporting

**Environment:**
- Python 3.13
- ubuntu-latest runner
- Full dev dependencies group

### Running Tests Locally

```bash
# Standard test run
uv run pytest tests/ -v

# With coverage threshold
uv run pytest tests/ --cov=filter_lib --cov-fail-under=80

# Generate HTML coverage report
uv run pytest tests/ --cov=filter_lib --cov-report=html
```

### Code Linting

[Ruff](https://docs.astral.sh/ruff/) enforces code quality:

```bash
# Check for linting issues
uv run ruff check .

# Format code
uv run ruff format .

# Check formatting without changes
uv run ruff format --check .
```

**Configuration** (pyproject.toml):
- Target: Python 3.10+
- Line length: 100 chars
- Rules: E (errors), F (pyflakes), I (imports), UP (upgrades), B (flake8-bugbear)
- Ignored: E501 (line too long - handled by formatter), B905

---

## Troubleshooting

### Import Errors

Ensure the package is installed in development mode:

```bash
uv sync --group dev
```

### Coverage Not Detected

Run from repository root:

```bash
cd /path/to/rf-filter-calculator
uv run pytest tests/ --cov=filter_lib
```

### Specific Test Failures

Run individual test with verbose output:

```bash
uv run pytest tests/test_lowpass_calculations.py::TestButterworthLowpass::test_basic_2component_50ohm_1mhz -v
```
