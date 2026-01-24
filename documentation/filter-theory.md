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

**Note**: For bandpass Chebyshev filters, an odd number of resonators is required.

### Bessel (Maximally Flat Delay)

- Best pulse response (minimal overshoot/ringing)
- Linear phase response in passband
- Gentlest rolloff of the three types
- Preserves waveform shape

**Best for**: Data/pulse applications, digital communications, timing-critical signals.

**Tradeoff**: Poorest stopband attenuation for given order.

---

## Filter Categories

### Lowpass (Pi Topology)

```
     ┌────[L1]────┬────[L2]────┐
IN ──┤            │            ├── OUT
    C1           C2           C3
     │            │            │
    GND          GND          GND
```

- Shunt capacitors to ground
- Series inductors between nodes
- First and last elements are capacitors
- Passes frequencies below cutoff

### Highpass (T Topology)

```
IN ───┤L1├───┬───┤L2├───┬───┤L3├─── OUT
             │          │
            C1         C2
             │          │
            GND        GND
```

- Series inductors in signal path
- Shunt capacitors to ground
- First and last elements are inductors
- Passes frequencies above cutoff

### Bandpass (Coupled Resonator)

```
           Cs12           Cs23
IN ────┬────┤├────┬────┤├────┬──── OUT
       │          │          │
    ┌──┴──┐    ┌──┴──┐    ┌──┴──┐
    Cp1  L1    Cp2  L2    Cp3  L3
    └──┬──┘    └──┬──┘    └──┬──┘
       │          │          │
      GND        GND        GND
```

- LC tank circuits tuned to center frequency
- Coupling capacitors determine bandwidth
- Top-coupled: series capacitors between resonators
- Shunt-coupled: parallel capacitors to ground

---

## Key Formulas

### Normalized g-values

All filter designs start with normalized lowpass prototype g-values, then transform to desired frequency and impedance.

### Frequency Scaling

```
C_scaled = C_normalized / (2π × f_c × Z₀)
L_scaled = L_normalized × Z₀ / (2π × f_c)
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

---

## Component Q Requirements

### Definition

Q (quality factor) describes component losses. Higher Q = lower losses.

```
Q_inductor = ωL / R_series
Q_capacitor = 1 / (ωC × R_series)
```

### Minimum Q for Bandpass Filters

The calculator displays minimum required Q based on:
```
Q_min = f₀ / BW × Q_safety
```

Default safety factor is 2.0. Increase for better filter performance.

### Practical Considerations

| Frequency | Typical Inductor Q |
|-----------|-------------------|
| 1-10 MHz | 50-100 |
| 10-100 MHz | 80-200 |
| 100+ MHz | 100-300 |

Air-core inductors generally have higher Q than ferrite-core at RF frequencies.

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

## External Q (Bandpass)

For coupled-resonator bandpass filters, external Q determines coupling to source/load:

```
Q_ext = f₀ / BW × g_value
```

The calculator displays Q_ext values for input and output matching networks.
