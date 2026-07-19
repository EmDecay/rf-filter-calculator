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
uv run filter-calc lp <filter_type> -T pi|t -f <frequency> [options]
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
| `-e, --eseries` | E24 | Preferred-value density for capacitor selection (E12, E24, E96) |
| `--no-match` | - | Keep calculated capacitor values; disable preferred-value selection |
| `--raw` | - | Show raw values (Farads/Henries) |
| `-q, --quiet` | - | Minimal output |
| `--format` | table | Output format: `table`, `json`, `csv`, `spice` |
| `--plot` | - | Show ASCII frequency response |
| `--plot-data` | - | Export response data: `json` or `csv` |
| `--explain` | - | Display filter type characteristics |
| `--no-toroids` | - | Suppress toroid recommendations |
| `--toroid-compact` | - | Compact 1-line-per-rec toroid output (text only) |
| `--toroid-full` | - | Show up to three qualified candidates (default: best available) |
| `--sim-build` | - | Analyze the selected nominal build, loss, and bounded tolerance cases |
| `--sim-matched` | - | Deprecated compatibility alias for a nominal-build comparison |

### Examples

```bash
# 5th-order Butterworth Pi at 7.1 MHz for 40m band
uv run filter-calc lp bw pi 7.1MHz -n 5

# T topology lowpass
uv run filter-calc lp bw -f 10MHz -n 5 --topology t

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

# Analyze a nominal build with explicit finite-Q and tolerance assumptions
uv run filter-calc lp bw pi 10MHz --sim-build \
  --inductor-q 100 --capacitor-q 500 \
  --capacitor-tolerance 5 --inductor-tolerance 10 --format json
```

### Build Analysis and SPICE Controls

These controls are shared by lowpass, highpass, and bandpass commands:

| Option | Meaning |
|--------|---------|
| `--sim-build` | Compare calculated values, selected nominal branches, and bounded tolerance cases |
| `--capacitor-tolerance PCT` | Capacitor bound for deterministic corners (default 5%) |
| `--inductor-tolerance PCT` | Inductor bound for deterministic corners (default 10%) |
| `--inductor-q Q`, `--capacitor-q Q` | Convert Q to constant series resistance at the reference frequency |
| `--source-resistance`, `--load-resistance` | Evaluate transducer gain with unequal ports; synthesis remains equal-termination |
| `--loss-reference-frequency` | Frequency at which supplied Q is converted to series resistance |
| `--sample-count N`, `--seed S` | Add repeatable uniform-bound screening cases; not a yield/probability model |
| `--analysis-points N` | Response grid size (default 601) |
| `--no-toroid-build` | Use calculated inductance as an explicit fallback in the nominal realization |
| `--format spice --spice-realization exact` | Generic lossless deck with calculated values |
| `--format spice --spice-realization nominal-build` | Generic deck with selected parts/fallbacks and configured loss |

Tolerance analysis is a bounded simulation, not a measurement or guaranteed worst case.

---

## Highpass Command

Designs high-pass filters with Pi or T topology.

- **T topology**: series C - shunt L - series C - ... (capacitors at odd positions)
- **Pi topology**: shunt L - series C - shunt L - ... (inductors at odd positions)

### Syntax

```bash
uv run filter-calc highpass <filter_type> <topology> <frequency> [options]
uv run filter-calc hp <filter_type> -T pi|t -f <frequency> [options]
```

### Arguments and Options

Same options as lowpass command, with topology required (`pi` or `t`).

### Examples

```bash
# Block below 14 MHz (20m band high-pass, T topology)
uv run filter-calc hp bw t 14MHz -n 5

# Pi topology highpass
uv run filter-calc hp bw -f 14MHz -n 5 --topology pi

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
| `coupling` | Coupling topology: `top` (series capacitors; the only supported kind, alias `t`) |

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

When `--fl` and `--fh` are used, the calculator derives the synthesis center from the
geometric mean `f₀ = √(f_low × f_high)`. JSON `requested_parameters` and the build-analysis
`target` block preserve the parsed edge values exactly and mark the edge-frequency input mode.
Top-level calculated edges and plot labels are reconstructed from center/bandwidth and agree
with the request to floating-point precision.

### Options

| Option | Default | Description |
|--------|---------|-------------|
| `-f, --frequency` | - | Center frequency |
| `-b, --bandwidth` | - | 3 dB bandwidth |
| `--fl` | - | Lower cutoff frequency |
| `--fh` | - | Upper cutoff frequency |
| `-n, --resonators` | 3 | Number of resonators (2-9) |
| `-z, --impedance` | 50 | System impedance |
| `-r, --ripple` | 0.5 | Chebyshev ripple in dB |
| `-e, --eseries` | E24 | E-series for matching |
| `--no-match` | - | Disable E-series matching |
| `--raw` | - | Raw scientific notation |
| `-q, --quiet` | - | Minimal output |
| `--format` | table | Output format: `table`, `json`, `csv`, `spice` |
| `--plot` | - | Show ASCII frequency response |
| `--plot-data` | - | Export response data (json or csv) |
| `--explain` | - | Explain filter characteristics |
| `--no-toroids` | - | Suppress toroid recommendations |
| `--toroid-compact` | - | Compact 1-line-per-rec toroid output (text only) |
| `--toroid-full` | - | Show up to three qualified toroid candidates |
| `--qu` | - | Complete resonator unloaded Q; used for Cohn estimate and nominal-build loss |
| `--ql`, `--qc` | - | Inductor and tank-capacitor Q; combined as `1/Qu = 1/QL + 1/QC` |
| `--resonator-impedance` | design Z | Select tank reactance `sqrt(L/C)` independently of terminations |
| `--resonator-inductance` | - | Fix tank inductance; mutually exclusive with tank impedance |
| `--sim-build` | - | Analyze nominal parts, effective loss, and tolerance cases |
| `--sim-matched` | - | Deprecated compatibility alias |

### Bandpass Coupling Topologies

| Type | Aliases | Description |
|------|---------|-------------|
| `top` | `t` | Top-coupled series capacitors (Ce_in/Ce_out, Cs12/Cs23) — the only supported kind |

### Examples

```bash
# 20m amateur band filter (14.0-14.35 MHz)
uv run filter-calc bp bw top -f 14.175MHz -b 350kHz

# Same filter using low/high specification
uv run filter-calc bp bw top --fl 14MHz --fh 14.35MHz

# 5-resonator Chebyshev (odd count required)
uv run filter-calc bp ch top -f 7.15MHz -b 200kHz -n 5 -r 0.5

# Choose 1.2 µH tanks and model separate inductor/tank-capacitor Q
uv run filter-calc bp bw top -f 14.2MHz -b 500kHz \
  --resonator-inductance 1.2uH --ql 180 --qc 500 --sim-build
```

The calculator calibrates each Top-C circuit to the requested −3 dB skirts and reports
`response_validation_status`. Some designs within 10% fractional bandwidth remain outside
the validated response envelope, and some combinations are unrealizable; inspect each result.

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

The wizard guides you through four screens. A selected frequency plot is rendered in Results;
it is not a separate screen.

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
│ Coupling: [Top-C (Series)]  │
│ ❯ Top-C (Series)           │
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
│ ❯ E24 (24 values/decade)    │
│   E12 (12 values/decade)    │
│   E96 (96 values/decade)    │
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
│ ☑ Show frequency plot       │
│ ☐ Raw units (Farads/Henries)│
│ ☐ Quiet mode (minimal)      │
│                              │
│ Realized-Build Analysis:     │
│ ☐ Analyze nominal parts and │
│   bounded tolerances         │
│   (reveals ports, tolerance, │
│    Q, sample, and grid input)│
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
│ - Frequency plot (if chosen  │
│   on Output Options screen)  │
│                              │
│ [Design Another] [Export]    │
│ [Quit]                       │
│ Esc: back · Q: quit          │
└──────────────────────────────┘
```

Output choices that would silently hide selected information are rejected. Raw table output
may use an E-series only when realized-build analysis consumes it for nominal part selection;
quiet output cannot hide build analysis. Export offers Text, JSON, or CSV as applicable, and
Save can also write the selected response-data sidecar.

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

JSON is strict: non-finite numbers are rejected instead of emitting `NaN` or `Infinity`.
With `--sim-build`, the schema separates the synthesis target, calculated response,
nominal realization, exact fallbacks, effective loss model, tolerance cases, evaluation
ports, and limitations. LP/HP measurements expose one cutoff; bandpass exposes two skirts,
center, and bandwidth.

### CSV

```bash
uv run filter-calc lp bw pi 10MHz --format csv
```

Spreadsheet-compatible, RFC-style quoted CSV. Every row has the same number of columns,
including when warning text contains commas. Preferred-value columns identify the one
selected realization and its policy; toroid columns identify the best qualified candidate
and explicitly mark RF Q, SRF, and power as not assessed.

### SPICE

```bash
# Calculated, lossless values
uv run filter-calc lp bw pi 10MHz --format spice --spice-realization exact

# Selected nominal branches, exact fallbacks, and optional Q-derived series loss
uv run filter-calc lp bw pi 10MHz --format spice \
  --spice-realization nominal-build --inductor-q 100 --capacitor-q 500
```

The deck is generic SPICE. It prints load voltage and comments the exact transducer-gain
relationship; it does not claim the voltage trace itself is transducer gain.

---

## E-Series Component Matching

The calculator automatically finds the nearest standard component values for capacitors.

### Available Series

| Series | Preferred Values per Decade |
|--------|-----------------------------|
| E12 | 12 |
| E24 | 24 |
| E96 | 96 |
| None | Calculated values only |

An E-series name is not a tolerance declaration. For example, an E24-valued capacitor
may be sold in multiple tolerances. Enter the actual tolerance separately in build analysis.

### Matching Modes

- **Single value**: selected when its absolute target error is at most 1%
- **Parallel combination**: selected only when it improves the single-part error by at least
  0.5 percentage points (capacitors add in parallel)
- **Below 1 pF**: automatic selection is withheld; the output asks for an expert override

**Note**: E-series matching recommendations are provided for capacitors only. Inductors are shown as raw design values — they are typically custom-wound (see toroid recommendations below).

### Example Output

```
C1 Calculated: 196.73 pF
  Nearest Std:  200.00 pF (+1.7%)
  Parallel Std: 47.00 pF || 150.00 pF (+0.1%)
```

---

## ASCII Frequency Response Plots

Add `--plot` to visualize filter response in the terminal. Both lowpass and highpass filters automatically include two plots with a dB threshold summary table.

### Full-Range and Zoomed Plots

Two vertically stacked ASCII plots appear automatically:

1. **Full-Range Plot**: Shows complete response from 1 MHz to 100+ MHz or sweep range
   - Logarithmic frequency axis
   - Automatic range from 0 dB, with the lower plot limit clamped at -60 dB
   - Cutoff frequency marked with (fc)
   - Works for all filter types

2. **Zoomed Passband Plot**: Detail view of low-dB region (0 to -6 dB)
   - 2× frequency resolution for smoother curves
   - Helps visualize ripple and transition sharpness
   - Skipped if passband is completely flat
   - For Chebyshev: adaptive range = max(6, 2×ripple) dB

### Threshold Summary Table

Automatically displays frequencies where response crosses key dB levels:
- **-3 dB** — Approximate -3dB frequency (cutoff point)
- **-10 dB** — Start of significant attenuation
- **-20 dB** — Strong attenuation reference

For **Lowpass** and **Highpass**: Single column with direction arrows:
- **↓** (down arrow) = Lowpass response falling below threshold
- **↑** (up arrow) = Highpass response rising above threshold

For **Bandpass**: Dual columns (f_low / f_high) showing where response crosses thresholds

If the bandpass filter was specified with `--fl` / `--fh`, the requested values remain in
machine-readable metadata. Plot labels use the calculator's geometrically centered edge values,
which reproduce the entered edges to floating-point precision.

Shows "N/A" when a threshold is not reached within the sweep frequency range.

### Export Plot Data

```bash
# JSON format with metadata
uv run filter-calc lp bw pi 10MHz --plot-data json > response.json

# CSV for spreadsheet/graphing software
uv run filter-calc lp bw pi 10MHz --plot-data csv > response.csv
```

## Toroid Winding Recommendations

For every inductor, the calculator may show a **screened winding candidate**. Automatic
selection is intentionally limited to T25-6, T50-2, and T68-2 because those records have
primary-sourced core, frequency, and winding-capacity data. A candidate must cover the
design frequency, fit the published winding capacity, and keep integer-turn error within
the core's published A_L tolerance.

Default table output shows the best qualified candidate. `--toroid-full` shows up to three,
JSON includes up to three, and CSV carries the best available candidate. “Up to” matters:
the calculator does not fill the list with unqualified cores.

### Default text output (top-1 core)

```
Screened Toroid Winding Candidates (Iron-Powder T-Series)
-------------------------------------------------------
(Integer turns, published frequency guidance, and winding capacity only)

  L1 target: 1.29 µH  (design freq 10 MHz)
  ────────────────────────────────────────────────────────────
  1. T68-2  (Red/Clear, mix 2, 95 ppm/°C)
     Turns: 15 of AWG 20   Actual L: 1.28 µH  (-0.40%)
     L range (A_L ±5%): 1.22 µH – 1.35 µH
     Wire: 294 mm of AWG 20 (0.812 mm)   DCR: 9.5 mΩ
     Wire-only ωL/Rdc diagnostic ceiling: 8,450 @ 10 MHz
     RF Q / SRF / power: not assessed
     Dims: 17.50 × 9.40 × 4.83 mm (OD × ID × H)
```

### Full output: show top-3 (`--toroid-full`)

Use `--toroid-full` to show up to three qualified cores in table format.

### Compact output (`--toroid-compact`)

```
  L1 target: 1.29 µH @ 10 MHz
  1. T68-2    N=15 AWG20 L=1.283µH (-0.40%) Rdc=10mΩ ωL/Rdc≤8,450
```

Use `--toroid-compact` for one line per qualified candidate in table output.

### Disable toroid output (`--no-toroids`)

`--no-toroids` skips candidate computation. Contradictory combinations such as
`--no-toroids --toroid-full` are usage errors rather than silently ignored controls.

### Bandpass behaviour

All N resonators share the chosen tank inductance, so bandpass prints one candidate block
that applies to L1…Ln. JSON retains candidate provenance and assessment status.

### Design frequency used

- Lowpass / highpass: filter cutoff frequency
- Bandpass: centre frequency `f0`

### Important caveats

- **No RF suitability claim**: RF Q, core loss, SRF, saturation, temperature rise, and
  power handling are not modeled. `ωL/Rdc` is only a wire-loss diagnostic ceiling.
- **Frequency guidance is a hard screen**: a core outside its published range is excluded.
- **Published winding tables are authoritative** where available; geometric estimates are
  labeled and are not used to promote unverified legacy records into automatic selection.
- Measure the built filter and consult the manufacturer data before applying power.
