# RF Filter Calculator

Calculates LC filter component values for RF engineers and amateur radio operators. There are three ways to use it, all backed by the same engine and producing the same results:

| Interface | Start it with | Best for |
|---|---|---|
| Command line | `uv run filter-calc lowpass …` | Scripting, repeatable designs, machine-readable output |
| Interactive wizard (terminal) | `uv run filter-calc` | Guided design without remembering flags |
| Web UI (browser, this computer only) | `uv run filter-calc web` | Point-and-click design with a response graph and downloads; needs the optional `web` dependencies |

## Features

- **Filter Types**: Low-pass (Pi/T topology), High-pass (Pi/T topology), Band-pass (coupled resonators with Top-C series-capacitor coupling, checked by circuit simulation)
- **Response Types**: Butterworth, Chebyshev (any ripple in (0, 3] dB), Bessel. Chebyshev LP/HP cutoff is the ripple-band edge (ARRL/Elsie/Zverev convention), not the −3 dB point; band-pass `bw` is the true −3 dB bandwidth
- **Standard Capacitor Values**: E12/E24/E96 sets how many standard values there are per decade, not the part tolerance. Each capacitor gets one choice: a single part within 1%, otherwise two in parallel if that is at least 0.5 percentage points closer. Below 1 pF no part is chosen automatically unless you turn on `--allow-sub-pf` (**Allow capacitors below 1 pF** in the wizard and web UI)
- **End Coupling**: Band-pass external Q is set by series end-coupling capacitors (Ce_in/Ce_out); transformation formula built-in
- **Checked Band-Pass Design**: Each Top-C design places both −3 dB edges where requested, and a response check simulates the circuit to confirm the passband, outer edges, passband shape, ripple, and points just outside the passband. Rejection farther out is not checked; the attenuation at 2×f₀ and 3×f₀ and the Cohn loss estimates are reported separately
- **Build Simulation**: `--sim-build` simulates the filter with the chosen parts (standard capacitor values and suggested toroid windings), optional part losses (Q), and tolerance cases plus repeatable extra random cases. Measurements include the exact requested band edges and say when a value did not converge or the response is above −3 dB in separate ranges
- **Generic SPICE Export**: decks with the calculated values (`exact`, or `calculated`) or the chosen parts (`nominal-build`, or `chosen-parts`) use the same named circuit as the build simulation; band-pass decks map SPICE names to table names in a `* names:` comment
- **Toroid Winding Suggestions**: Automatic suggestions are limited to cores with primary-source data (currently T25-6, T50-2, and T68-2) that are rated for the frequency, reach the inductance within the A_L tolerance using whole turns, and fit the winding. RF Q, SRF, core loss, saturation, heating, and power handling are not checked
- **ASCII Plots**: Visualize the frequency response (LP/HP ideal transfer function, BP simulated circuit)
- **Multiple Outputs**: Table, JSON, CSV, generic SPICE, and standalone response-data exports
- **Interactive Wizard**: Guided terminal (TUI) design mode with the same options, labels, defaults, and order as the web UI
- **Web UI**: A local browser page with the same designs, the CLI's own output text, an SVG response graph, and downloads identical to the CLI's files
- **Aligned interfaces**: In the wizard and the web UI, an option that cannot apply to the chosen output is disabled with a one-line reason, using the same rule the command line enforces
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

For the browser UI, add the optional `web` dependencies (FastAPI, uvicorn, Jinja2):
```bash
uv sync --extra web                  # add --group dev for development
```

For an installed package, the same extra is `pip install "rf-filter-calculator[web]"`.

## Quick Start

### Command line

```bash
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

### Interactive wizard

```bash
uv run filter-calc
```

Running with no arguments opens the terminal wizard: pick a filter category, fill in the form, choose output options, and read the result. See [Interactive Wizard](#interactive-wizard) below.

### Web UI

```bash
uv sync --extra web        # once: installs the optional web dependencies
uv run filter-calc web     # then open http://127.0.0.1:8765/ in your browser
```

Pick a tab (Low-pass, High-pass, Band-pass), adjust the form, and select **Design filter**. Press `Ctrl+C` in the terminal to stop the server. See [Web UI](#web-ui) below.

### Running without `uv run`

The `uv sync` command creates a virtual environment in `.venv/` at the project root. If you activate that virtual environment in your shell, you can run `./filter-calc.py` directly instead of prefixing every command with `uv run`:

```bash
# Activate the virtual environment
source .venv/bin/activate    # macOS/Linux (bash/zsh)
source .venv/bin/activate.fish  # Fish shell
.venv\Scripts\activate       # Windows

# Now you can run the script directly
./filter-calc.py lowpass butterworth pi 10MHz -n 5
./filter-calc.py            # wizard
./filter-calc.py web        # web UI (needs the optional web dependencies)

# When you're done, deactivate the virtual environment
deactivate
```

## Command-Line Usage

### Low-Pass Filter

```bash
uv run filter-calc lowpass <FILTER_TYPE> <TOPOLOGY> <FREQUENCY> [options]
uv run filter-calc lp <FILTER_TYPE> -T pi|t -f <FREQUENCY> [options]
```

**Example:**
```bash
uv run filter-calc lp bw pi 7.1MHz -n 5 --plot
```

See [sample output](docs/sample-output.md) for current table, JSON, build-simulation, and SPICE examples.

### High-Pass Filter

```bash
uv run filter-calc highpass <FILTER_TYPE> <TOPOLOGY> <FREQUENCY> [options]
uv run filter-calc hp <FILTER_TYPE> -T pi|t -f <FREQUENCY> [options]
```

### Band-Pass Filter (Coupled Resonators)

```bash
uv run filter-calc bandpass <FILTER_TYPE> <COUPLING> [options]
uv run filter-calc bp <FILTER_TYPE> <COUPLING> [options]
```

**Frequency specification:**
```bash
# Method 1: Center frequency + bandwidth
uv run filter-calc bp bw top -f 14.175MHz -b 350kHz

# Method 2: Lower and upper -3 dB edges
uv run filter-calc bp bw top --fl 14MHz --fh 14.35MHz
```

When using `--fl` and `--fh`, the calculator designs around the geometric center
`f₀ = √(f_low × f_high)`. The reported edges are reconstructed from that center and
bandwidth and agree with the requested values to floating-point precision.

**Coupling:**
- `top` / `t` — series capacitors (Ce_in/Ce_out for external Q, Cs12/Cs23 between resonators; the only supported type)

### Options

| Option | Description |
|--------|-------------|
| `-T, --topology` | Topology: `pi` (shunt first) or `t` (series first) (required for lowpass/highpass, positionally or as a flag) |
| `--type` | Response type: butterworth, chebyshev, bessel (or bw/ch/bs aliases) |
| `-n, --components` | LP/HP number of components (2–9, default: 3; Chebyshev needs an odd number) |
| `-n, --resonators` | Band-pass number of resonators (2–9, default: 3; Chebyshev needs an odd number) |
| `-f, --frequency, --freq` | LP/HP cutoff frequency (the −3 dB point for Butterworth and Bessel, the ripple-band edge for Chebyshev); band-pass center frequency (or use `--fl`/`--fh`). Both spellings work on every subcommand |
| `-c, --coupling` | Band-pass coupling `top` (alias `t`), as a flag instead of the positional argument |
| `-z, --impedance` | Source and load impedance in ohms (default: 50; accepts 50, 50ohm, 1k, 1M; `m` also means mega) |
| `-r, --ripple` | Chebyshev passband ripple in dB, 0 < r ≤ 3.0 (default: 0.5; warns if used with non-Chebyshev) |
| `-b, --bandwidth` | Band-pass bandwidth between the −3 dB edges (or use `--fl`/`--fh` for the edges) |
| `-e, --eseries` | Standard capacitor values to choose from: E12, E24, E96 (default: E24) |
| `--no-match` | Show only calculated capacitor values; do not choose standard values |
| `--allow-sub-pf` | Also choose standard values for capacitors below 1 pF (table, CSV, JSON, `--sim-build`, and the `nominal-build` SPICE deck); needs an E-series |
| `--raw` | Unrounded values in farads and henries (scientific notation) |
| `-q, --quiet` | Print only the component values, one per line |
| `--format` | Output format: table, json, csv, spice (default: table) |
| `--plot` | Add a text plot of the frequency response to the table |
| `--plot-data` | Print only the frequency response, as json or csv |
| `--explain` | Print a short description of the filter type and exit |
| `--no-toroids` | Leave out the suggested toroid windings from all outputs |
| `--toroid-compact` | Table output: the best toroid suggestion for each inductor on one line |
| `--toroid-full` | Table output: up to three toroid suggestions per inductor (default: the best one; JSON lists up to three, CSV the best) |
| `--sim-matched` | Deprecated; use `--sim-build` |
| `--sim-build` | Build simulation: simulate the filter with the chosen parts at nominal values and across tolerance cases, with optional part losses (Q) |
| `--capacitor-tolerance`, `--inductor-tolerance` (aliases `--cap-tolerance`, `--ind-tolerance`) | ± percent tolerances for `--sim-build` (defaults 5 and 10); not taken from the E-series |
| `--inductor-q`, `--capacitor-q` | Part losses (Q) for `--sim-build` or the `nominal-build` SPICE deck |
| `--loss-reference-frequency` | Frequency at which the Q values apply (default: cutoff or center frequency); needs a Q option |
| `--source-resistance`, `--load-resistance` | Simulation source and load resistance; component values are still designed for equal source and load impedance |
| `--sample-count` (alias `--samples`), `--seed`, `--analysis-points` | Extra random tolerance cases, their random seed, and the number of frequency points; measurements are refined automatically |
| `--no-toroid-build` | Simulate the calculated inductances instead of the suggested toroid windings |
| `--spice-realization` | Values in the `--format spice` deck: `exact` or `calculated` (calculated values, lossless), or `nominal-build` or `chosen-parts` (chosen parts; default) |
| `--qu` | Band-pass resonator Qu (inductor and capacitor losses together), for the loss estimate and the build simulation |
| `--ql`, `--qc` | Band-pass inductor/capacitor Q; combined as `1/Qu = 1/QL + 1/QC` |
| `--resonator-impedance`, `--resonator-inductance` (aliases `--tank-impedance`, `--tank-inductance`) | Resonator (L–C tank) impedance `sqrt(L/C)` or inductance, independent of the source and load impedance |
| `--version` | Root option: `filter-calc --version` |
| `--host`, `--port` | `web` subcommand only: bind address (default `127.0.0.1`) and port (default `8765`) |

## Interactive Wizard

```bash
uv run filter-calc          # default when no arguments given
uv run filter-calc wizard   # explicit subcommand (alias: w)
```

Running with no arguments starts a Textual TUI wizard with screen-based navigation:

1. **Welcome Screen** - Choose a filter (low-pass, high-pass, band-pass)
2. **Filter Configuration** - Set response, topology or coupling, frequency, impedance, and number of components or resonators. Band-pass takes the center and width or the two −3 dB band edges, plus optional resonator size and resonator Q (Qu, or QL and QC)
3. **Output options** - Format (Table, Values only, JSON, CSV), standard capacitor values (and **Allow capacitors below 1 pF**), toroid windings (Best, detailed; Up to 3, detailed; Best, one line; None), text plot and raw units, a response data file, and the optional build simulation. An option that cannot apply to the chosen format is disabled with the reason under it
4. **Results** - View the calculation and save it; the component file and an optional response-data file are chosen separately

**Keyboard shortcuts:**
- `Tab` / `Shift+Tab` - Navigate between fields
- `Enter` - Submit / select
- `Escape` - Go back to previous screen
- `Ctrl+C` - Quit

Fields start at the CLI defaults; a blank frequency field uses the value its label names (for example `blank = 10MHz`). Enter moves to the next control and Space ticks a box.

## Web UI

The web UI needs the optional `web` dependencies (`uv sync --extra web`, or `pip install "rf-filter-calculator[web]"` for an installed package). Start it with:

```bash
uv run filter-calc web [--host <address>] [--port <port>]
```

It prints its address (by default `http://127.0.0.1:8765/`) and serves until you press `Ctrl+C`. Without the dependencies, it exits with a message saying how to install them.

**What the page offers:**
- A tab for each filter category and a form whose fields match the command-line flags (see the [field-to-flag table](docs/user-guide.md#web-ui)).
- A result panel showing exactly the text the command line prints for the same settings, with a **Copy** button.
- An optional **response graph**, drawn from the same frequency data as `--plot-data`.
- **Downloads**: Design (JSON), Components (CSV), SPICE – calculated values, SPICE – chosen parts, and response data (JSON or CSV), each identical to the matching command-line output.
- The **Allow capacitors below 1 pF** option and the optional build simulation (**Simulate the built filter**). A calculation that runs longer than 60 seconds is stopped.
- The same options, labels, defaults, and order as the wizard. An option that cannot apply to the chosen format is disabled with the reason under it, and downloads use the inputs of the result shown; a notice says when the form has changed since.

**Local by design.** The web UI is meant for use on your own computer. It listens only on the loopback address unless you pass `--host`, warns when you do, and has no login. It accepts form submissions only from its own page, so other websites you visit cannot make your browser use it. Only use `--host 0.0.0.0` on a network you trust.

## Filter Type Aliases

| Alias | Filter Type |
|-------|-------------|
| `bw`, `b` | Butterworth |
| `ch`, `c` | Chebyshev |
| `bs` | Bessel |

## Frequency Input Formats

These formats work on the command line, in the wizard, and in the web form. All of these are equivalent (case-insensitive):
```
10MHz  10M  10mhz  10m  10000000  10e6  10000k  10000kHz
```

Supported suffixes: `GHz`, `MHz`, `kHz`, `Hz`, `G`, `M`, `k`

**Note:** Frequency and impedance must be positive values. Zero or negative values raise a validation error.

## Output Formats

The web UI offers the same formats as download buttons; each download is identical to the command shown here.

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

**Build simulation:**
```bash
uv run filter-calc lp bw pi 10MHz --sim-build --inductor-q 100 \
  --capacitor-q 500 --sample-count 100 --seed 73 --format json > build.json
```

The tolerance cases (all parts low, all high, each part low and high alone, plus the extra random cases) show spread; they are not a guaranteed worst case, a production-yield estimate, or a measurement.

**SPICE deck:**
```bash
uv run filter-calc bp bw top -f 14.175MHz -b 350kHz \
  --format spice --spice-realization nominal-build --qu 200 > filter.cir
```

The deck prints load-node voltage. Its comment gives the transducer-gain expression; the printed voltage is not itself gain in dB. `--spice-realization nominal-build` (the default) uses the chosen parts and lists each one in a `* part used:` comment; `exact` uses the calculated values without losses. `chosen-parts` and `calculated` are the same choices under the names the web UI uses.

## Release Notes

### Plain-language output and aligned interfaces (v2.3.0)

Version 2.3.0 rewrites help, error messages, table output, and the wizard and web labels in plain wording (for example "build simulation", "chosen parts", "toroid winding suggestions"). The new `--allow-sub-pf` option (**Allow capacitors below 1 pF** in the wizard and web UI) lets the calculator choose capacitors below 1 pF. The wizard and web UI now offer the same options with the same labels, defaults, and order, and disable an option that cannot apply instead of ignoring or refusing it. On the command line, `--frequency` and `--freq` work on every subcommand, `--spice-realization` also accepts `calculated` and `chosen-parts`, and every bad `-n` gets the same "Number of … must be from 2 to 9" error (exit status 1). No JSON key, CSV column, flag, or choice value was removed or renamed; numeric results are unchanged. See [docs/project-changelog.md](docs/project-changelog.md).

### Web UI and shared design service (v2.2.0)

Version 2.2.0 adds the local web UI (`filter-calc web`, optional `web` extra) and moves the command line, wizard, and web UI onto one shared design engine, so all three produce identical results. Command-line and wizard output is unchanged. It also ships the accuracy and stability fixes made after 2.1.0. See [docs/project-changelog.md](docs/project-changelog.md).

### Accuracy and build remediation (v2.1.0)

Version 2.1.0 makes calculated, nominal-build, tolerance-screening, and SPICE results explicit. It also replaces blanket bandpass support claims with per-design validation metadata, hardens finite-number handling, adds independent tank L/impedance controls and complete-resonator Q semantics, restricts automatic toroid selection to primary-sourced parts, and makes E-series selection deterministic. `--sim-matched` remains as a deprecated compatibility alias; use `--sim-build` for new workflows.

### Breaking changes (v2.0.0)

**Migration from v1.x:** `-t` short flag removed (use `--type` instead); `--verify` removed from bandpass; `-r` now warns if used with non-Chebyshev filters; ripple validation changed from hardcoded tiers to 0 < r ≤ 3.0; wizard resonator default changed to 3. See [docs/project-changelog.md](docs/project-changelog.md) for full details and migration path.

## Testing & CI

Run the test suite with pytest. Install the `web` extra too, or the web UI tests skip themselves:

```bash
uv sync --group dev --extra web

# Run all tests
uv run pytest tests/ -v

# Run with coverage
uv run pytest tests/ --cov=filter_lib --cov-report=term-missing
```

**Test suite:** More than 4,500 collected cases, with a CI coverage floor of 90%, including an exhaustive 128-cell bandpass study, independent response verification, build/tolerance/loss contracts, strict JSON, generic SPICE, Python 3.10–3.13, wheel/sdist inspection, installed-wheel smoke tests, and real Textual pilot tests. See [docs/testing.md](docs/testing.md) for current details.

### Linting

[Ruff](https://docs.astral.sh/ruff/) is used for linting and formatting:

```bash
uv run ruff check .          # Lint
uv run ruff format --check .  # Check formatting
```

### Continuous Integration

GitHub Actions runs Ruff, the full coverage-gated suite on Python 3.10–3.13 with the `web` extra, the suite again on a core install without it, and wheel/sdist build plus installed-wheel smoke checks on every push and PR to `main`.

## Project Structure

```
rf-filter-calculator/
├── filter-calc.py          # Main CLI entry point
├── tests/                  # Test suite (pytest)
└── filter_lib/
    ├── cli/                # Subcommand handlers
    ├── design/             # Shared request → synthesis → render/export path for every surface
    ├── lowpass/            # Lowpass calculations (Pi/T)
    ├── highpass/           # Highpass calculations (Pi/T)
    ├── bandpass/           # Top-C band-pass design and its response check
    ├── wizard/             # Interactive design mode
    ├── web/                # Local browser UI (optional web dependencies)
    └── shared/             # Parsing, part selection, build simulation, SPICE, plotting
```

## Documentation

See [docs/](docs/README.md) for the full index. Good starting points:
- [Quick Start Guide](docs/quick-start.md) - Common commands for all three interfaces
- [User Guide](docs/user-guide.md) - Complete reference, including the [web UI field-to-flag table](docs/user-guide.md#web-ui)
- [Sample Output](docs/sample-output.md) - What each output format looks like
- [Filter Theory](docs/filter-theory.md) - Background on filter types
- [Caveats & Known Issues](docs/caveats-and-known-issues.md) - Limits of the models and of the web UI
- [Testing Guide](docs/testing.md) - Test suite documentation

## License

GPL-3.0. See [LICENSE](LICENSE) for details.

## Author

Matt N3AR (with AI assistance)
