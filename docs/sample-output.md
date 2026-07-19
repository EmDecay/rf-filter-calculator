# Sample Output

These examples reflect version 2.1.0. Long machine-readable payloads are shown as
selected valid fragments; run the command to obtain the complete schema.

## Lowpass Table

```bash
uv run filter-calc lp bw pi 10MHz --no-toroids
```

```text
Butterworth PI Low Pass Filter
==================================================
Cutoff Frequency:    10 MHz
Impedance Z0:        50 Ohm
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
Inductors: wind to value

E24 Preferred-Value Capacitor Selection
---------------------------------------------
(Series density is not part tolerance; policy selects at most one realization;
expert action may be required)

C1 Calculated: 318.31 pF
  Nearest Std:  330.00 pF (+3.7%)
  Parallel Std: 47.00 pF || 270.00 pF (-0.4%)
C2 Calculated: 318.31 pF
  Nearest Std:  330.00 pF (+3.7%)
  Parallel Std: 47.00 pF || 270.00 pF (-0.4%)
```

The parallel row appears only when policy selects it: it must improve absolute error by
at least 0.5 percentage points. A target below 1 pF is instead labeled
`EXPERT ACTION REQUIRED`; the nearest enumerated value is reference-only and is not
silently selected.

## Highpass Table

```bash
uv run filter-calc hp bw t 10MHz --no-toroids
```

```text
Butterworth T High Pass Filter
==================================================
Cutoff Frequency:    10 MHz
Impedance Z0:        50 Ohm
Order:               3
==================================================

Topology:
  IN ───┤C1├───┬───┤C2├─── OUT
               │
              ===
              L1
               │
              GND

Component values: C1 = C2 = 318.31 pF; L1 = 397.89 nH
```

## Calibrated Bandpass Table

```bash
uv run filter-calc bp bw top -f 14.175MHz -b 350kHz --no-toroids --no-match
```

```text
Butterworth Coupled Resonator Bandpass Filter
==================================================
Center Frequency f₀: 14.18 MHz
Lower Cutoff fₗ:     14 MHz
Upper Cutoff fₕ:     14.35 MHz
Bandwidth BW:        350 kHz
Fractional BW:       2.47%
Impedance Z₀:        50 Ω
Resonators:          3
Coupling:            Top-C (Series)
==================================================

Loss examples use complete-resonator unloaded Q (not inductor Q alone).
Est. insertion loss (Cohn): 7.0 dB @ Qu=100, 2.8 dB @ Qu=250

Tank capacitors: Cp1 = 185.84 pF, Cp2 = 216.75 pF, Cp3 = 185.84 pF
Tank inductors:  L1 = L2 = L3 = 561.45 nH
End coupling:    Ce_in = Ce_out = 35.71 pF
Interstage:      Cs12 = Cs23 = 3.92 pF
External Q:      40.55 at each port, realized by Ce_in/Ce_out
```

The full table includes the physical Top-C diagram. Bandpass values are calibrated against
the circuit netlist, and every result carries its own `response_validation_status`.

## Strict JSON

```bash
uv run filter-calc lp bw pi 10MHz --format json --no-toroids
```

A selected component fragment is:

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
          "selected": {
            "kind": "parallel",
            "components": [
              {"value_farads": 4.7e-11},
              {"value_farads": 2.7000000000000005e-10}
            ],
            "value_farads": 3.1700000000000004e-10,
            "error_pct": -0.41151288120355006
          },
          "reason": "parallel_materially_improves_error",
          "warnings": []
        }
      }
    ]
  }
}
```

The complete result includes all components and match-policy fields. JSON serialization is
strict: `NaN` and infinities are never emitted.

For explicit bandpass edges, `requested_parameters` and the `--sim-build` `target` block
retain the parsed requested values exactly and mark
`"frequency_specification": "edge_frequencies"`.

## Rectangular CSV

```bash
uv run filter-calc lp bw pi 10MHz --format csv --no-toroids
```

```csv
Component,Value,Unit,NearestStdValue,NearestStdUnit,NearestStdErrorPct,ParallelStdValues,ParallelStdErrorPct,Eseries,RecommendedStdKind,RecommendedStdValues,RecommendedStdErrorPct,RecommendationStatus,RecommendationReason,RecommendationWarnings,RecommendationPolicy
C1,318.31,pF,330.00,pF,3.7,47.00 pF || 270.00 pF,-0.4,E24,parallel,47.00 pF || 270.00 pF,-0.4,recommended,parallel_materially_improves_error,,single<=1%;parallel-improvement>=0.5pp;minimum-cap=1pF
C2,318.31,pF,330.00,pF,3.7,47.00 pF || 270.00 pF,-0.4,E24,parallel,47.00 pF || 270.00 pF,-0.4,recommended,parallel_materially_improves_error,,single<=1%;parallel-improvement>=0.5pp;minimum-cap=1pF
L1,1.59,µH,,,,,,,,,,,,,
```

All rows have the same column count. Warning fields are CSV-quoted when necessary.

## Screened Toroid Candidates

```bash
uv run filter-calc lp bw pi 10MHz --toroid-compact
```

```text
Screened Toroid Winding Candidates (Iron-Powder T-Series)
-------------------------------------------------------
  L1 target: 1.59 µH @ 10 MHz
  1. T50-2    N=18 AWG20 L=1.588µH (-0.25%) Rdc=12mΩ ωL/Rdc≤8,210 [RF Q/SRF/power not assessed]
```

This is a candidate screen, not a claim of RF suitability. Automatic candidates are limited
to the exact primary-sourced T25-6, T50-2, and T68-2 records and do not predict RF Q, SRF,
core loss, saturation, thermal rise, or power handling.

## Realized-Build Analysis

```bash
uv run filter-calc lp bw pi 10MHz --sim-build --no-toroids \
  --inductor-q 100 --capacitor-q 500 \
  --sample-count 20 --seed 73 --format json > build.json
```

The complete component JSON is augmented with these top-level blocks:

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
    "realization": "selected_nominal_parts_and_calculated_exact_fallbacks"
  },
  "tolerance_analysis": {
    "method": "deterministic_corners_plus_seeded_uniform_screening",
    "sample_count": 20,
    "seed": 73,
    "grid_points": 601
  },
  "evaluation": {
    "source_resistance_ohm": 50.0,
    "load_resistance_ohm": 50.0,
    "gain_metric": "transducer_power_gain_db",
    "unequal_loads_change_evaluation_not_synthesis": true
  }
}
```

The omitted fields include substitutions, exact fallbacks, physical branches, measurements,
all bounded cases, metric summaries, the effective loss model, warnings, and limitations.
This analysis is a simulation, not a measurement, yield estimate, or guaranteed worst case.

## Generic SPICE

```bash
uv run filter-calc bp bw top -f 14.175MHz -b 350kHz \
  --format spice --spice-realization exact
```

```spice
* RF Filter Calculator generic AC deck
* category: bandpass
* realization: calculated_exact
* printed trace: vm(5) is load-node voltage, not gain in dB
* transducer gain: Gt=4*Rs/Rl*|V(5)/V(NSOURCE)|^2
* limitations: ideal values omit layout, parasitics, SRF, temperature, and power behavior
* ports: input=4 output=5 ground=0 source=NSOURCE
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
.ac dec 200 11368069.3069 17675000
.print ac vm(5)
.end
```

`nominal-build` is the default SPICE realization. It uses the same selected physical branches
and Q-derived constant-series-resistance model as build analysis. The `.print` trace is load
voltage; use the commented expression for transducer power gain.

## Response-Data Export

```bash
uv run filter-calc lp bw pi 10MHz --plot-data csv
```

```csv
frequency_hz,magnitude_db
1e+06,-0.00
1.09648e+06,-0.00
1.20226e+06,-0.00
```

JSON response export uses a `filter` metadata object and a parallel `data` array. Frequencies
must be positive finite numbers and magnitudes must be finite real dB values.

## Wizard and Version

```bash
uv run filter-calc       # wizard
uv run filter-calc --version
```

The wizard uses four screens: Welcome, one filter form, Output Options, and Results. The
Results screen renders a selected plot in place and offers Design Another, Save/Export, and
Quit. Escape navigates back; Ctrl+C exits.
