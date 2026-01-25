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

- **Must be positive** (> 0 dB)
- Typical range: 0.1 to 3.0 dB
- Higher ripple = steeper rolloff but more passband variation
- **Wizard mode**: Only accepts 0.1, 0.5, or 1.0 dB (validated choices)
- **CLI mode**: Accepts any positive ripple value (formula-based calculation)

### Bandpass Resonator Count

- **Chebyshev bandpass requires odd number of resonators**
- Error produced for even counts
- Use 3, 5, 7, or 9 resonators

---

## Bandpass Frequency Specification

### Mutually Exclusive Methods

Cannot use both methods simultaneously:
- Method 1: `-f` (center) + `-b` (bandwidth)
- Method 2: `--fl` (low) + `--fh` (high)

Using both produces an error.

### Geometric vs Arithmetic Center

When using `--fl` and `--fh`, the center frequency is the **geometric mean**:
```
f₀ = √(f_low × f_high)
```

This differs from arithmetic mean. For wide bandwidths, the difference is noticeable.

Example: 14 MHz to 14.35 MHz
- Arithmetic center: 14.175 MHz
- Geometric center: 14.1747 MHz (what calculator uses)

### Frequency Order

`--fl` must be less than `--fh`. Reversed values produce an error.

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

3. **Bessel bandpass**: Less common; response characteristics may not match theoretical exactly

4. **Impedance transformation**: Calculator assumes matched source and load impedance

---

## Verification

### Self-Test

For bandpass filters, run the built-in verification:

```bash
./filter-calc.py bp bw top -f 10MHz -b 1MHz --verify
```

This checks g-value calculations and component formulas.

### Cross-Check Recommendations

For critical applications:
1. Compare results with established filter design software
2. Simulate in SPICE before building
3. Verify E-series matches with actual measurements
4. Build and measure prototype before final construction
