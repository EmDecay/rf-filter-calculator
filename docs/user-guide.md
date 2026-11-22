# User Guide

Complete reference for all commands, options, and features. Upgrading from 2.x? See
[Migrating from 2.x](#migrating-from-2x).

## Commands Overview

| Command | Aliases | Description |
|---------|---------|-------------|
| `lowpass` | `lp` | Low-pass filter (Pi or T topology) |
| `highpass` | `hp` | High-pass filter (Pi or T topology) |
| `bandpass` | `bp` | Coupled-resonator band-pass filter |
| `wizard` | `w` | Interactive terminal wizard (also the default with no arguments) |
| `web` | - | Browser interface on this computer (needs the optional `web` dependencies) |

`filter-calc --version` prints the version of the code that runs, and
`filter-calc <command> --help` lists every option for that command.

## Lowpass Command

Designs low-pass filters with Pi or T topology.

- **Pi topology**: shunt C - series L - shunt C - ... (capacitors at odd positions)
- **T topology**: series L - shunt C - series L - ... (inductors at odd positions)

### Syntax

```bash
uv run filter-calc lowpass <FILTER_TYPE> <TOPOLOGY> <FREQUENCY> [options]
uv run filter-calc lp <FILTER_TYPE> -T pi|t -f <FREQUENCY> [options]
```

### Positional Arguments

| Argument | Description |
|----------|-------------|
| `FILTER_TYPE` | Response type: `butterworth` (`bw`, `b`), `chebyshev` (`ch`, `c`), or `bessel` (`bs`) |
| `TOPOLOGY` | `pi` (shunt first) or `t` (series first), the element nearest the input (also `--topology`) |
| `FREQUENCY` | Cutoff frequency, e.g. `10MHz`: the −3 dB point for Butterworth and Bessel, the ripple-band edge for Chebyshev |

### Options

| Option | Default | Description |
|--------|---------|-------------|
| `--type` | - | Response type, as a flag instead of the positional argument |
| `-T, --topology` | - | Topology: `pi` (shunt first) or `t` (series first), as a flag instead of the positional argument |
| `-f, --frequency, --freq` | - | Cutoff frequency, as a flag instead of the positional argument |
| `-n, --components` | 3 | Order: the number of inductors and capacitors, 2-9; Chebyshev needs an odd order. Anything else, including a non-whole number, is refused with `Order must be from 2 to 9` (exit status 1) |
| `-z, --impedance` | 50 | Source and load impedance in ohms; k and M suffixes allowed (`m` also means mega) |
| `-r, --ripple` | 0.5 | Chebyshev ripple in dB, `0 < r <= 3.0` (ignored by other types) |
| `-e, --eseries` | E24 | Standard capacitor values to choose from: E12, E24, or E96 (12, 24, or 96 values per decade); sets how many values there are, not part tolerance |
| `--no-match` | - | Show only calculated capacitor values; do not choose standard values |
| `--allow-sub-pf` | - | Also choose standard values for capacitors below 1 pF (see [below](#standard-capacitor-values-e-series)) |
| `--raw` | - | Unrounded values in farads and henries (scientific notation), without standard-value matching |
| `-q, --quiet` | - | Print only the component values, one per line |
| `--format` | table | Output format: `table`, `json`, `csv`, `spice` |
| `--plot` | - | Add a text plot of the frequency response to the table |
| `--plot-data` | - | Print only the frequency response, as `json` or `csv` |
| `--explain` | - | Print a short description of the response type and exit |
| `--inductor-suggestions` | best | Inductor suggestions: `best`, `full`, `compact` (table only), or `none` (left out of every output); see [Inductor Suggestions](#inductor-suggestions) |
| `--sim-build` | - | Build simulation: simulate the filter with the chosen parts, part losses (Q), and tolerance cases |

### Examples

```bash
# 5th-order Butterworth Pi at 7.1 MHz for 40m band
uv run filter-calc lp bw pi 7.1MHz -n 5

# Chebyshev with 1 dB ripple at 28 MHz
uv run filter-calc lp ch pi 28MHz -r 1.0 -n 7

# Output with frequency response plot
uv run filter-calc lp bw pi 10MHz --plot

# JSON output for scripting
uv run filter-calc lp bw pi 10MHz --format json

# Finer E96 standard capacitor values
uv run filter-calc lp bw pi 10MHz -e E96

# Tight-grade capacitors, a looser 3% tolerance floor, and a 0.1 pF stray across each pair
uv run filter-calc lp bw pi 146MHz -n 5 --capacitor-grade tight --capacitor-tolerance 3 --stray-capacitance 0.1pF

# Simulate the built filter with part losses (Q) and component tolerances
uv run filter-calc lp bw pi 10MHz --sim-build \
  --inductor-q 100 --capacitor-q 500 \
  --capacitor-tolerance 5 --inductor-tolerance 10 --format json
```

### Build Simulation and SPICE Controls

These controls are shared by lowpass, highpass, and bandpass commands. The build simulation
uses the chosen parts: the standard capacitor values and the inductor suggestions.

| Option | Meaning |
|--------|---------|
| `--sim-build` | Simulate the ideal values and the chosen parts, at nominal values and across tolerance cases (all parts low, all high, each part low and high alone). Table or JSON output only |
| `--inductor-tolerance PCT` (alias `--ind-tolerance`) | Tolerance of every inductor in ± percent, 0 to under 100 (default: each chip inductor's own guaranteed tolerance, and 10 for toroid windings and calculated values). Capacitors use their own tolerances; see Standard Capacitor Values |
| `--inductor-q Q`, `--capacitor-q Q` | Part losses (Q), 0.01 to 1e9, for `--sim-build` and the chosen-parts SPICE deck. Each Q becomes a fixed series resistance at the frequency where the Q values apply. Omit for lossless parts |
| `--source-resistance`, `--load-resistance` | Simulation source and load resistance (1e-6 to 1e6 times `-z`). Component values are still designed for equal source and load impedance |
| `--loss-reference-frequency` | Frequency at which the Q values apply (default: cutoff or center frequency); needs a Q option |
| `--sample-count N` (alias `--samples`), `--seed S` | Extra random tolerance cases, 0 to 10000, each part drawn uniformly within its tolerance; the same seed repeats the same cases. Not a production-yield estimate |
| `--analysis-points N` | Frequency points in the `--sim-build` sweep, 51–5001 (default 601); measurements are refined between points automatically |
| `--build-inductors` | What `--sim-build` and the chosen-parts SPICE deck use for each inductor: `auto` (default), `toroid`, `air-coil`, `chip`, or `calculated`; see [Inductors in the build](#inductors-in-the-build) |
| `--format spice --spice-realization exact` (or `calculated`) | SPICE deck with the calculated values, without losses |
| `--format spice --spice-realization nominal-build` (or `chosen-parts`) | SPICE deck with the chosen parts and any Q losses (the default) |

The build simulation is a simulation, not a measurement, and the tolerance cases do not
guarantee the true worst case.

### Interpreting response measurements

Build measurements evaluate the exact requested band boundaries and refine interior extrema
and −3 dB crossings; `--analysis-points` sets the initial frequency points, not the total
number of circuit evaluations. The [refinement rules](../filter_lib/shared/response_refinement.py)
compare successive meshes to 0.001 dB and 0.00001 times the requested bandwidth (BP) or cutoff
(LP/HP), with at most four passes, and narrow crossing brackets to 0.0000001 times that scale.
That is numerical convergence, not hardware accuracy or proof that no narrower feature lies
between evaluated frequencies. More points, extra random cases, and high-order or strongly
perturbed cases cost more circuit evaluations.

Every ideal-value, chosen-parts, and tolerance-case record in JSON includes
`measurement_converged` and `response_evaluations`. A case that did not converge stays in the
case list but is left out of the spread figures ("did not converge; values approximate";
JSON `unresolved_cases` and `omitted_cases` count them). A −3 dB point outside the simulated
frequency range is `null`, with `edge_at_simulation_grid_boundary: true`, and is left out of
the edge figures; more points do not widen that range.

BP bandwidth belongs to the range above −3 dB around the peak nearest the requested center,
identified by `reference_peak_frequency_hz`, `reference_peak_gain_db`, and
`half_power_threshold_db`; when it differs from the overall `peak_transducer_gain_db` the table
says "−3 dB measured from the … peak at …". `half_power_regions` lists every range above that
level, `selected_region_index` (zero-based) the one used, and `center_in_selected_region`
whether it holds the requested center; with separate ranges the table says so. Check these
cases before relying on the spread figures. The build's −3 dB level is half power,
3.0102999566 dB below the reference peak; the plot tables use exactly 3.0 dB. For LP/HP,
"lowest gain in passband" covers the simulated part of the passband, not DC or infinity.

## Highpass Command

Designs high-pass filters with Pi or T topology.

- **T topology**: series C - shunt L - series C - ... (capacitors at odd positions)
- **Pi topology**: shunt L - series C - shunt L - ... (inductors at odd positions)

### Syntax

```bash
uv run filter-calc highpass <FILTER_TYPE> <TOPOLOGY> <FREQUENCY> [options]
uv run filter-calc hp <FILTER_TYPE> -T pi|t -f <FREQUENCY> [options]
```

Arguments and options are the same as for the lowpass command.

### Examples

```bash
# Block below 14 MHz (20m band high-pass, T topology)
uv run filter-calc hp bw t 14MHz -n 5

# Pi topology highpass
uv run filter-calc hp bw -f 14MHz -n 5 --topology pi

# Steep Chebyshev rolloff
uv run filter-calc hp ch t 3.5MHz -r 0.5 -n 7
```

## Bandpass Command

Designs coupled-resonator band-pass filters; each resonator is an L–C tank.

### Syntax

```bash
uv run filter-calc bandpass <FILTER_TYPE> <COUPLING> [options]
uv run filter-calc bp <FILTER_TYPE> <COUPLING> [options]
```

### Positional Arguments

| Argument | Description |
|----------|-------------|
| `FILTER_TYPE` | Response type: `butterworth`, `chebyshev`, `bessel` (or aliases) |
| `COUPLING` | Coupling between resonators: `top` or `t` (series capacitors Ce_in/Ce_out and Cs12/Cs23; the only supported type) |

### Frequency Specification

Give either the center and bandwidth (`-f <center> -b <bandwidth>`) or the lower and upper
−3 dB edges (`--fl <lower_edge> --fh <upper_edge>`), not both. With edges, the design center is
the geometric mean `f₀ = √(f_low × f_high)`; JSON `requested_parameters` and the build `target`
keep the parsed edges exactly, and the reported edges agree with them to floating-point precision.

### Options

The standard-value options (`-e`, `--no-match`, `--allow-sub-pf`, `--capacitor-grade`,
`--capacitor-tolerance`, `--stray-capacitance`), the output options (`--raw`, `-q`, `--format`,
`--plot`, `--plot-data`, `--explain`), `--inductor-suggestions`, and the
[build simulation and SPICE controls](#build-simulation-and-spice-controls) are the same as for
lowpass. Band-pass adds:

| Option | Default | Description |
|--------|---------|-------------|
| `--type` | - | Response type, as a flag instead of the positional argument |
| `-c, --coupling` | - | Coupling `top` (alias `t`), as a flag instead of the positional argument |
| `-f, --frequency, --freq` | - | Center frequency |
| `-b, --bandwidth` | - | Bandwidth between the −3 dB edges, for every response type including Chebyshev |
| `--fl`, `--fh` | - | Lower and upper −3 dB edges, together, instead of `-f` and `-b` |
| `-n, --resonators` | 3 | Number of resonators, 2-9; Chebyshev needs an odd number. Anything else is refused with `Number of resonators must be from 2 to 9` |
| `-z, --impedance` | 50 | Source and load impedance in ohms |
| `-r, --ripple` | 0.5 | Chebyshev ripple in dB, `0 < r <= 3.0` |
| `--qu` | - | Resonator Qu: unloaded Q of each resonator, inductor and capacitor losses together (0.01 to 1e9). Adds an insertion-loss estimate and sets the resonator losses for `--sim-build` and the chosen-parts SPICE deck. Estimates at Qu = 100 and 250 are always shown |
| `--ql`, `--qc` | - | Resonator inductor Q and resonator capacitor Q at the center frequency (each 0.01 to 1e9), instead of `--qu`; combined as `1/Qu = 1/(inductor Q) + 1/(capacitor Q)` |
| `--resonator-impedance` (alias `--tank-impedance`) | `-z` | Resonator (L–C tank) impedance `sqrt(L/C)`; it can differ from the source and load impedance |
| `--resonator-inductance` (alias `--tank-inductance`) | - | Inductance of every resonator, e.g. `1.2uH`; cannot be combined with `--resonator-impedance` |

### Examples

```bash
# 20m amateur band filter (14.0-14.35 MHz)
uv run filter-calc bp bw top -f 14.175MHz -b 350kHz

# Same filter using low/high specification
uv run filter-calc bp bw top --fl 14MHz --fh 14.35MHz

# 5-resonator Chebyshev (odd count required)
uv run filter-calc bp ch top -f 7.15MHz -b 200kHz -n 5 -r 0.5

# 1.2 µH resonator inductors, with separate inductor and capacitor Q
uv run filter-calc bp bw top -f 14.2MHz -b 500kHz \
  --resonator-inductance 1.2uH --ql 180 --qc 500 --sim-build
```

The calculator places each top-coupled design's −3 dB edges where requested and prints a
**Response Check** line (`response_validation_status` in JSON): `Passed (simulated circuit
matches the requested response)` or `Not confirmed; see warnings below`. The verified range
goes up to 10% fractional bandwidth, but some designs within it are not confirmed and some
cannot be built; check each result. The check covers the −3 dB edges, the passband shape, and
points just outside the passband; farther out, top-coupled rejection can differ from the ideal
response and is not checked. The `Attenuation at 2×f₀ … at 3×f₀` line (`harmonic_response` in
JSON) reports the lossless circuit there, without an acceptance limit.

The **Insertion loss at f₀** block gives, for each resonator Qu, the Cohn estimate (a small-loss
approximation) and a circuit simulation of the calculated parts with one equivalent series loss
in each resonator inductor. When they differ by more than 0.5 dB the table adds `(estimate off by
more than 0.5 dB; use the simulated value)` and JSON `loss_estimate_validation` says
`poor_approximation_at_center`; this is a reporting rule, not a reason to reject the design.
Use `--sim-build` for separate inductor and capacitor Q or the chosen parts. Q keys in
`il_estimates` keep enough precision to tell a user value from the examples; parse them as numbers.

## Interactive Wizard (Textual TUI)

Running `uv run filter-calc` with no arguments starts the wizard for guided filter design.

### Design Flow

The wizard has four screens; a selected text plot is rendered in Results. The wizard and the
web UI offer the same options with the same labels, defaults, and order. Fields start at the
CLI defaults; a blank frequency field uses the value its label names (for example
`blank = 10MHz`). Invalid values are reported on the field to fix.

#### 1. Welcome

Under *Choose a filter*, pick **Low-Pass**, **High-Pass**, or **Band-Pass** and press Enter.

#### 2. Filter design (one screen per category)

- **Low-pass and high-pass:** *Response and topology*: Response (Butterworth, Chebyshev,
  Bessel), Topology (Pi (shunt first) or T (series first); low-pass defaults to Pi, high-pass
  to T), and passband ripple in dB, shown only for Chebyshev. *Frequency and size*: cutoff
  frequency (the label says −3 dB point or ripple-band edge to match the response), order
  (the number of inductors and capacitors, 2-9), and impedance, equal source and load (`50`).
- **Band-pass:** *Response and coupling*: Response, Coupling (top-coupled, the only option), and
  ripple for Chebyshev. *Passband*: *Specify the band by* **Center and width** (`14.175MHz`,
  `350kHz`) or **Band edges** (lower and upper −3 dB edges, `14MHz` and `14.35MHz`, the same as
  `--fl`/`--fh`), with a fractional bandwidth note shown as you type; number of resonators
  (2-9) and impedance. *Resonators and losses (optional)*: resonator impedance `sqrt(L/C)` or
  resonator inductance, not both; and **Resonator Qu**, or **Resonator inductor Q** and
  **Resonator capacitor Q** (`--qu`, `--ql`, `--qc`). These are disabled, with the reason,
  when the format chosen on the next screen cannot show them (Values only and CSV).

#### 3. Output options

- *Format*: Table (default), Values only (`-q`), JSON, or CSV.
- *Standard capacitor values*: E12, E24 (default), E96, or None (`--no-match`), plus **Allow
  capacitors below 1 pF** (`--allow-sub-pf`; needs E12, E24, or E96).
- *Inductor suggestions (table detail)*: Best, detailed (default), Up to 3 per kind, detailed,
  Best, one line, or None (`--inductor-suggestions best|full|compact|none`); see
  [Inductor Suggestions](#inductor-suggestions).
- **Text plot in the table** (`--plot`, off by default) and **Raw units (F, H)** (`--raw`).

*Response data file*: None, or a JSON or CSV response file (`--plot-data`), saved when you export
the results. It is the ideal response, so it leaves out the resonator Q.

*Build simulation (optional)*: tick **Simulate the built filter** (`--sim-build`) to show its
fields, pre-filled with the CLI defaults (a blank field takes that default): capacitor and
inductor tolerance (±%), inductor Q and capacitor Q, **Frequency at which the Q values apply**
(`--loss-reference-frequency`; blank = the cutoff or center frequency), simulation source and
load resistance, extra random tolerance cases, random seed, frequency points, and **Inductors
in the build** (`--build-inductors`): Auto (default), Toroid windings, Air-core coils, Chip
inductors, or Calculated values.

An option that cannot apply is disabled, with a one-line reason under it, and treated as not
set, like leaving out the CLI flag (the rule is the one the CLI enforces): Values only disables
the standard capacitor values, the text plot, the two table-only inductor suggestion choices,
and the build simulation; Inductor suggestions None disables the three forced kinds of
**Inductors in the build** (Auto and Calculated values stay usable and build the calculated
values).
Select **Show results** to calculate.

#### 4. Results

Shows the same output the CLI prints for these settings. **Design another** starts over, and
**Export** offers *Save as* Text (as shown), JSON (full design), or CSV (components) plus
**Save**, which also writes the selected response-data file, in the folder shown on the
screen. If a file cannot be written, or the starting folder no longer exists, the wizard says
so and keeps running.

Saved JSON and CSV files use each disabled option's visible value where that file can show it,
like the web UI's downloads: with Values only and None, the JSON file is `--format json
--no-match`; with Values only and the build ticked, the JSON file includes the build, simulated
when you save it ("Preparing the JSON file…"; a problem with the build fields is reported then).
CSV is disabled, with the reason shown, when the result includes the build or resonator Q.

**Keys:** ↑↓ and Tab/Shift+Tab move between fields, Enter selects or continues, Space ticks a
box, Escape goes back (quits from Welcome), Q quits from Results, and Ctrl+C exits. Frequency
and impedance fields accept the CLI's [input formats](#input-formats).

## Web UI

The web UI is a third way to use the same calculator. It needs the optional extra:

```bash
uv sync --extra web
uv run filter-calc web [--host <address>] [--port <port>]
```

The server listens on `127.0.0.1:8765` unless told otherwise and prints its address. It has no
authentication and is meant for one computer; binding to any other address prints a warning.
Only the calculator's own page can submit designs: a browser request from another site is
refused with HTTP 403 (scripts such as `curl` are not affected). Requests must be addressed to
`127.0.0.1`, `localhost`, `[::1]`, or the `--host` address; binding to every interface
(`--host 0.0.0.0` or `::`) skips that check, so only do that on a network you trust.

### What the page shows

- The result panel shows exactly the text `filter-calc` prints for the same settings, including
  the inductor suggestions, the text plot when ticked, and the build-simulation block.
  Band-pass design warnings appear once: in the table for Table format, otherwise in a notice
  above the output.
- **Response graph** adds an SVG chart of the `--plot-data` frequency and magnitude data (ideal
  transfer function for LP/HP, simulated circuit for BP), with a dashed −3 dB guide.
- Invalid input shows the CLI's message (web-only fields have their own plain messages), and
  the form keeps what you typed. Without JavaScript, submissions reload the whole page.

### Downloads

Each button returns a file whose contents are byte-identical to the CLI command shown:

| Button | CLI equivalent |
|---|---|
| Design (JSON) | `--format json` (includes the build simulation when **Simulate the built filter** is ticked) |
| Components (CSV) | `--format csv` |
| SPICE – calculated values | `--format spice --spice-realization exact` |
| SPICE – chosen parts | `--format spice` (uses the build section's Q, source/load and **Inductors in the build** values when it is ticked; needs an E-series) |
| Response data (JSON) / (CSV) | `--plot-data json` / `--plot-data csv` |

Downloads use the inputs of the result shown; after an edit the page says "Inputs changed —
select Design filter to update the result and downloads." until you select **Design filter** or
undo the edit. A disabled option's visible value is used by each download that can show it,
judged by the same rule as the page. With Values only and None, Design (JSON) is `--format json --no-match`; with
Values only or CSV and the build ticked, Design (JSON) and SPICE – chosen parts include it; with
CSV and Qu, Design (JSON) and SPICE – chosen parts use `--qu`. Raw units, the text plot, and the
table-only inductor suggestion choices never reach a download; Inductor suggestions None does.
**Allow capacitors below 1 pF** is used by the Design, Components, and SPICE – chosen parts
downloads; SPICE – calculated values and the response data ignore it.

Components (CSV) and SPICE – calculated values refuse resonator Q (Qu, or the inductor and
capacitor Q) that the result shown used, as the CLI does. The response data downloads leave the
resonator Q out, so they equal `--plot-data` without them (the wizard's response data file does
the same). `POST /api/design/<category>` with the same form fields returns the `--format json`
document directly, for scripts: the same bytes as the Design JSON download. As for that
download, display-only fields (Format, Raw units, Text plot, the table-only inductor detail)
are ignored, and a `visible.<name>` value is used where it applies to the JSON.

### Form fields and CLI flags

Field names mirror the CLI flags, so a design can move between the two.

| Form field (name) | CLI flag | Notes |
|---|---|---|
| Response (`filter_type`) | positional type or `--type` | Aliases such as `bw`, `ch`, `bs` are accepted |
| Topology (`topology`) | positional or `-T` | Lowpass and highpass |
| Coupling (`coupling`) | positional `top` | Bandpass; top coupling is the only coupling |
| Cutoff / Center frequency (`frequency`) | positional or `-f` | Same unit suffixes as the CLI |
| Bandwidth (−3 dB) (`bandwidth`) | `-b` | Bandpass, when the band is given by center and width |
| Lower / Upper edge (−3 dB) (`f_low`, `f_high`) | `--fl`, `--fh` | Bandpass, when `band_spec` is `edges` |
| Order / Number of resonators (`components`, `resonators`) | `-n` | |
| Impedance (`impedance`) | `-z` | |
| Passband ripple (`ripple`) | `-r` | Shown and used for Chebyshev only |
| Resonator impedance / inductance (`resonator_impedance`, `resonator_inductance`) | `--resonator-impedance`, `--resonator-inductance` | Bandpass |
| Resonator Qu, Resonator inductor Q, Resonator capacitor Q (`qu`, `ql`, `qc`) | `--qu`, `--ql`, `--qc` | Bandpass; disabled with Values only and CSV |
| Format (`output_format`: table, quiet, json, csv) | `--format`; Values only is `-q` | |
| Standard capacitor values (`eseries`) | `-e`; **None** is `--no-match` | |
| Allow capacitors below 1 pF (`allow_sub_pf`) | `--allow-sub-pf` | Needs E12, E24, or E96 |
| Capacitor grade (`capacitor_grade`: standard, tight) | `--capacitor-grade` | Needs E12, E24, or E96 |
| Capacitor tolerance (±%) (`capacitor_tolerance_pct`) | `--capacitor-tolerance` | Blank by default (the grade's tolerance); needs E12, E24, or E96 |
| Stray capacitance per extra part (`stray_capacitance`) | `--stray-capacitance` | Blank by default (0.2 pF); needs E12, E24, or E96 |
| Inductor suggestions (table detail) (`inductor_suggestions`: best, full, compact, none) | `--inductor-suggestions` | Best, detailed (default) / Up to 3 per kind, detailed / Best, one line / None; full and compact need Table |
| Text plot in the table (`plot`) | `--plot` | Table only |
| Raw units (F, H) (`raw`) | `--raw` | Table or Values only |
| Response graph (`svg_plot`) | none | Web only |
| Simulate the built filter (`sim_build`) | `--sim-build` | Needs table or JSON output and an E-series |
| Build fields (`build_inductor_tolerance_pct`, `build_inductor_q`, `build_capacitor_q`, `build_reference_frequency`, `build_source_resistance`, `build_load_resistance`, `build_sample_count`, `build_seed`, `build_grid_points`) | `--inductor-tolerance`, `--inductor-q`, `--capacitor-q`, `--loss-reference-frequency`, `--source-resistance`, `--load-resistance`, `--sample-count`, `--seed`, `--analysis-points` | Labeled Inductor tolerance (±%), Inductor/Capacitor Q, Frequency at which the Q values apply, Simulation source/load resistance (Ω), Extra random tolerance cases, Random seed, Frequency points. Pre-filled with the CLI defaults (the inductor tolerance is blank: each chip inductor's own tolerance, and 10% for toroid windings and calculated values); a blank takes the default. Read only when the build box is ticked. A nonzero seed needs extra random cases |
| Inductors in the build (`build_inductors`: auto, toroid, air-coil, chip, calculated) | `--build-inductors` | Auto (default) / Toroid windings / Air-core coils / Chip inductors / Calculated values. A build field: read only when the build box is ticked. With Inductor suggestions None, the three forced kinds are disabled; the SPICE – calculated values and response-data downloads leave it out |

An option that cannot apply is disabled, with the reason under it, by the wizard's rule, and is
not submitted (like leaving out the CLI flag). A hand-made request that sets one anyway is
refused with that reason, except two that are ignored: the standard capacitor values with
Values only or Raw units (a radio choice is always submitted), and **Inductors in the build**
set to Auto or Calculated values with Inductor suggestions None (the build then uses the
calculated inductances, as the CLI does); a kind with None is refused, as on the CLI. The
deprecated `--q-safety` has no web field. The **SPICE – calculated values** and **Response
data** downloads leave out every standard-capacitor field, as if disabled.

### Long calculations

A request waits up to 60 seconds. When that runs out, the page reports "Calculation stopped
after 60 s. Try fewer resonators, or with the build simulation, fewer extra random tolerance
cases or frequency points." and the calculation
stops at its next check: a band-pass calibration or response check before its next circuit
evaluation, part resolution before its next part, and the build simulation before its next
case. A low-pass or high-pass synthesis is one closed-form step and is checked before it
starts. At most two calculations run at once; further requests wait their turn.

## Input Formats

Frequencies take `Hz`, `kHz`, `MHz`, or `GHz`, with or without `Hz` (`10MHz`, `10M`, `500k`,
`1G`), scientific notation (`10e6`), or plain hertz (`10000000`). Impedances take a plain
number of ohms (`50`), `ohm` or `Ω` (`50ohm`, `50Ω`), and k or M suffixes (`1kohm`, `1M`).
Suffixes are case-insensitive, so `10m` is 10 MHz and `50mohm` is 50 MΩ, not 50 mΩ. Zero or
negative frequencies and impedances are refused.

## Output Formats

The default **table** has ASCII diagrams, component tables, standard capacitor values, and
inductor suggestions. [Sample Output](sample-output.md) shows every format.

### JSON

```bash
uv run filter-calc lp bw pi 10MHz --format json
```

Strict JSON (non-finite numbers are refused, never emitted as `NaN` or `Infinity`):
`filter_type`, `cutoff_frequency_hz` (band-pass: center, edges, and bandwidth),
`impedance_ohms`, `order`, `topology`, and `components` with `capacitors` (each with its
`standard_match`) and `inductors` (each with its [`inductor_suggestions`](#inductor-suggestions)).
With `--sim-build`, it keeps the requested target, the ideal-value response (`simulated`), the
chosen parts (`nominal_build`, including any calculated values used in place of a part), the
effective loss model, the tolerance cases (`tolerance_analysis`), the simulation source and
load resistance (`evaluation`), and the limitations separate. LP/HP measurements expose one
cutoff; bandpass exposes two −3 dB edges, center, and bandwidth.

### CSV

```bash
uv run filter-calc lp bw pi 10MHz --format csv
```

RFC-style quoted CSV; every row has the same number of columns, even when warning text
contains commas. The standard-value columns give the one choice
made for each capacitor and the selection rule (`RecommendationPolicy`). For each inductor's best
suggestion, `InductorKind`, `InductorPart` and `InductorSRFBasis` name it, the
`InductorBudget*` columns give its error budget in percent of the target (the SRF drift columns
blank when it is not checked), the `Toroid*` columns give a toroid's details and repeat
that RF Q, SRF, and power handling are not checked, and the `Chip*` columns give a chip
inductor's maker, tolerance and catalog test frequency, minimum SRF, minimum Q with its test
frequency, the inductance at the top of the check window with that frequency, the
self-capacitance, the range within its allowances, the source URL, the model basis (the
parallel-LC model and the maker's fixture; board mounting changes the SRF) and the chip
caveats.

### SPICE

```bash
# Calculated, lossless values
uv run filter-calc lp bw pi 10MHz --format spice --spice-realization exact

# Chosen parts, with part losses (Q) as series resistance
uv run filter-calc lp bw pi 10MHz --format spice \
  --spice-realization nominal-build --inductor-q 100 --capacitor-q 500
```

The deck is generic SPICE. It prints load voltage and comments the exact transducer-gain
relationship. Comment lines say which values it uses (`* values: calculated, lossless (exact)`
or `* values: chosen parts (nominal-build)`), list each part of a chosen-parts deck
(`* part used: … part=T50-2 turns=18`), and, for bandpass, map SPICE names to table names
(`* names: CT1=Cp1 LT1=L1 … CK1=Cs12 … CIN=Ce_in COUT=Ce_out`; a pair is `CT2A+CT2B=Cp2`).
As in the build simulation block, each warning appears once with its parts, and the toroid
limitation only when a toroid was used. BP decks sweep linearly with at least 128 intervals per
resonator per requested bandwidth, LP/HP with 200 points per decade, over the build-simulation
range rather than remote rejection requirements. `--analysis-points` is not accepted for
SPICE-only output. No simulator is bundled.

## Standard Capacitor Values (E-Series)

The calculator chooses a standard value for each calculated capacitor from E12, E24 (default),
or E96: 12, 24, or 96 values per decade; `--no-match` shows calculated values only. An
E-series sets how many standard values there are, not the part tolerance. Tolerances come from
one sourced C0G series, Murata GRM1885C1H…A01 (0603, 50 V);
[component-data-sources.md](component-data-sources.md) records each value and its source.

| Value range | Standard grade (default) | Tight grade |
|---|---|---|
| 0.5–0.9 pF | ±0.1 pF | ±0.05 pF |
| 1–5 pF | ±0.25 pF | ±0.1 pF |
| 5.1–9.9 pF | ±0.5 pF | ±0.25 pF |
| 10–910 pF | ±5% | ±2% |
| 1–10 nF | ±5% | ±5% |

### How a value is chosen

Each capacitor gets one choice, shown on the `Use:` line, by its worst case within tolerance.
Each candidate covers an interval, its nominal value ± its tolerance (plus, for a pair, the
assumed stray across its second part), and scores the larger distance from the calculated
value to either end.

- **Single part or two in parallel**: the best single part and the best pair come from an
  exhaustive search over the values the sourced table lists; the pair is used only when it scores
  at least 0.5 percentage points better, and `Nearest single:` then shows the nearest single
  part. Ties go to the single part, then the pair with the smaller ratio, then the lower value;
  a pair's parts are within 10:1.
- **Tolerance not sourced**: a value the sourced table does not list (most E96 values, and parts
  above 10 nF) is chosen by the nominal rule (the nearest single part within 1%, otherwise a
  pair at least 0.5 points closer), and the row adds `Tolerance not sourced (a part is not in
  the sourced table): chosen by nominal value, ±5% assumed for it.`
- **Below 1 pF**: no part is chosen automatically. The row reads `Use: none (below 1 pF; see
  warning)`, the nearest single value is shown for reference only, and the warning says `Below
  1 pF no part is chosen automatically. Choose one manually, or turn on "Allow capacitors below
  1 pF" (--allow-sub-pf).`

The section heading states the grade, its tolerances, any override and the stray. Three
options change the choice; they apply to the table, CSV, JSON, `--sim-build` and the
chosen-parts SPICE deck, need an E-series, and are refused with `--no-match`, `--quiet`,
`--raw` (unless `--sim-build` is used), `--explain`, `--plot-data` and
`--spice-realization exact`:

| Option | Wizard and web | Meaning |
|--------|----------------|---------|
| `--capacitor-grade standard\|tight` | **Capacitor grade** | The tolerance grade (default standard; tight is one step tighter below 1000 pF, and from 1000 pF both grades are ±5%) |
| `--capacitor-tolerance PCT` | **Capacitor tolerance (±%)** | An override that can only loosen the grade: each part uses the larger of this percentage and its grade's tolerance. Blank: the grade's tolerance. A value the sourced table does not list uses it instead of the assumed 5% |
| `--stray-capacitance CAP` | **Stray capacitance per extra part** | The assumed stray across the second part of a pair, 0 to 10 pF (default 0.2 pF, blank in the wizard and web). An assumption: no source gives a pad-to-pad value for the footprint |

`--allow-sub-pf` (**Allow capacitors below 1 pF** in the wizard and web UI) also chooses parts
below 1 pF, all "tolerance not sourced" (the table lists no value below 1 pF). It applies to the
same outputs, needs an E-series, and is refused with the same options.

JSON gives each choice's `status` (`recommended`, `tolerance_not_sourced` or
`expert_override_required`) and `tolerance_basis` (`sourced` or `assumed`), and the rule in
`standard_match.policy` (`rule`, `capacitor_series`, `capacitor_grade`, `grade_tolerances`,
`tolerance_override_pct`, `assumed_tolerance_pct_when_not_sourced`, `stray_capacitance_f`,
`stray_capacitance_basis`, `min_parallel_improvement_pct_points`, `minimum_capacitance_f`,
`allow_sub_pf`). CSV gives the status and a one-line `RecommendationPolicy`. Standard values
are chosen for capacitors only; inductors keep their calculated values, with
[inductor suggestions](#inductor-suggestions) where a part qualifies.

### Example Output

From `uv run filter-calc lp bw pi 5GHz -n 3`, where the target is below 1 pF:

```text
C1 calculated 636.62 fF
  Use:            none (below 1 pF; see warning)
  Nearest single: 620.00 fF (-2.6%), for reference only
  Warning: Below 1 pF no part is chosen automatically. Choose one manually, or
           turn on "Allow capacitors below 1 pF" (--allow-sub-pf).
```

With `--allow-sub-pf` added, the same capacitor reads:

```text
C1 calculated 636.62 fF
  Use:            75.00 fF || 560.00 fF (-0.3%)
  Nearest single: 620.00 fF (-2.6%)
  Tolerance not sourced (a part is not in the sourced table): chosen by nominal
    value, ±5% assumed for it.
```

From `uv run filter-calc lp bw pi 146MHz -n 5`, a 2 m low-pass: the worst case of 13 pF
(±0.65 pF) is 1.12 pF from the target, and of 4.3 pF ∥ 9.1 pF (±0.25 and ±0.5 pF, plus the
0.2 pF stray) 0.88 pF, so the pair is chosen:

```text
C1 calculated 13.47 pF
  Use:            4.30 pF || 9.10 pF (-0.6%)
  Nearest single: 13.00 pF (-3.5%)
```

## ASCII Frequency Response Plots

Add `--plot` to draw the frequency response in the terminal. The table then ends with two
vertically stacked plots and a table of the frequencies at −3, −10, and −20 dB:

1. **Ideal Frequency Response (dB)**: the complete response on a logarithmic frequency axis,
   from 0 dB down to a bottom row labeled `≤-60` (lower values are drawn there), with the
   cutoff marked (fc) or the bandpass center (f₀). Bandpass simulates the circuit with
   lossless, exact-value parts: `Simulated Response, ideal parts (dB)`.
2. **Ideal Response Detail (0 to -6 dB)** (bandpass: Simulated Response Detail): the top few
   dB at twice the frequency resolution, to show ripple and the transition; BP also narrows
   the window to the passband. Chebyshev uses max(6, 2×ripple) dB; a completely flat passband
   skips it. LP/HP mark the −3 dB point under the axis, e.g. `▲ -3 dB at 10.9 MHz`.

The table under the plots lists where the response crosses each level: −3 dB is half power
(the cutoff for Butterworth and Bessel; beyond the ripple-band edge for Chebyshev), −10 dB
the start of significant attenuation, and −20 dB a strong attenuation reference. "N/A" means
the level is not reached within the sweep. For **Lowpass** and **Highpass** the table has one
`Frequency` column, found by bisecting the ideal response inside the bracket the plot grid
gives, so it is exact to the digits shown: `lp ch pi 10MHz -n 9 -r 0.01 --plot` reports the
−3 dB point as `10.9 MHz` (exactly 10.87 MHz).

For **Bandpass** the table has `Lower` and `Upper` columns, under a line naming the reference:
`Levels below are relative to the peak nearest the center (0.000 dB at 14.17 MHz).` A second
line says how many ranges are above −3 dB when there is more than one, and `The frequencies
below did not converge; treat them as approximate.` is printed when that happens. BP plots and
response-data exports share a bandwidth-relative sweep that includes the requested center and
both geometric band edges (for at least five points); exports are sampled curves, not
converged measurements. Narrow-band frequencies keep extra digits (in Hz). With `--fl`/`--fh`,
plot labels use the geometrically centered edges, which reproduce the entered edges to
floating-point precision.

### Export Response Data

`--plot-data json` (with metadata) or `--plot-data csv` prints only the response samples, for
example `uv run filter-calc lp bw pi 10MHz --plot-data json > response.json`.

## Inductor Suggestions

For every inductor the calculator looks for a buildable part of each kind, always in the same
order: toroid winding, air-core coil, chip inductor. Each kind keeps its own selection rules,
and a kind with no part for an inductor states the limit that failed. Toroid windings on HF
cores and chip inductors are offered:

| Kind | Offered | Reason shown when there is no part |
|---|---|---|
| Toroid winding | T25-6, T50-2, and T68-2, within each core's rated frequency range ([below](#toroid-winding-suggestions)) | "No suitable toroid core in the built-in list: …" naming the limit that failed (whole-turn inductance within the A_L tolerance, or winding fit), or above every core's range "No built-in toroid core is rated for 146 MHz. VHF toroids are not offered: the core maker publishes no self-resonance or winding-capacitance data, so the inductance near the band cannot be checked." |
| Air-core coil | No | "Air-core coils are not offered: no published self-capacitance model is validated for coils of a few spaced turns, so their self-resonance cannot be checked." |
| Chip inductor | 259 parts from Coilcraft 0603CS and Murata LQW18AN_00, LQW18AN_80 and LQW15AN_80, 10 nH to 100 nH, each with a guaranteed tolerance, minimum SRF and minimum Q ([below](#chip-inductor-suggestions)) | "No chip inductor qualifies: …" naming the limit that failed (the ±10% allowance once tolerance and SRF drift are counted, the ±5% SRF drift, or either) and the frequencies checked |

[component-data-sources.md](component-data-sources.md) records the evidence behind each
decision (its "Chip inductors", "VHF iron-powder toroids", "Air-core coils", and "Decisions"
sections); the packaged chip catalog is its "Recommended catalog" table.

### How much is shown

`--inductor-suggestions` (wizard and web **Inductor suggestions (table detail)**) sets how
much of the suggestions the table shows:

| Value | Wizard and web | Table shows |
|---|---|---|
| `best` (default) | Best, detailed | The part the build uses, else the first suggestion in kind order |
| `full` | Up to 3 per kind, detailed | Up to three of every kind, and why each kind without a part has none |
| `compact` | Best, one line | The best suggestion on one line |
| `none` | None | Nothing; suggestions are left out of every output, and the build simulation and the chosen-parts SPICE deck use the calculated inductances |

`full` and `compact` change only the table, so they are refused with `--quiet`, JSON, CSV,
SPICE, and `--plot-data` (`--inductor-suggestions full cannot be used with --format json`).
`best`, `full`, and `compact` resolve the same parts, so the build and every other document
are the same for each: JSON always lists up to three per kind and CSV the best. The list is never filled with parts that do not
qualify.

Each detailed suggestion ends with its error budget, for example `Error budget: -0.25%
nominal, ±4.99% tolerance, SRF drift not checked`, every term in percent of the target: the
part's nominal distance from the target, its ± manufacturing tolerance (for a toroid, the
core's ±5% A_L tolerance of the achieved inductance, restated against the target), and the
change of inductance from self-resonance, not checked for toroid windings. The terms add up
to the part's true worst case. A chip inductor, whose SRF is checked, adds a line with the
worst case they total and the ±10% allowance it meets. An inductor with no suggestion lists one
reason per kind, as from `uv run filter-calc lp bw pi 146MHz -n 5 -z 300`, whose 529 nH is
above the chip catalog:

```text
  L1 target: 529.15 nH at 146 MHz
  ────────────────────────────────────────────────
  No inductor suggestion qualifies:
  - No built-in toroid core is rated for 146 MHz. VHF toroids are not offered: the core
    maker publishes no self-resonance or winding-capacitance data, so the inductance
    near the band cannot be checked.
  - Air-core coils are not offered: no published self-capacitance model is validated for
    coils of a few spaced turns, so their self-resonance cannot be checked.
  - No chip inductor qualifies: every part in the built-in chip catalog (10.00 nH to
    100.00 nH) misses this inductance by more than ±10% once its tolerance and SRF drift
    are counted (checked from DC to 146 MHz).
```

The component table's footnote reads `Inductors: no standard values; see Inductor
Suggestions.` when the section shows a suggestion, else `…; use the calculated value.`
Bandpass resonators share one inductance and one block (`L1–L3 (all equal) target: …`). The
design frequency is the cutoff (lowpass, highpass) or the center frequency `f0` (bandpass).

In JSON each inductor carries `inductor_suggestions` (absent with `none`): `best` (`kind` and
`rank`, or `null`) and `kinds`, one entry per kind in order with its `suggestions` and
`reason_none`. Each suggestion gives `kind`, `rank`, `part_name`, `status`, `target_henries`,
`achieved_henries`, `tolerance_pct`, `srf_basis` (`not_checked` for toroids,
`guaranteed_minimum` for chip inductors), `srf_accuracy`, `error_budget` (with `worst_case_pct`
when the SRF is checked), `allowance_range_hz` (the frequencies where a chip inductor stays
within its allowances; `null` for toroids), `source`, the kind's own `build` details, and
`warnings`.

### Inductors in the build

`--build-inductors` (wizard and web **Inductors in the build**, a build field) sets what
`--sim-build` and the chosen-parts SPICE deck use for each inductor:

| Value | Wizard and web | Build uses |
|---|---|---|
| `auto` (default) | Auto | Each inductor's first suggestion in the order toroid, air coil, chip |
| `toroid`, `air-coil`, `chip` | Toroid windings, Air-core coils, Chip inductors | That kind's best suggestion |
| `calculated` | Calculated values | The calculated inductances; the suggestions stay visible |

It needs `--sim-build` or `--format spice` (`--build-inductors requires --sim-build or --format
spice`) and is refused with an exact SPICE deck, which uses no parts. An inductor with no
suggestion of the chosen kind is simulated at its calculated value and the build warnings say
why; with `uv run filter-calc lp bw pi 10MHz --sim-build --build-inductors chip`, whose 1.59 µH is
above the chip catalog: `L1: No chip inductor qualifies: every part in the built-in chip catalog
(10.00 nH to 100.00 nH) misses this inductance by more than ±10% once its tolerance and SRF
drift are counted (checked from DC to 10 MHz). The simulation uses the calculated value.` A kind
cannot be forced without
suggestions: `--inductor-suggestions none --build-inductors toroid` is refused with `There are
no inductor suggestions to build with when Inductor suggestions is None; the build uses the
calculated inductances`. `auto` and `calculated` are accepted with `none`.

### Toroid winding suggestions

A toroid core is suggested only when its records have primary-sourced core, frequency, and
winding-capacity data, which limits automatic suggestions to T25-6, T50-2, and T68-2. The core
must be rated for the design frequency, reach the inductance within its A_L tolerance using
whole turns, and fit the winding. From `uv run filter-calc lp bw pi 10MHz`:

```text
Inductor Suggestions
──────────────────────────────────────────────────
Toroid windings (iron-powder T-series):
Checked: rated frequency range, whole-turn inductance within A_L tolerance, wire fit.
Not checked: RF Q, core loss, SRF, saturation, heating, power handling. Measure before use.
% vs target: error from rounding to whole turns.
L range: the same turns across the core's ±5% A_L tolerance.

  L1 target: 1.59 µH at 10 MHz
  ────────────────────────────────────────────────
  1. Toroid winding T50-2  (mix 2, red/clear, 95 ppm/°C)
     18 turns of AWG 20   L: 1.59 µH (-0.25% vs target)
     L range (A_L ±5%): 1.51 µH – 1.67 µH
     Wire: 311 mm of AWG 20 (0.800 mm dia.)   DCR: 12.1 mΩ   Fit: single layer (datasheet)
     Q limit from wire DCR alone (ωL/DCR): 8,210 at 10 MHz. Real Q is lower.
     Size: 12.70 × 7.70 × 4.83 mm (OD × ID × H)   Source: Micrometals, Inc. datasheet
     Error budget: -0.25% nominal, ±4.99% tolerance, SRF drift not checked
```

`compact` prints one line for the best part, and one legend line replaces the detailed view's
`% vs target` and `L range` lines (from `uv run filter-calc lp bw pi 10MHz --inductor-suggestions compact`):

```text
% in parentheses: error vs target from rounding to whole turns.

  L1 target: 1.59 µH at 10 MHz
  1. Toroid T50-2    18 turns AWG 20   1.59 µH (-0.25%)   DCR 12.1 mΩ   Q limit (wire DCR): 8,210
```

When the build simulation uses a winding, its `Parts used:` line names the inductance, turns,
wire gauge, core, and wire length (bandpass lines use the table names Cp1, L1, Cs12, Ce_in,
Ce_out). For `uv run filter-calc bp bw top -f 10MHz -b 500kHz -n 3 --sim-build`:

```text
  L1:     820.80 nH, 12 turns of AWG 14 on T68-2 (277 mm wire)
```

The JSON substitution record gives `method: "suggested_inductor"` with `inductor_kind`,
`part_name`, `turns`, `wire_awg`, and `wire_length_mm`; they are `null` for capacitors and for
inductors where the calculated value is used (`calculated value used (no inductor suggestion
used)` or `(inductor suggestions not used)` in the table).

A winding is a suggestion, not an RF suitability claim: RF Q, core loss, SRF, saturation,
heating, and power handling are not checked, and `ωL/DCR` uses only the wire's DC resistance,
so it is an upper limit, not RF Q. A core outside its published frequency range is excluded.
Published winding tables decide the fit where they exist; a geometric estimate is labeled
`Fit: estimated from core size` and never adds an unverified legacy core. Measure the built
filter and consult the manufacturer data before applying power; see the
[caveats](caveats-and-known-issues.md#toroid-winding-suggestions).


### Chip inductor suggestions

A chip inductor is suggested only from the sourced catalog: Coilcraft 0603CS and Murata
LQW18AN_00, LQW18AN_80 and LQW15AN_80 wirewound parts from 10 nH to 100 nH, each with its
guaranteed inductance tolerance (2%, 3% or 5%), minimum self-resonant frequency (SRF) and
minimum Q, as listed in [component-data-sources.md](component-data-sources.md#recommended-catalog).
Each part is modelled as `L0` in parallel with a self-capacitance `C_self`, where
`L0 = L_m (1 − (f_m/SRF)²)` from its catalog value `L_m` at its test frequency `f_m`, and
`C_self = 1/((2π·SRF)²·L0)` from the minimum SRF (an upper bound at the catalog inductance,
because a real part's SRF is at or above the minimum; a part at the low end of its tolerance may
have a slightly larger one). Its inductance then drifts with frequency, `L(f) = L0/(1 − (f/SRF)²)`,
below its catalog value under `f_m` and above it over `f_m`.

**Check window.** A part is checked over the design's check window: a low-pass from DC to the
cutoff, a band-pass from DC to the upper −3 dB edge, and a high-pass from the cutoff to twice
the cutoff. It qualifies when, everywhere in the window:

- its drift at the minimum SRF stays within ±5% of the catalog value, and
- at both ends of its guaranteed tolerance, both window ends, and both SRF limits (the
  minimum, and no drift), its inductance stays within ±10% of the target. Tolerance and drift
  combine in henries, so a 5% part at 5% drift is 10.25% and fails. A part exactly at a limit
  is within it.

The checks always use the maker's guaranteed tolerance, even when a tighter inductor tolerance
is entered for the build. Qualifying parts rank by the smallest worst case, then by part
number; the minimum Q is shown and never used for ranking. The figures depend on this
parallel-LC model and on the maker's fixture measurements: on a board the SRF changes.

From `uv run filter-calc lp ch pi 146MHz -n 5 -r 0.1`:

```text
Chip inductors (wirewound; the maker's guaranteed tolerance and minimum SRF):
Checked from DC to 146 MHz: SRF drift within ±5% of the catalog value, and tolerance
plus drift within ±10% of the target.
Not checked: Q (the minimum is shown, not used), current rating, heating, power
handling, and the SRF once mounted on a board. Measure before use.
L at 146 MHz: the part's inductance there at its minimum SRF. Self-capacitance: the
upper bound from that SRF at the catalog inductance. Both come from the maker's fixture;
board mounting changes the SRF.

  L1 target: 74.74 nH at 146 MHz
  ────────────────────────────────────────────────
  1. Chip inductor LQW15AN75NG80D  Murata LQW15AN_80, 0402 (1005) package
     75.00 nH ±2% at 100 MHz   SRF min 2.4 GHz   Q min 25 at 200 MHz
     L at 146 MHz: 75.15 nH   Self-capacitance: 58.74 fF
     Within its allowances from DC to 532.7 MHz
     Source: Murata LQW15AN_80 reference specification, Spec No. JELF243A_0100K-01, p. 8
     Error budget: +0.35% nominal, ±2.01% tolerance, SRF drift -0.17% to +0.20%
     Worst case: -1.83% to +2.56% of the target (allowance ±10%)
```

The lines give the part number, maker, family and package; the catalog value with its
guaranteed tolerance and test frequency, the minimum SRF and the minimum Q; the inductance at
the top of the check window and the self-capacitance, both at the minimum SRF; the frequencies
at which the part stays within both allowances; the source (title, revision and page); and the
error budget. The budget's drift runs from the most negative to the most positive drift in the
window, including no drift, each taken at the tolerance end it adds to, so the worst case is
the budget's total; the printed range is rounded inward, so the part is within its allowances
everywhere in it. `compact` prints `1. Chip LQW15AN75NG80D (Murata)   75.15 nH at 146 MHz   ±2%
SRF min 2.4 GHz`.

**In the build.** The build simulation and the chosen-parts SPICE deck model each chip inductor
as `L0` with a fixed capacitor `CSELF_<inductor>` across it (`L1 self-capacitance` in readable
text), which together give the catalog value at the test frequency; the `Parts used:` line
reads `L1: 75.00 nH, chip inductor LQW15AN75NG80D, plus 58.74 fF self-capacitance`. Without an
entered inductor tolerance each chip inductor's tolerance cases use its own guaranteed
tolerance (`Tolerance cases: …, each chip inductor at its own tolerance (±2%).`); toroid
windings and calculated values keep ±10%. The self-capacitance stays fixed while a case moves
the inductance, so a case can fall slightly outside the part's guaranteed range: the cases are
stress cases of the model, not qualified values. Capacitor ESL, package and trace parasitics,
and each part's Q and loss (unless a Q is given) are not modelled. An entered inductor Q is
applied to the chip's inductance alone, so with its self-capacitance across it the Q at its
terminals is a little lower, more so near its SRF (the model limits say so), and the qualified
range says it is the lossless part model's.

**Qualified range.** The build states the frequencies where every chip inductor it uses stays
within its allowances: `Qualified range: DC to 532.7 MHz, where every chip inductor stays
within its allowances; results outside it are predicted with the parasitic model, not
qualified.` Every frequency a chosen-parts result reports is checked against it: a cutoff or
edge (and a band-pass center and bandwidth taken from it), the peak the −3 dB points are
measured from, the frequency of the peak gain, and any separate range above −3 dB. Any of them
outside the range is labelled (`-3 dB cutoff predicted with the parasitic model, not
qualified`), a spread row with such a case says so, and JSON lists them in
`outside_qualified_range` (each spread summary has the same flag); ideal values, the band-pass attenuation at 2×f₀ and 3×f₀ (ideal
lossless parts), and the response data are never labelled. A high-pass build's passband has no
upper edge, so it ends at the top of the qualified range (never below twice the cutoff), and
its peak and half-power threshold are taken only inside that range: `Passband = from the
requested cutoff up to 900 MHz, including both; a high-pass build takes its peak and half-power
threshold only where its chip inductors are qualified.` (`uv run filter-calc hp bw pi 125MHz -n
3 -z 19.8 --sim-build`). A cutoff crossing below the range is still reported, labelled. A build
whose inductors are toroid windings or calculated values has no qualified range, and its figures
use the whole sweep as before.
## Migrating from 2.x

Version 3.0.0 renames the toroid-only options to generic inductor-suggestion names, without
compatibility aliases, and removes `--sim-matched`. The renames change no number: HF designs keep
their inductor values and toroid picks, and only labels changed. (Capacitor choices change for a
separate reason, the [worst-case rule](#how-a-value-is-chosen).) Each old name maps to a new one:

| 2.x | 3.0.0 |
|---|---|
| `--sim-matched`, `shared/matched_simulation.py` | removed; use `--sim-build` |
| `--no-toroids` | `--inductor-suggestions none` (hides suggestions everywhere; build and chosen-parts SPICE use calculated inductances) |
| `--no-toroid-build` | `--build-inductors calculated` (suggestions stay visible; build and SPICE use calculated inductances) |
| `--toroid-full` / `--toroid-compact` | `--inductor-suggestions full` / `compact` (table detail only; JSON and CSV unaffected) |
| `BuildConfig.use_toroid_candidates` | `DesignRequest.build_inductors` |
| `RenderOptions.include_toroids`/`toroid_full`/`toroid_compact`, `OutputChoices.include_toroids` | `DesignRequest.inductor_suggestions`; `OutputChoices.inductor_detail` |
| `option_applicability.TOROID_DETAIL`/`TOROID_BUILD` | `INDUCTOR_DETAIL`/`BUILD_INDUCTORS` |
| Web `toroids`, `toroid_build`, `no_toroid_build`, `simulate_toroid_windings` | `inductor_suggestions`, `build_inductors` |
| Wizard `FilterState.toroid_detail` | `inductor_detail`, plus `build_inductors` |
| JSON `toroid_recommendations`, `resonator_toroid_recommendations`, `resonator_toroid_candidates` | per-inductor `inductor_suggestions` |
| Build JSON `toroid_candidate_screen_enabled`, `verified_toroid_candidate_used`, `verified_toroid_elements`, `uses_verified_toroid_candidates` | `build_inductor_choice`, `suggested_inductors_used`, `suggested_inductor_elements` |
| Method `verified_toroid_integer_turns`; status `candidate_screen_disabled`, `calculated_exact_value_toroid_selection_disabled` | method `suggested_inductor` with `inductor_kind`; status `suggestions_not_used` |

The table's "Toroid Winding Suggestions (iron-powder T-series)" section is now **Inductor
Suggestions**, CSV gains the `InductorKind`, `InductorPart`, `InductorSRFBasis` and
`InductorBudget*` columns before the `Toroid*` columns, and the
chosen-parts SPICE deck writes `part=T50-2` where it wrote `core=T50-2`. The Python API changes
are listed in the [changelog](project-changelog.md).
