# Quick Start Guide

## Basic Commands

### Lowpass Filter (Pi/T Topology)

```bash
# 5th-order Butterworth at 10 MHz
./filter-calc.py lowpass butterworth 10MHz -n 5

# Short form
./filter-calc.py lp bw 10MHz -n 5
```

### Highpass Filter (Pi/T Topology)

```bash
# 5th-order Chebyshev T at 14 MHz with 0.5 dB ripple
./filter-calc.py highpass chebyshev t 14MHz -n 5 -r 0.5

# Short form
./filter-calc.py hp ch t 14MHz -r 0.5

# Pi topology
./filter-calc.py hp ch pi 14MHz -r 0.5
```

### Bandpass Filter (Coupled Resonator)

```bash
# 20m amateur band (14.0-14.35 MHz)
./filter-calc.py bandpass butterworth top -f 14.175MHz -b 350kHz

# Alternative: specify low/high cutoffs directly
./filter-calc.py bp bw top --fl 14MHz --fh 14.35MHz
```

### Interactive Wizard

```bash
./filter-calc.py
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
| `-e E96` | Use E96 series for matching |

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
