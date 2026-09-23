# Caveats & Known Issues

The calculator separates a synthesis target, a selected nominal build, and simulated behavior. None of those is a measurement of an assembled filter.

## Input and numeric limits

- Reactive-element counts are integers from 2 through 9. Equal-termination Chebyshev designs require odd order: 3, 5, 7, or 9.
- Chebyshev ripple is finite and in `0 < ripple <= 3.0 dB` in the CLI, wizard, and public synthesis APIs.
- Frequency, bandwidth, impedance, Q, and component values must be positive finite numbers. Values whose formulas underflow or overflow IEEE-754 binary64 are rejected instead of producing zero, infinity, NaN, or a misleading component value.
- Component Q (`--inductor-q`, `--capacitor-q`, the wizard's resonator Q, and bandpass `--qu`/`--ql`/`--qc`) must be in `[0.01, 1e9]`; omit Q for a lossless part. Build-analysis and SPICE source/load resistances must be within 1e-6 to 1e6 times the design impedance. These bounds exclude only values no lumped filter contains; beyond them a single analysis could take minutes.
- Bandpass requires `bw < f0`. Use either center plus bandwidth or low/high edges, not both. Explicit low/high edges must be ordered.
- The program has no arbitrary “RF maximum,” but lumped components, interconnects, and the built-in ideal models become inappropriate well before every numerically representable input does.

## Bandpass validation boundary

Top-C bandpass synthesis uses a bounded two-variable calibration to place both requested −3 dB skirts. A separate dense sweep then checks:

- the center-connected lower and upper skirts;
- the outermost skirts and whether the −3 dB region is connected;
- passband error relative to the selected prototype;
- Chebyshev ripple; and
- near-stopband samples at normalized deviations −2, −1.5, +1.5 and +2.

Each result carries `synthesis_validation` and `response_validation_status`. A calibrated skirt pair does not by itself prove the complete response shape. Treat `outside_validated_envelope` as a direction to inspect the warnings and verify externally before building.

`validated` does not establish far-stopband rejection. Top-C harmonic leakage can exceed the
ideal prototype prediction substantially. The additional 2×/3× center circuit samples are
informational and have no application-specific rejection mask; see [filter theory](filter-theory.md#top-c-rejection-away-from-the-passband).

The maintained acceptance study contains 128 cells at 1%, 2%, 5%, and 10% fractional bandwidth: 106 currently meet every validation gate, 17 synthesize with explicit `outside_validated_envelope` status, and 5 known-unrealizable cells are rejected. In particular, some 3 dB Chebyshev cases develop disconnected −3 dB regions; calibration of the center-connected skirts must not be mistaken for validation of the outer envelope.

Designs above 10% fractional bandwidth are outside the studied calibration envelope even if both requested skirts can be placed. Above 40%, the tool also recommends considering a distributed or transmission-line design. There is no blanket “all designs <=10% are valid” claim—inspect the status of the individual result.

For Bessel bandpass, the lowpass-to-bandpass transformation does not preserve maximally flat group delay. Verify phase/group delay externally for phase-critical work.

## E-series selection is not tolerance

E12, E24, and E96 describe preferred-value density. They do not declare the tolerance of a part in hand. Manufacturing tolerance is a separate build-analysis input.

The default automatic capacitor policy is intentionally conservative:

- keep a single value when its absolute error is at most 1%;
- otherwise choose a two-capacitor parallel realization only when it improves absolute error by at least 0.5 percentage points;
- limit the ratio between the pair to 10:1, decided on exact nominal values so the same
  pair is accepted in every decade;
- when two pairs give exactly the same nominal value, choose the more balanced pair; and
- do not automatically select a physical capacitor below 1 pF.

For a sub-1 pF target, the calculated value remains visible and the nominal builder records an
explicit `expert_override_required`/exact fallback instead of silently recommending a dubious
part. Machine output records the policy and at most one selected realization; the sub-1 pF path
records that no part was selected. Inductors are not E-series matched.

## Q and loss semantics

Bandpass `--qu` means unloaded Q of the complete resonator. `--ql` and `--qc` describe inductor and tank-capacitor Q and combine as:

```text
1 / Qu = 1 / QL + 1 / QC
```

When only one of QL or QC is supplied, the omitted loss channel is treated as ideal. Coupling and end capacitors remain lossless when the synthesis-level `--qc` model is used.

The historical `q_min = (f0 / bw) * q_safety` field is only a heuristic retained for compatibility. It is not a stability threshold and `--q-safety` is not a build-model control. Non-default `--q-safety` is accepted only in JSON so that its compatibility status is visible.

Realized-build Q inputs are converted to a constant series resistance at the design frequency or explicit `--loss-reference-frequency`. That resistance is constant in the sweep, so the model is not constant-Q away from the reference. A loss-reference frequency without any Q input is rejected.

Cohn estimates can be seriously inaccurate for large loss. The center-frequency comparison
flags disagreement with the equivalent-loss circuit; agreement at that one frequency is not
full-passband or hardware validation. The comparison uses exact components, not the selected
nominal build, and a single equivalent resonator-loss channel rather than the separate
QL/tank-QC model. See [user-guide interpretation](user-guide.md#interpreting-response-measurements).

## Realized-build analysis

`--sim-build` uses the authoritative named circuit and distinguishes:

1. calculated exact values;
2. selected nominal physical parts;
3. deterministic tolerance cases; and
4. optional repeatable uniform-bounds samples.

The deterministic set contains nominal, coherent-low, coherent-high, and one-part-low/high cases for every physical element. It is useful for screening but is not an exhaustive mathematical worst case. Seeded samples are not Monte Carlo yield or a probability model. Percentiles are order statistics of only the generated cases.

The internal solver reports transducer power gain and supports independently specified finite source/load resistances. Those resistances change evaluation only; synthesis still assumes equal terminations at the selected design impedance.

Grid-boundary-censored skirts are flagged and omitted from relevant summary statistics. Extend or independently simulate the sweep before interpreting a censored edge.

Automatic response refinement includes the requested boundaries, extrema and evaluated
crossings. Cases that exhaust its budget remain visible as unresolved and are excluded from
summary statistics. Convergence on successively finer meshes is not a mathematical bound on
all frequencies. For disconnected bands, bandwidth refers to the reported selected local-peak
region, not the outer envelope; inspect the region records and worst requested-passband gain.

The model omits layout and package parasitics, interconnect coupling, component self-resonance, temperature dependence, nonlinear voltage/current effects, saturation, thermal rise, and power behavior.

## Toroid candidate screen

The packaged data set retains 43 legacy records for inspection, but automatic selection is restricted to exact cores with primary-source core data: T25-6, T50-2, and T68-2. Material-frequency guidance has its own recorded source.

A core appears automatically only when:

- its published material guidance covers the design frequency;
- rounded integer-turn error is no larger than that core's published A_L tolerance; and
- a manufacturer winding limit is not exceeded when such a table exists.

Unsourced geometric winding capacity is labeled `estimated`; it is not used as a hard exclusion. A candidate count is therefore “up to three,” and zero or one candidate can be the correct result.

The reported `omega L / Rdc` number is a wire-only reactance/DCR ceiling. It is not predicted or measured RF Q. RF Q, core loss, AC copper loss, SRF, saturation, temperature rise, and power handling are reported as `not_assessed`. The deprecated JSON alias `q_dc_upper_bound` is retained for compatibility and must be interpreted with the adjacent assessment metadata.

A_L is stored in nH/turn². The turn calculation is:

```text
Nideal = sqrt(1000 * L[uH] / A_L[nH/turn^2])
```

Measure the wound inductance and characterize Q/SRF under the intended operating conditions before committing to a build.

## Generic SPICE export

`--format spice` exports either calculated exact values or the same selected nominal physical branches used by build analysis. Nominal decks can include explicit series-loss resistors; tolerance cases are not embedded in a deck.

The deck's `.print ac vm(node)` is load-node voltage, not gain in dB. A comment gives the transducer-gain expression:

```text
Gt = 4 * Rs / Rl * |Vout / Vsource|^2
```

The project structurally and numerically tests generated decks but does not bundle or invoke an external SPICE engine. Run the deck in your chosen simulator and inspect its dialect-specific diagnostics.

The bandwidth/order-aware BP linear sweep resolves the requested passband; it does not qualify
every possible sharp resonance in a perturbed build. Extend or refine it for the particular
measurement and remote rejection requirements. LP/HP decks use logarithmic sweeps.

## Construction reality

Use C0G/NP0 or other suitable RF capacitors, short interconnects, a solid return path, and physical separation between input and output. Measure actual parts, simulate with package/layout parasitics when they matter, build a prototype, and verify it with a VNA or equivalent instrument.

The calculator does not implement elliptic/notch, active, transmission-line, crystal, or SAW filters. It also does not synthesize unequal source/load terminations or impedance-transforming filters.
