# Sample Output

These examples reflect version 3.0.0 (see the [changelog](project-changelog.md)). Long
machine-readable payloads are shown as selected valid fragments; run the command to obtain the
complete schema.

## Low-Pass Table

```bash
uv run filter-calc lp bw pi 10MHz --inductor-suggestions none
```

```text
Butterworth Pi Low-Pass Filter
==================================================
Cutoff Frequency:    10 MHz
Impedance Z₀:        50 Ω
Order:               3
==================================================

Topology:
  IN ───┬───┤ L1 ├───┬─── OUT
        │            │       
       ===          ===      
       C1           C2       
        │            │       
       GND          GND      

                 Component Values                 
┌────────────────────────┬────────────────────────┐
│       Capacitors       │       Inductors        │
├────────────────────────┼────────────────────────┤
│ C1: 318.31 pF          │ L1: 1.59 µH            │
│ C2: 318.31 pF          │                        │
└────────────────────────┴────────────────────────┘
Inductors: no standard values; use the calculated value.

E24 Standard Capacitor Values
──────────────────────────────────────────────────
E24 = 24 standard values per decade; it does not set the part tolerance.
Each capacitor gets the single part or parallel pair whose worst case (each part at
either end of its tolerance, plus the assumed stray across a pair) is closest to
the calculated value; a pair only if it is at least 0.5 percentage points closer.
Tolerance (standard grade, Murata GRM1885C1H…A01): ±0.1 pF (0.5–0.9 pF),
±0.25 pF (1–5 pF), ±0.5 pF (5.1–9.9 pF), ±5% (10–10000 pF).
Stray: 0.2 pF across the second part of a pair (an assumption).

C1 calculated 318.31 pF
  Use:            47.00 pF || 270.00 pF (-0.4%)
  Nearest single: 330.00 pF (+3.7%)
C2 calculated 318.31 pF
  Use:            47.00 pF || 270.00 pF (-0.4%)
  Nearest single: 330.00 pF (+3.7%)
```

`Use:` is the one choice made for each capacitor, by its worst case within tolerance: the
single part or parallel pair whose interval (each part at either end of its tolerance, plus the
assumed stray across a pair) ends closest to the calculated value. A pair is used only when it
is at least 0.5 percentage points better than the best single part; `Nearest single:` then
shows the nearest single part for comparison. A value the sourced table does not list is
chosen by the nominal rule and marked "Tolerance not sourced". Below 1 pF no part is chosen
automatically: the row reads `Use: none (below 1 pF; see warning)`, the nearest single value is
shown for reference only, and a warning names the `--allow-sub-pf` option (**Allow capacitors
below 1 pF** in the wizard and web UI), which lets the calculator choose those values too.
Without `--inductor-suggestions none`, the table ends with the
[inductor suggestions](#inductor-suggestions) and its footnote points to them.

## High-Pass Table

```bash
uv run filter-calc hp bw t 10MHz --inductor-suggestions none
```

```text
Butterworth T High-Pass Filter
==================================================
Cutoff Frequency:    10 MHz
Impedance Z₀:        50 Ω
Order:               3
==================================================

Topology:
  IN ───┤C1├───┬───┤C2├─── OUT
               │              
              ===             
              L1              
               │              
              GND             

                 Component Values                 
┌────────────────────────┬────────────────────────┐
│       Capacitors       │       Inductors        │
├────────────────────────┼────────────────────────┤
│ C1: 318.31 pF          │ L1: 397.89 nH          │
│ C2: 318.31 pF          │                        │
└────────────────────────┴────────────────────────┘
Inductors: no standard values; use the calculated value.

E24 Standard Capacitor Values
──────────────────────────────────────────────────
E24 = 24 standard values per decade; it does not set the part tolerance.
Each capacitor gets the single part or parallel pair whose worst case (each part at
either end of its tolerance, plus the assumed stray across a pair) is closest to
the calculated value; a pair only if it is at least 0.5 percentage points closer.
Tolerance (standard grade, Murata GRM1885C1H…A01): ±0.1 pF (0.5–0.9 pF),
±0.25 pF (1–5 pF), ±0.5 pF (5.1–9.9 pF), ±5% (10–10000 pF).
Stray: 0.2 pF across the second part of a pair (an assumption).

C1 calculated 318.31 pF
  Use:            47.00 pF || 270.00 pF (-0.4%)
  Nearest single: 330.00 pF (+3.7%)
C2 calculated 318.31 pF
  Use:            47.00 pF || 270.00 pF (-0.4%)
  Nearest single: 330.00 pF (+3.7%)
```

## Band-Pass Table

```bash
uv run filter-calc bp bw top -f 14.175MHz -b 350kHz --inductor-suggestions none --no-match
```

```text
Butterworth Coupled-Resonator Band-Pass Filter
==================================================
Center Frequency f₀: 14.175 MHz
Lower -3 dB Edge fₗ: 14.00108 MHz
Upper -3 dB Edge fₕ: 14.35108 MHz
-3 dB Bandwidth:     350 kHz
Fractional BW:       2.47%
Impedance Z₀:        50 Ω
Resonators:          3
Coupling:            Top-coupled (series capacitors)
Response Check:      Passed (simulated circuit matches the requested response)
==================================================

Insertion loss at f₀ for resonator Qu (inductor and capacitor losses together):
  Qu=100:  Cohn estimate 7.04 dB, circuit simulation 6.87 dB
  Qu=250:  Cohn estimate 2.82 dB, circuit simulation 2.81 dB
Response check covers the -3 dB edges, passband shape, and points just outside the passband.
Farther out, top-coupled rejection can differ from the ideal Butterworth response and is not checked.
  Attenuation at 2×f₀: 83.36 dB; at 3×f₀: 84.96 dB (ideal lossless parts)

Topology:
      Ce_in     Cs12           Cs23      Ce_out     
  IN ──┤├──┬──────┤├──────┬──────┤├──────┬──┤├── OUT
           │              │              │          
        ┌──┴──┐        ┌──┴──┐        ┌──┴──┐       
        │     │        │     │        │     │       
        Cp1  L1        Cp2  L2        Cp3  L3       
        │     │        │     │        │     │       
        └──┬──┘        └──┬──┘        └──┬──┘       
           │              │              │          
          GND            GND            GND         

                 Component Values                 
┌────────────────────────┬────────────────────────┐
│    Tank Capacitors     │       Inductors        │
├────────────────────────┼────────────────────────┤
│ Cp1: 185.84 pF         │ L1: 561.45 nH          │
│ Cp2: 216.75 pF         │ L2: 561.45 nH          │
│ Cp3: 185.84 pF         │ L3: 561.45 nH          │
└────────────────────────┴────────────────────────┘
Inductors: no standard values; use the calculated value.

┌────────────────────────┐
│  Coupling Capacitors   │
├────────────────────────┤
│ Ce_in: 35.71 pF        │
│ Cs12: 3.92 pF          │
│ Cs23: 3.92 pF          │
│ Ce_out: 35.71 pF       │
└────────────────────────┘

External Q (input):  40.55 (set by Ce_in)
External Q (output): 40.55 (set by Ce_out)
```

Band-pass values are calibrated against a simulation of the circuit, and every result carries its
own response check (`response_validation_status` in JSON). The attenuation line reports the
lossless circuit at harmonics of f₀; it is not part of the response check.

## Strict JSON

```bash
uv run filter-calc lp bw pi 10MHz --format json
```

A selected capacitor fragment is:

```json
{
  "filter_type": "butterworth",
  "cutoff_frequency_hz": 10000000.0,
  "impedance_ohms": 50.0,
  "order": 3,
  "topology": "pi",
  "components": {
    "capacitors": [
      {
        "name": "C1",
        "value_farads": 3.183098861837907e-10,
        "standard_match": {
          "status": "recommended",
          "tolerance_basis": "sourced",
          "selected": {
            "kind": "parallel",
            "components": [
              {
                "value_farads": 4.7e-11
              },
              {
                "value_farads": 2.7e-10
              }
            ],
            "value_farads": 3.17e-10,
            "error_pct": -0.41151288120356627
          },
          "reason": "parallel_worst_case_materially_better",
          "warnings": []
        }
      }
    ]
  }
}
```

and the inductor's suggestions, with the toroid's `build` details (core, winding, wire, and
what was and was not checked) left out here:

```json
{
  "name": "L1",
  "value_henries": 1.5915494309189518e-06,
  "inductor_suggestions": {
    "best": {
      "kind": "toroid",
      "rank": 1
    },
    "kinds": [
      {
        "kind": "toroid",
        "suggestions": [
          {
            "kind": "toroid",
            "rank": 1,
            "part_name": "T50-2",
            "status": "screened_candidate",
            "target_henries": 1.5915494309189518e-06,
            "achieved_henries": 1.5875999999999992e-06,
            "tolerance_pct": 5.0,
            "srf_basis": "not_checked",
            "srf_accuracy": null,
            "error_budget": {
              "nominal_mismatch_pct": -0.2481500632168454,
              "tolerance_pct": 4.987592496839158,
              "srf_drift_pct": null
            },
            "source": {
              "publisher": "Micrometals, Inc.",
              "title": "T50-2 DataSheet, revision 20190524",
              "url": "https://datasheets.micrometals.com/T50-2-DataSheet.pdf"
            },
            "warnings": [
              "Not checked: RF Q, core loss, SRF, saturation, heating, power handling. Measure before use."
            ]
          }
        ],
        "reason_none": null
      },
      {
        "kind": "air-coil",
        "suggestions": [],
        "reason_none": "Air-core coils are not offered: no published self-capacitance model is validated for coils of a few spaced turns, so their self-resonance cannot be checked."
      },
      {
        "kind": "chip",
        "suggestions": [],
        "reason_none": "Chip inductor suggestions are not available in this version."
      }
    ]
  }
}
```

The complete result includes all components and the selection-rule fields
(`standard_match.policy`: the rule, the capacitor series and grade with its tolerances, any
override, the assumed stray, and `allow_sub_pf`). JSON serialization is strict: `NaN` and
infinities are never emitted. With `--inductor-suggestions none` the `inductor_suggestions` key
is absent.

For explicit band-pass edges, `requested_parameters` and the `--sim-build` `target` block
retain the parsed requested values exactly and mark
`"frequency_specification": "edge_frequencies"`.

## Rectangular CSV

```bash
uv run filter-calc lp bw pi 10MHz --format csv
```

```csv
Component,Value,Unit,NearestStdValue,NearestStdUnit,NearestStdErrorPct,ParallelStdValues,ParallelStdErrorPct,Eseries,RecommendedStdKind,RecommendedStdValues,RecommendedStdErrorPct,RecommendationStatus,RecommendationReason,RecommendationWarnings,RecommendationPolicy,InductorKind,InductorPart,InductorSRFBasis,InductorBudgetNominalPct,InductorBudgetTolerancePct,InductorBudgetSRFDriftLowPct,InductorBudgetSRFDriftHighPct,ToroidCore,ToroidMix,ToroidTurns,ToroidAWG,ToroidActualL_uH,ToroidErrorPct,ToroidWireLength_mm,ToroidDCR_mohm,ToroidWireDCRReactanceRatioCeiling,ToroidTempCoeff_ppm,ToroidCandidateStatus,ToroidProvenanceStatus,ToroidCoreSourceURL,ToroidFrequencySourceURL,ToroidMechanicalStatus,ToroidMechanicalSourceURL,ToroidRFQStatus,ToroidSRFStatus,ToroidPowerStatus,ToroidWarnings
C1,318.31,pF,330.00,pF,3.7,47.00 pF || 270.00 pF,-0.4,E24,parallel,47.00 pF || 270.00 pF,-0.4,recommended,parallel_worst_case_materially_better,,worst-case;grade=standard;grade-tolerance=0.5-0.9pF:0.1pF/1-5pF:0.25pF/5.1-9.9pF:0.5pF/10-10000pF:5%;part-tolerance=larger-of-grade-and-override;tolerance-override=none;not-sourced-tolerance=5%(assumed);stray=0.2pF(assumed);parallel-improvement>=0.5pp;minimum-cap=1pF,,,,,,,,,,,,,,,,,,,,,,,,,,,
C2,318.31,pF,330.00,pF,3.7,47.00 pF || 270.00 pF,-0.4,E24,parallel,47.00 pF || 270.00 pF,-0.4,recommended,parallel_worst_case_materially_better,,worst-case;grade=standard;grade-tolerance=0.5-0.9pF:0.1pF/1-5pF:0.25pF/5.1-9.9pF:0.5pF/10-10000pF:5%;part-tolerance=larger-of-grade-and-override;tolerance-override=none;not-sourced-tolerance=5%(assumed);stray=0.2pF(assumed);parallel-improvement>=0.5pp;minimum-cap=1pF,,,,,,,,,,,,,,,,,,,,,,,,,,,
L1,1.59,µH,,,,,,,,,,,,,,toroid,T50-2,not_checked,-0.25,4.99,,,T50-2,2,18,20,1.5876,-0.25,310.8,12.15,8210,95,screened_candidate,primary_verified,https://datasheets.micrometals.com/T50-2-DataSheet.pdf,https://www.amidoncorp.com/2ipt/,manufacturer_single_layer,https://datasheets.micrometals.com/T50-2-DataSheet.pdf,not_assessed,not_assessed,not_assessed,"Not checked: RF Q, core loss, SRF, saturation, heating, power handling. Measure before use."
```

All rows have the same column count. Warning fields are CSV-quoted when necessary.
The inductor columns describe each inductor's best suggestion: its kind, part, SRF basis and
error budget (each term in percent of the target; the drift is blank when the SRF is not
checked), then the `Toroid*` details; with `--inductor-suggestions none` they are left out.

## Inductor Suggestions

```bash
uv run filter-calc lp bw pi 10MHz --inductor-suggestions compact
```

The suggestion section of the output is:

```text
Inductor Suggestions
──────────────────────────────────────────────────
Toroid windings (iron-powder T-series):
Checked: rated frequency range, whole-turn inductance within A_L tolerance, wire fit.
Not checked: RF Q, core loss, SRF, saturation, heating, power handling. Measure before use.
% in parentheses: error vs target from rounding to whole turns.

  L1 target: 1.59 µH at 10 MHz
  1. Toroid T50-2    18 turns AWG 20   1.59 µH (-0.25%)   DCR 12.1 mΩ   Q limit (wire DCR): 8,210
```

At 146 MHz no inductor kind has a part, and each kind says why
(`uv run filter-calc lp bw pi 146MHz -n 3 --inductor-suggestions compact`):

```text
Inductor Suggestions
──────────────────────────────────────────────────

  L1 target: 109.01 nH at 146 MHz
  No inductor suggestion qualifies:
  - No built-in toroid core is rated for 146 MHz. VHF toroids are not offered: the core
    maker publishes no self-resonance or winding-capacitance data, so the inductance
    near the band cannot be checked.
  - Air-core coils are not offered: no published self-capacitance model is validated for
    coils of a few spaced turns, so their self-resonance cannot be checked.
  - Chip inductor suggestions are not available in this version.
```

A toroid suggestion is checked only for the core's rated frequency range, whole-turn inductance
within the A_L tolerance, and wire fit; automatic suggestions are limited to the primary-sourced
T25-6, T50-2, and T68-2 records. RF Q, core loss, SRF, saturation, heating, and power handling
are not checked; measure the winding before use. The detailed views (`best`, the default, and
`full`) end each suggestion with its error budget; see the
[user guide](user-guide.md#inductor-suggestions).

## Build Simulation

```bash
uv run filter-calc lp bw pi 10MHz -n 5 --sim-build
```

The build-simulation block that follows the table and the inductor suggestions is:

```text
Build Simulation (chosen parts; simulated, not measured)
──────────────────────────────────────────────────
Simulated with a 50 Ω source and a 50 Ω load; gains are transducer gain (Gt).
Source and load are equal, so each gain in dB is the negative of the insertion loss.
Part losses (Q): none; all parts are lossless.
Passband = up to the requested cutoff, including it.
Ideal values:  -3 dB cutoff 10 MHz
               peak gain 0.00 dB, lowest gain in passband -3.01 dB
Chosen parts:  -3 dB cutoff 10.04 MHz
               peak gain 0.00 dB, lowest gain in passband -2.93 dB
Parts used:
  C1: 47.00 pF || 150.00 pF (E24), plus 200.00 fF stray (assumed)
  L1: 1.28 µH, 15 turns of AWG 16 on T68-2 (328 mm wire)
  C2: 75.00 pF || 560.00 pF (E24), plus 200.00 fF stray (assumed)
  L2: 1.28 µH, 15 turns of AWG 16 on T68-2 (328 mm wire)
  C3: 47.00 pF || 150.00 pF (E24), plus 200.00 fF stray (assumed)
Tolerance cases: each capacitor at its standard-grade tolerance, L ±10%.
  19 cases: nominal, all low, all high,
  and each part low and high alone.
Spread across these cases (min / 5th percentile / median / 95th percentile / max):
  Peak gain:               0.000 / 0.000 / 0.000 / 0.000 / 0.000 dB
  Lowest gain in passband: -4.896 / -3.744 / -2.927 / -2.274 / -1.531 dB
  -3 dB cutoff:            9.298 / 9.698 / 10.04 / 10.4 / 10.92 MHz
Build warnings:
  - L1, L2: Not checked: RF Q, core loss, SRF, saturation, heating, power handling. Measure
    before use.
Model limits:
  - Chosen parts are simulated at their nominal values, without lead or package parasitics.
  - Each parallel pair has an assumed 0.2 pF stray across it, the same in every tolerance case;
    it is an assumption, not a measured value.
  - Toroid windings were checked only for frequency range, whole-turn inductance, and wire fit.
  - The tolerance cases do not guarantee the true worst case.
  - The simulation leaves out layout and wiring (other than the assumed pair stray),
    self-resonance (SRF), temperature drift, nonlinear effects, and power handling.
```

With `--format json`, the complete component JSON gains these top-level blocks:

```bash
uv run filter-calc lp bw pi 10MHz --sim-build \
  --inductor-q 100 --capacitor-q 500 \
  --sample-count 20 --seed 73 --format json > build.json
```

```json
{
  "target": {
    "category": "lowpass",
    "response_type": "butterworth",
    "order": 3,
    "cutoff_frequency_hz": 10000000.0,
    "design_impedance_ohm": 50.0,
    "equal_termination_synthesis": true
  },
  "simulated": {
    "realization": "calculated_exact_values"
  },
  "nominal_build": {
    "realization": "selected_nominal_physical_parts",
    "substitutions": [
      {
        "logical_name": "L1",
        "kind": "L",
        "method": "suggested_inductor",
        "status": "screened_candidate",
        "inductor_kind": "toroid",
        "part_name": "T50-2",
        "turns": 18,
        "wire_awg": 20
      }
    ]
  },
  "tolerance_analysis": {
    "method": "deterministic_corners_plus_seeded_uniform_screening",
    "tolerance_source": "each_part",
    "capacitor_grade": "standard",
    "capacitor_tolerance_override_pct": null,
    "inductor_tolerance_pct": 10.0,
    "sample_count": 20,
    "seed": 73,
    "grid_points": 601
  },
  "evaluation": {
    "source_resistance_ohm": 50.0,
    "load_resistance_ohm": 50.0,
    "gain_metric": "transducer_power_gain_db",
    "unequal_loads_change_evaluation_not_synthesis": true
  },
  "build_model": {
    "build_inductor_choice": "auto",
    "suggested_inductors_used": true,
    "suggested_inductor_elements": [
      "L1"
    ]
  }
}
```

JSON key and enum names did not change when the readable text was reworded: `nominal_build` is
the chosen-parts simulation, `simulated` the ideal values, and `tolerance_analysis` the
tolerance cases. `build_model.build_inductor_choice` is the `--build-inductors` value, and each
inductor that uses a suggestion has `method: "suggested_inductor"` with its `inductor_kind` and
`part_name`; an inductor simulated at its calculated value has `method: "exact_fallback"` and
says why in its `status` and warning. The omitted fields include the other parts used, the
simulated branches, measurements, every tolerance case, the spread summaries, the effective loss
model, warnings, and limitations. This is a simulation, not a measurement, a yield estimate, or
a guaranteed worst case.

The measurement records also identify `measurement_converged`, `response_evaluations`,
`reference_peak_gain_db`, `half_power_threshold_db`, `half_power_regions`, and the selected
zero-based region index. `grid_points` is the initial number of frequency points. A measurement
that did not converge remains in the case list but is left out of the spread figures and
counted explicitly. See [interpretation](user-guide.md#interpreting-response-measurements)
before using results whose response is above −3 dB in separate ranges or whose −3 dB point is
outside the simulated frequency range.

## Generic SPICE

```bash
uv run filter-calc bp bw top -f 14.175MHz -b 350kHz \
  --format spice --spice-realization exact
```

```spice
* RF Filter Calculator generic AC deck
* category: bandpass
* values: calculated, lossless (exact)
* printed trace: vm(5) is load-node voltage, not gain in dB
* transducer gain: Gt=4*Rs/Rl*|V(5)/V(NSOURCE)|^2
* limitations: ideal values; no layout, parasitic, SRF, temperature, or power effects
* ports: input=4 output=5 ground=0 source=NSOURCE
* names: CT1=Cp1 LT1=L1 CT2=Cp2 LT2=L2 CT3=Cp3 LT3=L3 CK1=Cs12 CK2=Cs23 CIN=Ce_in COUT=Ce_out
VINPUT NSOURCE 0 AC 1
RSOURCE NSOURCE 4 50
CT1 1 0 1.85835651098e-10
LT1 1 0 5.61451636781e-07
CT2 2 0 2.16748717175e-10
LT2 2 0 5.61451636781e-07
CT3 3 0 1.85835651098e-10
LT3 3 0 5.61451636781e-07
CK1 1 2 3.91596876867e-12
CK2 2 3 3.91596876867e-12
CIN 4 1 3.57096111503e-11
COUT 3 5 3.57096111503e-11
RLOAD 5 0 50
.ac lin 6921 11368069.3069 17675000
.print ac vm(5)
.end
```

`nominal-build` is the default `--spice-realization`: it uses the chosen parts (standard
capacitor values and the inductor suggestions `--build-inductors` picks) and the same
fixed-series-resistance Q model as the build simulation, and adds a `* part used:` comment for
each part (`part=T50-2 turns=18` for a toroid winding). Each parallel pair also gets its assumed
stray as a capacitor named `CSTRAY_<part>` across the pair's terminals, with a `* stray:`
comment; it stays fixed in every tolerance case. `exact` uses the calculated values without
losses, and takes none of the standard-capacitor options or `--build-inductors`. `chosen-parts` and
`calculated` are accepted as the same two choices. Band-pass decks keep the SPICE element names
`CT1`, `LT1`, `CK1`, `CIN`, and `COUT`; the `* names:` comment maps them to the table names
(`Cp1`, `L1`, `Cs12`, `Ce_in`, `Ce_out`). The `.print` trace is load voltage; use the commented
expression for transducer power gain. The band-pass sweep is linear and sized by bandwidth and
resonator count so narrow bands are sampled. Low-pass and high-pass decks keep a logarithmic
sweep.

## Response-Data Export

```bash
uv run filter-calc lp bw pi 10MHz --plot-data csv
```

```csv
frequency_hz,magnitude_db
1000000.0,0.00
1096478.196143185,0.00
1202264.4346174132,0.00
```

JSON response export uses a `filter` metadata object and a parallel `data` array. Frequencies
must be positive finite numbers and magnitudes must be finite real dB values. CSV frequencies
use the shortest decimal that round-trips to the same binary64 value, so each row matches the
JSON `frequency_hz` exactly; neither format prints a negative zero.

## Wizard, Web UI, and Version

```bash
uv run filter-calc       # wizard
uv run filter-calc web   # web UI (needs the optional web dependencies)
uv run filter-calc --version
```

The wizard uses four screens: Welcome (Choose a filter), one filter form, Output options, and
Results. The Results screen renders a selected plot in place and offers Design another, Export
(Save as Text, JSON, or CSV), and Quit. Escape navigates back; Ctrl+C exits.

The web UI's result panel shows the same text as the table examples above, and its downloads
match the JSON, CSV, SPICE, and response-data examples byte for byte.
