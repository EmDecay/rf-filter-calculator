# Caveats & Known Issues

The calculator keeps three things apart: the ideal design (the calculated values), the chosen parts (standard capacitor values and suggested toroid windings), and simulations of either. None of those is a measurement of an assembled filter.

## Input and numeric limits

- The order (low-pass and high-pass: the number of inductors and capacitors) or the number of resonators (band-pass) is a whole number from 2 to 9. Chebyshev needs an odd order or number of resonators (3, 5, 7, or 9) for equal source and load impedance.
- Chebyshev ripple is finite and in `0 < ripple <= 3.0 dB` in the CLI, wizard, web UI, and public synthesis APIs.
- Frequency, bandwidth, impedance, Q, and component values must be positive finite numbers. Values whose formulas underflow or overflow IEEE-754 binary64 are rejected instead of producing zero, infinity, NaN, or a misleading component value.
- Part Q (`--inductor-q`, `--capacitor-q`, and bandpass `--qu`/`--ql`/`--qc`, with the same fields in the wizard and web UI) must be from 0.01 to 1e9; omit Q for a lossless part. The simulation source and load resistances (build simulation and SPICE) must be within 1e-6 to 1e6 times the design impedance. These bounds exclude only values no lumped filter contains; beyond them a single simulation could take minutes.
- Bandpass requires `bw < f0`. Give either the center and bandwidth or the lower and upper −3 dB edges, not both; the lower edge must be below the upper edge.
- The program has no arbitrary “RF maximum,” but lumped components, interconnects, and the built-in ideal models become inappropriate well before every numerically representable input does.

## Band-pass response check

Top-coupled band-pass design uses a bounded two-variable calibration to place both requested −3 dB edges. A separate dense circuit sweep, the **response check**, then checks:

- the lower and upper −3 dB edges around the center;
- the outermost −3 dB edges, and whether the response is above −3 dB in one range or in separate ranges;
- the passband shape compared with the ideal Butterworth, Chebyshev, or Bessel response;
- Chebyshev ripple; and
- points just outside the passband, at normalized deviations −2, −1.5, +1.5 and +2.

The table shows the result on its `Response Check:` line, and JSON carries `synthesis_validation` and `response_validation_status`. Matching −3 dB edges do not by themselves prove the complete response shape. Treat `Not confirmed; see warnings below` (`outside_validated_envelope` in JSON) as a direction to read the warnings and check the response yourself before building.

`Passed` (`validated`) does not cover rejection farther from the passband. Harmonic leakage through the top-coupled design can be much higher than the ideal response predicts. The `Attenuation at 2×f₀ … at 3×f₀` line reports the circuit at those frequencies for information only, with no acceptance limit; see [filter theory](filter-theory.md#top-coupled-rejection-away-from-the-passband).

The maintained acceptance study contains 128 cells at 1%, 2%, 5%, and 10% fractional bandwidth: 106 currently pass the response check, 17 are designed but marked not confirmed (`outside_validated_envelope`), and 5 known-unrealizable cells are rejected. Three of the rejected cells are 3 dB Chebyshev designs whose −3 dB edges cannot be placed (the error suggests a smaller ripple); two are 10% Bessel designs whose end coupling or resonator capacitors cannot be built. Some 3 dB Chebyshev cases are above −3 dB in separate ranges (for example, a ripple dip inside the band); matching the edges of the range around the center must not be mistaken for checking the whole response.

Above 10% fractional bandwidth the design method has not been tested: the −3 dB edges still match the request, but the response shape may differ from the ideal, and a warning says so. Above 40%, a coupled-resonator design becomes impractical, and the warning suggests a high-pass filter followed by a low-pass filter instead. There is no blanket "all designs up to 10% are valid" claim; read the response check of each result.

For Bessel bandpass, the lowpass-to-bandpass transformation does not preserve maximally flat group delay. Verify phase/group delay externally for phase-critical work.

## E-series selection is not tolerance

E12, E24, and E96 set how many standard values there are per decade. They do not declare the
tolerance of a part. Capacitor tolerances come from one sourced C0G series, Murata
GRM1885C1H…A01 (0603, 50 V), recorded with its sources in
[component-data-sources.md](component-data-sources.md):

| Value range | Standard grade (default) | Tight grade (`--capacitor-grade tight`) |
|---|---|---|
| 0.5–0.9 pF | ±0.1 pF | ±0.05 pF |
| 1–5 pF | ±0.25 pF | ±0.1 pF |
| 5.1–9.9 pF | ±0.5 pF | ±0.25 pF |
| 10–910 pF | ±5% | ±2% |
| 1–10 nF | ±5% | ±5% |

The sourced table lists 0.5–9.9 pF in 0.1 pF steps and the E24 values from 10 pF to 10 nF
(values with a current reference sheet; a refused request is only "not found"), so every
E12 and E24 value from 1 pF to 10 nF is covered, but only the E96 values with two significant
digits (such as 1.0, 1.1 and 75 pF).

Each capacitor gets one choice, by its worst case within tolerance:

- each candidate covers an interval from its nominal value minus its tolerance to its nominal
  value plus its tolerance, plus, for a pair, the assumed stray across its second part
  (`--stray-capacitance`, default 0.2 pF; an assumption, because no source gives a pad-to-pad
  value for the footprint);
- its score is the larger distance from the calculated value to either end of that interval;
- the best single part and the best pair are found by exhaustive search over the values the
  sourced table lists; the pair is chosen only when it scores at least 0.5 percentage points better;
- ties go to the single part, then to the pair with the smaller ratio, then to the lower
  value; the ratio between the two parts is limited to 10:1;
- `--capacitor-tolerance` can only loosen the grade: each part uses the larger of that
  percentage and its grade's tolerance;
- a value the sourced table does not list (most E96 values, and parts above 10 nF) keeps the
  nominal rule (the nearest single part within 1%, otherwise a pair at least 0.5 points
  closer), is labelled "tolerance not sourced" (JSON and CSV status `tolerance_not_sourced`; the
  CSV policy and the chosen-parts SPICE comment state the assumption), and in the build
  simulation each part not in the table uses an assumed ±5% (or the override) while a listed
  part of the same pair keeps its own tolerance; and
- below 1 pF no part is chosen automatically, unless `--allow-sub-pf` (**Allow capacitors below
  1 pF** in the wizard and web UI) is on. The sourced table lists no E-series value below 1 pF, so
  those choices are always "tolerance not sourced".

Without that option, a target below 1 pF keeps its calculated value, the row reads
`Use: none (below 1 pF; see warning)`, and the build simulation and chosen-parts SPICE deck use
the calculated value (JSON status `expert_override_required`, an exact fallback). JSON and CSV
record the rule, the grade, any override and the stray (`standard_match.policy`, CSV
`RecommendationPolicy`) and at most one choice per capacitor. Inductors are not E-series
matched.

Tolerances are at room temperature (1 MHz up to 1000 pF); the C0G temperature coefficient
(0 ± 30 ppm/°C) adds to them, and the lifecycle of each orderable part is not checked.

## Q and loss semantics

Bandpass `--qu` is the resonator Qu: the unloaded Q of each resonator, with inductor and capacitor losses together. `--ql` and `--qc` give the resonator inductor Q and resonator capacitor Q separately and combine as:

```text
1 / Qu = 1 / (inductor Q) + 1 / (capacitor Q)
```

The labels spell these out instead of writing QL and QC, because filter texts use QL for loaded Q. When only one of them is given, the other part is treated as lossless. The coupling and end capacitors stay lossless when `--qc` is used.

The historical `q_min = (f0 / bw) * q_safety` field is only a heuristic retained for compatibility. It is not a stability threshold and `--q-safety` is not a build-model control. Non-default `--q-safety` is accepted only in JSON so that its compatibility status is visible.

In the build simulation and the chosen-parts SPICE deck, each Q is modeled as a fixed series resistance that gives that Q at the frequency where the Q values apply: the cutoff or center frequency, or `--loss-reference-frequency`. The resistance is fixed across the sweep, so away from that frequency the modeled Q changes. `--loss-reference-frequency` without any Q option is rejected.

Cohn estimates can be seriously inaccurate for large loss. The **Insertion loss at f₀** block puts
each Cohn estimate next to a circuit simulation and notes when they differ by more than 0.5 dB;
agreement at that one frequency does not prove accuracy across the passband or on hardware. The
circuit simulation uses the calculated values, not the chosen parts, and one equivalent series
loss in each resonator inductor rather than separate inductor and capacitor Q. See [user-guide interpretation](user-guide.md#interpreting-response-measurements).

## Build simulation

`--sim-build` (**Simulate the built filter** in the wizard and web UI) uses the same named circuit as the SPICE export and keeps apart:

1. the ideal values (the calculated components);
2. the chosen parts (standard capacitor values and suggested toroid windings, or the calculated value where no part was chosen);
3. the fixed tolerance cases; and
4. optional extra random tolerance cases, repeatable for the same seed.

The fixed cases are nominal, all parts low, all parts high, and each part low and high alone. They show spread but do not guarantee the true worst case. Each capacitor varies by its own tolerance (its grade's, or the larger override; ±5% assumed where the tolerance is not sourced) and each inductor by `--inductor-tolerance` (default 10%). The extra random cases draw each part uniformly within its tolerance; they are not a Monte Carlo yield estimate or a probability model. The percentiles in the spread table come from only these cases.

A parallel pair also gets its assumed stray (`--stray-capacitance`, default 0.2 pF) as a fixed capacitor across the pair's terminals. It is the same in every case and is never varied, so it does not change the list of cases or the random draws of the real parts; a stray of 0 adds nothing. The chosen-parts SPICE deck contains the same element, named `CSTRAY_<part>`. The build's `Parts used:` list shows the stray on each pair; when no pair carries one (every pair lost, or the stray is 0) it adds a line stating the assumed stray, because the stray decides whether a pair can win.

The simulation reports transducer gain (Gt) and accepts separate simulation source and load resistances. With equal source and load, Gt in dB is the negative of the insertion loss, and the table says so. Those resistances change only the simulation; the component values are still designed for equal source and load impedance at the impedance you entered.

A −3 dB point outside the simulated frequency range is flagged and left out of the cutoff or edge figures; JSON lists each such case. The simulated frequency range is not adjustable (`--analysis-points` adds points, not range), so check such a design independently, for example with the SPICE deck.

Automatic refinement includes the requested band edges, peaks and dips, and the −3 dB
crossings. A case whose measurement did not converge stays in the case list, is marked "did not
converge; values approximate", and is left out of the spread figures. Convergence on
successively finer frequency points is not a mathematical bound on all frequencies. When the
response is above −3 dB in separate ranges, the cutoff or edges come from the range that holds
the peak (bandpass: the range around the peak nearest the center), not the outermost edges;
check the JSON region records and the lowest gain in passband.

The simulation leaves out layout and wiring (other than the assumed pair stray), package parasitics, coupling between parts, self-resonance (SRF), temperature drift, nonlinear effects, saturation, heating, and power handling.

## Toroid winding suggestions

The packaged data set retains 43 legacy records for inspection, but automatic suggestions are restricted to exact cores with primary-source core data: T25-6, T50-2, and T68-2. Material-frequency guidance has its own recorded source.

A core is suggested automatically only when:

- its published material guidance covers the design frequency;
- the whole-turn inductance is within that core's published A_L tolerance of the target; and
- a manufacturer winding limit is not exceeded when such a table exists.

When no core qualifies, the output says `No suitable core in the built-in list` and asks you to choose a core manually. Unsourced geometric winding capacity is labeled `Fit: estimated from core size`; it is not used as a hard exclusion. A suggestion count is therefore "up to three," and zero or one suggestion can be the correct result.

The `Q limit from wire DCR alone (ωL/DCR)` number uses only the wire's DC resistance, so it is an upper limit, not predicted or measured RF Q. RF Q, core loss, AC copper loss, SRF, saturation, heating, and power handling are not checked (`not_assessed` in JSON and CSV). The deprecated JSON alias `q_dc_upper_bound` is retained for compatibility and must be interpreted with the adjacent assessment metadata.

A_L is stored in nH/turn². The turn calculation is:

```text
Nideal = sqrt(1000 * L[uH] / A_L[nH/turn^2])
```

Measure the wound inductance and characterize Q/SRF under the intended operating conditions before committing to a build.

## Generic SPICE export

`--format spice` exports either the calculated values (`--spice-realization exact`, or `calculated`; lossless) or the same chosen parts used by the build simulation (`nominal-build`, or `chosen-parts`; the default). Chosen-parts decks can include series-loss resistors from the Q options, list each part in a `* part used:` comment, and add each pair's assumed stray as `CSTRAY_<part>` (with a `* stray:` comment); tolerance cases are not embedded in a deck, and making a deck never runs them. Band-pass decks keep the SPICE names `CT1`, `LT1`, `CK1`, `CIN`, `COUT` and map them to the table names in a `* names:` comment.

The deck's `.print ac vm(node)` is load-node voltage, not gain in dB. A comment gives the transducer-gain expression:

```text
Gt = 4 * Rs / Rl * |Vout / Vsource|^2
```

The project structurally and numerically tests generated decks but does not bundle or invoke an external SPICE engine. Run the deck in your chosen simulator and inspect its dialect-specific diagnostics.

The bandwidth/order-aware BP linear sweep resolves the requested passband; it does not qualify
every possible sharp resonance in a perturbed build. Edit the deck's `.ac` line in your simulator
for the particular measurement and remote rejection requirements. LP/HP decks use logarithmic
sweeps.

## Web UI limits

- The web UI is a local tool. It has no login, stores nothing, and is not hardened for hosting on the internet. Binding with `--host 0.0.0.0` exposes it to everyone on the network and turns off its check that requests are addressed to this computer.
- Browser submissions are accepted only from the web UI's own page. Scripts that send no browser origin headers, such as `curl`, can still use it.
- A calculation is cut off after 60 seconds ("Calculation stopped after 60 s"). The build simulation stops at its next case; a design calculation already running cannot be interrupted and finishes in the background, then is discarded. At most two calculations run at once and the rest wait their turn.
- Options that cannot apply to the chosen output are disabled on the page with the reason, and a hand-made request that sets one is refused with that reason, as the CLI refuses the flag. Two are ignored instead: the standard capacitor values with Values only or Raw units (a radio choice is always submitted), and the toroid box with Toroid windings None. Downloads judge each option again for their own document: **Allow capacitors below 1 pF** is ignored by the SPICE – calculated values and response-data downloads, and the response-data downloads leave out the resonator Q, while Components (CSV) and SPICE – calculated values refuse resonator Q that the result used.
- Without JavaScript nothing is disabled live and no stale-inputs notice appears; the server still refuses options that cannot apply, and downloads still use the inputs of the result shown.
- The response graph shows magnitude only, on the fixed frequency points of the response-data export; zoom with the text plot (`--plot`) or by plotting the downloaded data.

## Construction reality

Use C0G/NP0 or other suitable RF capacitors, short interconnects, a solid return path, and physical separation between input and output. Measure actual parts, simulate with package/layout parasitics when they matter, build a prototype, and verify it with a VNA or equivalent instrument.

The calculator does not design elliptic/notch, active, transmission-line, crystal, or SAW filters. It also does not design for unequal source and load impedances or impedance-transforming filters.
