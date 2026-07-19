# Quick Start Guide

## Basic Commands

### Lowpass Filter (Pi/T Topology)

```bash
# 5th-order Butterworth Pi at 10 MHz
uv run filter-calc lowpass butterworth pi 10MHz -n 5

# Short form
uv run filter-calc lp bw pi 10MHz -n 5
```

### Highpass Filter (Pi/T Topology)

```bash
# 5th-order Chebyshev T at 14 MHz with 0.5 dB ripple
uv run filter-calc highpass chebyshev t 14MHz -n 5 -r 0.5

# Short form
uv run filter-calc hp ch t 14MHz -r 0.5

# Pi topology
uv run filter-calc hp ch pi 14MHz -r 0.5
```

### Bandpass Filter (Coupled Resonator)

```bash
# 20m amateur band (14.0-14.35 MHz)
uv run filter-calc bandpass butterworth top -f 14.175MHz -b 350kHz

# Alternative: specify low/high cutoffs directly
uv run filter-calc bp bw top --fl 14MHz --fh 14.35MHz
```

With `--fl` / `--fh`, the calculator uses the geometric center internally. Reported
edges are reconstructed from that center and bandwidth and agree with the requested
values to floating-point precision.

Every bandpass result includes a per-design response status. Inspect warnings and
`response_validation_status` before treating a design as build-ready.

### Analyze a Realized Build

```bash
# Select nominal capacitor branches, screen toroids, apply component Q,
# and run deterministic tolerance corners plus two repeatable sample cases.
uv run filter-calc lp bw pi 10MHz --sim-build \
  --inductor-q 100 --capacitor-q 500 \
  --cap-tolerance 5 --ind-tolerance 10 \
  --samples 2 --seed 73 --format json

# Export the same nominal-build circuit as a generic SPICE deck.
uv run filter-calc lp bw pi 10MHz --format spice \
  --spice-realization nominal-build
```

Build analysis is a finite circuit simulation, not a measurement, guaranteed worst
case, yield prediction, or substitute for a VNA check.

### Interactive Wizard

```bash
uv run filter-calc
```

Running with no arguments starts the interactive wizard.

## Common Options

| Option | Description |
|--------|-------------|
| `-n` | Number of components (2-9) |
| `-z` | System impedance (default: 50Ω) |
| `-r` | Chebyshev ripple in dB |
| `--plot` | Show ASCII frequency response |
| `--format json` | Output as JSON |
| `-e E96` | Use E96 preferred-value density for capacitor selection |
| `--no-match` | Keep calculated capacitor values; do not select preferred values |
| `--no-toroids` | Disable screened toroid candidates |
| `--sim-build` | Compare calculated and realized circuits with tolerance screening |
| `--format spice` | Export a generic exact or nominal-build SPICE deck |

E12/E24/E96 do not specify part tolerance. Enter capacitor and inductor tolerances
separately when using build analysis.

## Filter Type Aliases

| Alias | Full Name |
|-------|-----------|
| `bw`, `b` | Butterworth |
| `ch`, `c` | Chebyshev |
| `bs` | Bessel |

## Frequency Formats

All equivalent:
```
10MHz  10M  10000000  10e6  10000k  10000kHz
```
