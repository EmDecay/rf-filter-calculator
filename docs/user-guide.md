# User Guide

Complete reference for all commands, options, and features.

## Commands Overview

| Command | Aliases | Description |
|---------|---------|-------------|
| `lowpass` | `lp` | Low-pass filter (Pi or T topology) |
| `highpass` | `hp` | High-pass filter (Pi or T topology) |
| `bandpass` | `bp` | Coupled-resonator band-pass filter |
| `wizard` | `w` | Interactive terminal wizard (also the default with no arguments) |
| `web` | - | Browser interface on this computer (needs the optional `web` dependencies) |

`filter-calc --version` prints the installed version, and `filter-calc <command> --help` lists
every option for that command.

---

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
| `-n, --components` | 3 | Number of components, 2-9; Chebyshev needs an odd number. Anything else, including a non-whole number, is refused with `Number of components must be from 2 to 9` (exit status 1) |
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
| `--explain` | - | Print a short description of the filter type and exit |
| `--no-toroids` | - | Leave out the suggested toroid windings from all outputs |
| `--toroid-compact` | - | Table output: the best toroid suggestion for each inductor on one line |
| `--toroid-full` | - | Table output: up to three toroid suggestions per inductor (default: the best one) |
| `--sim-build` | - | Build simulation: simulate the filter with the chosen parts, part losses (Q), and tolerance cases |
| `--sim-matched` | - | Deprecated; use `--sim-build` |

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

# Finer E96 standard capacitor values
uv run filter-calc lp bw pi 10MHz -e E96

# Export frequency response data
uv run filter-calc lp bw pi 10MHz --plot-data csv > response.csv

# Simulate the built filter with part losses (Q) and component tolerances
uv run filter-calc lp bw pi 10MHz --sim-build \
  --inductor-q 100 --capacitor-q 500 \
  --capacitor-tolerance 5 --inductor-tolerance 10 --format json
```

### Build Simulation and SPICE Controls

These controls are shared by lowpass, highpass, and bandpass commands. The build simulation
uses the chosen parts: the standard capacitor values plus the suggested toroid windings.

| Option | Meaning |
|--------|---------|
| `--sim-build` | Simulate the ideal values and the chosen parts, at nominal values and across tolerance cases (all parts low, all high, each part low and high alone). Table or JSON output only |
| `--capacitor-tolerance PCT` (alias `--cap-tolerance`) | Capacitor tolerance in ± percent, 0 to under 100 (default 5) |
| `--inductor-tolerance PCT` (alias `--ind-tolerance`) | Inductor tolerance in ± percent, 0 to under 100 (default 10) |
| `--inductor-q Q`, `--capacitor-q Q` | Part losses (Q), 0.01 to 1e9, for `--sim-build` and the chosen-parts SPICE deck. Each Q becomes a fixed series resistance at the frequency where the Q values apply. Omit for lossless parts |
| `--source-resistance`, `--load-resistance` | Simulation source and load resistance (1e-6 to 1e6 times `-z`). Component values are still designed for equal source and load impedance |
| `--loss-reference-frequency` | Frequency at which the Q values apply (default: cutoff or center frequency); needs a Q option |
| `--sample-count N` (alias `--samples`), `--seed S` | Extra random tolerance cases, 0 to 10000, each part drawn uniformly within its tolerance; the same seed repeats the same cases. Not a production-yield estimate |
| `--analysis-points N` | Frequency points in the `--sim-build` sweep, 51–5001 (default 601); measurements are refined between points automatically |
| `--no-toroid-build` | In `--sim-build` and the chosen-parts SPICE deck, use the calculated inductances instead of the suggested whole-turn toroid windings |
| `--format spice --spice-realization exact` (or `calculated`) | SPICE deck with the calculated values, without losses |
| `--format spice --spice-realization nominal-build` (or `chosen-parts`) | SPICE deck with the chosen parts and any Q losses (the default) |

The build simulation is a simulation, not a measurement, and the tolerance cases do not
guarantee the true worst case.

### Interpreting response measurements

Build measurements evaluate the exact requested band boundaries and refine interior extrema
and −3 dB crossings. `--analysis-points` sets the initial frequency points, not the total
number of circuit evaluations. The [refinement rules](../filter_lib/shared/response_refinement.py)
compares successive meshes to 0.001 dB and 0.00001 times requested bandwidth (BP) or cutoff
(LP/HP), with at most four passes. Crossing brackets are narrowed further, to 0.0000001 times
that frequency scale. These tolerances describe numerical convergence, not hardware accuracy
or a proof that no narrower feature exists between evaluated frequencies.
High-order or strongly perturbed cases can require more circuit evaluations and take longer;
increasing the initial frequency points or the number of extra random tolerance cases increases
that cost.

Every ideal-value, chosen-parts, and tolerance-case record in JSON includes
`measurement_converged` and `response_evaluations`. A case whose measurement did not converge
stays in the case list but is left out of the spread figures; the table says "did not
converge; values approximate", and JSON `unresolved_cases` and `omitted_cases` count the
exclusions. A −3 dB point outside the simulated frequency range is `null`, with
`edge_at_simulation_grid_boundary: true`, and is left out of the edge figures. Increasing the
point count does not widen the simulated frequency range.

BP bandwidth belongs to the range above −3 dB around the peak nearest the requested center.
`reference_peak_frequency_hz`, `reference_peak_gain_db`, and `half_power_threshold_db` identify
that reference peak; it can differ from the overall `peak_transducer_gain_db`, and the table
then says "−3 dB measured from the … peak at …". `half_power_regions` lists every frequency range
above that level; `selected_region_index` is zero-based, and `center_in_selected_region` says
whether the requested center lies in the selected range. When there are separate ranges, the
table says so and the spread figures use the selected range. Check these cases before relying
on the spread figures.

The build simulation's −3 dB level is half power, 3.0102999566 dB below the reference peak. The
plot tables use exactly 3.0 dB. For LP/HP, "lowest gain in passband" covers the simulated part
of the passband, not DC or infinite frequency.

---

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

---

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
−3 dB edges (`--fl <lower_edge> --fh <upper_edge>`), not both.

When `--fl` and `--fh` are used, the calculator derives the design center from the
geometric mean `f₀ = √(f_low × f_high)`. JSON `requested_parameters` and the build-simulation
`target` block preserve the parsed edge values exactly and mark the edge-frequency input mode.
Top-level calculated edges and plot labels are reconstructed from center/bandwidth and agree
with the request to floating-point precision.

### Options

| Option | Default | Description |
|--------|---------|-------------|
| `--type` | - | Response type, as a flag instead of the positional argument |
| `-c, --coupling` | - | Coupling `top` (alias `t`), as a flag instead of the positional argument |
| `-f, --frequency, --freq` | - | Center frequency |
| `-b, --bandwidth` | - | Bandwidth between the −3 dB edges, for every response type including Chebyshev |
| `--fl` | - | Lower −3 dB edge; use with `--fh` instead of `-f` and `-b` |
| `--fh` | - | Upper −3 dB edge; use with `--fl` instead of `-f` and `-b` |
| `-n, --resonators` | 3 | Number of resonators, 2-9; Chebyshev needs an odd number. Anything else is refused with `Number of resonators must be from 2 to 9` |
| `-z, --impedance` | 50 | Source and load impedance in ohms |
| `-r, --ripple` | 0.5 | Chebyshev ripple in dB, `0 < r <= 3.0` |
| `-e, --eseries` | E24 | Standard capacitor values to choose from (E12, E24, E96) |
| `--no-match` | - | Show only calculated capacitor values |
| `--allow-sub-pf` | - | Also choose standard values for capacitors below 1 pF |
| `--raw` | - | Unrounded values in farads and henries (scientific notation) |
| `-q, --quiet` | - | Print only the component values, one per line |
| `--format` | table | Output format: `table`, `json`, `csv`, `spice` |
| `--plot` | - | Add a text plot of the frequency response to the table |
| `--plot-data` | - | Print only the frequency response, as `json` or `csv` |
| `--explain` | - | Print a short description of the filter type and exit |
| `--no-toroids` | - | Leave out the suggested toroid windings from all outputs |
| `--toroid-compact` | - | Table output: the best toroid suggestion on one line |
| `--toroid-full` | - | Table output: up to three toroid suggestions |
| `--qu` | - | Resonator Qu: unloaded Q of each resonator, inductor and capacitor losses together (0.01 to 1e9). Adds a loss estimate and sets the resonator losses for `--sim-build` and the chosen-parts SPICE deck. Estimates at Qu = 100 and 250 are always shown |
| `--ql`, `--qc` | - | Inductor and resonator-capacitor Q at the center frequency (each 0.01 to 1e9), instead of `--qu`; combined as `1/Qu = 1/QL + 1/QC` |
| `--resonator-impedance` (alias `--tank-impedance`) | `-z` | Resonator (L–C tank) impedance `sqrt(L/C)`; it can differ from the source and load impedance |
| `--resonator-inductance` (alias `--tank-inductance`) | - | Inductance of every resonator, e.g. `1.2uH`; cannot be combined with `--resonator-impedance` |
| `--sim-build` | - | Build simulation (see [Build Simulation and SPICE Controls](#build-simulation-and-spice-controls)) |
| `--sim-matched` | - | Deprecated; use `--sim-build` |

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

The calculator places each Top-C design's −3 dB edges where requested and prints a
**Response Check** line (`response_validation_status` in JSON): `Passed (simulated circuit
matches the requested response)` or `Not confirmed; see warnings below`. The verified range
goes up to 10% fractional bandwidth, but some designs within it are still not confirmed and
some combinations cannot be built; check each result.

The response check covers the −3 dB edges, the passband shape, and points just outside the
passband. Farther out, Top-C rejection can differ from the ideal (e.g. Butterworth) response
and is not checked.
The `Attenuation at 2×f₀ … at 3×f₀` line (`harmonic_response` in JSON) reports the lossless
circuit at twice and three times the requested center, without an acceptance limit.

The **Added loss at f₀** block compares two numbers for each resonator Qu (inductor and capacitor
losses together): the Cohn estimate, a small-loss approximation, and a circuit simulation of the
calculated parts with one equivalent series loss in each resonator inductor. When they differ by
more than 0.5 dB the table adds `(estimate off by more than 0.5 dB; use the simulated value)`,
and JSON `loss_estimate_validation` says `poor_approximation_at_center`. This is a reporting
rule, not a reason to reject the design; agreement at the center does not prove accuracy across
the passband or on hardware. Separate inductor and capacitor Q and the chosen parts can give a
different loss; use `--sim-build` for those.
Q keys in `il_estimates` retain enough precision to distinguish a user value from the standard
examples; parse them as numbers rather than assuming a fixed number of displayed digits.

---

## Interactive Wizard (Textual TUI)

Running `uv run filter-calc` with no arguments starts the wizard for guided filter design.

### Design Flow

The wizard guides you through four screens. A selected text plot is rendered in Results; it is
not a separate screen. The wizard and the web UI offer the same options with the same labels,
defaults, and order. Fields start at the CLI defaults; a blank frequency field uses the value
its label names (for example `blank = 10MHz`). Invalid values are reported on the field to fix.

#### 1. Welcome

Under *Choose a filter*, pick **Low-Pass**, **High-Pass**, or **Band-Pass** and press Enter.

#### 2. Filter design (one screen per category)

- **Low-pass and high-pass:** *Response and topology*: Response (Butterworth, Chebyshev,
  Bessel), Topology (Pi (shunt first) or T (series first); low-pass defaults to Pi, high-pass
  to T), and passband ripple in dB, shown only for Chebyshev. *Frequency and size*: cutoff
  frequency (the label says −3 dB point or ripple-band edge to match the response), number of
  components (2-9), and impedance, equal source and load (`50`).
- **Band-pass:** *Response and coupling*: Response, Coupling (Top-C, the only option), and
  ripple for Chebyshev. *Passband*: *Specify the band by* **Center and width** (`14.175MHz`,
  `350kHz`) or **Band edges** (lower and upper −3 dB edges, `14MHz` and `14.35MHz`, the same as
  `--fl`/`--fh`), with a fractional bandwidth note shown as you type; number of resonators
  (2-9) and impedance. *Resonators and losses (optional)*: resonator impedance `sqrt(L/C)` or
  resonator inductance, not both; and **Resonator Qu**, or **Inductor QL** and **Capacitor QC**
  (`--qu`, `--ql`, `--qc`). Qu, QL, and QC are disabled, with the reason, when the format
  chosen on the next screen cannot show them (Values only and CSV).

#### 3. Output options

- *Format*: Table (default), Values only (`-q`), JSON, or CSV.
- *Standard capacitor values*: E12, E24 (default), E96, or None (`--no-match`), plus **Allow
  capacitors below 1 pF** (`--allow-sub-pf`; needs E12, E24, or E96).
- *Toroid windings (table detail)*: see [below](#toroid-winding-suggestions).
- **Text plot in the table** (`--plot`, off by default) and **Raw units (F, H)** (`--raw`).

*Response data file*: None, or a JSON or CSV response file (`--plot-data`), saved when you export
the results. It is the ideal response, so it leaves out Qu, QL, and QC.

*Build simulation (optional)*: tick **Simulate the built filter** (`--sim-build`) to show its
fields, pre-filled with the CLI defaults (a blank field takes that default): capacitor and
inductor tolerance (±%), inductor Q and capacitor Q, **Frequency at which the Q values apply**
(`--loss-reference-frequency`; blank = the cutoff or center frequency), simulation source and
load resistance, extra random tolerance cases, random seed, and frequency points. **Simulate
inductors as the suggested toroid windings** is ticked by default; untick it for
`--no-toroid-build`.

An option that cannot apply to the chosen format is disabled, with a one-line reason under it,
and the result is calculated as if it were not set, the same as leaving out the CLI flag. For
example, Values only disables the standard capacitor values, the text plot, the toroid detail,
and the build simulation. The rule is the one the CLI enforces. Enter moves through the
controls in the order shown, skipping disabled ones; Space ticks a box. Select **Show results**
to calculate.

#### 4. Results

Shows the same output the CLI prints for these settings. **Design another** starts over, and
**Export** offers *Save as* Text (as shown), JSON (full design), or CSV (components) plus
**Save**, which also writes the selected response-data file. Files are saved in the folder shown
on the screen. If a file cannot be written, or the folder the wizard was started from no longer
exists, the wizard says so and keeps running.

Saved JSON and CSV files use each disabled option's visible value where that file can show it,
like the web UI's downloads: with Values only and None, the JSON file is `--format json
--no-match`; with Values only and the build ticked, the JSON file includes the build, simulated
when you save it ("Preparing the JSON file…"; a problem with the build fields is reported then).
CSV is disabled, with the reason shown, when the result includes the build or resonator Q.

### Keyboard Reference

| Key | Action |
|-----|--------|
| ↑↓ | Navigate between options/fields |
| Tab | Move to next input field |
| Shift+Tab | Move to previous field |
| Enter | Select / move to the next control / Continue |
| Space | Toggle checkbox |
| Escape | Go back to previous screen (quits from Welcome) |
| Q | Quit (Results screen) |
| Ctrl+C | Exit wizard |

Frequency and impedance fields accept the same formats as the CLI (see [Input Formats](#input-formats)).

---

## Web UI

The web UI is a third way to use the same calculator. It needs the optional extra:

```bash
uv sync --extra web
uv run filter-calc web [--host <address>] [--port <port>]
```

The server listens on `127.0.0.1:8765` unless told otherwise and prints its address. It has no
authentication and is meant for use on one computer; binding to any other address prints a
warning. Only the calculator's own page can submit designs: a browser request from another site
is refused with HTTP 403 (scripts such as `curl` are not affected). Requests must also be
addressed to this server: `127.0.0.1`, `localhost`, `[::1]`, or the address given to `--host`.
Binding to every interface (`--host 0.0.0.0` or `::`) skips that address check, because the
server cannot know which names other machines will use; only do that on a network you trust.

### What the page shows

- The result panel shows exactly the text `filter-calc` prints for the same settings:
  tables, standard capacitor values, toroid winding suggestions, the text plot when **Text
  plot in the table** is ticked, and the build-simulation block. Band-pass design warnings
  appear once: inside the table for Table format, or in a notice above the output for the
  other formats.
- **Response graph** adds an SVG chart beneath the text. It draws the same frequency and
  magnitude data as `--plot-data` (ideal transfer function for LP/HP, simulated circuit for
  BP), with a dashed −3 dB guide.
- Invalid input shows the same message the CLI gives (fields that exist only on the web
  have their own plain messages), and the form keeps what you typed. The page
  also works without JavaScript; submissions then reload the whole page.

### Downloads

Each button returns a file whose contents are byte-identical to the CLI command shown:

| Button | CLI equivalent |
|---|---|
| Design (JSON) | `--format json` (includes the build simulation when **Simulate the built filter** is ticked) |
| Components (CSV) | `--format csv` |
| SPICE – calculated values | `--format spice --spice-realization exact` |
| SPICE – chosen parts | `--format spice` (uses the build section's Q and source/load values when it is ticked; needs an E-series) |
| Response data (JSON) / (CSV) | `--plot-data json` / `--plot-data csv` |

Downloads use the inputs of the result shown, not the form as it is now. If you edit the form
after a result, the page says "Inputs changed — select Design filter to update the result and
downloads." until you select **Design filter** or undo the edit.

A disabled option's visible value is used by each download that can show it, judged by the same
rule as the page. With Values only and None, Design (JSON) is `--format json --no-match`; with
Values only or CSV and the build ticked, Design (JSON) and SPICE – chosen parts include it; with
CSV and Qu, Design (JSON) and SPICE – chosen parts use `--qu`. Raw units, the text plot, and
the toroid detail never reach a download. **Allow capacitors below 1 pF** is used by the Design,
Components, and SPICE – chosen parts downloads; SPICE – calculated values and the response data
ignore it.

Components (CSV) and SPICE – calculated values refuse resonator Q (Qu, QL, QC) that the result
shown used, as the CLI does. The response data downloads leave Qu, QL, and QC out, so they equal
`--plot-data` without them (the wizard's response data file does the same).

`POST /api/design/<category>` with the same form fields returns the `--format json`
document directly, for scripts.

### Form fields and CLI flags

Field names mirror the CLI flags, so a design can move between the two.

| Form field (name) | CLI flag | Notes |
|---|---|---|
| Response (`filter_type`) | positional type or `--type` | Aliases such as `bw`, `ch`, `bs` are accepted |
| Topology (`topology`) | positional or `-T` | Lowpass and highpass |
| Coupling (`coupling`) | positional `top` | Bandpass; Top-C is the only coupling |
| Cutoff / Center frequency (`frequency`) | positional or `-f` | Same unit suffixes as the CLI |
| Bandwidth (−3 dB) (`bandwidth`) | `-b` | Bandpass, when the band is given by center and width |
| Lower / Upper edge (−3 dB) (`f_low`, `f_high`) | `--fl`, `--fh` | Bandpass, when `band_spec` is `edges` |
| Number of components / resonators (`components`, `resonators`) | `-n` | |
| Impedance (`impedance`) | `-z` | |
| Passband ripple (`ripple`) | `-r` | Shown and used for Chebyshev only |
| Resonator impedance / inductance (`resonator_impedance`, `resonator_inductance`) | `--resonator-impedance`, `--resonator-inductance` | Bandpass |
| Resonator Qu, Inductor QL, Capacitor QC (`qu`, `ql`, `qc`) | `--qu`, `--ql`, `--qc` | Bandpass; disabled with Values only and CSV |
| Format (`output_format`: table, quiet, json, csv) | `--format`; Values only is `-q` | |
| Standard capacitor values (`eseries`) | `-e`; **None** is `--no-match` | |
| Allow capacitors below 1 pF (`allow_sub_pf`) | `--allow-sub-pf` | Needs E12, E24, or E96 |
| Toroid windings (table detail) (`toroids`: best, full, compact, none) | default, `--toroid-full`, `--toroid-compact`, `--no-toroids` | Best, detailed (default) / Up to 3, detailed / Best, one line / None; the middle two need Table |
| Text plot in the table (`plot`) | `--plot` | Table only |
| Raw units (F, H) (`raw`) | `--raw` | Table or Values only |
| Response graph (`svg_plot`) | none | Web only |
| Simulate the built filter (`sim_build`) | `--sim-build` | Needs table or JSON output and an E-series |
| Build fields (`build_capacitor_tolerance_pct`, `build_inductor_tolerance_pct`, `build_inductor_q`, `build_capacitor_q`, `build_reference_frequency`, `build_source_resistance`, `build_load_resistance`, `build_sample_count`, `build_seed`, `build_grid_points`) | `--capacitor-tolerance`, `--inductor-tolerance`, `--inductor-q`, `--capacitor-q`, `--loss-reference-frequency`, `--source-resistance`, `--load-resistance`, `--sample-count`, `--seed`, `--analysis-points` | Labeled Capacitor/Inductor tolerance (±%), Inductor/Capacitor Q, Frequency at which the Q values apply, Simulation source/load resistance (Ω), Extra random tolerance cases, Random seed, Frequency points. Pre-filled with the CLI defaults; a blank takes the default. Read only when the build box is ticked. A nonzero seed needs extra random cases |
| Simulate inductors as the suggested toroid windings (`toroid_build`) | unticked is `--no-toroid-build` | Ticked by default; disabled when Toroid windings is None. The 2.2.0 field `no_toroid_build=on` is still accepted |

An option that cannot apply to the chosen output is disabled, with the reason under it, by the
same rule the wizard uses; a disabled control is not submitted, which matches leaving out the
CLI flag. A hand-made request that sets one anyway is refused with that reason, except two
that are ignored: the standard capacitor values with Values only or Raw units (a radio choice is
always submitted), and the toroid box with None (the CLI also accepts `--no-toroid-build` with
`--no-toroids`). The deprecated `--sim-matched` and `--q-safety` have no web fields.

### Long calculations

A request waits up to 60 seconds. When that runs out, the page reports
"Calculation stopped after 60 s. Try fewer extra random tolerance cases or frequency points."
and a running build simulation stops at its next case. The design calculation itself cannot be interrupted,
but the accepted input ranges bound its run time. At most two calculations run at once; further requests wait their turn.

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
| kΩ / MΩ | `1kohm`, `1M` | 1000 Ω, 1,000,000 Ω |

Suffixes are case-insensitive, so `m` also means mega: `50mohm` is 50 MΩ, not 50 mΩ.
**Validation**: Impedance must be positive. Zero or negative values raise an error.

---

## Output Formats

### Table (default)

Human-readable format with ASCII diagrams, component tables, standard capacitor values, and
toroid winding suggestions.

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
With `--sim-build`, the schema keeps the requested target, the ideal-value response
(`simulated`), the chosen parts (`nominal_build`, including any calculated values used in
place of a part), the effective loss model, the tolerance cases (`tolerance_analysis`), the
simulation source and load resistance (`evaluation`), and the limitations separate. JSON key
names did not change when the readable text was reworded. LP/HP measurements expose one
cutoff; bandpass exposes two −3 dB edges, center, and bandwidth.

### CSV

```bash
uv run filter-calc lp bw pi 10MHz --format csv
```

Spreadsheet-compatible, RFC-style quoted CSV. Every row has the same number of columns,
including when warning text contains commas. The standard-value columns give the one choice
made for each capacitor and the selection rule (`RecommendationPolicy`); the toroid columns
give the best winding suggestion and repeat that RF Q, SRF, and power handling are not
checked.

### SPICE

```bash
# Calculated, lossless values
uv run filter-calc lp bw pi 10MHz --format spice --spice-realization exact

# Chosen parts, with part losses (Q) as series resistance
uv run filter-calc lp bw pi 10MHz --format spice \
  --spice-realization nominal-build --inductor-q 100 --capacitor-q 500
```

The deck is generic SPICE. It prints load voltage and comments the exact transducer-gain
relationship; it does not claim the voltage trace itself is transducer gain. Comment lines
say which values the deck uses (`* values: calculated, lossless (exact)` or
`* values: chosen parts (nominal-build)`), list each part used in a chosen-parts deck
(`* part used: …`), and, for bandpass, map the SPICE element names to the table names
(`* names: CT1=Cp1 LT1=L1 … CK1=Cs12 … CIN=Ce_in COUT=Ce_out`; a parallel pair is shown as
`CT2A+CT2B=Cp2`). As in the build simulation block, each warning appears once with its parts
(`* warning: C1, C2: Below 1 pF …`), and the toroid limitation only when a toroid was used.
BP decks use a bounded linear sweep sized to provide at least 128 intervals per resonator per
requested bandwidth; LP/HP retain 200 points per decade. This avoids skipping narrow bands.
The sweep covers the build-simulation frequency range, not arbitrary remote rejection
requirements. `--analysis-points` is a build-simulation control and is not accepted for
SPICE-only output. Running the deck is up to your own SPICE simulator; none is bundled.

---

## Standard Capacitor Values (E-Series)

The calculator chooses standard capacitor values for each calculated capacitor.

### Available Series

| Series | Standard Values per Decade |
|--------|-----------------------------|
| E12 | 12 |
| E24 | 24 |
| E96 | 96 |
| None (`--no-match`) | Show calculated values only |

An E-series sets how many standard values there are per decade; it does not set the part
tolerance. For example, an E24-valued capacitor may be sold in several tolerances. Enter the
actual tolerance separately for the build simulation (`--capacitor-tolerance`).

### How a value is chosen

Each capacitor gets one choice, shown on the `Use:` line:

- **Single part**: used when it is within 1% of the calculated value.
- **Two in parallel**: used only when the pair is at least 0.5 percentage points closer than
  the best single part. `Nearest single:` then shows that single part for comparison.
- **Below 1 pF**: no part is chosen automatically. The row reads
  `Use: none (below 1 pF; see warning)`, the nearest single value is shown for reference only,
  and the warning says: `Below 1 pF no part is chosen automatically. Choose one manually, or
  turn on "Allow capacitors below 1 pF" (--allow-sub-pf).`

`--allow-sub-pf` (**Allow capacitors below 1 pF** in the wizard and web UI) applies the same
single/parallel rule below 1 pF too. It applies to the table, CSV, JSON, `--sim-build`, and the
chosen-parts (`nominal-build`) SPICE deck, and is reported in JSON as
`standard_match.policy.allow_sub_pf` and in CSV as `RecommendationPolicy`. It needs an E-series,
so it is refused with `--no-match`, `--quiet`, `--raw` (unless `--sim-build` is used),
`--explain`, `--plot-data`, `--spice-realization exact`, and the deprecated `--sim-matched`.

**Note**: Standard values are chosen for capacitors only. Inductors are shown at their
calculated values; they are usually wound by hand (see the toroid winding suggestions below).

### Example Output

From `uv run filter-calc lp bw pi 10MHz -n 5`:

```text
C1 calculated 196.73 pF
  Use:            47.00 pF || 150.00 pF (+0.1%)
  Nearest single: 200.00 pF (+1.7%)
```

From `uv run filter-calc lp bw pi 5GHz -n 3`, where the target is below 1 pF:

```text
C1 calculated 636.62 fF
  Use:            none (below 1 pF; see warning)
  Nearest single: 620.00 fF (-2.6%), for reference only
  Warning: Below 1 pF no part is chosen automatically. Choose one manually, or
           turn on "Allow capacitors below 1 pF" (--allow-sub-pf).
```

With `--allow-sub-pf` added, the same capacitor reads
`Use:            75.00 fF || 560.00 fF (-0.3%)`.

---

## ASCII Frequency Response Plots

Add `--plot` to draw the frequency response in the terminal. The table then ends with
two plots and a table of the frequencies at −3, −10, and −20 dB.

### Full-Range and Detail Plots

Two vertically stacked ASCII plots appear automatically:

1. **Ideal Frequency Response (dB)**: the complete response over the sweep range. Bandpass
   simulates the circuit with lossless, exact-value parts: `Simulated Response, ideal parts (dB)`
   - Logarithmic frequency axis
   - Automatic range from 0 dB; the bottom row is labeled `≤-60` because lower values are
     drawn there
   - Cutoff frequency marked with (fc), bandpass center with (f₀)
   - Works for all filter types

2. **Ideal Response Detail (0 to -6 dB)** (bandpass: Simulated Response Detail): the top few dB
   - 2× frequency resolution for smoother curves; BP also narrows the horizontal window to the
     passband neighborhood
   - Helps visualize ripple and transition sharpness
   - Skipped if the passband is completely flat
   - For Chebyshev: adaptive range = max(6, 2×ripple) dB
   - LP/HP mark the −3 dB point under the axis, e.g. `▲ -3 dB at 10.9 MHz`

### Frequencies at −3 / −10 / −20 dB

The table under the plots lists the frequencies where the response crosses each level:
- **-3 dB**: half power (the cutoff for Butterworth and Bessel; beyond the ripple-band edge
  for Chebyshev)
- **-10 dB**: start of significant attenuation
- **-20 dB**: strong attenuation reference

For **Lowpass** and **Highpass** the table has one `Frequency` column. The plot grid only
brackets each crossing; the printed frequency comes from bisecting the ideal response inside
that bracket, so it is exact to the digits shown. For example,
`lp ch pi 10MHz -n 9 -r 0.01 --plot` reports the −3 dB point as `10.9 MHz`; the exact value is
10.87 MHz.

For **Bandpass** the table has `Lower` and `Upper` columns. Above it, a line names the reference:
`Levels below are relative to the peak nearest the center (0.000 dB at 14.17 MHz).` When the
response is above −3 dB in more than one range, a second line says how many, and when the
crossings did not converge the line `The frequencies below did not converge; treat them as
approximate.` is printed.

BP plots and response-data exports share a bandwidth-relative sweep; the former minimum
0.1-decade half-span no longer stretches very narrow bands. For grids with at least five
points, the requested center and both geometric band edges are included when inside the
window, including even point counts. Response exports retain the requested sample count and
are sampled curves, not converged measurement reports. CLI and wizard threshold tables refine
peaks and crossings. Narrow-band frequencies keep extra digits (in Hz) so the two edges remain
distinguishable.

If the bandpass filter was specified with `--fl` / `--fh`, the requested values remain in
machine-readable metadata. Plot labels use the calculator's geometrically centered edge values,
which reproduce the entered edges to floating-point precision.

Shows "N/A" when a threshold is not reached within the sweep frequency range.

### Export Response Data

`--plot-data json` (with metadata) or `--plot-data csv` prints only the response samples, for
example `uv run filter-calc lp bw pi 10MHz --plot-data json > response.json`.

## Toroid Winding Suggestions

For every inductor, the calculator may suggest a **toroid winding**. Automatic suggestions
are limited to T25-6, T50-2, and T68-2 because those records have primary-sourced core,
frequency, and winding-capacity data. A suggested core must be rated for the design
frequency, reach the inductance within its A_L tolerance using whole turns, and fit the
winding. When no core qualifies, the section says `No suitable core in the built-in list`
and asks you to choose a core manually.

Default table output shows the best suggestion. `--toroid-full` shows up to three, JSON
includes up to three, and CSV carries the best one. "Up to" matters: the calculator does not
fill the list with cores that do not qualify.

### Default text output (best core)

From `uv run filter-calc lp bw pi 10MHz`:

```text
Toroid Winding Suggestions (iron-powder T-series)
──────────────────────────────────────────────────
Checked: rated frequency range, whole-turn inductance within A_L tolerance, wire fit.
Not checked: RF Q, core loss, SRF, saturation, heating, power handling. Measure before use.
% vs target: error from rounding to whole turns.
L range: the same turns across the core's ±5% A_L tolerance.

  L1 target: 1.59 µH at 10 MHz
  ────────────────────────────────────────────────
  1. T50-2  (mix 2, red/clear, 95 ppm/°C)
     18 turns of AWG 20   L: 1.59 µH (-0.25% vs target)
     L range (A_L ±5%): 1.51 µH – 1.67 µH
     Wire: 311 mm of AWG 20 (0.800 mm dia.)   DCR: 12.1 mΩ   Fit: single layer (datasheet)
     Q limit from wire DCR alone (ωL/DCR): 8,210 at 10 MHz. Real Q is lower.
     Size: 12.70 × 7.70 × 4.83 mm (OD × ID × H)   Source: Micrometals, Inc. datasheet
```

`--toroid-full` shows up to three cores in this form. `--toroid-compact` prints one line for the
best core, and one legend line replaces the full view's `% vs target` and `L range` lines
(from `uv run filter-calc lp bw pi 10MHz --toroid-compact`):

```text
% in parentheses: error vs target from rounding to whole turns.

  L1 target: 1.59 µH at 10 MHz
  1. T50-2    18 turns AWG 20   1.59 µH (-0.25%)   DCR 12.1 mΩ   Q limit (wire DCR): 8,210
```

`--toroid-compact` and `--toroid-full` cannot be combined. `--no-toroids` skips the suggestions
in every output; contradictory combinations such as `--no-toroids --toroid-full` are usage
errors rather than silently ignored controls.

In the wizard and the web UI, **Toroid windings (table detail)** offers **Best, detailed** (the
default), **Up to 3, detailed** (`--toroid-full`), **Best, one line** (`--toroid-compact`), and
**None** (`--no-toroids`). Apart from None, the choice applies to table output only; JSON always
includes up to three suggestions and CSV the best one.

### Toroid windings in the build simulation

When the build simulation (`--sim-build`, or **Simulate the built filter** in the wizard and
web UI) uses a suggested winding, its `Parts used:` line names the inductance, turns, wire
gauge, core, and wire length. Bandpass lines use the table names (Cp1, L1, Cs12, Ce_in, Ce_out).
For `uv run filter-calc bp bw top -f 10MHz -b 500kHz -n 3 --sim-build`:

```text
  L1:     820.80 nH, 12 turns of AWG 14 on T68-2 (277 mm wire)
```

The JSON substitution record carries the same values as `wire_awg` and `wire_length_mm`.
Both are `null` for capacitors and for inductors where the calculated value is used
(`calculated value used (no suitable toroid)` or `(toroid windings off)` in the table).

### Bandpass and design frequency

All N resonators share the same inductance, so bandpass prints one suggestion block
(`L1–L3 (all equal) target: …`). JSON keeps the core's source and the checks it passed. The
design frequency is the cutoff for lowpass and highpass and the center frequency `f0` for
bandpass.

### Important caveats

- **No RF suitability claim**: RF Q, core loss, SRF, saturation, heating, and power handling
  are not checked. `ωL/DCR` uses only the wire's DC resistance, so it is an upper limit, not
  RF Q.
- **The rated frequency range is a hard limit**: a core outside its published range is
  excluded.
- **Published winding tables are authoritative** where available; geometric estimates are
  labeled (`Fit: estimated from core size`) and are not used to add unverified legacy records
  to automatic selection.
- Measure the built filter and consult the manufacturer data before applying power.
