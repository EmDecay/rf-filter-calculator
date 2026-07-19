# RF Filter Calculator

A command-line tool for calculating LC filter component values. Designed for RF engineers and amateur radio operators.

## Features

- **Filter Types**: Lowpass (Pi/T topology), Highpass (Pi/T topology), Bandpass (top-C series coupling, netlist-simulated)
- **Response Types**: Butterworth, Chebyshev (arbitrary ripple in (0, 3] dB), Bessel. Chebyshev LP/HP cutoff is the ripple-band edge (ARRL/Elsie/Zverev convention), not the −3 dB point; bandpass `bw` is the true −3 dB bandwidth
- **Buildable Capacitor Selection**: E12/E24/E96 is treated as preferred-value density, not tolerance. The default policy keeps a single part within 1%, uses a two-part parallel value only when it improves absolute error by at least 0.5 percentage points, and requires expert action below 1 pF
- **End-Coupling Realization**: Bandpass external Q realized by series end-coupling capacitors (Ce_in/Ce_out); transformation formula built-in
- **Calibrated, Verified Bandpass Synthesis**: Each Top-C design is calibrated to both requested −3 dB skirts and independently checked for connected passband, outer skirts, passband shape, ripple, and representative stopband behavior. JSON reports whether the individual design is inside the validated envelope
- **Realized-Build Analysis**: `--sim-build` selects nominal physical parts, optionally adds finite-Q loss, evaluates deterministic tolerance cases plus repeatable samples, and keeps synthesis targets separate from simulated results
- **Generic SPICE Export**: Exact or nominal-build passive decks use the same named circuit and physical-part realization as the internal analysis
- **Screened Toroid Candidates**: Automatic selection is limited to exact parts with primary-source core data (currently T25-6, T50-2, and T68-2), published material guidance, acceptable integer-turn error, and winding-capacity checks. RF Q, SRF, core loss, saturation, temperature rise, and power suitability are explicitly not assessed
- **ASCII Plots**: Visualize frequency response (LP/HP analytic, BP simulated)
- **Multiple Outputs**: Table, JSON, CSV, generic SPICE, and standalone response-data exports
- **Interactive Wizard**: Guided TUI design mode with error surface
- **Root --version Support**: `filter-calc --version` prints the installed version and exits

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

### Accuracy and Build Remediation (v2.1.0)

Version 2.1.0 makes calculated, nominal-build, tolerance-screening, and SPICE results explicit. It also replaces blanket bandpass support claims with per-design validation metadata, hardens finite-number handling, adds independent tank L/impedance controls and complete-resonator Q semantics, restricts automatic toroid selection to primary-sourced parts, and makes E-series selection deterministic. `--sim-matched` remains as a deprecated compatibility alias; use `--sim-build` for new workflows.

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

See [sample output](docs/sample-output.md) for current table, JSON, build-analysis, and SPICE examples.

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
`f₀ = √(f_low × f_high)`. The reported edges are reconstructed from that center and
bandwidth and agree with the requested values to floating-point precision.

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
3. **Output Options** - Choose E-series matching, output/export settings, and optional realized-build controls
4. **Results** - View the current calculation; stale or canceled workers cannot overwrite a newer result, and Save exports the component format independently of an optional response-data sidecar

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
| `-n, --components` | LP/HP reactive component count (2–9, default: 3) |
| `-n, --resonators` | Bandpass resonator count (2–9, default: 3; Chebyshev requires odd) |
| `-f, --freq` | LP/HP cutoff frequency |
| `-f, --frequency` | Bandpass center frequency (or use `--fl`/`--fh`) |
| `-z, --impedance` | System impedance (default: 50Ω; accepts 50, 50ohm, 1k, 1M, etc.) |
| `-r, --ripple` | Chebyshev passband ripple in dB, 0 < r ≤ 3.0 (default: 0.5; warns if used with non-Chebyshev) |
| `-b, --bandwidth` | Bandpass bandwidth (or use `--fl`/`--fh` for explicit edges) |
| `-e, --eseries` | E-series for matching: E12, E24, E96 (default: E24) |
| `--no-match` | Disable E-series matching |
| `--raw` | Show raw values (Farads/Henries) |
| `-q, --quiet` | Minimal output |
| `--format` | Output format: table, json, csv, spice (default: table) |
| `--plot` | Show ASCII frequency response |
| `--plot-data` | Export response data: json, csv |
| `--explain` | Explain filter type characteristics |
| `--no-toroids` | Suppress toroid recommendations in all output formats |
| `--toroid-compact` | One-line-per-candidate toroid output; valid only with table output |
| `--toroid-full` | Show up to three qualified toroid candidates per inductor in table output (default top-1; JSON includes up to three, CSV the best available) |
| `--sim-matched` | Deprecated nominal-build comparison alias; use `--sim-build` |
| `--sim-build` | Compare calculated and selected nominal circuits; add bounded tolerance screening and optional finite-Q loss |
| `--capacitor-tolerance`, `--inductor-tolerance` | Independent bounds used by `--sim-build`; these are not inferred from the selected E-series |
| `--inductor-q`, `--capacitor-q` | Component Q at the loss-reference frequency for build analysis or nominal SPICE |
| `--loss-reference-frequency` | Reference used to convert supplied Q to constant series resistance; requires an effective Q |
| `--source-resistance`, `--load-resistance` | Evaluation ports for transducer gain; synthesis remains equal-termination |
| `--sample-count`, `--seed`, `--analysis-points` | Repeatable bounded screening and frequency-grid controls |
| `--no-toroid-build` | Keep exact inductance as an explicit nominal fallback instead of selecting a screened winding |
| `--spice-realization` | Select `exact` or `nominal-build` for `--format spice` (default: `nominal-build`) |
| `--qu` | Complete resonator unloaded Q for bandpass loss estimates/build realization |
| `--ql`, `--qc` | Bandpass inductor/capacitor Q; combined as `1/Qu = 1/QL + 1/QC` |
| `--resonator-impedance`, `--resonator-inductance` | Choose tank reactance or L independently of the termination impedance |
| `--version` | Root option: `filter-calc --version` |

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

**Realized-build analysis:**
```bash
uv run filter-calc lp bw pi 10MHz --sim-build --inductor-q 100 \
  --capacitor-q 500 --sample-count 100 --seed 73 --format json > build.json
```

The generated cases are a deterministic engineering screen, not a guaranteed worst case, Monte Carlo yield estimate, or measurement.

**SPICE deck:**
```bash
uv run filter-calc bp bw top -f 14.175MHz -b 350kHz \
  --format spice --spice-realization nominal-build --qu 200 > filter.cir
```

The deck prints load-node voltage. Its comment gives the transducer-gain expression; the printed voltage is not itself gain in dB.

## Testing & CI

Run the test suite with pytest:

```bash
# Run all tests
uv run pytest tests/ -v

# Run with coverage
uv run pytest tests/ --cov=filter_lib --cov-report=term-missing
```

**Test suite:** More than 2,000 collected cases, with a CI coverage floor of 90%, including an exhaustive 128-cell bandpass study, independent response verification, build/tolerance/loss contracts, strict JSON, generic SPICE, Python 3.10–3.13, wheel/sdist inspection, installed-wheel smoke tests, and real Textual pilot tests. See [docs/testing.md](docs/testing.md) for current details.

### Linting

[Ruff](https://docs.astral.sh/ruff/) is used for linting and formatting:

```bash
uv run ruff check .          # Lint
uv run ruff format --check .  # Check formatting
```

### Continuous Integration

GitHub Actions runs Ruff, the full coverage-gated suite on Python 3.10–3.13, and wheel/sdist build plus installed-wheel smoke checks on every push and PR to `main`.

## Project Structure

```
rf-filter-calculator/
├── filter-calc.py          # Main CLI entry point
├── tests/                  # Test suite (pytest)
└── filter_lib/
    ├── cli/                # Subcommand handlers
    ├── lowpass/            # Lowpass calculations (Pi/T)
    ├── highpass/           # Highpass calculations (Pi/T)
    ├── bandpass/           # Calibrated Top-C synthesis and independent verification
    ├── wizard/             # Interactive design mode
    └── shared/             # Parsing, realization, loss/tolerance analysis, SPICE, plotting
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
