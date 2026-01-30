# Code Standards & Architecture Guidelines

Standards and patterns for maintaining code quality in RF Filter Calculator.

## Naming Conventions

### Files & Modules
- **Python files**: kebab-case with descriptive names
  - `chebyshev_g_calculator.py` - describes function clearly
  - `display_common.py` - obvious purpose
  - `topology_diagrams.py` - explicit intent
- **Avoid**: Abbreviations (e.g., don't use `calc.py`, use `calculations.py`)
- **Exception**: `__init__.py` for Python package structure

### Functions & Variables
- **Functions**: snake_case (lowercase with underscores)
  - `format_capacitance()` - clear purpose
  - `_primary_component()` - leading underscore = internal only
- **Constants**: UPPER_SNAKE_CASE
  - `E24_VALUES = [...]`
  - `DEFAULT_IMPEDANCE = 50`
- **Classes**: PascalCase
  - `FilterResult`, `ChebyshevCalculator`
- **Variables**: snake_case
  - `capacitors`, `impedance_ohms`, `filter_type`

### Modules & Packages
- **Lowercase with underscores**: `lowpass`, `highpass`, `bandpass`, `shared`, `wizard`
- **Purpose-driven**: Module names should indicate what they contain

## Code Organization

### File Structure

**Calculation modules** (e.g., `lowpass/calculations.py`):
```python
"""Module docstring describing purpose."""

# Imports
from ..shared.constants import ...
from ..shared.parsing import ...

# Main functions
def calculate_lowpass_pi(...) -> dict:
    """Calculate lowpass Pi topology values.

    Args:
        freq_hz: Cutoff frequency in Hz
        impedance: System impedance in ohms
        order: Filter order (2-9)
        ...

    Returns:
        dict with keys: filter_type, freq_hz, impedance, order,
                        capacitors, inductors, topology
    """
```

**Display modules** (e.g., `lowpass/display.py`):
```python
"""Display functions for low-pass filters."""

from ..shared.formatting import format_capacitance, ...
from ..shared.display_common import format_json_result, ...

def _primary_component(result: dict) -> str:
    """Internal helper for identifying primary component."""

def display_results(result: dict, raw: bool = False, ...) -> None:
    """Main display function - called by CLI."""
```

### Import Organization
1. Standard library imports
2. Third-party imports (Click, Rich)
3. Local relative imports (`..shared`, etc.)
4. Blank line between groups

Example:
```python
import json
from io import StringIO
from typing import Optional

import click
from rich.table import Table

from ..shared.parsing import parse_frequency
from ..shared.formatting import format_capacitance
```

## Code Quality Standards

### Docstrings
- **Module level**: Brief description of module purpose
- **Functions**: Include Args, Returns, Raises sections
- **Classes**: Document init parameters and key methods

```python
def calculate_chebyshev_g_values(order: int, ripple_db: float) -> list:
    """Calculate normalized g-values for Chebyshev filter.

    Uses standard formulas from Matthaei/Young/Jones.

    Args:
        order: Filter order (2-9, must be even for Chebyshev)
        ripple_db: Passband ripple in dB (typically 0.5 or 1.0)

    Returns:
        list of normalized g-values

    Raises:
        ValueError: If order is odd or ripple is negative
    """
```

### Type Hints
- All functions should have type hints for parameters and return values
- Use `Optional[T]` for nullable types
- Use `Union[A, B]` for multiple types

```python
def format_frequency(freq_hz: float, decimals: int = 2) -> str:
    """Format frequency in Hz to human-readable form."""

def find_eseries_match(value: float,
                       series: str = 'E24',
                       tolerance: Optional[float] = None) -> dict:
    """Find E-series component matches."""
```

### Error Handling
- Use descriptive error messages
- Validate inputs early with clear validation errors
- Use `ValueError` for invalid parameters
- Use `RuntimeError` for unexpected conditions

```python
def parse_frequency(freq_str: str) -> float:
    """Parse frequency string to Hz."""
    try:
        value = float(freq_str)
    except ValueError:
        raise ValueError(f"Invalid frequency: {freq_str}")

    if value <= 0:
        raise ValueError(f"Frequency must be positive, got {value}")

    return value
```

### Function Length
- **Target**: 30-50 lines per function
- **Guideline**: Extract subroutines if function exceeds 80 lines
- **Exception**: Data structure initialization or complex conditionals

### Comments
- Explain **why**, not **what** (code shows what)
- Focus on non-obvious logic or design decisions
- Keep comments updated with code changes

```python
# ✓ Good - explains non-obvious calculation
# Series inductors in Pi topology are symmetrical for equal ripple
L1 = L2 = Z0 / (2 * pi * fc)

# ✗ Poor - repeats what code obviously does
# Calculate L1
L1 = Z0 / (2 * pi * fc)
```

## Patterns & Best Practices

### Result Dictionary Pattern
All calculation functions return a standard dictionary:

```python
result = {
    'filter_type': 'butterworth',           # str
    'freq_hz': 10e6,                        # float
    'impedance': 50.0,                      # float
    'order': 5,                             # int
    'topology': 'pi',                       # str: pi/t/top/shunt
    'capacitors': [1e-10, 2e-10, ...],     # list[float] Farads
    'inductors': [1e-6, ...],              # list[float] Henries
    'ripple': 0.5,                          # float or None
}
```

### Primary Component Concept
Functions identify which component type is "primary" (shown in E-series matching):

```python
def _primary_component(result: dict) -> str:
    """Return primary component type based on topology.

    Lowpass Pi: Capacitors are in shunt (odd positions)
    Lowpass T: Inductors are in series (odd positions)
    Highpass T: Capacitors are in series (odd positions)
    Highpass Pi: Inductors are in shunt (odd positions)
    """
    if result['filter_type'] == 'lowpass':
        return 'capacitors' if result['topology'] == 'pi' else 'inductors'
    else:  # highpass
        return 'inductors' if result['topology'] == 'pi' else 'capacitors'
```

### Display Module Interface
Each filter type implements consistent display interface:

```python
def display_results(result: dict, raw: bool = False,
                    output_format: str = 'table', quiet: bool = False,
                    eseries: str = 'E24', show_match: bool = True,
                    show_plot: bool = False) -> None:
    """Display calculated filter component values."""
    # Router pattern: delegate to format function
    if output_format == 'json':
        print(format_json(result))
        return
    if output_format == 'csv':
        print(format_csv(result), end='')
        return
    if quiet:
        print(format_quiet(result, raw))
        return

    # Main table display logic
    print_header(result, ...)
    print_topology_diagram(...)
    print_component_table(...)
    if show_match:
        print_eseries_recommendations(...)
    if show_plot:
        print_frequency_response(...)
```

### Shared Utilities Pattern
Reduce duplication via centralized shared functions:

- `display_common.py` - Shared display formatting
- `formatting.py` - Number formatting (mF, pF, µH, nH)
- `eseries.py` - E-series value databases
- `topology_diagrams.py` - ASCII circuit diagrams
- `transfer_functions.py` - Transfer function calculations

## Testing Standards

### Test Organization
- One test file per major module
- Test file naming: `test_{module_name}.py`
- Tests should be independent and isolated

### Test Structure
```python
def test_lowpass_pi_butterworth():
    """Test lowpass Pi topology Butterworth filter."""
    result = calculate_lowpass_pi(
        freq_hz=10e6,
        impedance=50,
        order=3,
        filter_type='butterworth'
    )

    assert result['filter_type'] == 'butterworth'
    assert result['topology'] == 'pi'
    assert len(result['capacitors']) == 3
    assert len(result['inductors']) == 2
    assert all(c > 0 for c in result['capacitors'])
```

### Fixtures
Use pytest fixtures for common test data:

```python
@pytest.fixture
def lowpass_result():
    """Sample lowpass filter result."""
    return {
        'filter_type': 'butterworth',
        'freq_hz': 10e6,
        'impedance': 50.0,
        'order': 3,
        'capacitors': [1e-10, 2e-10, 1e-10],
        'inductors': [1e-6, 1e-6],
        'ripple': None,
        'topology': 'pi',
    }
```

### Coverage
- Target: >90% code coverage
- Run tests with coverage: `uv run pytest tests/ --cov=filter_lib`
- Focus on logic branches, not 100% line coverage

## Performance Considerations

### Optimization Priority
1. **Correctness** - Never sacrifice accuracy for speed
2. **Readability** - Code must be maintainable
3. **Performance** - Optimize only if measurable bottleneck

### Common Bottlenecks (Acceptable)
- Frequency response calculation (multiple frequency points) - acceptable
- E-series matching loops (at most ~100 iterations) - acceptable
- Transfer function evaluation - optimized already

## Security Standards

### Input Validation
- Validate all user inputs at entry point
- Check frequency > 0
- Check impedance > 0
- Check order in range [2, 9]
- Check ripple >= 0 for Chebyshev

### Safe Data Handling
- No shell command execution
- No unsafe eval/exec
- All file I/O uses pathlib or relative paths
- No credential handling in code

## File Size Guidelines

| File Type | Soft Limit | Hard Limit | Rationale |
|-----------|-----------|-----------|-----------|
| Calculation module | 120 lines | 150 lines | Keep logic focused |
| Display module | 90 lines | 120 lines | Easy to understand |
| Shared utility | 150 lines | 200 lines | Complex helpers OK |
| Main entry point | N/A | 400 lines | Router exception |
| Test file | 200 lines | 300 lines | Keep test focused |

**Splitting strategy**: When approaching limit, extract subroutines or move helpers to shared module.

## Documentation in Code

### Inline Documentation
- Add docstrings to all public functions
- Comment non-obvious logic
- Document mathematical formulas or references

### References
- Include source citations for algorithms
- Example: "Based on Matthaei/Young/Jones normalized g-values"
- Link to filter theory docs where applicable

## Recent Refactoring Principles

Based on commit history:

1. **Centralize display logic** - Move common formatting to `display_common.py`
2. **Reduce branching** - Simplify topology handling in display modules
3. **Consistent interfaces** - Align all filter display modules
4. **Clear naming** - Descriptive function names over abbreviations
5. **Topological awareness** - Helper functions identify primary components per topology
