# Testing Guide

Comprehensive test suite for the RF Filter Calculator.

---

## Running Tests

### Quick Start

```bash
# Run all tests
pytest tests/

# Run with verbose output
pytest tests/ -v

# Run specific test file
pytest tests/test_lowpass_calculations.py

# Run with coverage report
pytest tests/ --cov=filter_lib --cov-report=term-missing
```

### Requirements

```bash
pip install pytest pytest-cov
```

---

## Test Suite Overview

| Test File | Tests | Description |
|-----------|-------|-------------|
| `test_lowpass_calculations.py` | 35 | Pi topology filter calculations |
| `test_highpass_calculations.py` | 20 | T topology filter calculations |
| `test_chebyshev_calculator.py` | 21 | Chebyshev g-value computation |
| `test_eseries_matching.py` | 37 | E12/E24/E96 component matching |
| `test_bandpass_calculations.py` | 27 | Coupled resonator calculations |
| `test_parsing_validation.py` | 18 | Input parsing and validation |
| `test_display_modules.py` | 21 | Output formatting (JSON/CSV/table) |

**Total: 167+ tests**

---

## Test Categories

### Calculation Tests

Verify mathematical correctness of filter component calculations.

**Lowpass (Pi Topology)**
- Butterworth coefficient verification against Zverev formulas
- Chebyshev g-value computation for arbitrary ripple
- Bessel filter constants from Thomson filter theory
- Impedance and frequency scaling relationships
- Component count ranges (2-9 elements)

**Highpass (T Topology)**
- Dual transformation from lowpass prototype
- Proper component ordering (series inductors, shunt capacitors)
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

### Not Covered (Interactive/CLI)

| Module | Reason |
|--------|--------|
| `filter_lib/wizard/*.py` | Interactive prompts require user input |
| `filter_lib/cli/*.py` | Argument parsing wrappers |

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
C_scaled = C_prototype / (2π * f * Z0)
L_scaled = L_prototype * Z0 / (2π * f)
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

Tests run automatically on:
- Pull requests
- Commits to main branch

### CI Commands

```bash
# Standard test run
pytest tests/ -v

# With coverage threshold
pytest tests/ --cov=filter_lib --cov-fail-under=80

# Generate HTML coverage report
pytest tests/ --cov=filter_lib --cov-report=html
```

---

## Troubleshooting

### Import Errors

Ensure the package is installed in development mode:

```bash
pip install -e .
```

### Coverage Not Detected

Run from repository root:

```bash
cd /path/to/rf-filter-calculator
pytest tests/ --cov=filter_lib
```

### Specific Test Failures

Run individual test with verbose output:

```bash
pytest tests/test_lowpass_calculations.py::TestButterworthLowpass::test_basic_2component_50ohm_1mhz -v
```
