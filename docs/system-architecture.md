# System Architecture

**Last Updated**: April 24, 2026

Detailed architecture design and component interactions for RF Filter Calculator.

## System Overview

**RF Filter Calculator** is a command-line tool that computes LC filter component values for RF circuits. The system follows a modular architecture with clear separation of concerns:

```
┌─────────────────────────────────────────────────────┐
│          CLI Entry Point (filter-calc.py)           │
│  - Argument parsing                                 │
│  - Command routing                                  │
│  - Error handling                                   │
└─────────────────────────────────────────────────────┘
                        │
         ┌──────────────┼──────────────┐
         │              │              │
    ┌────▼─────┐  ┌────▼─────┐  ┌────▼──────┐
    │ Lowpass  │  │ Highpass │  │ Bandpass  │
    │ Subcommand   │ Subcommand   │ Subcommand
    └────┬─────┘  └────┬─────┘  └────┬──────┘
         │              │              │
    ┌────▼──────────────┴──────────────▼──────┐
    │  Filter Calculation Modules              │
    │  - calculations.py (topology-specific)   │
    │  - transfer.py (frequency response)      │
    │  - display.py (output formatting)        │
    └────┬───────────────────────────────────┘
         │
    ┌────▼──────────────────────────────┐
    │  Shared Utilities (filter_lib/shared/)   │
    │  - Parsing & validation            │
    │  - Formatting & display            │
    │  - E-series matching               │
    │  - Transfer functions              │
    │  - Topology diagrams               │
    └────────────────────────────────────┘
```

## Component Architecture

### Layer 1: CLI Entry Point

**File**: `filter-calc.py`

```python
# Responsibilities
- Parse command-line arguments (Click framework)
- Route to appropriate subcommand (lowpass/highpass/bandpass/wizard)
- Invoke wizard if no arguments provided
- Handle top-level exceptions
```

**Key Functions**:
- `main()` - Entry point, routes to subcommands
- `cli` - Click group for subcommand registration

### Layer 2: Subcommand Handlers

**Location**: `filter_lib/cli/`

Each file handles one filter type:

#### `lowpass_cmd.py`
```python
@click.command('lowpass')  # Register as 'lowpass' subcommand
def lowpass(filter_type, topology, frequency, ...):
    """Handle lowpass filter calculations and display."""
    # 1. Validate inputs using shared parsing
    freq_hz = parse_frequency(frequency)
    # 2. Call calculation module
    result = calculate_lowpass(freq_hz, topology, ...)
    # 3. Route to appropriate display
    display_results(result, format=output_format, ...)
```

**Pattern**: Input → Validate → Calculate → Display

#### `highpass_cmd.py` & `bandpass_cmd.py`
Similar structure, filter-type-specific inputs.

#### `wizard_cmd.py`
Interactive mode coordinator (Textual TUI):
- Entry point for interactive wizard mode
- Initializes FilterWizardApp and starts event loop
- Routes back to CLI with final results if needed

### Layer 3: Filter Calculation Modules

**Directories**: `filter_lib/{lowpass,highpass,bandpass}/`

Each filter type has three core modules:

#### `calculations.py`
```python
# Core responsibility: Compute component values

def calculate_lowpass_pi(freq_hz, impedance, order, filter_type, ripple):
    """Calculate Pi topology lowpass filter values.

    Design Process:
    1. Compute normalized g-values (butterworth/chebyshev/bessel tables)
    2. Denormalize for given frequency and impedance
    3. Build result dictionary
    4. Return for display and verification
    """
    g_values = get_normalized_values(order, filter_type, ripple)
    capacitors = [denormalize_cap(g, Z0, fc) for g in g_caps]
    inductors = [denormalize_ind(g, Z0, fc) for g in g_inds]
    return {
        'filter_type': filter_type,
        'freq_hz': freq_hz,
        'impedance': impedance,
        'order': order,
        'capacitors': capacitors,
        'inductors': inductors,
        'topology': 'pi',
        'ripple': ripple,
    }
```

**Result Dictionary** (Standard across all filters):
```python
{
    'filter_type': 'butterworth' | 'chebyshev' | 'bessel',
    'freq_hz': float,                    # Frequency in Hz
    'impedance': float,                  # Impedance in ohms
    'order': int,                        # Filter order (2-9)
    'capacitors': list[float],           # Values in Farads
    'inductors': list[float],            # Values in Henries
    'ripple': float | None,              # Chebyshev ripple in dB
    'topology': 'pi' | 't' | 'top' | 'shunt',
}
```

#### `transfer.py`
```python
# Responsibility: Compute frequency response

def frequency_response(filter_type, frequencies, cutoff_hz, order, ripple=None):
    """Calculate magnitude response at each frequency.

    Algorithm:
    1. Build transfer function H(s) from normalized g-values
    2. Substitute s = j*2*pi*f for each frequency point
    3. Compute magnitude |H(jw)| in dB
    4. Return response array
    """
    # Uses transfer function formulas from filter theory
    # For Butterworth: |H(jw)| = 1 / sqrt(1 + (w/wc)^(2n))
    # For Chebyshev: Uses Chebyshev polynomial
```

#### `display.py`
```python
# Responsibility: Format results for user output

def display_results(result, format='table', raw=False, eseries='E24', ...):
    """Route to appropriate formatter."""
    if format == 'json':
        print(format_json(result))
    elif format == 'csv':
        print(format_csv(result))
    elif format == 'quiet':
        print(format_quiet(result, raw))
    else:  # default: table
        print_header(result)
        print_topology_diagram(result)
        print_component_table(result, raw)
        if show_eseries:
            print_eseries_recommendations(result, eseries)
        if show_plot:
            print_frequency_response_plot(result)
```

### Layer 4: Wizard Module (Textual TUI)

**Location**: `filter_lib/wizard/`

**Framework**: Textual - Terminal User Interface library for rich interactive applications

#### Architecture Overview

```
FilterWizardApp (Textual App)
├─ Manages screen stack
├─ Stores centralized FilterState
└─ Bindings:
   ├─ Escape: Back (pop screen)
   ├─ Ctrl+C: Quit
   └─ Tab/Shift+Tab: Navigate fields

Screen Stack (User Workflow):
  1. WelcomeScreen
     └─ Select filter category (lowpass/highpass/bandpass)
        │
        ├─ LowpassScreen (if lowpass)
        │   └─ Collect: frequency, topology, impedance, order, ripple
        ├─ HighpassScreen (if highpass)
        │   └─ Collect: frequency, topology, impedance, order, ripple
        └─ BandpassScreen (if bandpass)
            └─ Collect: center_frequency, bandwidth, impedance, resonators, ripple
        │
        └─ OutputOptionsScreen
            ├─ E-series selection (E12/E24/E96/None)
            ├─ Output format (table/json/csv)
            ├─ Export data format (no/json/csv)
            ├─ Additional flags (raw/quiet)
            └─ Show frequency response plot? (Y/n)
        │
        └─ ResultsScreen
            └─ Display calculated output with async worker
```

#### Core Components

**`app.py` - FilterWizardApp**
- Textual App subclass
- Manages screen navigation via push_screen/pop_screen
- Stores FilterState singleton (self.filter_state)
- Binds keyboard shortcuts (Escape=back, Ctrl+C=quit)

```python
class FilterWizardApp(App):
    BINDINGS = [
        Binding("escape", "back", "Back"),
        Binding("ctrl+c", "quit", "Quit"),
        Binding("tab", "focus_next", "Next"),
    ]

    def on_mount(self):
        self.push_screen(WelcomeScreen())
```

**`state.py` - FilterState**
- Dataclass holding all filter parameters
- Shared across all screens via app.filter_state
- Mutable: screens update state, results screen reads final state

```python
@dataclass
class FilterState:
    category: str = ""              # lowpass, highpass, bandpass
    filter_type: str = "butterworth"  # butterworth, chebyshev, bessel
    topology: str = "pi"            # pi, t (for LP/HP); top, shunt (BP)
    frequency_hz: float = 0.0
    bandwidth_hz: float = 0.0       # bandpass only
    impedance: float = 50.0
    order: int = 3
    ripple_db: float = 0.5
    # ... output options, results
```

**Screen Implementations** (`screens/`)

Each screen extends `Screen` and uses Textual widgets:

1. **WelcomeScreen** - Category selection
   - Radio buttons for lowpass/highpass/bandpass
   - On selection: push appropriate filter screen

2. **LowpassScreen/HighpassScreen** - Parameter collection
   - Input fields: frequency, impedance, order
   - Select/Radio: topology (Pi/T), response type
   - Conditional UI: ripple field shows only for Chebyshev
   - Vertical scrolling for terminals <25 lines
   - On submit: push output_options screen

3. **BandpassScreen** - Bandpass-specific parameters
   - Input fields: center_frequency, bandwidth, impedance, resonators
   - Select/Radio: topology (top/shunt), response type
   - Conditional ripple field
   - On submit: push output_options screen

4. **OutputOptionsScreen** - Output configuration
   - Radio buttons: E-series (E12/E24/E96/None)
   - Radio buttons: format (table/json/csv)
   - Checkboxes: raw_units, quiet_mode
   - Radio buttons: export format (no/json/csv)
   - On confirm: push results screen

5. **ResultsScreen** - Display results
   - Shows loading indicator
   - Spawns async Worker thread for calculation
   - On calculation complete: displays formatted output
   - Prompt for frequency response plot (Y/n)

**`calculation_handler.py` - Calculation Orchestration** (35 LOC)

Router for orchestrating calculations (refactored):

```python
def calculate_and_format(state: FilterState) -> str:
    """Perform calculation and return formatted output."""
    if state.category == "lowpass":
        return _calculate_lowpass(state)
    elif state.category == "highpass":
        return _calculate_highpass(state)
    elif state.category == "bandpass":
        return _calculate_bandpass(state)
```

**Calculation & Formatting (Extracted)**:
- `filter_type_calculators.py` (185 LOC) - LP/HP/BP type-specific calculations
- `formatting_helpers.py` (155 LOC) - Wizard output formatting
- `filter_screen_navigation_mixin.py` (46 LOC) - Reusable screen navigation logic
- `radio_button_helpers.py` (19 LOC) - Radio button widget utilities

Module responsibilities:
- calculation_handler.py - Routing only
- filter_type_calculators.py - Calculation logic (strategies for each filter type)
- formatting_helpers.py - Display formatting specific to wizard output
- filter_screen_navigation_mixin.py - Shared navigation behavior for screens
- radio_button_helpers.py - Reusable radio button widget creation

**`validation.py` - Input Validators**

Reusable validators for user inputs:
- `validate_frequency(hz)` - Must be positive
- `validate_impedance(ohms)` - Must be positive
- `validate_order(n, category)` - 2-9 range
- `validate_ripple(db)` - Must be positive

**`styles.tcss` - Textual CSS** (192 lines)

Styling rules for all screens:
- Input field focus colors
- Button highlighting
- Scrollbar styling
- Grid layouts

**`widgets/` directory - Custom Widgets**

Placeholder for future custom Textual widget extensions:
- Can add custom Input subclasses for specialized validation
- Can add composite widgets combining multiple Textual widgets
- Currently minimal: future enhancement point for reusable UI components

#### User Interaction Flow

```
1. User runs: uv run filter-calc
   └─ interactive.py calls FilterWizardApp.run()

2. WelcomeScreen displays
   └─ User presses arrow keys to select category
   └─ User presses Enter to confirm
   └─ app.push_screen(LowpassScreen) [or High/Bandpass]

3. Parameter Screen displays
   └─ User presses Tab to move between fields
   └─ User types values (defaults shown in placeholders)
   └─ User presses Enter to submit form
   └─ app.push_screen(OutputOptionsScreen)

4. OutputOptionsScreen displays
   └─ User selects E-series with arrow keys + Enter
   └─ User selects format with arrow keys + Enter
   └─ User presses Space to toggle checkboxes
   └─ User presses Enter to confirm
   └─ app.push_screen(ResultsScreen)

5. ResultsScreen displays
   └─ Shows "Calculating..." message
   └─ Worker thread runs calculate_and_format(state)
   └─ On complete: displays formatted output
   └─ User presses (Y/n) for frequency plot
   └─ User presses Escape to exit
```

#### Key Design Patterns

1. **Screen Stack Navigation**
   - Each step is a Screen subclass
   - Push new screen forward, pop screen to go back
   - Escape key always pops screen (go back)

2. **Centralized State**
   - Single FilterState instance on app
   - All screens access via self.app.filter_state
   - State updated as user navigates forward
   - Final state read by ResultsScreen for calculation

3. **Event-Driven with @on() Decorators**
   - on_button_pressed(event) - Button clicks
   - on_input_changed(event) - Text input changes
   - on_input_submitted(event) - Enter key in input
   - on_select_changed(event) - Radio/select changes

4. **Async Calculations**
   - ResultsScreen uses Worker thread
   - Prevents UI freeze during calculation
   - Worker calls calculate_and_format(state)
   - App remains responsive during processing

5. **Placeholder Values as Defaults**
   - Input fields show default values as placeholders
   - User can see defaults without needing [] brackets
   - On submit, empty field = default value from FilterState

### Layer 5: Shared Utilities

**Location**: `filter_lib/shared/`

**New Base Modules (LP/HP Strategy Pattern)**:
- `lp_hp_base_calculations.py` (342 LOC) - Shared LP/HP calculation logic via strategy
- `lp_hp_base_transfer_functions.py` (164 LOC) - Shared transfer function calculations

These modules implement the Strategy pattern to handle differences between LP and HP filters, reducing duplication in `lowpass/calculations.py` and `highpass/calculations.py`.

#### Parsing & Validation (`parsing.py`)
```python
# Parse and validate user inputs
parse_frequency(freq_str: str) -> float
parse_impedance(impedance_str: str) -> float
validate_frequency(freq_hz: float) -> None
validate_impedance(impedance: float) -> None
validate_order(order: int, filter_type: str) -> None
```

#### Formatting (`formatting.py`)
```python
# Convert raw values to human-readable units
format_capacitance(value_farads: float) -> str    # "196.73 pF"
format_inductance(value_henries: float) -> str    # "1.29 µH"
format_frequency(value_hz: float) -> str          # "10.0 MHz"
```

#### E-Series Matching (`eseries.py` & `display_helpers.py`)
```python
# Component value matching and recommendations
E12_VALUES = [10, 12, 15, 18, 22, 27, 33, 39, 47, 56, 68, 82, ...]
E24_VALUES = [10, 11, 12, 13, 15, 16, 18, 20, ...]
E96_VALUES = [100, 102, 105, 107, 110, ...]

def find_eseries_match(value_farads, series='E24'):
    """Find nearest E-series value."""
    # Algorithm: Find closest value, then find best parallel combo

def format_eseries_match(value, series, format_func):
    """Format recommendation output."""
```

**Matching Algorithm**:
1. Find single closest E-series value
2. Find best parallel combination (two values)
3. Return both with error percentages
4. User chooses which to use

**Note**: As of v1.1+, E-series matching applies to **capacitors only**. Inductor E-series recommendations were removed in anticipation of future component tolerance enhancements.

#### Display Common (`display_common.py`)
```python
# Shared display functions used by all filter types
def print_header(result, topology=..., filter_category=...):
    """Print formatted header with filter specs."""

def print_component_table(result, raw=False, primary_component=None):
    """Print capacitor/inductor values in table format."""

def format_json_result(result, primary_component=None) -> str:
    """Return JSON representation of result."""

def format_csv_result(result, primary_component=None) -> str:
    """Return CSV representation of result."""

def format_quiet_result(result, raw=False, primary_component=None) -> str:
    """Return minimal output."""
```

#### Topology Diagrams (`topology_diagrams.py`)
```python
# ASCII circuit diagram generation
def print_pi_topology_diagram(n_shunt, n_series, shunt_label='C', series_label='L'):
    """Print Pi topology: shunt - series - shunt - ..."""
    # Example for lowpass Pi (C - L pattern)

def print_t_topology_diagram(n_series, n_shunt, series_label='L', shunt_label='C'):
    """Print T topology: series - shunt - series - ..."""
    # Example for lowpass T (L - C pattern)
```

#### Transfer Functions (`transfer_functions.py`)
```python
# Frequency response calculations
def butterworth_response(normalized_freq):
    """H(s) = 1 / (1 + s^n)^0.5"""

def chebyshev_response(normalized_freq, ripple_db):
    """H(s) using Chebyshev polynomial of first kind"""

def bessel_response(normalized_freq):
    """H(s) using Bessel polynomial"""
```

#### Plotting (Modular Structure - Apr 2026)

**Architecture**: Facade pattern with 5 focused modules (replaces monolithic `plotting.py`):

| Module | Purpose |
|--------|---------|
| `plotting.py` | **Facade** — re-exports all plot functions for backward compatibility |
| `plot_ascii_renderers.py` | ASCII plot rendering with configurable `db_floor` parameter for detail zooming |
| `plot_zoom_pairs.py` | Zoomed passband plot pairs: full-range + 0 to -6dB detail view side-by-side |
| `plot_threshold_analysis.py` | dB crossing detection and summary table formatting (-3, -10, -20 dB) |
| `plot_data_export.py` | JSON/CSV data export utilities |
| `transfer_response_dispatch.py` | Shared factory for response-function closures (LP/HP/BP) |

**Key Features** (GH-7):
- **dB Threshold Summary Table**: Shows frequencies where response crosses -3, -10, -20 dB thresholds
  - LP/HP: Single frequency column with direction arrows (↓ for LP, ↑ for HP)
  - BP: Dual-column table (f_low / f_high)
  - Shows "N/A" when threshold not reached within sweep range
- **Zoomed Passband Graph**: Detail view with 2× frequency resolution for smoother curves
  - Adaptive range: max(6, 2×ripple) dB for Chebyshev
  - Skipped if passband is flat (all 0 dB)
- Both features activate automatically with `--plot` flag (no new CLI flags)

**Example Output** (Butterworth 5th order):
```
Frequency Response (dB)         Passband Detail (0 to -6 dB)
  0 │███████████                   0 │████████████████
    │█████████████                   │█████████████████
    │██████████████                  │█████████████████
    │████████████████              -3 │██████████████████
    │██████████████████            -6 │████████████████████
-30 │███████████████████████
    │...                            dB Threshold Summary
-60 │██████████████████████████    ┌────────┬──────────────┐
    +┼──────┼──────┼──────┼──────┼  │ Level  │  Frequency   │
     1M         10M(fc)      100M   ├────────┼──────────────┤
                                    │ -3 dB  │   ↓ 9.99M    │
                                    │ -10 dB │   ↓ 12.4M    │
                                    │ -20 dB │   ↓ 15.8M    │
                                    └────────┴──────────────┘
```

#### Constants (`constants.py`)
```python
# Physical constants and defaults
DEFAULT_IMPEDANCE = 50  # Ohms
DEFAULT_RIPPLE = 0.5    # dB
MIN_ORDER = 2
MAX_ORDER = 9
SUPPORTED_RESPONSE_TYPES = ['butterworth', 'chebyshev', 'bessel']
```

#### Chebyshev Calculator (`chebyshev_g_calculator.py`)
```python
# Normalized g-values for Chebyshev filters
def get_chebyshev_g_values(order, ripple_db):
    """Lookup or calculate normalized g-values.

    Based on tables in Matthaei/Young/Jones,
    which define normalized prototype filters.
    """
```

## Data Flow

### Typical Lowpass Filter Calculation

```
User Input:
  lp butterworth pi 10MHz -n 5 -e E24

           ↓

Input Validation (parsing.py):
  freq_hz = 10,000,000
  topology = 'pi'
  order = 5
  filter_type = 'butterworth'

           ↓

Calculation (lowpass/calculations.py):
  1. Get normalized g-values for butterworth, n=5
  2. Denormalize to 10 MHz with 50Ω impedance
  3. Return result dict with capacitors, inductors

           ↓

E-Series Matching (eseries.py + display_helpers.py):
  For each capacitor value:
    - Find nearest E24 value
    - Find best E24 parallel combination
    - Format with error percentages

           ↓

Display (lowpass/display.py):
  - Print header (filter specs)
  - Print topology diagram
  - Print component table
  - Print E-series recommendations
  - Print toroid recommendations (shared/toroid_selection.py
    → shared/toroid_display.py → stdout; skipped when --no-toroids)
  - (Optional) Render frequency response plot

           ↓

Output to Console:
  Formatted table with circuit diagram
```

### Wizard Flow (Textual TUI)

```
User runs: uv run filter-calc

           ↓

FilterWizardApp starts with WelcomeScreen:
  - User selects filter category with arrow keys + Enter

           ↓

Category-Specific Parameter Screen (lowpass/highpass/bandpass):
  - User enters frequency, impedance, order via Tab navigation
  - User selects topology/filter type/ripple via arrow keys
  - Input fields show placeholder defaults
  - Conditional UI: ripple field only for Chebyshev filters
  - User presses Enter to submit form

           ↓

OutputOptionsScreen:
  - User selects E-series (E12/E24/E96/None)
  - User selects output format (table/json/csv)
  - User selects export format (no/json/csv)
  - User toggles additional options with Space
  - User presses Enter to proceed

           ↓

ResultsScreen (async calculation):
  - Shows "Calculating..." loading state
  - Worker thread runs calculate_and_format()
  - On complete: displays formatted output
  - User prompted for frequency response plot (Y/n)

           ↓

Final Output:
  - Same display modules as CLI (lowpass/highpass/bandpass display.py)
  - Full formatting with E-series recommendations, topology diagram, etc.
  - User presses Escape to exit wizard
```

## Design Patterns & Constraints

### Filter-Type Alias Canonicalization

**Single Source of Truth**: `filter_lib/shared/cli_aliases.py::FILTER_TYPE_ALIASES`

All filter-type dispatch logic must consult this mapping rather than re-implementing alias handling:

```python
FILTER_TYPE_ALIASES = {
    'butterworth': ['bw', 'b'],
    'chebyshev': ['ch', 'c'],
    'bessel': ['bs'],
}
```

**Canonical dispatch**: `shared/transfer_response_dispatch.py::_canonicalize_filter_type(alias)` normalizes any alias to its canonical form before use.

**Impact**: Ensures CLI, wizard, and API all recognize the same aliases with zero divergence.

### Chebyshev Even-Order Constraint

**Requirement**: Chebyshev filters with equal source/load terminations require **odd order only** (3, 5, 7, 9).

**Scope**: LP, HP, and BP designs
- CLI validation: `cli/lowpass_cmd.py`, `cli/highpass_cmd.py`, `cli/bandpass_cmd.py` reject even orders with clear error
- Wizard validation: `wizard/screens/lowpass.py`, `wizard/screens/highpass.py`, `wizard/screens/bandpass.py` pre-filter order selections for Chebyshev
- Core validation: `shared/lp_hp_base_calculations.py::_validate_chebyshev_order(order)` enforces at calculation time

**Error message**: "Chebyshev filters with equal source/load terminations require odd order (3, 5, 7, 9)"

**Ripple limits**: Wizard restricts ripple to 0.1, 0.5, 1.0 dB (practical tolerance range).

### Bandpass True -3 dB Edges

**Source of Truth**: `filter_lib/bandpass/calculations.py::compute_bandpass_3db_edges(f_low, f_high, bw, order, ripple_db, response_type)`

Instead of `f₀ ± BW/2`, true -3 dB edges are computed by solving `(f² - f₀²)/(BW·f) = ±1` using the quadratic formula.

**Key insight**: For wide bandwidth, `f_low = f₀² / f_high` avoids catastrophic cancellation in the `f_low = f₀ - (f₀² / f_high)` form.

**Impact**: High-accuracy edge detection for wide-band designs (BW > 30% of f₀).

### Chebyshev Bandpass 3 dB Semantics

For Chebyshev BP, user `bw` is true -3 dB BW via `chebyshev_3db_deviation()` in `bandpass/transfer.py`.

## Topology Design Patterns

### Filter Topologies

**Lowpass**: Pi (default; shunt C - series L) or T (series L - shunt C)
- Capacitors at odd positions (Pi) → primary component
- Inductors at odd positions (T) → primary component

**Highpass**: Topologies inverted vs. lowpass
- T (default; series C - shunt L) or Pi (shunt L - series C)
- Series capacitors (T) → primary component
- Shunt inductors (Pi) → primary component

**Bandpass**: Top-coupled (series) or shunt-coupled (parallel) resonators
- Top-coupled: series coupling capacitors
- Shunt-coupled: parallel coupling capacitors

## Error Handling

### Validation Points

| Layer | Check | Example |
|-------|-------|---------|
| Input parsing | Format validation | Frequency must be positive |
| Input validation | Range checks | Order 2-9 |
| Calculation | Sanity checks | Computed values positive |
| Display | Output formatting | Unicode width, JSON encoding |

### Error Types

```python
# ValueError: Invalid input
raise ValueError(f"Frequency must be positive, got {freq}")

# RuntimeError: Unexpected condition
raise RuntimeError(f"Failed to calculate g-values for order {n}")

# Click.BadParameter: CLI argument error (automatic)
# Handled by Click framework, shown to user
```

## Performance Characteristics

| Operation | Complexity | Time |
|-----------|-----------|------|
| Parse input | O(1) | <1ms |
| Calculate components | O(1) | <1ms |
| Frequency response (50 points) | O(n) | ~10ms |
| E-series matching | O(n*m) | ~50ms (n=cap values, m=eseries) |
| Display formatting | O(n) | <1ms |
| ASCII plot render | O(n*w) | ~20ms (n=points, w=width) |

**Total typical time**: <150ms for full calculation + display

## Extensibility Points

### Adding New Filter Type
1. Create `filter_lib/{filter_type}/` directory
2. Implement `calculations.py`, `transfer.py`, `display.py`
3. Create `filter_lib/cli/{filter_type}_cmd.py` subcommand
4. Add wizard support if interactive mode needed
5. Add tests in `tests/test_{filter_type}_*.py`

### Adding New Output Format
1. Add formatter to `{filter_type}/display.py`
2. Extend `display_results()` with new format case
3. Add tests for new format

### Adding New Response Type
1. Add g-values table to `shared/chebyshev_g_calculator.py`
2. Add transfer function to `shared/transfer_functions.py`
3. Add alias to `shared/cli_aliases.py`
4. Test with existing calculation modules

---

## Quality Assurance & CI/CD

### Automated Tooling

**Linting**: Ruff (py310 target, E/F/I/UP/B rules)
- Line length: 100 chars
- Enforced on all pushes via GitHub Actions
- 67 files reformatted (Feb 2026, commit cc4e9c1)

**Testing**: 1046 tests, 94% coverage
- Unit tests for all calculation modules
- Integration tests for CLI and wizard
- Coverage enforced via pytest-cov in CI

**CI/CD Pipeline** (.github/workflows/ci.yml):
1. **Lint** (ruff check .) - Fail fast on violations
2. **Format** (ruff format --check) - Code style compliance
3. **Test** (pytest --cov=filter_lib) - All tests with coverage

**Test Metrics** (as of Apr 24, 2026):
- Total: 1086 tests (94% coverage, ~0.5s runtime)

See [code-standards.md](./code-standards.md) for linting rules and [testing.md](./testing.md) for test coverage details.
