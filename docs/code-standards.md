# Code Standards & Architecture Guidelines

**Last Updated**: April 2, 2026

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

## Code Quality & Linting Standards

### Ruff Linting

[Ruff](https://docs.astral.sh/ruff/) enforces code quality across the project:

**Configuration** (pyproject.toml):
```toml
[tool.ruff]
target-version = "py310"
line-length = 100

[tool.ruff.lint]
select = ["E", "F", "I", "UP", "B"]
ignore = ["E501", "B905"]
```

**Rules enforced:**
- `E` - PEP 8 errors (indentation, whitespace, imports)
- `F` - Pyflakes (undefined names, unused imports, duplicates)
- `I` - isort (import sorting)
- `UP` - pyupgrade (Python 3.10+ syntax upgrades, f-strings)
- `B` - flake8-bugbear (likely bugs: `lambda x: ...` should be `def`, etc.)

**Ignored:**
- `E501` - Line too long (handled by formatter instead)
- `B905` - `zip()` without strict (Python 3.10 compat)

**Running linting locally:**
```bash
uv run ruff check .          # Report issues
uv run ruff check . --fix    # Auto-fix issues
uv run ruff format .         # Format code
uv run ruff format --check . # Check without changes
```

**Recent reformatting** (all 67 affected files):
- Lambda functions converted to `def` (E731)
- F-string syntax upgraded for py310+ compatibility
- Unused variable cleanup
- Import organization standardized

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

**Core Utilities:**
- `display_common.py` - Shared display formatting
- `formatting.py` - Number formatting (mF, pF, µH, nH)
- `eseries.py` - E-series value databases
- `topology_diagrams.py` - ASCII circuit diagrams
- `transfer_functions.py` - Transfer function calculations

**New Base Modules (Strategy Pattern for LP/HP):**
- `lp_hp_base_calculations.py` - Strategy-based LP/HP calculation logic
- `lp_hp_base_transfer_functions.py` - Shared transfer function implementations

**Pattern**: LP/HP calculation modules delegate to base modules, passing strategy functions to handle topology-specific differences (denormalization, component ordering).

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

## Wizard Module Architecture

See [system-architecture.md § Layer 4: Wizard Module](./system-architecture.md) for detailed wizard architecture, screen navigation flow, and state management patterns.

### Refactored Structure (Recent Simplification)

**calculation_handler.py** (35 LOC after refactoring):
- Minimal orchestration router
- Delegates to type-specific calculators
- Routes output formatting to helpers

**filter_type_calculators.py** (185 LOC):
- Contains _calculate_lowpass, _calculate_highpass, _calculate_bandpass
- Handles filter selection and parameter passing
- Calls shared base calculation modules

**formatting_helpers.py** (155 LOC):
- Wizard-specific formatting logic
- E-series matching display
- Output format selection (table/json/csv)

**Key Mixins:**
- `filter_screen_navigation_mixin.py` - Shared screen navigation logic
- `radio_button_helpers.py` - Radio button widget utilities

## Textual TUI Patterns

### Screen Architecture
Each wizard screen is an independent Textual `Screen` subclass:

```python
from textual.screen import Screen
from textual.app import ComposeResult

class LowpassScreen(Screen):
    """Lowpass filter configuration screen."""

    BINDINGS = [
        ("escape", "back", "Back"),
    ]

    def compose(self) -> ComposeResult:
        """Create screen widgets."""
        yield Header()
        with VerticalScroll(classes="content"):
            # Form fields
            yield Input(id="frequency", ...)
        yield Footer()

    @on(Button.Pressed, "#submit")
    def handle_submit(self):
        """Validate and update shared state."""
        state = self.app.query_one(FilterState)
        state.frequency_hz = parse_frequency(...)
        self.app.push_screen(OutputOptionsScreen())
```

### State Management
Use centralized `FilterState` dataclass for all screen-to-screen data sharing:

```python
@dataclass
class FilterState:
    """Shared filter parameters across all screens."""
    # Filter selection
    category: str = ""                         # lowpass/highpass/bandpass
    filter_type: str = "butterworth"
    topology: str = "pi"                       # pi, t for LP/HP; top, shunt for BP

    # Frequency parameters
    frequency_hz: float = 0.0                  # cutoff for LP/HP, center for BP
    bandwidth_hz: float = 0.0                  # bandpass only

    # Common parameters
    impedance: float = 50.0
    order: int = 3                             # num_components or resonators
    ripple_db: float = 0.5

    # Output options
    eseries: str = "E24"
    output_format: str = "table"
    show_plot: bool = True
    export_format: Optional[str] = None
    raw_units: bool = False
    quiet: bool = False

    # Results (populated after calculation)
    result: dict = {}
    output_text: str = ""
```

### Async Calculations
For expensive operations, use background workers to prevent UI freezing:

```python
def on_mount(self) -> None:
    """Start background calculation when results screen mounted."""
    self.run_worker(
        self._calculate_results(),
        exclusive=True,
        thread=True
    )

def _calculate_results(self) -> None:
    """Run calculation in background thread."""
    result = calculate_filter(...)  # Expensive calculation
    self.post_message(self.ResultsReady(result))

@on(ResultsReady)
def handle_results(self, message: ResultsReady) -> None:
    """Update display with calculated results."""
    self.result = message.result
    self.refresh()
```

### Navigation
Use `push_screen()` for forward navigation and `pop_screen()` for back:

```python
# Forward navigation with data passing
self.app.push_screen(OutputOptionsScreen())

# Back navigation
self.app.pop_screen()

# From Action binding (Escape key)
def action_back(self) -> None:
    """Go back to previous screen."""
    self.app.pop_screen()
```

## File Size Guidelines

| File Type | Soft Limit | Hard Limit | Rationale |
|-----------|-----------|-----------|-----------|
| Calculation module | 120 lines | 150 lines | Keep logic focused |
| Display module | 90 lines | 120 lines | Easy to understand |
| Shared utility | 150 lines | 200 lines | Complex helpers OK |
| Textual screen | 250 lines | 300 lines | Screen-specific logic |
| Main entry point | N/A | 400 lines | Router exception |
| Test file | 200 lines | 300 lines | Keep test focused |
| Documentation file | Soft limit: 800 LOC | Keep searchable and focused |

**Splitting strategy**: When approaching limit, extract subroutines or move helpers to shared module. For screens, extract complex validation to shared validators module or move business logic to calculation_handler.

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
