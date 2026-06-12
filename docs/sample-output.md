# Sample Output

Example outputs for all filter types and formats.

---

## Lowpass Filter (Butterworth, 5th Order, Pi Topology)

```bash
uv run filter-calc lp bw pi 10MHz -n 5 --plot
```

```
Butterworth PI Low Pass Filter
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
Inductors: wind to value (see toroid recommendations)

E24 Standard Capacitor Recommendations
---------------------------------------------
(Calculated values with nearest standard matches)

C1 Calculated: 196.73 pF
  Nearest Std:  200.00 pF (+1.7%)
  Parallel Std: 47.00 pF || 150.00 pF (+0.1%)
C2 Calculated: 636.62 pF
  Nearest Std:  620.00 pF (-2.6%)
  Parallel Std: 75.00 pF || 560.00 pF (-0.3%)
C3 Calculated: 196.73 pF
  Nearest Std:  200.00 pF (+1.7%)
  Parallel Std: 47.00 pF || 150.00 pF (+0.1%)

Toroid Winding Recommendations (Iron-Powder T-Series)
-------------------------------------------------------
(Accuracy: A_L tolerance ±5% per spec; N rounding shown as %)

  L1 target: 1.29 µH  (design freq 10 MHz)
  ────────────────────────────────────────────────────────────
  1. T68-2  (Red/Clear, mix 2, 95 ppm/°C)
     Turns: 15 of AWG 20   Actual L: 1.28 µH  (-0.40%)
     L range (A_L ±5%): 1.22 µH – 1.35 µH
     Wire: 294 mm of AWG 20 (0.812 mm)   DCR: 9.5 mΩ
     Q (DC est, upper bound): 8,450 @ 10 MHz
     Dims: 17.50 × 9.40 × 4.83 mm (OD × ID × H)

  L2 target: 1.29 µH  (design freq 10 MHz)
  ────────────────────────────────────────────────────────────
  1. T68-2  (Red/Clear, mix 2, 95 ppm/°C)
     Turns: 15 of AWG 20   Actual L: 1.28 µH  (-0.40%)
     L range (A_L ±5%): 1.22 µH – 1.35 µH
     Wire: 294 mm of AWG 20 (0.812 mm)   DCR: 9.5 mΩ
     Q (DC est, upper bound): 8,450 @ 10 MHz
     Dims: 17.50 × 9.40 × 4.83 mm (OD × ID × H)

Frequency Response (dB)

    0 │███████████████████████████                         
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

## Highpass Filter (Chebyshev, 5th Order, T Topology, 0.5 dB Ripple)

```bash
uv run filter-calc hp ch t 14MHz -r 0.5 -n 5
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
       IN ────┤ L1 ├────┬────┤ L2 ├────┬──── OUT
              │         │            │         
              L3        L4          L5        
              │         │            │         
             GND   ┌────┴────┐      GND      
                   C1        C2             
                   │         │              
                  GND       GND             

                 Component Values                 
┌────────────────────────┬────────────────────────┐
│       Capacitors       │       Inductors        │
├────────────────────────┼────────────────────────┤
│ C1: 31.82 pF           │ L1: 169.63 nH          │
│ C2: 31.82 pF           │ L2: 169.63 nH          │
│                        │ L3: 506.77 nH          │
│                        │ L4: 506.77 nH          │
│                        │ L5: 506.77 nH          │
└────────────────────────┴────────────────────────┘
Inductors: wind to value (see toroid recommendations)

E24 Standard Capacitor Recommendations
---------------------------------------------
(Calculated values with nearest standard matches)

C1 Calculated: 31.82 pF
  Nearest Std:  33.00 pF (+3.6%)
  Parallel Std: 12.00 pF || 22.00 pF (-0.4%)
C2 Calculated: 31.82 pF
  Nearest Std:  33.00 pF (+3.6%)
  Parallel Std: 12.00 pF || 22.00 pF (-0.4%)
```

---

## Bandpass Filter (Butterworth, 3 Resonators, Top-C Series Coupling)

```bash
uv run filter-calc bp bw top -f 14.175MHz -b 350kHz -n 3
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
│ Cp1: 185.79 pF         │ L1: 561.39 nH          │
│ Cp2: 216.72 pF         │ L2: 561.39 nH          │
│ Cp3: 185.79 pF         │ L3: 561.39 nH          │
└────────────────────────┴────────────────────────┘
Inductors: wind to value (see toroid recommendations)

┌────────────────────────┐
│  Coupling Capacitors   │
├────────────────────────┤
│ Ce_in: 35.73 pF        │
│ Cs12: 3.92 pF          │
│ Cs23: 3.92 pF          │
│ Ce_out: 35.73 pF       │
└────────────────────────┘

External Q (input):  40.50 (realized by Ce_in)
External Q (output): 40.50 (realized by Ce_out)

E24 Standard Capacitor Recommendations
─────────────────────────────────────────────
(Calculated values with nearest standard matches)

Cp1 Calculated: 185.79 pF
  Nearest Std:  180.00 pF (-3.1%)
  Parallel Std: 36.00 pF || 150.00 pF (+0.1%)
Cp2 Calculated: 216.72 pF
  Nearest Std:  220.00 pF (+1.5%)
  Parallel Std: 36.00 pF || 180.00 pF (-0.3%)
Cp3 Calculated: 185.79 pF
  Nearest Std:  180.00 pF (-3.1%)
  Parallel Std: 36.00 pF || 150.00 pF (+0.1%)
Ce_in Calculated: 35.73 pF
  Nearest Std:  36.00 pF (+0.8%)
  Parallel Std: 5.60 pF || 30.00 pF (-0.4%)
Cs12 Calculated: 3.92 pF
  Nearest Std:  3.90 pF (-0.5%)
  Parallel Std: 620.00 fF || 3.30 pF (-0.0%)
Cs23 Calculated: 3.92 pF
  Nearest Std:  3.90 pF (-0.5%)
  Parallel Std: 620.00 fF || 3.30 pF (-0.0%)
Ce_out Calculated: 35.73 pF
  Nearest Std:  36.00 pF (+0.8%)
  Parallel Std: 5.60 pF || 30.00 pF (-0.4%)
```

**Note:** External Q values shown indicate the series end-coupling capacitors (Ce_in/Ce_out) realize the designed external Q at the specified impedance. See [filter-theory.md](filter-theory.md) for design details.

---

## JSON Output

```bash
uv run filter-calc lp bw pi 10MHz -n 3 --format json
```

```json
{
  "capacitors": [
    {"value": 196.732, "unit": "pF", "order": 1},
    {"value": 636.621, "unit": "pF", "order": 2},
    {"value": 196.732, "unit": "pF", "order": 3}
  ],
  "inductors": [
    {"value": 1.29, "unit": "µH", "order": 1},
    {"value": 1.29, "unit": "µH", "order": 2}
  ],
  "response_type": "Butterworth",
  "filter_type": "lowpass",
  "topology": "Pi",
  "order": 5,
  "impedance": 50,
  "cutoff_frequency_hz": 10000000
}
```

---

## CSV Output

```bash
uv run filter-calc lp bw pi 10MHz -n 3 --format csv
```

```
component_type,order,calculated_value,unit
capacitor,1,196.732,pF
capacitor,2,636.621,pF
capacitor,3,196.732,pF
inductor,1,1.29,µH
inductor,2,1.29,µH
```

---

## Frequency Response Data Export

**JSON export (analytic for LP/HP, netlist-simulated for BP):**

```bash
uv run filter-calc lp bw pi 10MHz --plot-data json
```

```json
{
  "metadata": {
    "response_type": "Butterworth",
    "filter_type": "lowpass",
    "order": 5,
    "impedance": 50,
    "cutoff_frequency_hz": 10000000,
    "timestamp": "2026-06-12T10:45:22"
  },
  "frequency_response": [
    {"frequency_hz": 1000000, "magnitude_db": -0.02},
    {"frequency_hz": 2000000, "magnitude_db": -0.03},
    {"frequency_hz": 5000000, "magnitude_db": -0.08},
    {"frequency_hz": 10000000, "magnitude_db": -3.0},
    {"frequency_hz": 20000000, "magnitude_db": -24.3},
    {"frequency_hz": 50000000, "magnitude_db": -65.2},
    {"frequency_hz": 100000000, "magnitude_db": -104.8}
  ]
}
```

**CSV export:**

```bash
uv run filter-calc lp bw pi 10MHz --plot-data csv
```

```
frequency_hz,magnitude_db
1000000,-0.02
2000000,-0.03
5000000,-0.08
10000000,-3.0
20000000,-24.3
50000000,-65.2
100000000,-104.8
```

---

## Filter Explanation

```bash
uv run filter-calc lp ch --explain
```

```
Chebyshev filters offer a steeper roll-off than Butterworth in the transition band,
at the cost of passband ripple. They are useful when you need tight attenuation in
a narrow transition region and can tolerate some passband variation.

Chebyshev filters are defined by their ripple specification (in dB). Ripple must be
in the range 0 < ripple ≤ 3.0 dB. Common choices: 0.1 dB (tight), 0.5 dB (moderate),
1.0 dB (loose). Higher ripple produces sharper roll-off but more passband variation.

For equal source/load terminations, Chebyshev filters require odd order (3, 5, 7, 9).
```

---

## Wizard Mode

Start the interactive wizard:

```bash
uv run filter-calc
# or
uv run filter-calc wizard
# or (short alias)
uv run filter-calc w
```

The wizard guides you through:

1. **Filter Selection** — Choose lowpass, highpass, or bandpass
2. **Configuration** — Set response type, frequency, impedance, order, ripple (if Chebyshev)
3. **Output Options** — Choose E-series matching, output format, export settings
4. **Results** — View calculated components and (optionally) frequency response plot

All screens include keyboard navigation help and accept default values via Enter.

---

## Version Information

```bash
uv run filter-calc --version
```

```
filter-calc 2.0.0
```

