# Tips & Best Practices

Get the most out of RF Filter Calculator.

---

## Choosing Filter Type

### When to Use Butterworth

- Default choice for most applications
- When flat passband response is important
- Audio applications
- When you're unsure which to pick

### When to Use Chebyshev

- Need steeper rolloff with fewer components
- Can tolerate some passband ripple
- Adjacent channel rejection is critical
- Start with 0.5 dB ripple, increase only if needed
- Use an odd order (3, 5, 7, or 9 components or resonators); equal source and load
  terminations require it, and even orders are rejected

### When to Use Bessel

- Pulse/digital signals where shape matters
- Timing-critical applications
- When phase linearity is important
- Accept that rolloff will be gentler
- For bandpass, the LP→BP transformation does not preserve maximally flat group delay;
  verify phase/group delay externally

---

## E-Series Selection

### E12 (12 values per decade)

- Fewest choices, easiest to source
- Good for prototyping
- Acceptable when exact values aren't critical

### E24 (24 values per decade)

- Default, good balance of availability and precision
- Suitable for most RF applications
- Recommended starting point

### E96 (96 values per decade)

- Best accuracy
- Use for critical filters
- May be harder to source locally
- Worth it for bandpass filters

### Parallel Combinations

The E-series sets how many standard values there are per decade, not the component
tolerance. Each capacitor gets one choice: a single part when it is within 1% of the target,
otherwise two in parallel when the pair is at least 0.5 percentage points closer. Below 1 pF
no part is chosen automatically; add `--allow-sub-pf` (**Allow capacitors below 1 pF** in the
wizard and web UI) to have those chosen too. Inductors are not E-series matched; a toroid
winding suggestion is an option, not a suitability claim.

Example: Need 196.73 pF (`uv run filter-calc lp bw pi 10MHz -n 5`)
- `Use:` 47 pF || 150 pF (+0.1% error)
- `Nearest single:` 200 pF (+1.7% error)

---

## Bandpass Filter Tips

### Frequency Specification

**Method 1: Center + Bandwidth** (`-f` and `-b`)
- More intuitive for band planning
- Center frequency at geometric mean

**Method 2: Edge frequencies** (`--fl` and `--fh`)
- More precise control
- Calculator computes geometric center

### Coupling

**Top-C (series capacitors)** is the only supported coupling: series capacitors couple adjacent resonators, and series end-coupling capacitors (Ce_in/Ce_out) set the external Q at the ports. (Shunt-coupled topology was removed in v2.0.0 — netlist simulation showed it cannot realize the designed passband.)

### Resonator Count

- Start with 2-3 resonators for prototyping
- 5-7 for good selectivity
- Odd numbers required for Chebyshev
- More resonators = narrower transition band but more loss

### Q and Loss

The historical Q-safety field is only a compatibility heuristic; it does not determine
stability or select parts. For a real loss model:

- use `--qu` for the resonator Qu (inductor and capacitor losses together), or `--ql` and
  `--qc` for separate inductor and resonator-capacitor Q;
- use `--inductor-q` / `--capacitor-q` with the build simulation for part losses (Q);
- remember that each Q becomes a fixed series resistance at one frequency (the frequency at
  which the Q values apply);
- verify insertion loss and bandwidth on a VNA after construction.

---

## Practical Construction Tips

### Capacitors

- Use NP0/C0G ceramics for RF (best stability)
- Avoid X7R/Y5V for filter applications
- Silver mica excellent but expensive
- Measure actual values before assembly

### Inductors

- Air-core for highest Q at RF
- Choose core material from manufacturer frequency/loss data; the built-in toroid winding
  suggestions currently cover only primary-sourced T25-6, T50-2, and T68-2 iron-powder cores
- Consider using adjustable cores for tuning
- Minimize lead length

### Layout

- Keep leads short
- Separate input/output to prevent coupling
- Use ground plane
- Shield if necessary

### Tuning

1. Build filter
2. Measure frequency response
3. Adjust inductors (if adjustable) to center frequency
4. Fine-tune coupling capacitors for bandwidth

---

## Output Format Selection

### Table (default)

Best for:
- Quick visual inspection
- Understanding topology
- Getting component values

### JSON

Best for:
- Scripting and automation
- Integration with other tools
- Preserving full precision

```bash
uv run filter-calc lp bw pi 10MHz --format json | jq '.components'
```

### CSV

Best for:
- Spreadsheet import
- Component ordering
- Documentation

```bash
uv run filter-calc lp bw pi 10MHz --format csv > bom.csv
```

### SPICE

Best for reviewing the calculated values or the chosen parts in another simulator. The deck
does not include layout, package parasitics, measured core loss, SRF, or nonlinear power
behavior unless you add suitable models.

---

## Workflow Recommendations

### Design Iteration

1. Start with `--explain` to understand filter types
2. Run with no arguments for the wizard, or `uv run filter-calc web` for the browser page, if
   unfamiliar with the options; both show the same results the CLI prints
3. Try different orders: `uv run filter-calc lp bw pi 10MHz -n 3` vs `-n 5`
4. Compare Butterworth vs Chebyshev at same order
5. Use `--plot` to visualize response
6. Run `--sim-build --format json` with actual tolerances and Q assumptions
7. Export the chosen-parts SPICE deck if useful, then build and measure the hardware

### Documentation

```bash
# Save complete design
uv run filter-calc bp bw top -f 14.175MHz -b 350kHz -n 5 > design.txt

# Save response data for external plotting
uv run filter-calc bp bw top -f 14.175MHz -b 350kHz --plot-data json > response.json
```

### Scripting

```bash
#!/bin/bash
for freq in 7.1 14.175 21.2 28.5; do
    echo "=== ${freq} MHz filter ==="
    uv run filter-calc lp bw pi ${freq}MHz -n 5 --format json
done > all_designs.json
```

---

## Common Amateur Radio Frequencies

| Band | Center | Example Command |
|------|--------|-----------------|
| 160m | 1.9 MHz | `lp bw pi 1.9MHz -n 5` |
| 80m | 3.75 MHz | `lp bw pi 3.75MHz -n 5` |
| 40m | 7.15 MHz | `lp bw pi 7.15MHz -n 5` |
| 20m | 14.175 MHz | `bp bw top -f 14.175MHz -b 350kHz` |
| 15m | 21.2 MHz | `lp bw pi 21.2MHz -n 5` |
| 10m | 28.5 MHz | `lp bw pi 28.5MHz -n 5` |
