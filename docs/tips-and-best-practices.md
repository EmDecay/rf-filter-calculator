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

### When to Use Bessel

- Pulse/digital signals where shape matters
- Timing-critical applications
- When phase linearity is important
- Accept that rolloff will be gentler

---

## E-Series Selection

### E12 (±10%)

- Fewest choices, easiest to source
- Good for prototyping
- Acceptable when exact values aren't critical

### E24 (±5%)

- Default, good balance of availability and precision
- Suitable for most RF applications
- Recommended starting point

### E96 (±1%)

- Best accuracy
- Use for critical filters
- May be harder to source locally
- Worth it for bandpass filters

### Parallel Combinations

The calculator suggests parallel combinations that can achieve tighter tolerances than single components. For capacitors, values add directly. For inductors, the parallel formula applies.

Example: Need 196.73 pF
- Single E24: 200 pF (+1.7% error)
- Parallel: 47 pF || 150 pF (+0.1% error)

---

## Bandpass Filter Tips

### Frequency Specification

**Method 1: Center + Bandwidth** (`-f` and `-b`)
- More intuitive for band planning
- Center frequency at geometric mean

**Method 2: Edge frequencies** (`--fl` and `--fh`)
- More precise control
- Calculator computes geometric center

### Coupling Topology Selection

**Top-coupled (series)**: Default choice
- More common in amateur applications
- Easier to tune

**Shunt-coupled (parallel)**:
- Alternative for specific impedance requirements
- May work better at certain frequency ranges

### Resonator Count

- Start with 2-3 resonators for prototyping
- 5-7 for good selectivity
- Odd numbers required for Chebyshev
- More resonators = narrower transition band but more loss

### Q Safety Factor

Default is 2.0. Consider increasing to 3.0 or higher when:
- Using low-Q components
- Filter is narrowband (fractional BW < 5%)
- Operating at higher frequencies

---

## Practical Construction Tips

### Capacitors

- Use NP0/C0G ceramics for RF (best stability)
- Avoid X7R/Y5V for filter applications
- Silver mica excellent but expensive
- Measure actual values before assembly

### Inductors

- Air-core for highest Q at RF
- Toroidal ferrites for lower frequencies
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
uv run filter-calc lp bw 10MHz --format json | jq '.components'
```

### CSV

Best for:
- Spreadsheet import
- Component ordering
- Documentation

```bash
uv run filter-calc lp bw 10MHz --format csv > bom.csv
```

---

## Workflow Recommendations

### Design Iteration

1. Start with `--explain` to understand filter types
2. Run with no arguments for the wizard if unfamiliar with designs
3. Try different orders: `uv run filter-calc lp bw 10MHz -n 3` vs `-n 5`
4. Compare Butterworth vs Chebyshev at same order
5. Use `--plot` to visualize response

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
    uv run filter-calc lp bw ${freq}MHz -n 5 --format json
done > all_designs.json
```

---

## Common Amateur Radio Frequencies

| Band | Center | Example Command |
|------|--------|-----------------|
| 160m | 1.9 MHz | `lp bw 1.9MHz -n 5` |
| 80m | 3.75 MHz | `lp bw 3.75MHz -n 5` |
| 40m | 7.15 MHz | `lp bw 7.15MHz -n 5` |
| 20m | 14.175 MHz | `bp bw top -f 14.175MHz -b 350kHz` |
| 15m | 21.2 MHz | `lp bw 21.2MHz -n 5` |
| 10m | 28.5 MHz | `lp bw 28.5MHz -n 5` |
