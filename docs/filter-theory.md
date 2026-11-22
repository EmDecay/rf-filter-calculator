# Filter Theory

Background on filter types, response characteristics, and topologies.

---

## Response Types

The ARRL Handbook calls these filter *families*; this calculator calls them response types.

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
and below fc for highpass; the table of −3/−10/−20 dB frequencies printed with `--plot` reports it. Bandpass
`bw` is different: it is the true −3 dB bandwidth (what a VNA measures).

**Note**: For bandpass Chebyshev filters, an odd number of resonators is required.

### Bessel (Maximally Flat Delay)

- Best pulse response (minimal overshoot/ringing)
- Nearly linear phase in the passband (maximally flat group delay)
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
- ARRL Handbook names: Pi is *capacitor-input* and T is *inductor-input*

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
- ARRL Handbook names: T is *capacitor-input* and Pi is *inductor-input*. The Handbook names
  a ladder by the part at its input, so the same shape has the opposite name in low-pass and
  high-pass (ARRL Handbook, 102nd edition, §10.3.1 and Figs. 10.17, 10.18, and 10.23)

### Bandpass (Coupled Resonator, Top-Coupled Through Series Capacitors)

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
- Both requested −3 dB edges are placed numerically; a separate circuit sweep, the response check, reports per design on the edges, separate −3 dB ranges, the outer edges, ripple, passband shape, and points just outside the passband
- External Q set by series end-coupling capacitors (Ce)

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

The default safety factor is 2.0. This number is not a stability boundary, a component specification, or the loss model used by the build simulation. `q_safety` is explicitly marked compatibility-only in JSON.

### Resonator Qu

`Qu` is the unloaded Q of each resonator, with inductor and capacitor losses together. If inductor and capacitor Q are known separately, the calculator combines their loss channels as:

```text
1 / Qu = 1 / (inductor Q) + 1 / (capacitor Q)
```

If one of them is omitted, that part is modeled as lossless. In the build simulation, each Q is turned into a fixed series resistance at the frequency where the Q values apply. The resistance is held constant during the sweep, so the modeled Q varies with frequency.

**Cohn Insertion Loss Estimate**:

For circuits with low-loss (high-Q) components, insertion loss can be estimated using the Cohn formula:
```
IL (dB) ≈ 4.343 × Σgᵢ / (FBW_synth × Qu)
```

Where:
- **Σgᵢ** = sum of normalized g-values for all resonators
- **FBW_synth** = synthesized fractional bandwidth (may differ slightly from requested BW for Chebyshev)
- **Qu** = unloaded Q of each resonator (inductor and capacitor losses together)
- **4.343** ≈ `10 / ln(10)`, the coefficient in this small-loss power-gain approximation (not a general voltage-neper conversion)

The calculator shows estimates at Qu = 100 and Qu = 250 and adds the resonator Qu you give (`--qu`, or `--ql`/`--qc` combined). This is a low-loss approximation, not a substitute for the named-circuit loss simulation or a measurement.

The **Insertion loss at f₀** block prints each Cohn estimate next to a circuit simulation of the calculated values, which makes the approximation's breakdown visible. For
a 3-resonator Butterworth design at 10 MHz with 10 kHz bandwidth and Qu=100, Cohn gives about
174 dB while the equivalent-loss circuit gives about 62 dB of center loss. A finite answer
does not establish an approximation's applicability. See the [reporting policy](user-guide.md#interpreting-response-measurements)
and [independent circuit regressions](../tests/test_response_accuracy.py).

### Top-coupled rejection away from the passband

Capacitive couplers are frequency dependent; their near-passband equivalence to prototype
inverters does not extend to arbitrary remote frequencies. At 20 MHz, a 3-resonator
top-coupled Butterworth design that passes the response check, centered at 10 MHz with 1 MHz bandwidth, gives about −47.66 dB circuit
gain, versus about −70.57 dB for the ideal prototype. Both calculations can be correct for
their respective models. The response check's four points just outside the passband use normalized
deviations −2, −1.5, +1.5 and +2. The attenuation printed at 2× and 3× the center is for
information only and is not part of the response check; specific blocker/harmonic requirements need their own
frequency and rejection mask, including physical parasitics when relevant.

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

The calculator displays the external Q set by the end-coupling capacitors, e.g. `External Q (input):  40.55 (set by Ce_in)`.

**Effective shunt of an end capacitor.** Seen from its tank, Ce in series with the port
resistance R is a shunt of admittance `jωCe/(1 + jωRCe)`, whose susceptance is that of a
capacitance

```
Ce_eff = Ce / (1 + (ωRCe)²)
```

For the 2 m example (Ce = 2.662 pF, R = 50 Ω, at the 145.974 MHz tank frequency) that is
2.623 pF. Ce_eff is not monotone in Ce: it is largest at `Ce = 1/(ωR)`, where it is `1/(2ωR)`
(2.7257 pF and 1.3629 pF for a 400 Ω port), so the range of Ce_eff over an interval of Ce
uses both ends and that point when it lies inside.

## Tank Tuning from the Diagonal Susceptance (Bandpass)

Synthesis subtracts from each tank capacitor the coupling capacitors attached to its node and
the end capacitor's effective shunt, so at the calibrated tank frequency `f_tank` every tank
node's *diagonal susceptance* is zero: the imaginary part of the admittance seen at the node
with every other tank node shorted and each port at its resistance,

```
B_i(f_tank) = ω·Cp_i + Σ ω·Cs (couplers at i) + ω·Ce_eff (end tanks) − 1/(ω·L) = 0
```

A built tank must restore that susceptance whatever the other parts at its node turn out to be.
So the calculator sizes a fixed part plus a trimmer: the pair must cover the capacitance the
target needs less every other branch at its extreme corners (the inductor at both tolerance ends,
at its minimum SRF and with no drift; each coupler at both ends; the end capacitor through its
port at both ends and its stationary point), with the loss of the design's resonator Q. The
branches are independent, so the extremes add. A trimmer's effective capacitance at the tank
frequency is raised by its series inductance, `C/(1 − ω²LsC)`; the range relied on runs from
the raised minimum to the unraised maximum, on the rising part of the knob's travel only. With
`u = 1/(ωC)`, `a = ωLs` and a capacitor Q giving `R = αu` (`α = ω/(ω_ref·Q)`), the branch
susceptance `(u − a)/((αu)² + (u − a)²)` rises with C until `u = a(1 + α/√(1 + α²))`: the
series resonance when lossless, a loss peak before it otherwise. In the build, each trimmer is set by solving its
branch admittance so the node's susceptance, with every built branch (its series resistance from
Q, the chip inductors' self-capacitance, the strays and the ports), equals the calculated design's
again. That restores each tank's resonance; it does not restore the coupling between tanks or
the external Q, so a retuned build with off-nominal couplers still differs from the design.

## Iron-Powder Toroid Winding Math

For a core with published inductance factor A_L in nH/turn², the nominal turns are:

```text
Nideal = sqrt(1000 * L[uH] / A_L[nH/turn^2])
```

Turns must be whole, so the wound inductance is nominally `A_L * N²`. The calculator compares adjacent turn counts and suggests a core only when the chosen turn count's nominal error is within that exact core's published A_L tolerance.

Frequency guidance, A_L, and physical dimensions do not establish RF suitability. Automatic suggestions are deliberately limited to exact primary-sourced parts and check only the rated frequency range, whole-turn inductance within the A_L tolerance, and wire fit. The `ωL/DCR` value uses only the wire's DC resistance, so it is an upper limit, not RF Q. Core loss, AC copper loss, SRF, saturation, heating, and power handling require separate data and measurement.

See [the user guide](user-guide.md#toroid-winding-suggestions) for the output contract and
[caveats](caveats-and-known-issues.md#toroid-winding-suggestions) for the trust boundary.
