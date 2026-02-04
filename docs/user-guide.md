# User Guide

Complete reference for all commands, options, and features.

## Commands Overview

| Command | Aliases | Description |
|---------|---------|-------------|
| `lowpass` | `lp` | Low-pass filter (Pi or T topology) |
| `highpass` | `hp` | High-pass filter (Pi or T topology) |
| `bandpass` | `bp` | Coupled resonator bandpass filter |
| *(no args)* | - | Interactive wizard (default) |

---

## Lowpass Command

Designs low-pass filters with Pi or T topology.

- **Pi topology**: shunt C - series L - shunt C - ... (capacitors at odd positions)
- **T topology**: series L - shunt C - series L - ... (inductors at odd positions)

### Syntax

```bash
uv run filter-calc lowpass <filter_type> <topology> <frequency> [options]
uv run filter-calc lp <filter_type> <frequency> --topology pi|t [options]
```

### Positional Arguments

| Argument | Description |
|----------|-------------|
| `filter_type` | `butterworth`, `chebyshev`, `bessel` (or aliases) |
| `topology` | Filter topology: `pi` or `t` (also accepted via `--topology`) |
| `frequency` | Cutoff frequency (e.g., `10MHz`, `7.1M`) |

### Options

| Option | Default | Description |
|--------|---------|-------------|
| `--topology` | - | Filter topology: `pi` or `t` (required if not positional) |
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
# 5th-order Butterworth Pi at 7.1 MHz for 40m band
uv run filter-calc lp bw pi 7.1MHz -n 5

# T topology lowpass
uv run filter-calc lp bw 10MHz -n 5 --topology t

# Chebyshev with 1 dB ripple at 28 MHz
uv run filter-calc lp ch pi 28MHz -r 1.0 -n 7

# Output with frequency response plot
uv run filter-calc lp bw pi 10MHz --plot

# JSON output for scripting
uv run filter-calc lp bw pi 10MHz --format json

# High-precision E96 component matching
uv run filter-calc lp bw pi 10MHz -e E96

# Export frequency response data
uv run filter-calc lp bw pi 10MHz --plot-data csv > response.csv
```

---

## Highpass Command

Designs high-pass filters with Pi or T topology.

- **T topology**: series C - shunt L - series C - ... (capacitors at odd positions)
- **Pi topology**: shunt L - series C - shunt L - ... (inductors at odd positions)

### Syntax

```bash
uv run filter-calc highpass <filter_type> <topology> <frequency> [options]
uv run filter-calc hp <filter_type> <frequency> --topology pi|t [options]
```

### Arguments and Options

Same options as lowpass command, with topology required (`pi` or `t`).

### Examples

```bash
# Block below 14 MHz (20m band high-pass, T topology)
uv run filter-calc hp bw t 14MHz -n 5

# Pi topology highpass
uv run filter-calc hp bw 14MHz -n 5 --topology pi

# Steep Chebyshev rolloff
uv run filter-calc hp ch t 3.5MHz -r 0.5 -n 7
```

---

## Bandpass Command

Designs coupled-resonator bandpass filters using LC tank circuits.

### Syntax

```bash
uv run filter-calc bandpass <filter_type> <coupling> [options]
uv run filter-calc bp <filter_type> <coupling> [options]
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
uv run filter-calc bp bw top -f 14.175MHz -b 350kHz

# Same filter using low/high specification
uv run filter-calc bp bw top --fl 14MHz --fh 14.35MHz

# 5-resonator Chebyshev (odd count required)
uv run filter-calc bp ch top -f 7.15MHz -b 200kHz -n 5 -r 0.5

# Shunt-coupled topology
uv run filter-calc bp bw shunt -f 21.2MHz -b 450kHz
```

---

## Interactive Wizard (Textual TUI)

Running with no arguments starts the interactive Textual TUI wizard for guided filter design.

### Syntax

```bash
uv run filter-calc
```

### User Interface

The wizard is a **Terminal User Interface (TUI)** built with Textual framework, featuring:
- **Arrow key navigation**: Move between fields and options
- **Tab/Shift+Tab**: Jump to next/previous input field
- **Enter**: Submit form or confirm selection
- **Space**: Toggle checkbox options
- **Escape**: Go back to previous screen
- **Ctrl+C**: Exit the wizard

### Design Flow

The wizard guides you through a 4-screen sequence (5 if frequency plot selected):

#### 1. Welcome Screen
Select your filter category:
```
┌──────────────────────────────┐
│ RF Filter Calculator         │
├──────────────────────────────┤
│ Select Filter Category:      │
│                              │
│ ❯ Lowpass                    │
│   Highpass                   │
│   Bandpass                   │
│                              │
│ [Enter] to continue          │
└──────────────────────────────┘
```

#### 2. Parameter Screen (Lowpass/Highpass/Bandpass)

Enter filter parameters with defaults shown as placeholders:

**Lowpass/Highpass Example:**
```
┌──────────────────────────────┐
│ Lowpass Filter Parameters    │
├──────────────────────────────┤
│ Response Type: [Butterworth] │
│ ❯ Butterworth               │
│   Chebyshev (Ripple: 0.5 dB)│
│   Bessel                     │
│                              │
│ Topology: [Pi]              │
│ ❯ Pi                        │
│   T                         │
│                              │
│ Frequency: [10.0 MHz]       │
│ ▌                           │ (input field)
│                              │
│ Impedance: [50 Ω]           │
│ ▌                           │ (input field)
│                              │
│ Components: [3]             │
│ ▌                           │ (input field)
│                              │
│ [Tab] next field [Enter] next│
└──────────────────────────────┘
```

**Bandpass Example:**
```
┌──────────────────────────────┐
│ Bandpass Filter Parameters   │
├──────────────────────────────┤
│ Center Frequency: [10.0 MHz] │
│ ▌                           │ (input field)
│                              │
│ Bandwidth: [1.0 MHz]        │
│ ▌                           │ (input field)
│                              │
│ Topology: [Top-coupled]     │
│ ❯ Top-coupled              │
│   Shunt-coupled            │
│                              │
│ Resonators: [3]             │
│ ▌                           │ (input field)
│                              │
│ [Tab] next field [Enter] next│
└──────────────────────────────┘
```

**Key Features:**
- Input fields show **placeholder defaults** (e.g., "10.0 MHz")
- Press Tab to move between fields
- Press Enter to submit and continue
- Arrow keys to select among radio options
- Chebyshev ripple field appears only when needed

#### 3. Output Options Screen (Optional Export/Format Settings)

Configure output format and display options:

```
┌──────────────────────────────┐
│ Output Options               │
├──────────────────────────────┤
│ E-Series Matching:           │
│ ❯ E24 (±5% tolerance)       │
│   E12 (±10% tolerance)      │
│   E96 (±1% tolerance)       │
│   None (calculated only)    │
│                              │
│ Output Format:               │
│ ❯ Table (pretty display)    │
│   JSON (machine-readable)   │
│   CSV (spreadsheet)         │
│                              │
│ Export Frequency Data:       │
│ ❯ No export                 │
│   JSON file                 │
│   CSV file                  │
│                              │
│ Additional Options:          │
│ ☐ Raw units (Farads/Henries)│
│ ☐ Quiet mode (minimal)      │
│                              │
│ [Space] toggle [Enter] next  │
└──────────────────────────────┘
```

#### 4. Results Screen

View calculated filter components:

```
┌──────────────────────────────┐
│ Filter Results               │
├──────────────────────────────┤
│ [Loading calculation...]     │
│                              │
│ Then displays full output:   │
│ - Circuit topology diagram   │
│ - Component table            │
│ - E-series recommendations   │
│                              │
│ Show frequency plot? (y/n)   │
│                              │
│ [Esc] exit wizard            │
└──────────────────────────────┘
```

### Keyboard Reference

| Key | Action |
|-----|--------|
| ↑↓ | Navigate between options/fields |
| Tab | Move to next input field |
| Shift+Tab | Move to previous field |
| Enter | Confirm selection / Submit form / Continue |
| Space | Toggle checkbox |
| Escape | Go back to previous screen |
| Ctrl+C | Exit wizard |

### Input Formats

All frequency and impedance inputs support the same formats as CLI commands (see [Input Formats](#input-formats) section below).

---

## Input Formats

### Frequency

| Format | Example | Value |
|--------|---------|-------|
| Full suffix | `10MHz`, `500kHz`, `1GHz` | With Hz |
| Shorthand | `10M`, `500k`, `1G` | Without Hz |
| Scientific | `10e6` | 10,000,000 Hz |
| Plain Hz | `10000000` | 10,000,000 Hz |

Suffixes are case-insensitive: `10M`, `10m`, `10MHz`, `10mhz` all equal 10 MHz.

**Validation**: Frequency must be positive. Zero or negative values raise an error.

### Impedance

| Format | Example | Value |
|--------|---------|-------|
| Plain | `50` | 50 Ω |
| With unit | `50ohm` | 50 Ω |
| Unicode | `50Ω` | 50 Ω |
| kΩ | `1kohm` | 1000 Ω |

**Validation**: Impedance must be positive. Zero or negative values raise an error.

---

## Output Formats

### Table (default)

Human-readable format with ASCII diagrams, component tables, and E-series recommendations.

### JSON

```bash
uv run filter-calc lp bw pi 10MHz --format json
```

Structured output for programmatic use:
```json
{
  "filter_type": "butterworth",
  "cutoff_frequency_hz": 10000000.0,
  "impedance_ohms": 50.0,
  "order": 3,
  "topology": "pi",
  "components": {
    "capacitors": [...],
    "inductors": [...]
  }
}
```

### CSV

```bash
uv run filter-calc lp bw pi 10MHz --format csv
```

Spreadsheet-compatible format:
```
Component,Value,Unit
C1,318.31,pF
C2,318.31,pF
L1,1.59,µH
```

---

## E-Series Component Matching

The calculator automatically finds the nearest standard component values for capacitors.

### Available Series

| Series | Tolerance | Values per Decade |
|--------|-----------|-------------------|
| E12 | ±10% | 12 |
| E24 | ±5% | 24 |
| E96 | ±1% | 96 |
| None | - | Calculated values only |

### Matching Modes

- **Single value**: Closest E-series value
- **Parallel combination**: Two values in parallel for better accuracy

For capacitors, parallel combination is additive (C_total = C1 + C2).
For inductors, parallel combination is harmonic (L_total = L1*L2/(L1+L2)).

**Note**: E-series matching recommendations are provided for capacitors. Inductor component selection is typically custom-wound or sourced by specification.

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
uv run filter-calc lp bw pi 10MHz --plot-data json > response.json

# CSV for spreadsheet/graphing software
uv run filter-calc lp bw pi 10MHz --plot-data csv > response.csv
```
