# Quick Start Guide

There are three ways to design a filter. They share one engine, so the same settings give the same values everywhere:

- **Command line** — `uv run filter-calc <category> …`, best for scripts and repeatable designs.
- **Interactive wizard** — `uv run filter-calc` with no arguments, a guided terminal form.
- **Web UI** — `uv run filter-calc web`, a page in your browser on this computer (needs the optional web dependencies: `uv sync --extra web` once).

## Command Line

### Low-Pass Filter (Pi/T Topology)

```bash
# 5th-order Butterworth Pi at 10 MHz
uv run filter-calc lowpass butterworth pi 10MHz -n 5

# Short form
uv run filter-calc lp bw pi 10MHz -n 5
```

### High-Pass Filter (Pi/T Topology)

```bash
# 5th-order Chebyshev T at 14 MHz with 0.5 dB ripple
uv run filter-calc highpass chebyshev t 14MHz -n 5 -r 0.5

# Short form
uv run filter-calc hp ch t 14MHz -r 0.5

# Pi topology
uv run filter-calc hp ch pi 14MHz -r 0.5
```

### Band-Pass Filter (Coupled Resonators)

```bash
# 20m amateur band (14.0-14.35 MHz)
uv run filter-calc bandpass butterworth top -f 14.175MHz -b 350kHz

# Alternative: give the lower and upper -3 dB edges directly
uv run filter-calc bp bw top --fl 14MHz --fh 14.35MHz
```

With `--fl` / `--fh`, the calculator uses the geometric center internally. Reported
edges are reconstructed from that center and bandwidth and agree with the requested
values to floating-point precision.

Every band-pass result includes a **Response Check** line (`response_validation_status` in
JSON). Read it and any warnings before treating a design as ready to build.

### Simulate the Built Filter

```bash
# Simulate the chosen parts (standard capacitor values and suggested toroid
# windings) with part losses (Q), across the tolerance cases plus two extra
# random tolerance cases.
uv run filter-calc lp bw pi 10MHz --sim-build \
  --inductor-q 100 --capacitor-q 500 \
  --cap-tolerance 5 --ind-tolerance 10 \
  --samples 2 --seed 73 --format json

# Export the same chosen parts as a generic SPICE deck.
uv run filter-calc lp bw pi 10MHz --format spice \
  --spice-realization nominal-build
```

The build simulation is a circuit simulation, not a measurement, a guaranteed worst case,
a yield prediction, or a substitute for a VNA check.

## Interactive Wizard

```bash
uv run filter-calc
```

Running with no arguments starts the interactive wizard: choose a filter, fill in its form,
choose the output, and read the result. It offers the same options, labels, and defaults as the
web UI. An option that cannot apply to the chosen output is disabled, with the reason under it.

## Web UI

```bash
uv sync --extra web
uv run filter-calc web [--port <port>]
```

Open the printed address (default `http://127.0.0.1:8765/`), pick a tab, and select
**Design filter**. The result is the CLI's own text for the same settings, with an optional
response graph and download buttons; downloads use the inputs of the result shown. See the
[user guide](user-guide.md#web-ui) for how each field maps to a CLI flag.

## Common Options

| Option | Description |
|--------|-------------|
| `-f`, `--frequency`, `--freq` | Cutoff or center frequency, as a flag instead of the positional argument |
| `-n` | Number of components or resonators (2-9) |
| `-z` | Source and load impedance (default: 50 Ω) |
| `-r` | Chebyshev ripple in dB |
| `--plot` | Add a text plot of the frequency response to the table |
| `--format json` | Output as JSON |
| `-e E96` | Choose capacitors from the E96 standard values (96 per decade) |
| `--no-match` | Show only calculated capacitor values; do not choose standard values |
| `--allow-sub-pf` | Also choose standard values for capacitors below 1 pF |
| `--no-toroids` | Leave out the toroid winding suggestions |
| `--sim-build` | Build simulation: the ideal values compared with the chosen parts, across tolerance cases |
| `--format spice` | Export a generic SPICE deck (chosen parts by default, or `--spice-realization exact`, also spelled `calculated`) |

E12/E24/E96 set how many standard values there are per decade, not the part tolerance.
Enter capacitor and inductor tolerances separately for the build simulation. In the wizard
and web UI, **Allow capacitors below 1 pF** is the same as `--allow-sub-pf`.

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
