# Caveats & Known Issues

Edge cases, limitations, and important considerations.

---

## Input Validation

### Component Count Limits

- **Range**: 2-9 components/resonators
- Orders outside this range produce errors
- Very high orders (8-9) may produce impractical component values

### Frequency Limits

- **Minimum**: Must be positive (> 0)
- **Maximum**: No hard limit, but practical RF considerations apply
- Very low frequencies (< 100 Hz) may produce very large component values
- Very high frequencies (> 1 GHz) may produce impractically small values
- **Error**: Zero or negative values raise `ValueError: Frequency must be positive`

### Impedance

- Must be positive (> 0)
- Standard is 50Ω; 75Ω also common
- Extreme impedances (< 10Ω or > 1000Ω) may yield impractical values
- **Error**: Zero or negative values raise `ValueError: Impedance must be positive`

---

## Chebyshev-Specific Constraints

### Ripple Value

- **Must be in range** 0 < r ≤ 3.0 dB
- Higher ripple = steeper rolloff but more passband variation
- CLI and wizard both accept arbitrary values in this range (formula-based calculation)

### Bandpass Resonator Count

- **Chebyshev bandpass requires odd number of resonators**
- Error produced for even counts
- Use 3, 5, 7, or 9 resonators

---

## Bandpass Design Constraints

### Simulation-Proven Fractional Bandwidth Limit

Bandpass synthesis using top-C series coupling is **simulation-validated only for ≤10% fractional bandwidth**. Wider BW designs produce a warning; synthesis proceeds but passband realization is not guaranteed. The netlist-sweep harness verifies ±3% magnitude, ±0.5% f₀, ±50 kHz BW tolerances against simulation.

```
FBW = (f_high - f_low) / f₀  must be ≤ 0.10
```

### Frequency Specification Methods

Cannot use both methods simultaneously:
- Method 1: `-f` (center) + `-b` (bandwidth)
- Method 2: `--fl` (low) + `--fh` (high)

Using both produces an error.


### Frequency Edge Order

`--fl` must be less than `--fh`. Reversed values produce an error.

### Output with Explicit fₗ/fₕ

When using `--fl` and `--fh`, those exact values are preserved in output, JSON metadata, and bandpass plot labels. The internal synthesis uses geometric center f₀ = √(fₗ·fₕ).

---

## E-Series Matching Behavior

### Parallel Combination Mode

- **Capacitors**: Uses additive mode (C_total = C1 + C2)
- **Inductors**: Uses harmonic mode (L_total = L1×L2/(L1+L2))

The mode is auto-detected based on component value magnitude.

### Ratio Limit

Parallel combinations are limited to 10:1 ratio between components. Very extreme ratios are excluded even if mathematically better.

### Not Always Better

Sometimes a single E-series value is closer than any parallel combination. The calculator shows both options; use judgment.

---

## ASCII Plot Limitations

### Terminal Width

- Plots assume ~80 character terminal width
- Narrower terminals may wrap awkwardly
- Minimum plot width is 40 characters

### Frequency Range

- Plots show ±1 decade around cutoff frequency
- Very narrowband filters may not display well
- Bandpass plots show appropriate range automatically

### Resolution

- ASCII representation has limited resolution
- For precise analysis, export data with `--plot-data` and use external plotting tools

---

## Computational Considerations

### Floating Point Precision

- All calculations use Python's 64-bit float
- Very extreme frequency ratios may show precision artifacts
- Component values displayed to appropriate significant figures

### G-Value Calculation

- Butterworth uses closed-form formulas
- Bessel uses predefined g-value lookup tables (orders 2-9)
- Chebyshev uses direct formula calculation for arbitrary ripple values
- Higher-order filters (n > 9) not supported

---

## Practical RF Considerations

### Component Parasitics

The calculator produces **ideal** component values. Real components have:
- **Capacitors**: Equivalent series inductance (ESL), equivalent series resistance (ESR)
- **Inductors**: Parasitic capacitance, series resistance
- **PCB traces**: Stray inductance and capacitance

At higher frequencies (> 100 MHz), these parasitics significantly affect filter response.

### Component Q

The calculator assumes ideal (infinite Q) components. Real components have finite Q that:
- Increases insertion loss
- Rounds off the response peaks
- Degrades stopband attenuation

For bandpass filters, the calculator displays minimum required Q. Ensure actual component Q exceeds this.

### Coupling Between Stages

The calculator assumes no unintended coupling between filter sections. In practice:
- Shield critical filters
- Maintain physical separation between input and output
- Use ground plane

### Temperature Effects

Component values drift with temperature:
- NP0/C0G capacitors: ±30 ppm/°C
- X7R capacitors: ±15% over temp range (avoid for filters)
- Inductors: Vary by core material

---

## Known Limitations

### Not Implemented

- Notch (band-reject) filters
- Elliptic (Cauer) response
- Active filter designs
- Transmission line filters
- Crystal/SAW filters

### Edge Cases

1. **Very narrow bandpass** (fractional BW < 1%): May require impractically high-Q components

2. **High order + narrow bandwidth**: Component tolerances become critical; parallel E-series combinations essential

3. **Wideband direct-coupled bandpass**: Uses ideal prototype/FBW synthesis and does not include a Cohn-style correction for coupling-reactance frequency dispersion at wider bandwidths

4. **Impedance transformation**: Calculator assumes matched source and load impedance

---

## Cross-Check Recommendations

For critical applications:
1. Compare results with established filter design software
2. Simulate in SPICE before building
3. Verify E-series matches with actual measurements
4. Build and measure prototype before final construction

### Bessel Highpass Group Delay

Bessel highpass filters preserve linear phase in the passband but exhibit significant group delay at the cutoff edge. This is inherent to the Bessel response and more pronounced in highpass vs lowpass. Plan accordingly for phase-sensitive or timing-critical applications.

---

## Toroid Recommendations (v1)

### Schema additions (JSON / CSV)

- **JSON (LP/HP)**: each inductor object gains a `toroid_recommendations` array (up to 3 entries). Consumers that strictly reject unknown fields must handle this. Opt out with `--no-toroids`.
- **JSON (BP)**: top-level key `resonator_toroid_recommendations` added. Opt out with `--no-toroids`.
- **CSV (LP/HP/BP)**: 10 additional columns appended (`ToroidCore`, `ToroidMix`, `ToroidTurns`, `ToroidAWG`, `ToroidActualL_uH`, `ToroidErrorPct`, `ToroidWireLength_mm`, `ToroidDCR_mohm`, `ToroidQ_DC_Upper`, `ToroidTempCoeff_ppm`). `--no-toroids` restores the pre-feature column count exactly for scripted consumers.

### What Q (DC est, upper bound) really is

`Q = 2πfL / R_dc`, using bare-copper DC resistance. This **does not** model core loss, skin effect, proximity effect, or saturation. Actual measured Q at HF is typically 5–10× lower. Labelled "upper bound" for honesty; do not use for tight-Q budget sizing without measurement.

### What is excluded in v1

- FT-series ferrite, FB ferrite beads, BLN binocular cores
- AC resistance (skin effect), self-resonant frequency, core loss, saturation
- Temperature derating into the reported L range (ppm/°C shown but not applied)
- Multi-toroid stacking, user-override AWG per inductor

See `plan.md` "Deferred" section in the GH-6 plan directory for the full list.

### Unit-convention warning

A_L values in the database are in **nH/turn²** (e.g. T50-2 = 4.9). The Amidon "µH per 100 turns²" convention uses numerically 10× larger values. The code uses nH/turn² exclusively. The upstream research doc's `N = 100·√(L/A_L)` formula is unit-mismatched for our database; the correct form is `N_ideal = √(1000·L[µH] / A_L[nH/turn²])`. A regression test locks this.
