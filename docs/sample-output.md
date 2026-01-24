# Sample Output

Example outputs for all filter types and formats.

---

## Lowpass Filter (Butterworth, 5th Order)

```bash
./filter-calc.py lp bw 10MHz -n 5 --plot
```

```
Butterworth Pi Low Pass Filter
==================================================
Cutoff Frequency:    10 MHz
Impedance Z0:        50 Ohm
Order:               5
==================================================

Topology:
  IN ───┬───┤ L1 ├───┬───┤ L2 ├───┬─── OUT
        │            │            │
       ===          ===          ===
       C1           C2           C3
        │            │            │
       GND          GND          GND

                 Component Values
┌────────────────────────┬────────────────────────┐
│       Capacitors       │       Inductors        │
├────────────────────────┼────────────────────────┤
│ C1: 196.73 pF          │ L1: 1.29 µH            │
│ C2: 636.62 pF          │ L2: 1.29 µH            │
│ C3: 196.73 pF          │                        │
└────────────────────────┴────────────────────────┘

E24 Standard Capacitor Recommendations
─────────────────────────────────────────────
(Calculated values with nearest standard matches)

C1 Calculated: 196.73 pF
  Nearest Std:  200.00 pF (+1.7%)
  Parallel Std: 47.00 || 150.00 pF (+0.1%)
C2 Calculated: 636.62 pF
  Nearest Std:  620.00 pF (-2.6%)
  Parallel Std: 75.00 || 560.00 pF (-0.3%)
C3 Calculated: 196.73 pF
  Nearest Std:  200.00 pF (+1.7%)
  Parallel Std: 47.00 || 150.00 pF (+0.1%)

Frequency Response (dB)

   -3 │███████████████████████████ · · · · · · · · · · · ·
      │█████████████████████████████
      │██████████████████████████████
      │████████████████████████████████
      │██████████████████████████████████
  -30 │███████████████████████████████████
      │█████████████████████████████████████
      │███████████████████████████████████████
      │████████████████████████████████████████
  -60 │██████████████████████████████████████████████████ █
      +┼──────┼─────────┼───────┼───────┼─────────┼───────┼
       1M                     10M(fc)                   100M
```

---

## Highpass Filter (Chebyshev, 5th Order)

```bash
./filter-calc.py hp ch 14MHz -r 0.5 -n 5
```

```
Chebyshev T High Pass Filter
==================================================
Cutoff Frequency:    14 MHz
Impedance Z0:        50 Ohm
Ripple:              0.5 dB
Order:               5
==================================================

Topology:
  IN ───┤L1├───┬───┤L2├───┬───┤L3├─── OUT
               │          │
              ===        ===
              C1         C2
               │          │
              GND        GND

                 Component Values
┌────────────────────────┬────────────────────────┐
│       Inductors        │       Capacitors       │
├────────────────────────┼────────────────────────┤
│ L1: 333.22 nH          │ C1: 279.57 pF          │
│ L2: 223.71 nH          │ C2: 279.57 pF          │
│ L3: 333.22 nH          │                        │
└────────────────────────┴────────────────────────┘

E24 Standard Inductor Recommendations
─────────────────────────────────────────────
(Calculated values with nearest standard matches)

L1 Calculated: 333.22 nH
  Nearest Std:  330.00 nH (-1.0%)
  Parallel Std: 33.00 || 300.00 nH (-0.1%)
L2 Calculated: 223.71 nH
  Nearest Std:  220.00 nH (-1.7%)
  Parallel Std: 24.00 || 200.00 nH (+0.1%)
L3 Calculated: 333.22 nH
  Nearest Std:  330.00 nH (-1.0%)
  Parallel Std: 33.00 || 300.00 nH (-0.1%)
```

---

## Bandpass Filter (Butterworth, 3 Resonators)

```bash
./filter-calc.py bp bw top -f 14.175MHz -b 350kHz -n 3
```

```
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

Minimum Component Q: 81
  (Q safety factor: 2.0)

Topology:
                Cs12           Cs23
  IN ──────┬──────┤├──────┬──────┤├──────┬────── OUT
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
│ Cp1: 220.64 pF         │ L1: 561.39 nH          │
│ Cp2: 216.72 pF         │ L2: 561.39 nH          │
│ Cp3: 220.64 pF         │ L3: 561.39 nH          │
└────────────────────────┴────────────────────────┘

┌────────────────────────┐
│  Coupling Capacitors   │
├────────────────────────┤
│ Cs12: 3.92 pF          │
│ Cs23: 3.92 pF          │
└────────────────────────┘

External Q (input):  40.50
External Q (output): 40.50

E24 Standard Capacitor Recommendations
─────────────────────────────────────────────
(Calculated values with nearest standard matches)

Cp1 Calculated: 220.64 pF
  Nearest Std:  220.00 pF (-0.3%)
  Parallel Std: 91.00 || 130.00 pF (+0.2%)
Cp2 Calculated: 216.72 pF
  Nearest Std:  220.00 pF (+1.5%)
  Parallel Std: 36.00 || 180.00 pF (-0.3%)
Cp3 Calculated: 220.64 pF
  Nearest Std:  220.00 pF (-0.3%)
  Parallel Std: 91.00 || 130.00 pF (+0.2%)
Cs12 Calculated: 3.92 pF
  Nearest Std:  3.90 pF (-0.5%)
  Parallel Std: 0.62 || 3.30 pF (-0.0%)
Cs23 Calculated: 3.92 pF
  Nearest Std:  3.90 pF (-0.5%)
  Parallel Std: 0.62 || 3.30 pF (-0.0%)
```

---

## JSON Output

```bash
./filter-calc.py lp bw 10MHz --format json
```

```json
{
  "filter_type": "butterworth",
  "cutoff_frequency_hz": 10000000.0,
  "impedance_ohms": 50.0,
  "order": 3,
  "components": {
    "capacitors": [
      {
        "name": "C1",
        "value_farads": 3.1830988618379065e-10
      },
      {
        "name": "C2",
        "value_farads": 3.1830988618379065e-10
      }
    ],
    "inductors": [
      {
        "name": "L1",
        "value_henries": 1.5915494309189533e-06
      }
    ]
  }
}
```

---

## CSV Output

```bash
./filter-calc.py lp bw 10MHz --format csv
```

```
Component,Value,Unit
C1,318.31,pF
C2,318.31,pF
L1,1.59,µH
```

---

## Frequency Response Data Export

### JSON Format

```bash
./filter-calc.py lp bw 10MHz --plot-data json
```

```json
{
  "filter_type": "butterworth",
  "cutoff_hz": 10000000.0,
  "order": 3,
  "data": [
    {"frequency_hz": 1000000.0, "magnitude_db": -0.0},
    {"frequency_hz": 1096478.19, "magnitude_db": -0.0},
    {"frequency_hz": 1202264.43, "magnitude_db": -0.0},
    ...
    {"frequency_hz": 100000000.0, "magnitude_db": -60.0}
  ]
}
```

### CSV Format

```bash
./filter-calc.py lp bw 10MHz --plot-data csv
```

```
frequency_hz,magnitude_db
1000000.0,-0.00
1122018.45,-0.00
1258925.41,-0.01
1412537.54,-0.01
...
100000000.0,-60.00
```

---

## Filter Explanation

```bash
./filter-calc.py lp ch --explain
```

```
Chebyshev Filter (Equiripple)
- Steeper rolloff than Butterworth for same order
- Ripple in passband (specified in dB)
- Better stopband attenuation
- Good for RF applications requiring sharp cutoff
```

---

## Quiet Mode

```bash
./filter-calc.py lp bw 10MHz -n 3 -q
```

```
C1: 318.31 pF
C2: 318.31 pF
L1: 1.59 µH
```

---

## Verification Test

```bash
./filter-calc.py bp bw top -f 10MHz -b 1MHz --verify
```

```
Running verification tests...
Verification passed
```
