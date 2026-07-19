# Filter Theory

Background on filter types, response characteristics, and topologies.

---

## Response Types

### Butterworth (Maximally Flat Magnitude)

- Flattest possible passband response
- No ripple in the passband
- Moderate rolloff steepness
- -20n dB/decade rolloff (n = order)

**Best for**: General-purpose filtering, audio applications, situations where flat passband is critical.

**Tradeoff**: Requires higher order than Chebyshev for equivalent stopband attenuation.

### Chebyshev (Equiripple)

- Steeper rolloff than Butterworth for same order
- Controlled ripple in passband (user-specified in dB)
- Better stopband attenuation
- Ripple trades flatness for steepness

**Best for**: RF applications requiring sharp cutoff, situations where some passband ripple is acceptable.

**Tradeoff**: Passband ripple may affect signal quality. Higher ripple = steeper rolloff.

**Cutoff convention**: For Chebyshev LP/HP, the specified cutoff is the ripple-band
edge (attenuation equals the ripple value at fc), matching ARRL Handbook / Elsie /
Zverev tables — not the −3 dB point. The −3 dB frequency lies beyond fc for lowpass
and below fc for highpass; the threshold table in plot output reports it. Bandpass
`bw` is different: it is the true −3 dB bandwidth (what a VNA measures).

**Note**: For bandpass Chebyshev filters, an odd number of resonators is required.

### Bessel (Maximally Flat Delay)

- Best pulse response (minimal overshoot/ringing)
- Linear phase response in passband
- Gentlest rolloff of the three types
- Preserves waveform shape

**Note**: The flat-group-delay property holds for the lowpass prototype. The LP→BP transformation warps phase, so a Bessel *bandpass* is not maximally flat in group delay — verify externally (e.g. SPICE) for phase-critical work.

**Best for**: Data/pulse applications, digital communications, timing-critical signals.

**Tradeoff**: Poorest stopband attenuation for given order.

---

## Filter Categories

### Lowpass (Pi/T Topology)

**Pi topology** (default): shunt C - series L - shunt C pattern
```
     ┌────[L1]────┬────[L2]────┐
IN ──┤            │            ├── OUT
    C1           C2           C3
     │            │            │
    GND          GND          GND
```

**T topology**: series L - shunt C - series L pattern
```
IN ───┤L1├───┬───┤L2├───┬───┤L3├─── OUT
             │          │
            C1         C2
             │          │
            GND        GND
```

- Passes frequencies below cutoff
- Pi: capacitors at odd (shunt) positions, inductors at even (series)
- T: inductors at odd (series) positions, capacitors at even (shunt)

### Highpass (Pi/T Topology)

**T topology** (default): series C - shunt L - series C pattern
```
IN ───┤C1├───┬───┤C2├───┬───┤C3├─── OUT
             │          │
            L1         L2
             │          │
            GND        GND
```

**Pi topology**: shunt L - series C - shunt L pattern
```
     ┌────[C1]────┬────[C2]────┐
IN ──┤            │            ├── OUT
    L1           L2           L3
     │            │            │
    GND          GND          GND
```

- Passes frequencies above cutoff
- T: capacitors at odd (series) positions, inductors at even (shunt)
- Pi: inductors at odd (shunt) positions, capacitors at even (series)

### Bandpass (Coupled Resonator, Top-C Series Coupling)

```
       Ce_in     Cs12           Cs23      Ce_out
IN ──┤├──┬──────┤├──────┬──────┤├──────┬──┤├── OUT
        │              │              │
     ┌──┴──┐        ┌──┴──┐        ┌──┴──┐
     Cp1  L1        Cp2  L2        Cp3  L3
     └──┬──┘        └──┬──┘        └──┬──┘
        │              │              │
       GND            GND            GND
```

- LC tank circuits tuned to center frequency
- **Top-coupled series capacitors only**: Cs12, Cs23 couple adjacent resonators; Ce_in/Ce_out couple to ports
- Both requested −3 dB skirts are numerically calibrated; a separate netlist sweep reports per-design edge, connected-region, outer-skirt, ripple, passband-shape, and representative-stopband validation
- External Q realized by series end-coupling capacitors (Ce)

---

## Key Formulas

### Normalized g-values

All filter designs start with normalized lowpass prototype g-values, then transform to desired frequency and impedance.

### Lowpass Frequency Scaling

```
C = g / (2π × f_c × Z₀)
L = g × Z₀ / (2π × f_c)
```

### Highpass Transformation

Derived from the lowpass prototype via the 1/g transformation:

```
C = 1 / (g × 2π × f_c × Z₀)
L = Z₀ / (g × 2π × f_c)
```

### Bandpass Transformation

For bandpass filters, the geometric center frequency:
```
f₀ = √(f_low × f_high)
```

Fractional bandwidth:
```
FBW = (f_high - f_low) / f₀
```

Normalized bandpass deviation:
```
δ = (f² - f₀²) / (BW × f)
```

Butterworth, Chebyshev, and Bessel bandpass responses are evaluated from their
respective lowpass prototypes using `|δ|`.

---

## Component Q Requirements

### Definition

Q (quality factor) describes component losses. Higher Q = lower losses.

```
Q_inductor = ωL / R_series
Q_capacitor = 1 / (ωC × R_series)
```

### Historical Q heuristic

For compatibility, the result still includes the heuristic:
```
Q_min = f₀ / BW × Q_safety
```

The default safety factor is 2.0. This number is not a stability boundary, a component specification, or the loss model used by realized-build simulation. `q_safety` is explicitly marked compatibility-only in JSON.

### Complete-resonator Q

`Qu` is the unloaded Q of the complete resonator. If inductor and capacitor Q are known separately, the calculator combines their loss channels as:

```text
1 / Qu = 1 / QL + 1 / QC
```

The omission of one channel means that channel is modeled as ideal. In realized-build analysis, Q at one reference frequency is converted to explicit series resistance. The resistance is held constant during the sweep, so Q then varies with frequency.

**Cohn Insertion Loss Estimate** (v2.0.1):

For circuits with low-loss (high-Q) components, insertion loss can be estimated using the Cohn formula:
```
IL (dB) ≈ 4.343 × Σgᵢ / (FBW_synth × Qu)
```

Where:
- **Σgᵢ** = sum of normalized g-values for all resonators
- **FBW_synth** = synthesized fractional bandwidth (may differ slightly from requested BW for Chebyshev)
- **Qu** = unloaded Q of reactive components
- **4.343** = conversion constant (dB = nepers × 4.343)

The calculator shows reference estimates at Qu = 100 and Qu = 250 and adds the supplied complete-resonator Q. This is a low-loss approximation, not a substitute for the named-circuit loss simulation or a measurement.

---

## Order vs. Steepness

Higher order filters provide:
- Steeper rolloff (-20n dB/decade for Butterworth)
- Better stopband attenuation
- Sharper transition band

But require:
- More components
- Tighter tolerances
- Higher-Q components for bandpass

### Practical Order Selection

| Application | Typical Order |
|-------------|---------------|
| Basic filtering | 3-5 |
| Amateur radio | 5-7 |
| Commercial RF | 7-9 |

---

## External Q & End-Coupling Capacitors (Bandpass)

For coupled-resonator bandpass filters, external Q determines coupling to source/load:

```
Q_ext = f₀ / BW × g_value
```

**Realization by Series End-Coupling**: The end resonators see a series capacitor (Ce_in or Ce_out) at their port. This capacitor acts as an impedance transformer, stepping up the termination resistance seen by the tank from Z₀ to a parallel equivalent Rp = Qe·ω₀·L. The transformation is governed by:

```
Rp = Z₀·(1 + q²)   where  q = 1/(ω₀·Z₀·Ce)
```

The designer solves for Ce such that the tank sees the target Rp. A series-equivalent capacitance correction is included in the tank. Because finite coupling reactance perturbs the complete multi-resonator network, the implementation subsequently calibrates tank frequency and prototype fractional bandwidth against both requested −3 dB skirts.

The calculator displays Q_ext values indicating the external Q realized by the end-coupling capacitors.

## Iron-Powder Toroid Winding Math

For a core with published inductance factor A_L in nH/turn², the nominal turns are:

```text
Nideal = sqrt(1000 * L[uH] / A_L[nH/turn^2])
```

Turns must be integral, so the realized nominal inductance is `A_L * N²`. The calculator compares adjacent turn options and accepts an automatic candidate only when the selected turn count's nominal error is within that exact core's published A_L tolerance.

Frequency guidance, A_L, and physical dimensions do not establish RF suitability. The automatic screen is deliberately limited to exact primary-sourced parts and checks only recorded material guidance, integer-turn accuracy, and winding capacity. Its `omega L / Rdc` value uses wire DC resistance and is only a diagnostic ceiling—not RF Q. Core loss, AC copper loss, SRF, saturation, thermal rise, and power handling require separate data and measurement.

See [the user guide](user-guide.md#toroid-winding-recommendations) for the output contract and
[caveats](caveats-and-known-issues.md#toroid-candidate-screen) for the trust boundary.
