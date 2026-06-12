# RF Filter Calculator

A command-line tool for calculating LC filter component values. Designed for RF engineers and amateur radio operators.

## Features

- **Filter Types**: Lowpass (Pi/T topology), Highpass (Pi/T topology), Bandpass (top-C series coupling, netlist-simulated)
- **Response Types**: Butterworth, Chebyshev (arbitrary 0–3 dB ripple), Bessel
- **E-Series Matching**: Capacitors matched to E12/E24/E96 standard values with parallel combinations; inductors show design values with toroid recommendations
- **End-Coupling Realization**: Bandpass external Q realized by series end-coupling capacitors (Ce_in/Ce_out); transformation formula built-in
- **Netlist-Simulated Plots**: Bandpass frequency response generated from the synthesized circuit netlist with the built-in nodal-analysis solver (simulation-proven ≤10% FBW)
- **Toroid Recommendations**: Amidon T-series core suggestions on by default (top-1 in table, top-3 in JSON, best match in CSV); 43-core database; `--no-toroids` to suppress, `--toroid-compact` for one-line recommendations, `--toroid-full` for top-3 in table
- **ASCII Plots**: Visualize frequency response (LP/HP analytic, BP simulated)
- **Multiple Outputs**: Table, JSON, CSV formats
- **Interactive Wizard**: Guided TUI design mode with error surface
- **--version Support**: Print version and exit

## Installation

Requires Python 3.10+ and [uv](https://docs.astral.sh/uv/).

Install uv if you don't have it:
```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
# or: brew install uv
```

Then set up the project:
```bash
git clone https://github.com/EmDecay/rf-filter-calculator.git
cd rf-filter-calculator
uv sync
```

For development (includes pytest and ruff):
```bash
uv sync --group dev
```

### Breaking Changes (v2.0.0)

**Migration from v1.x:** `-t` short flag removed (use `--type` instead); `--verify` removed from bandpass; `-r` now warns if used with non-Chebyshev filters; ripple validation changed from hardcoded tiers to 0 < r ≤ 3.0; wizard resonator default changed to 3. See [docs/project-changelog.md](docs/project-changelog.md) for full details and migration path.

## Quick Start

```bash
# Start interactive wizard (default when no arguments given)
uv run filter-calc

# 5th-order Butterworth lowpass Pi at 10 MHz
uv run filter-calc lowpass butterworth pi 10MHz -n 5

# Lowpass T topology
uv run filter-calc lowpass butterworth t 10MHz -n 5

# Chebyshev highpass T at 14 MHz with 0.5 dB ripple
uv run filter-calc highpass chebyshev t 14MHz -r 0.5

# Highpass Pi topology via the -T flag
uv run filter-calc highpass chebyshev -T pi -f 14MHz -r 0.5

# Bandpass for 20m amateur band (14.0-14.35 MHz)
uv run filter-calc bandpass butterworth top -f 14.175MHz -b 350kHz
```

### Running without `uv run`

The `uv sync` command creates a virtual environment in `.venv/` at the project root. If you activate that virtual environment in your shell, you can run `./filter-calc.py` directly instead of prefixing every command with `uv run`:

```bash
# Activate the virtual environment
source .venv/bin/activate    # macOS/Linux (bash/zsh)
source .venv/bin/activate.fish  # Fish shell
.venv\Scripts\activate       # Windows

# Now you can run the script directly
./filter-calc.py lowpass butterworth pi 10MHz -n 5

# When you're done, deactivate the virtual environment
deactivate
```

## Usage

### Lowpass Filter

```bash
uv run filter-calc lowpass <type> <topology> <frequency> [options]
uv run filter-calc lp <type> -T pi|t -f <frequency> [options]
```

**Example:**
```bash
uv run filter-calc lp bw pi 7.1MHz -n 5 --plot
```

```
╔══════════════════════════════════════════════════════════════════════════════╗
║                        LOW-PASS FILTER DESIGN                                ║
╠══════════════════════════════════════════════════════════════════════════════╣
║  Type: Butterworth (5th order)        Cutoff: 7.1 MHz       Z₀: 50Ω          ║
╚══════════════════════════════════════════════════════════════════════════════╝

  Topology: Pi (shunt C - series L - shunt C - series L - shunt C)

         ┌────[L1]────┬────[L2]────┐
    IN ──┤            │            ├── OUT
        C1           C2           C3
         │            │            │
        GND          GND          GND

┌──────────────────────────────────────────────────────────────────────────────┐
│  Capacitors                      │  Inductors                                │
├──────────────────────────────────┼───────────────────────────────────────────┤
│  C1: 138.8 pF  (150pF -7.5%)     │  L1: 1.457 µH  (1.5µH -2.9%)              │
│  C2: 449.0 pF  (470pF -4.5%)     │  L2: 1.457 µH  (1.5µH -2.9%)              │
│  C3: 138.8 pF  (150pF -7.5%)     │                                           │
└──────────────────────────────────┴───────────────────────────────────────────┘
```

### Highpass Filter

```bash
uv run filter-calc highpass <type> <topology> <frequency> [options]
uv run filter-calc hp <type> -T pi|t -f <frequency> [options]
```

### Bandpass Filter (Coupled Resonator)

```bash
uv run filter-calc bandpass <type> <coupling> [options]
uv run filter-calc bp <type> <coupling> [options]
```

**Frequency specification:**
```bash
# Method 1: Center frequency + bandwidth
uv run filter-calc bp bw top -f 14.175MHz -b 350kHz

# Method 2: Lower and upper cutoff
uv run filter-calc bp bw top --fl 14MHz --fh 14.35MHz
```

When using `--fl` and `--fh`, the calculator synthesizes around the geometric center
`f₀ = √(f_low × f_high)`. Output tables and bandpass plot labels preserve the exact
`f_low` and `f_high` values you entered.

**Coupling topologies:**
- `top` / `t` — Top-coupled series capacitors (Ce_in/Ce_out for external Q, Cs12/Cs23 for inter-resonator coupling; the only supported kind)

### Interactive Wizard

```bash
uv run filter-calc          # default when no arguments given
uv run filter-calc wizard   # explicit subcommand (alias: w)
```

Running with no arguments starts a Textual TUI wizard with screen-based navigation:

1. **Welcome Screen** - Select filter type (lowpass, highpass, bandpass)
2. **Filter Configuration** - Set response type, topology, frequency, impedance, order
3. **Output Options** - Choose E-series matching, output format, export settings
4. **Results** - View calculated component values and frequency response

**Keyboard shortcuts:**
- `Tab` / `Shift+Tab` - Navigate between fields
- `Enter` - Submit / select
- `Escape` - Go back to previous screen
- `Ctrl+C` - Quit

Default values shown as placeholders; press Enter with empty field to use default.

## Options

| Option | Description |
|--------|-------------|
| `-T, --topology` | Filter topology: pi or t (required for lowpass/highpass) |
| `--type` | Filter response: butterworth, chebyshev, bessel (or bw/ch/bs aliases) |
| `-n, --components` | Number of components/resonators (2–9, default: 3) |
| `-f, --frequency` | Center/cutoff frequency (or `-fl`/`--fh` for bandpass limits) |
| `-z, --impedance` | System impedance (default: 50Ω; accepts 50, 50ohm, 1k, 1M, etc.) |
| `-r, --ripple` | Chebyshev passband ripple in dB, 0 < r ≤ 3.0 (default: 0.5; warns if used with non-Chebyshev) |
| `-b, --bandwidth` | Bandpass bandwidth (or use -fl/-fh for explicit edges) |
| `-e, --eseries` | E-series for matching: E12, E24, E96 (default: E24) |
| `--no-match` | Disable E-series matching |
| `--raw` | Show raw values (Farads/Henries) |
| `-q, --quiet` | Minimal output |
| `--format` | Output format: table, json, csv (default: table) |
| `--plot` | Show ASCII frequency response |
| `--plot-data` | Export response data: json, csv |
| `--explain` | Explain filter type characteristics |
| `--no-toroids` | Suppress toroid recommendations in all output formats |
| `--toroid-compact` | One-line-per-recommendation toroid text output (ignored for JSON/CSV) |
| `--toroid-full` | Show top-3 toroid cores per inductor in table output (default top-1; JSON always top-3, CSV best match) |
| `--version` | Print version and exit |

## Filter Type Aliases

| Alias | Filter Type |
|-------|-------------|
| `bw`, `b` | Butterworth |
| `ch`, `c` | Chebyshev |
| `bs` | Bessel |

## Frequency Input Formats

All of these are equivalent (case-insensitive):
```
10MHz  10M  10mhz  10m  10000000  10e6  10000k  10000kHz
```

Supported suffixes: `GHz`, `MHz`, `kHz`, `Hz`, `G`, `M`, `k`

**Note:** Frequency and impedance must be positive values. Zero or negative values raise a validation error.

## Output Formats

**JSON:**
```bash
uv run filter-calc lp bw pi 10MHz --format json
```

**CSV:**
```bash
uv run filter-calc lp bw pi 10MHz --format csv > components.csv
```

**Frequency Response Data:**
```bash
uv run filter-calc lp bw pi 10MHz --plot-data json > response.json
uv run filter-calc lp bw pi 10MHz --plot-data csv > response.csv
```

## Testing & CI

Run the test suite with pytest:

```bash
# Run all tests
uv run pytest tests/ -v

# Run with coverage
uv run pytest tests/ --cov=filter_lib --cov-report=term-missing
```

**Test suite:** 1227 tests (94% coverage) covering filter calculations, transfer functions, topology diagrams, E-series matching, input validation, CLI commands, output formatting, the interactive wizard, toroid recommendations, and netlist-simulated bandpass validation. See [docs/testing.md](docs/testing.md) for details.

### Linting

[Ruff](https://docs.astral.sh/ruff/) is used for linting and formatting:

```bash
uv run ruff check .          # Lint
uv run ruff format --check .  # Check formatting
```

### Continuous Integration

GitHub Actions runs lint, format check, and the full test suite on every push and PR to `main`.

## Project Structure

```
rf-filter-calculator/
├── filter-calc.py          # Main CLI entry point
├── tests/                  # Test suite (pytest)
└── filter_lib/
    ├── cli/                # Subcommand handlers
    ├── lowpass/            # Lowpass calculations (Pi/T)
    ├── highpass/           # Highpass calculations (Pi/T)
    ├── bandpass/           # Coupled resonator calculations
    ├── wizard/             # Interactive design mode
    └── shared/             # Common utilities (parsing, E-series, plotting)
```

## Documentation

See [docs/](docs/) for comprehensive documentation:
- [User Guide](docs/user-guide.md) - Complete usage reference
- [Filter Theory](docs/filter-theory.md) - Background on filter types
- [Testing Guide](docs/testing.md) - Test suite documentation

## License

GPL-3.0. See [LICENSE](LICENSE) for details.

## Author

Matt N3AR (with AI assistance)
