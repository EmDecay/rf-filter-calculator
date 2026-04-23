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
| `test_cli_and_helpers.py` | 50 | CLI commands, plotting, and formatting helpers |
| `test_transfer_functions.py` | 49 | Frequency response (shared + LPF/HPF/BPF) |
| `test_display_modules.py` | 49 | Output formatting (JSON/CSV/table/topology) |
| `test_bandpass_modules.py` | 39 | Bandpass g-values, formatters, display, diagrams |
| `test_eseries_matching.py` | 35 | E12/E24/E96 component matching |
| `test_bandpass_calculations.py` | 26 | Coupled resonator calculations |
| `test_lowpass_calculations.py` | 24 | Pi/T topology lowpass calculations |
| `test_highpass_calculations.py` | 20 | Pi/T topology highpass calculations |
| `test_topology_calculations.py` | 19 | Pi/T topology formulas and component counts |
| `test_parsing_validation.py` | 18 | Input parsing and validation |
| `test_chebyshev_calculator.py` | 15 | Chebyshev g-value computation |
| `test_wizard_unit.py` | 40+ | Wizard module unit tests (Feb 2026) |
| `test_plotting_edge_cases.py` | 15+ | ASCII plot edge cases (Feb 2026) |
| `test_plot_threshold_analysis.py` | 41 | dB threshold detection and summary tables (Apr 2026) |
| `test_plot_zoomed.py` | 68 | Zoomed passband plot computation and rendering (Apr 2026) |
| `test_transfer_response_dispatch.py` | 26 | Response function factory (Apr 2026) |
| `test_toroid_core_data.py` | 12 | Iron-powder T-series core database (Apr 2026) |
| `test_toroid_inductance.py` | 16 | L↔N math + T68-2 unit-mismatch regression (Apr 2026) |
| `test_toroid_wire.py` | 16 | AWG, wire length, DCR, mechanical fit (Apr 2026) |
| `test_toroid_selection.py` | 12 | Freq-range gate + ranking algorithm (Apr 2026) |
| `test_toroid_display.py` | 12 | Full/compact text, JSON, CSV formatters (Apr 2026) |
| `test_toroid_integration.py` | 19 | End-to-end LP/HP/BP × flag matrix (Apr 2026) |
| `conftest.py` | - | Shared pytest fixtures and configuration |

**Total: 826 tests**

**New Modules** (tested and integrated):
- `filter_lib/shared/lp_hp_base_calculations.py` - Shared LP/HP strategy calculations
- `filter_lib/shared/lp_hp_base_transfer_functions.py` - Shared LP/HP transfer functions
- `filter_lib/shared/plot_ascii_renderers.py` - ASCII plot rendering with db_floor
- `filter_lib/shared/plot_zoom_pairs.py` - Zoomed passband plot pairs
- `filter_lib/shared/plot_threshold_analysis.py` - dB threshold detection
- `filter_lib/shared/plot_data_export.py` - JSON/CSV export
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
- Frequency: Must be positive (> 0), supports suffixes (MHz, kHz, M, k, G)
- Impedance: Must be positive (> 0)
- Component count: Must be 2-9
- Chebyshev ripple: Must be positive

### Display Tests

Verify output formatting for all export formats.

**JSON Output**
- Correct structure with filter_type, frequency, impedance
- Component arrays with proper naming (C1, L1, etc.)
- Ripple included for Chebyshev filters

**CSV Output**
- Header row: `Component,Value,Unit`
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
| `filter_lib/shared/chebyshev_g_calculator.py` | Chebyshev g-value math |
| `filter_lib/shared/constants.py` | Butterworth/Bessel constants |
| `filter_lib/shared/parsing.py` | Input parsing/validation |

### Partially Covered Modules

| Module | Coverage | Notes |
|--------|----------|-------|
| `filter_lib/shared/display_common.py` | 93% | Core formatting tested |
| `filter_lib/shared/eseries.py` | 91% | Matching algorithms tested |
| `filter_lib/bandpass/calculations.py` | 44% | Core formulas tested |
| `filter_lib/shared/lp_hp_base_calculations.py` | 85%+ | Strategy logic tested (Feb 2026) |
| `filter_lib/shared/lp_hp_base_transfer_functions.py` | 80%+ | Transfer functions tested (Feb 2026) |

### Not Covered (Interactive)

| Module | Reason |
|--------|--------|
| `filter_lib/wizard/screens/*.py` | Interactive TUI screens require user input |
| `filter_lib/wizard/app.py` | Screen stack navigation requires user interaction |

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
