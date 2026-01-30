# System Architecture

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
Interactive mode coordinator:
- Prompt for filter type selection
- Delegate to appropriate wizard module
- Present output options interactively

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

### Layer 4: Wizard Module

**Location**: `filter_lib/wizard/`

Interactive design flow:

```
filter_wizard.py
  ├─ Prompt: Select filter category (lowpass/highpass/bandpass)
  │
  ├─ Delegate to:
  │   - bandpass_wizard.py (if bandpass)
  │   - filter_wizard.py prompts (if lp/hp)
  │
  ├─ Prompt: Response type (butterworth/chebyshev/bessel)
  ├─ Prompt: Topology (pi/t) [lp/hp only]
  ├─ Prompt: Frequency parameters
  ├─ Prompt: Order/resonators
  ├─ Prompt: Impedance
  ├─ Prompt: Ripple (if chebyshev)
  │
  ├─ Calculate using appropriate calculation module
  │
  └─ Output Options Screen:
      ├─ E-series selection (E12/E24/E96/None)
      ├─ Output format (table/json/csv)
      ├─ Export frequency data (no/json/csv)
      ├─ Additional options (raw/quiet)
      └─ Show plot? (Y/n)
```

**Key Files**:
- `filter_wizard.py` - Main wizard orchestrator
- `bandpass_wizard.py` - Bandpass-specific prompts
- `interactive.py` - Interactive choice UI (arrow keys, space selection)
- `prompts.py` - Reusable input prompts and validators

### Layer 5: Shared Utilities

**Location**: `filter_lib/shared/`

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

#### Plotting (`plotting.py`)
```python
# ASCII frequency response plots
def render_ascii_plot(frequencies, magnitude_db, cutoff_hz, filter_type='lowpass'):
    """Generate ASCII plot with dB scale and frequency axis."""
    # Algorithm:
    # 1. Scale frequency to log axis
    # 2. Scale magnitude to dB range
    # 3. Render bar chart with Unicode blocks
    # 4. Add axis labels and reference lines
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
  - (Optional) Render frequency response plot

           ↓

Output to Console:
  Formatted table with circuit diagram
```

### Wizard Flow

```
User runs: uv run filter-calc

           ↓

Wizard invoked (wizard/filter_wizard.py):
  - Interactive prompts for all parameters
  - Shows defaults in brackets

           ↓

Calculate based on filter type

           ↓

Output Options Screen (interactive.py):
  - Choose E-series (arrow keys + Enter)
  - Choose output format
  - Choose plot options
  - Toggle additional options (space + Enter)

           ↓

Final Output:
  Uses same display path as CLI
```

## Topology Design Patterns

### Lowpass Filters

**Pi Topology** (default):
- Pattern: Shunt C - Series L - Shunt C - Series L - Shunt C
- Capacitors at odd positions (primary component)
- Used for: Input impedance matching, low source impedance

**T Topology**:
- Pattern: Series L - Shunt C - Series L - Shunt C - Series L
- Inductors at odd positions (primary component)
- Used for: Output impedance matching, high source impedance

### Highpass Filters

**Note**: Topologies are inverted compared to lowpass!

**T Topology** (default):
- Pattern: Series C - Shunt L - Series C - Shunt L - Series C
- Capacitors at odd positions (primary component)
- Opposite of lowpass T!

**Pi Topology**:
- Pattern: Shunt L - Series C - Shunt L - Series C - Shunt L
- Inductors at odd positions (primary component)
- Opposite of lowpass Pi!

### Bandpass Filters

**Top-Coupled** (series coupling):
- LC tank resonators coupled via series capacitors
- Coupling capacitors in series path
- Better for low impedance systems

**Shunt-Coupled** (parallel coupling):
- LC tank resonators coupled via parallel capacitors
- Coupling capacitors to ground
- Better for high impedance systems

## Request-Response Cycle

### CLI Command

```
Request: uv run filter-calc lp bw pi 10MHz -n 5 --format json
         │
         ├─ Parse args (Click)
         ├─ Route to lowpass_cmd
         ├─ Validate inputs
         ├─ Call calculate_lowpass
         ├─ Call display_results(format='json')
         │
Response: {"filter_type": "butterworth", "capacitors": [...], ...}
```

### Wizard Mode

```
Request: uv run filter-calc
         │
         ├─ No args → invoke wizard
         ├─ Interactive prompts (loop until valid)
         ├─ Calculate based on responses
         ├─ Show output options screen
         ├─ Format and display based on selections
         │
Response: Pretty table with topology diagram
          + E-series recommendations
          + (Optional) frequency response plot
```

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
