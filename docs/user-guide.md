# User Guide

Complete reference for all commands, options, and features.

## Commands Overview

| Command | Aliases | Description |
|---------|---------|-------------|
| `lowpass` | `lp` | Pi topology low-pass filter |
| `highpass` | `hp` | T topology high-pass filter |
| `bandpass` | `bp` | Coupled resonator bandpass filter |
| *(no args)* | - | Interactive wizard (default) |

---

## Lowpass Command

Designs Pi-topology low-pass filters with shunt capacitors and series inductors.

### Syntax

```bash
./filter-calc.py lowpass <filter_type> <frequency> [options]
./filter-calc.py lp <filter_type> <frequency> [options]
```

### Positional Arguments

| Argument | Description |
|----------|-------------|
| `filter_type` | `butterworth`, `chebyshev`, `bessel` (or aliases) |
| `frequency` | Cutoff frequency (e.g., `10MHz`, `7.1M`) |

### Options

| Option | Default | Description |
|--------|---------|-------------|
| `-n, --components` | 3 | Number of reactive components (2-9) |
| `-z, --impedance` | 50 | System impedance in ohms |
| `-r, --ripple` | 0.5 | Chebyshev passband ripple in dB |
| `-e, --eseries` | E24 | E-series for component matching (E12, E24, E96) |
| `--no-match` | - | Disable E-series matching display |
| `--raw` | - | Show raw values (Farads/Henries) |
| `-q, --quiet` | - | Minimal output |
| `--format` | table | Output format: `table`, `json`, `csv` |
| `--plot` | - | Show ASCII frequency response |
| `--plot-data` | - | Export response data: `json` or `csv` |
| `--explain` | - | Display filter type characteristics |

### Examples

```bash
# Basic 5th-order Butterworth at 7.1 MHz for 40m band
./filter-calc.py lp bw 7.1MHz -n 5

# Chebyshev with 1 dB ripple at 28 MHz
./filter-calc.py lp ch 28MHz -r 1.0 -n 7

# Output with frequency response plot
./filter-calc.py lp bw 10MHz --plot

# JSON output for scripting
./filter-calc.py lp bw 10MHz --format json

# High-precision E96 component matching
./filter-calc.py lp bw 10MHz -e E96

# Export frequency response data
./filter-calc.py lp bw 10MHz --plot-data csv > response.csv
```

---

## Highpass Command

Designs T-topology high-pass filters with series inductors and shunt capacitors.

### Syntax

```bash
./filter-calc.py highpass <filter_type> <frequency> [options]
./filter-calc.py hp <filter_type> <frequency> [options]
```

### Arguments and Options

Same as lowpass command. The topology is automatically inverted (T instead of Pi).

### Examples

```bash
# Block below 14 MHz (20m band high-pass)
./filter-calc.py hp bw 14MHz -n 5

# Steep Chebyshev rolloff
./filter-calc.py hp ch 3.5MHz -r 0.5 -n 7
```

---

## Bandpass Command

Designs coupled-resonator bandpass filters using LC tank circuits.

### Syntax

```bash
./filter-calc.py bandpass <filter_type> <coupling> [options]
./filter-calc.py bp <filter_type> <coupling> [options]
```

### Positional Arguments

| Argument | Description |
|----------|-------------|
| `filter_type` | `butterworth`, `chebyshev`, `bessel` (or aliases) |
| `coupling` | Coupling topology: `top` (series) or `shunt` (parallel) |

### Frequency Specification

Two methods available (use one, not both):

**Method 1: Center + Bandwidth**
```bash
-f <center_freq> -b <bandwidth>
```

**Method 2: Low/High Cutoffs**
```bash
--fl <low_cutoff> --fh <high_cutoff>
```

### Options

| Option | Default | Description |
|--------|---------|-------------|
| `-f, --frequency` | - | Center frequency |
| `-b, --bandwidth` | - | 3 dB bandwidth |
| `--fl` | - | Lower cutoff frequency |
| `--fh` | - | Upper cutoff frequency |
| `-n, --resonators` | 2 | Number of resonators (2-9) |
| `-z, --impedance` | 50 | System impedance |
| `-r, --ripple` | 0.5 | Chebyshev ripple in dB |
| `--q-safety` | 2.0 | Q safety factor for component selection |
| `-e, --eseries` | E24 | E-series for matching |
| `--no-match` | - | Disable E-series matching |
| `--raw` | - | Raw scientific notation |
| `-q, --quiet` | - | Minimal output |
| `--format` | table | Output format: `table`, `json`, `csv` |
| `--plot` | - | Show ASCII frequency response |
| `--plot-data` | - | Export response data |
| `--explain` | - | Explain filter characteristics |
| `--verify` | - | Run self-verification tests |

### Coupling Topologies

| Type | Aliases | Description |
|------|---------|-------------|
| `top` | `t` | Top-coupled (series coupling capacitors between resonators) |
| `shunt` | `s` | Shunt-coupled (parallel coupling capacitors to ground) |

### Examples

```bash
# 20m amateur band filter (14.0-14.35 MHz)
./filter-calc.py bp bw top -f 14.175MHz -b 350kHz

# Same filter using low/high specification
./filter-calc.py bp bw top --fl 14MHz --fh 14.35MHz

# 5-resonator Chebyshev (odd count required)
./filter-calc.py bp ch top -f 7.15MHz -b 200kHz -n 5 -r 0.5

# Shunt-coupled topology
./filter-calc.py bp bw shunt -f 21.2MHz -b 450kHz
```

---

## Interactive Wizard

Running with no arguments starts the interactive wizard for guided filter design.

### Syntax

```bash
./filter-calc.py
```

### Design Parameters

The wizard prompts for:
1. Filter category (lowpass, highpass, bandpass)
2. Response type (Butterworth, Chebyshev, Bessel)
3. Frequency parameters
4. Number of components/resonators
5. Impedance
6. Chebyshev ripple (if applicable)

### Output Options

After calculation, an output options screen lets you customize the display:

```
Select options (enter numbers separated by spaces, or press Enter for defaults):

  [1] E12 series       - Use E12 component values (fewer choices, looser tolerance)
  [2] E96 series       - Use E96 component values (more choices, tighter tolerance)
  [3] No matching      - Show calculated values only (no E-series matching)
  [4] Raw units        - Display in Farads/Henries instead of pF/nH/µH
  [5] Quiet mode       - Minimal output (component values only)
  [6] JSON output      - Output in JSON format
  [7] CSV output       - Output in CSV format
  [8] Export plot JSON - Export frequency response data as JSON
  [9] Export plot CSV  - Export frequency response data as CSV

Select options (e.g., '1 4' or Enter for defaults):
```

Enter space-separated numbers to combine options (e.g., `2 4` for E96 + raw units).
Conflicting options (E12+E96, JSON+CSV) are validated and rejected.

---

## Input Formats

### Frequency

| Format | Example | Value |
|--------|---------|-------|
| With unit | `10MHz` | 10,000,000 Hz |
| SI prefix | `10M` | 10,000,000 Hz |
| Scientific | `10e6` | 10,000,000 Hz |
| Plain Hz | `10000000` | 10,000,000 Hz |
| kHz | `10000kHz` | 10,000,000 Hz |
| GHz | `1.5GHz` | 1,500,000,000 Hz |

### Impedance

| Format | Example | Value |
|--------|---------|-------|
| Plain | `50` | 50 Ω |
| With unit | `50ohm` | 50 Ω |
| Unicode | `50Ω` | 50 Ω |
| kΩ | `1kohm` | 1000 Ω |

---

## Output Formats

### Table (default)

Human-readable format with ASCII diagrams, component tables, and E-series recommendations.

### JSON

```bash
./filter-calc.py lp bw 10MHz --format json
```

Structured output for programmatic use:
```json
{
  "filter_type": "butterworth",
  "cutoff_frequency_hz": 10000000.0,
  "impedance_ohms": 50.0,
  "order": 3,
  "components": {
    "capacitors": [...],
    "inductors": [...]
  }
}
```

### CSV

```bash
./filter-calc.py lp bw 10MHz --format csv
```

Spreadsheet-compatible format:
```
type,name,value
capacitor,C1,3.183e-10
capacitor,C2,3.183e-10
inductor,L1,1.592e-06
```

---

## E-Series Component Matching

The calculator automatically finds the nearest standard component values.

### Available Series

| Series | Tolerance | Values per Decade |
|--------|-----------|-------------------|
| E12 | ±10% | 12 |
| E24 | ±5% | 24 |
| E96 | ±1% | 96 |

### Matching Modes

- **Single value**: Closest E-series value
- **Parallel combination**: Two values in parallel for better accuracy

For capacitors, parallel combination is additive (C_total = C1 + C2).
For inductors, parallel combination is harmonic (L_total = L1*L2/(L1+L2)).

### Example Output

```
C1 Calculated: 196.73 pF
  Nearest Std:  200.00 pF (+1.7%)
  Parallel Std: 47.00 || 150.00 pF (+0.1%)
```

---

## ASCII Frequency Response Plots

Add `--plot` to visualize filter response in the terminal.

Features:
- Logarithmic frequency axis
- Adaptive dB scale based on response
- -3 dB reference line
- Cutoff frequency marking
- Works for all filter types

### Export Plot Data

```bash
# JSON format with metadata
./filter-calc.py lp bw 10MHz --plot-data json > response.json

# CSV for spreadsheet/graphing software
./filter-calc.py lp bw 10MHz --plot-data csv > response.csv
```
