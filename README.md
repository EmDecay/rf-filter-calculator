# RF Filter Calculator

A command-line tool for calculating LC filter component values. Designed for RF engineers and amateur radio operators.

## Features

- **Filter Types**: Lowpass (Pi topology), Highpass (T topology), Bandpass (coupled resonator)
- **Response Types**: Butterworth, Chebyshev, Bessel
- **E-Series Matching**: Find closest E12/E24/E96 standard values with parallel combinations
- **ASCII Plots**: Visualize frequency response in terminal
- **Multiple Outputs**: Table, JSON, CSV formats
- **Interactive Wizard**: Guided filter design mode

## Installation

Requires Python 3.10+.

```bash
git clone https://github.com/yourusername/rf-filter-calculator.git
cd rf-filter-calculator
chmod +x filter-calc.py
```

## Quick Start

```bash
# 5th-order Butterworth lowpass at 10 MHz
./filter-calc.py lowpass butterworth 10MHz -n 5

# Chebyshev highpass at 14 MHz with 0.5 dB ripple
./filter-calc.py highpass chebyshev 14MHz -r 0.5

# Bandpass for 20m amateur band (14.0-14.35 MHz)
./filter-calc.py bandpass butterworth top -f 14.175MHz -b 350kHz

# Interactive wizard
./filter-calc.py wizard
```

## Usage

### Lowpass Filter (Pi Topology)

```bash
./filter-calc.py lowpass <type> <frequency> [options]
./filter-calc.py lp <type> <frequency> [options]
```

**Example:**
```bash
./filter-calc.py lp bw 7.1MHz -n 5 --plot
```

```
╔══════════════════════════════════════════════════════════════════════════════╗
║                        LOW-PASS FILTER DESIGN                                ║
╠══════════════════════════════════════════════════════════════════════════════╣
║  Type: Butterworth (5th order)        Cutoff: 7.1 MHz       Z₀: 50Ω         ║
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

### Highpass Filter (T Topology)

```bash
./filter-calc.py highpass <type> <frequency> [options]
./filter-calc.py hp <type> <frequency> [options]
```

### Bandpass Filter (Coupled Resonator)

```bash
./filter-calc.py bandpass <type> <coupling> [options]
./filter-calc.py bp <type> <coupling> [options]
```

**Frequency specification:**
```bash
# Method 1: Center frequency + bandwidth
./filter-calc.py bp bw top -f 14.175MHz -b 350kHz

# Method 2: Lower and upper cutoff
./filter-calc.py bp bw top --fl 14MHz --fh 14.35MHz
```

**Coupling topologies:**
- `top` / `t` - Top-coupled (series coupling capacitors)
- `shunt` / `s` - Shunt-coupled (parallel coupling capacitors)

### Interactive Wizard

```bash
./filter-calc.py wizard
./filter-calc.py w
```

Step-by-step guided design for all filter types.

## Options

| Option | Description |
|--------|-------------|
| `-n, --components` | Number of components/resonators (2-9) |
| `-z, --impedance` | System impedance (default: 50Ω) |
| `-r, --ripple` | Chebyshev passband ripple in dB (default: 0.5) |
| `-e, --eseries` | E-series for matching: E12, E24, E96 (default: E24) |
| `--no-match` | Disable E-series matching |
| `--raw` | Show raw values (Farads/Henries) |
| `-q, --quiet` | Minimal output |
| `--format` | Output format: table, json, csv |
| `--plot` | Show ASCII frequency response |
| `--plot-data` | Export response data: json, csv |
| `--explain` | Explain filter type characteristics |

## Filter Type Aliases

| Alias | Filter Type |
|-------|-------------|
| `bw`, `b` | Butterworth |
| `ch`, `c` | Chebyshev |
| `bs` | Bessel |

## Frequency Input Formats

All of these are equivalent:
```
10MHz  10M  10000000  10e6  10000k  10000kHz
```

## Output Formats

**JSON:**
```bash
./filter-calc.py lp bw 10MHz --format json
```

**CSV:**
```bash
./filter-calc.py lp bw 10MHz --format csv > components.csv
```

**Frequency Response Data:**
```bash
./filter-calc.py lp bw 10MHz --plot-data json > response.json
./filter-calc.py lp bw 10MHz --plot-data csv > response.csv
```

## Project Structure

```
rf-filter-calculator/
├── filter-calc.py          # Main CLI entry point
└── filter_lib/
    ├── cli/                # Subcommand handlers
    ├── lowpass/            # Pi topology calculations
    ├── highpass/           # T topology calculations
    ├── bandpass/           # Coupled resonator calculations
    ├── wizard/             # Interactive design mode
    └── shared/             # Common utilities (parsing, E-series, plotting)
```

## License

GPL-3.0. See [LICENSE](LICENSE) for details.

## Author

Matt N3AR
