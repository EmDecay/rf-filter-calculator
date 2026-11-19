# Component Data Sources

This page records the sourced part data and the coverage evidence behind the planned VHF/UHF
part suggestions (designs up to about 450 MHz): fixed capacitor tolerances, chip inductors,
VHF toroids, air-core coils and trimmer capacitors. It also records which kinds of inductor
can cover the acceptance designs, and why the others are not offered.

**Status (2026-11-19): evidence only.** No calculator output uses this data yet. When a feature
packages part of it as a data file, the packaged rows must match this page and cite the same
sources; a data change updates this page in the same change.

## How to read this page

- Every value comes from a primary source: the manufacturer's own datasheet, specification or
  catalog for an exact orderable part or grade, or a published formula used inside its stated
  validated range. Distributor pages are never used as evidence.
- Each value states its **guarantee type** in the source's own terms:
  - **minimum** or **maximum**: a specification limit (for example a column headed "SRF min",
    or a tolerance given as the rated value of the part);
  - **typical**: a characteristic value, not a limit;
  - **reference-only**: printed for information, explicitly not controlled.
  Only minimum or maximum figures may qualify a part.
- Each value states its **test conditions** (frequency, fixture, setting) where the source
  gives them.
- Source IDs in square brackets, for example [CC-0603CS], point to the
  [source index](#source-index), which gives the title, revision or date, URL and the SHA-256
  of the copy that was read. All sources were retrieved on 2026-11-19.

## Acceptance designs and limits

These four designs define what the suggestions must cover. Values are from
`uv run filter-calc ... --format json` on `main` at d8c550f.

| Design | Inductors | Check window | C_self limit for 5 % drift | SRF needed if f_m ≪ SRF |
|---|---|---|---|---|
| `lp ch pi 146MHz -n 5 -r 0.1` | L1, L2 = 74.7381 nH | DC to 146 MHz (cutoff) | 0.757 pF | ≥ 669 MHz |
| `lp ch pi 222MHz -n 5 -r 0.1` | L1, L2 = 49.1521 nH | DC to 222 MHz | 0.498 pF | ≥ 1017 MHz |
| `lp ch pi 440MHz -n 5 -r 0.1` | L1, L2 = 24.7995 nH | DC to 440 MHz | 0.251 pF | ≥ 2016 MHz |
| `bp ch top -f 146MHz -b 4MHz -n 3 -r 0.5` | L1–L3 = 54.5148 nH | DC to 148.0137 MHz (upper −3 dB edge) | 1.010 pF | ≥ 678 MHz |

- The check window is the low-pass passband up to the cutoff, and the band-pass passband up to
  the upper −3 dB edge. A high-pass design is checked from the cutoff to 2 × cutoff.
- The capacitance limit is the largest parallel capacitance that keeps the inductance drift at
  the top of the window within 5 %: C ≤ (1 − 1/1.05) / ((2πf)²·L). With f_m ≪ SRF that is
  SRF ≥ √21·f ≈ 4.583·f. These two columns are a reference case only: the chip screen below
  uses each part's real test frequency f_m, so a part slightly below this SRF can still pass.
- **Band-pass coupling.** The 146 MHz band-pass needs Cs12 = Cs23 = 0.38634 pF with its
  54.51 nH tanks, which is below the 1 pF floor for a chosen part. The coupling capacitance
  scales roughly as 1/L, so the estimate for 1 pF is 54.5148 × 0.38634 = 21.061 nH. Reruns with
  `--tank-inductance` (all with a passing response check):

| Tank L | Cs12 = Cs23 | Ce_in = Ce_out | Cp1 / Cp2 | Every coupling capacitor ≥ 1 pF |
|---|---|---|---|---|
| 18 nH | 1.16936 pF | 4.7030 pF | 60.378 / 63.703 pF | yes |
| 19 nH | 1.10785 pF | 4.5721 pF | 57.078 / 60.350 pF | yes |
| 20 nH | 1.05249 pF | 4.4515 pF | 54.112 / 57.332 pF | yes |
| 21 nH | 1.00241 pF | 4.3400 pF | 51.430 / 54.602 pF | yes |
| 21.0117 nH | 1.00185 pF | 4.3387 pF | 51.400 / 54.572 pF | yes |
| 21.06 nH | 0.99955 pF | 4.3336 pF | 51.277 / 54.447 pF | no |
| 22 nH | 0.95687 pF | 4.2365 pF | 48.995 / 52.120 pF | no |

  21.0117 nH is the effective inductance at the 145.974 MHz tank frequency of the 21 nH part
  named in [Coverage](#coverage-of-the-acceptance-designs). The inverse-L estimate itself
  (21.06 nH) misses the floor, so the advice must use a value a part actually supplies.

## Fixed capacitors: Murata GRM1885C1H…A01

**Series.** Murata GRM, 1608M (0603), 0.8 mm thick, C0G (EIA), DC 50 V, individual
specification A01; the orderable part number adds one packaging letter (D, W, J or V)
[MU-GRM]. It is the only candidate that meets all three needs: absolute pF tolerances below
10 pF, ±5 % above the crossover, and a range reaching HF values. The runner-up, Murata
GJM1555C1H (0402 high-Q), stops at 47 pF [MU-GJM-47] and cannot cover HF designs.

**Guarantee and conditions.** Each per-part document is a "Reference Sheet" that says "Please
consult the approval sheet before ordering." Its Specifications and Test Methods table, item 6
"Capacitance", reads "Shown in Rated value", and the Rated Value line gives the tolerance as a
specification limit (not typical). Measured at room temperature, 1.0 ± 0.1 MHz and 0.5–5.0 Vrms
up to 1000 pF, and at 1.0 ± 0.1 kHz and 1.0 ± 0.2 Vrms from 1100 pF [MU-GRM, p. 3]. No fixture
is named. The temperature coefficient is 0 ± 30 ppm/°C; temperature drift is on top of the
tolerance.

### Tolerance grades

| Value range | Codes found (sheet available) | Standard | Tight | Evidence (Rated Value line, p. 2) |
|---|---|---|---|---|
| 0.5–0.9 pF (0.1 pF steps) | W ±0.05 pF, B ±0.1 pF | B ±0.1 pF | W ±0.05 pF | GRM1885C1HR50BA01: "0.5pF +/-0.1pF" |
| 1.0–5.0 pF (0.1 pF steps) | W, B, C ±0.25 pF | C ±0.25 pF | B ±0.1 pF | GRM1885C1H1R0CA01: "1pF +/-0.25pF"; GRM1885C1H4R3CA01: "4.3pF +/-0.25pF" |
| 5.1–9.9 pF (0.1 pF steps) | W, B, C, D ±0.5 pF | D ±0.5 pF | C ±0.25 pF | GRM1885C1H5R1DA01: "5.1pF +/-0.5pF"; GRM1885C1H9R1DA01: "9.1pF +/-0.5pF" |
| 10–910 pF (E24) | G ±2 %, J ±5 % | J ±5 % | G ±2 % | GRM1885C1H100JA01: "10pF +/-5%"; GRM1885C1H911GA01: "910pF +/-2%" |
| 1000–10 000 pF (E24) | J ±5 % only | J ±5 % | J ±5 % (no tighter current sheet found) | GRM1885C1H102JA01: "1000pF +/-5%"; GRM1885C1H103JA01: "10000pF +/-5%" |

- **Crossover.** Absolute pF tolerances stop at 9.9 pF; percentage tolerances start at 10 pF.
  The standard grade is almost continuous there: ±0.5 pF at 9.9 pF, ±0.5 pF (5 %) at 10 pF.
- **F and K codes.** No current reference sheet was found for an F (±1 %) or K (±10 %) part.
  F parts have existed: a Murata reference sheet as of Mar. 31, 2012 covers GRM1885C1H102FA01
  (1000 pF) [MU-GRM-102F-2012]. Whether any is still orderable is not verified, so the table
  uses only codes with a current sheet.
- **Standard and tight.** Murata's GJM lineup page names a "Standard Capacitance Tolerance"
  and a "Narrow Capacitance Tolerance" for each range [MU-GJM-LINEUP]: ≤0.9 pF B / W;
  1–5 pF C / W, B; 5.1–9.9 pF D / W, B, C; ≥10 pF J / G. The GRM availability boundaries match
  that table exactly, but the GRM page has no such table, so the designation is carried over by
  analogy. **Standard** is Murata's standard code. **Tight** is the loosest of Murata's narrow
  codes, which is one step tighter than standard. Every code in the
  table has a current sheet, so a tighter custom choice (W everywhere below 10 pF) remains
  possible.
- **Ineligible parts.** None: the smallest part is 0.5 pF with at most ±0.1 pF. The worst
  relative standard tolerances are 0.5 pF B (±20 %) and 1.0 pF C (±25 %).
- **Lifecycle.** Not verified. Murata shows lifecycle status only on script-rendered product
  pages. A current reference sheet shows the part base is catalogued, not that every packaging
  suffix is still sold.

### Value coverage

Coverage was established by requesting Murata's per-part reference sheet (976 requests for
970 distinct part numbers), because Murata no longer publishes ceramic-capacitor catalogs
[MU-FAQ-CATALOG]. 450 distinct parts across 168 values answered HTTP 200. That is a status
check: the 14 GRM sheets listed in the source index were downloaded and read. A refused request (HTTP 403)
is recorded only as "not found": it does not prove that a part is not made.

- Sheets were found for 0.5 to 9.9 pF in 0.1 pF steps and for every E24 value from 10 pF to
  10 nF. None was found below 0.5 pF or above 10 nF (every E24 value from 11 to 91 nF was
  requested).
- **E12 and E24:** every value from 1.0 pF to 10 nF has a sheet; no value below 1 pF does.
- **E96:** the capacitance code has only two significant digits, so a three-digit value such
  as 1.02 pF cannot be ordered in this series. Of the 481 E96 values from 0.1 pF to 10 nF, the
  30 with two significant digits have a sheet (1.0, 1.1, 1.3, 1.4, 1.5, 2.0, 2.1, 2.8, 3.4, 5.9,
  7.5, 10, 11, 13, 15, 20, 75, 100, 110, 130, 150, 200, 750, 1000, 1100, 1300, 1500, 2000, 7500 and
  10 000 pF).

**HF designs outside the series.** A survey of 1872 HF ladder designs (low-pass and high-pass,
Pi and T, 50 Ω, cutoffs 1.8–30 MHz at amateur band edges, Butterworth and Bessel orders 3–9,
Chebyshev orders 3, 5, 7, 9 at 0.1, 0.5 and 1 dB; 5616 capacitors from 8.3 pF to 22.7 nF) gives,
using today's part choices:

| Series | Capacitors with a part outside the series coverage | Why |
|---|---|---|
| E12 | 6 of 5616 (0.1 %) | a part above 10 nF (Bessel high-pass T at 1.8 and 2 MHz) |
| E24 | 5 of 5616 (0.1 %) | a part above 10 nF (same designs) |
| E96 | 5328 of 5616 (94.9 %) | a three-significant-digit value (5043); a two-digit value the series does not make above 10 pF, such as 3400 pF (277); or only a part above 10 nF (8) |

Those capacitors keep today's nominal rule, labelled "tolerance not sourced".

**Worked example.** For 13.4744 pF with E24 values from 1 pF, a 10:1 pair limit and a 0.2 pF
stray allowance for the second part of a pair, an exhaustive search over this table gives:

| Grade | Best single (score) | Best pair (score) |
|---|---|---|
| Standard | 13 pF (1.1244 pF) | 4.3 ∥ 9.1 pF (0.8756 pF) |
| Tight | 13 pF (0.7344 pF) | 2.4 ∥ 11 pF (0.4456 pF) |

A candidate's score is the larger distance from the target to either end of its interval
(nominal − tolerance to nominal + tolerance + stray).

## Layout stray

No manufacturer or published measurement gives a pad-to-pad (across-the-terminals) stray
capacitance for an 0603 capacitor footprint. **The 0.2 pF allowance per extra part stays a
labelled, user-configurable assumption.** The nearest primary data measures something else:

- Johanson [JT-MOUNT]: pad and body capacitance to ground of about 0.03 pF each for a series
  mounting on 0.025 in FR-4 over a ground plane (model fitted to measured S-parameters; "makes
  no warranty"). It is shunt to ground, not across the part.
- Vishay [VI-TN0004]: 0.0403 pF internal shunt capacitance of an 0603 thin-film resistor on
  quartz. It is a resistor body, not a capacitor pair on FR-4.
- Murata [MU-SIM-COND]: the 1608M land pattern (a = 0.8, b = 0.7, c = 0.8 mm), with land effects
  removed from the published data. It gives no stray value.

## Chip inductors

A chip inductor qualifies only with a guaranteed inductance tolerance, a guaranteed minimum
SRF and a guaranteed minimum Q (Q is shown, never used for ranking).

### Qualifying families

| Manufacturer | Families | Wording that qualifies them | Sources |
|---|---|---|---|
| Coilcraft | 0603CS, 0603HC, 0604HQ, 0805HQ, 0805HT, 1008CS, 1008CT, 1008HQ, 1008HT, 1206CS | Column headers "Q min" and "SRF min"; "Electrical specifications at 25°C" | [CC-0603CS], [CC-0603HC], [CC-0604HQ], [CC-0805HQ], [CC-0805HT], [CC-1008CS], [CC-1008CT], [CC-1008HQ], [CC-1008HT], [CC-1206CS] |
| Murata | LQW15AN_00, LQW15AN_80, LQW15AW_80, LQW18AN_00, LQW18AN_10, LQW18AN_80, LQW18AS_00, LQW18AS_0C, LQW2BAN_00, LQW2BAS_00, LQW2BAS_0C, LQW2UAS_00, LQW2UAS_0C | Rating table headers "Q (Min.)" and "Self-resonant frequency (MHz min.)" or "(GHz min.)"; §7 "Meet chapter 3 ratings" | [MU-LQW15AN-00], [MU-LQW15AN-80], [MU-LQW15AW-80], [MU-LQW18AN-00], [MU-LQW18AN-10], [MU-LQW18AN-80], [MU-LQW18AS-00], [MU-LQW18AS-0C], [MU-LQW2BAN-00], [MU-LQW2BAS-00], [MU-LQW2BAS-0C], [MU-LQW2UAS-00], [MU-LQW2UAS-0C] |
| Johanson | LRW0402W, LRW0603W, LRW0805W | Per-part charts headed "Q (min.)" and "SRF (min.)". Lower confidence: the series summary is labelled "(Typ.)", no fixture is named, no revision is printed, and the 0402 chart stops at 30 nH | [JO-WW] |

**Excluded** (the wording that excludes them):

| Family | Wording | Reason | Sources |
|---|---|---|---|
| Coilcraft 0603HP, 0402HP, 0805HP | "Q typ", "SRF typ" | Q and SRF typical | [CC-0603HP], [CC-0402HP], [CC-0805HP] |
| Coilcraft 0402CS | "SRF min" but "Q typ" | no Q minimum | [CC-0402CS] |
| Coilcraft 0805CS, 0403HQ | "Q min" but "SRF typ" | SRF typical | [CC-0805CS], [CC-0403HQ] |
| Coilcraft 0402DC, 0603DC | "Q typ", "SRF typ" | typical only | [CC-0402DC], [CC-0603DC] |
| Murata LQW15CN_00, LQW18CN_00 | SRF "(MHz min.)" but no Q column | no Q guarantee | [MU-LQW15CN-00], [MU-LQW18CN-00] |
| TDK | product.tdk.com refused both download routes (HTTP 403) | not verified | — |

Coilcraft's web part pages do not list the 1 % (F) variants that the 1008CS/CT/HQ/HT, 1206CS
and 0805HT datasheets print, so Coilcraft 1 % parts are left out. Murata's 1 % parts (for
example LQW2UAS47NF00L, [MU-LQW2UAS-00] p. 2) are in its specifications; none of the recommended families below
offers 1 % between 10 and 100 nH.

### Recommended catalog

The coverage below needs only four 0402/0603 families, all with named fixtures and minimum
SRF and Q columns. Larger packages and Johanson add nothing the acceptance designs need.

| Family | Package | L test | Q test | Tolerances | Measurement (as stated) | Source |
|---|---|---|---|---|---|---|
| Coilcraft 0603CS | 0603 (1608) | per row: 250 MHz to 43 nH, 200 MHz 47–68 nH, 150 MHz 72–150 nH | same as L | G 2 %, H 3 %, J 5 % | L: Coilcraft SMD-A fixture, Agilent/HP 4286; Q: HP 4291A with 16193 fixture; SRF: HP 8720D with Coilcraft SMD-D fixture | [CC-0603CS] p. 2 |
| Murata LQW18AN_00 | 0603 (1608) | 100 MHz | 250 MHz to 39 nH, 200 MHz 43–68 nH, 150 MHz 72–160 nH | G ±2 %, J ±5 % (10–100 nH) | L and Q: Keysight E4991A with 16197A fixture; SRF: Keysight N5230A | [MU-LQW18AN-00] pp. 2–4 |
| Murata LQW18AN_80 | 0603 (1608) | 100 MHz | 250 MHz to 44 nH, 200 MHz 47–69 nH, 150 MHz 72–150 nH | G ±2 %, J ±5 % | as LQW18AN_00 | [MU-LQW18AN-80] |
| Murata LQW15AN_80 | 0402 (1005) | 100 MHz | 250 MHz to 43 nH, 200 MHz 47–75 nH | G ±2 %, J ±5 % | L and Q as LQW18AN_00; SRF: Keysight N5230 | [MU-LQW15AN-80] pp. 6–9 |

Murata's documents are "reference specifications" that ask buyers to approve the product
specification or obtain the approval sheet before ordering, like the capacitor reference
sheets above.

**Catalog rows, 10–100 nH.** Every value the four families make in that range. L is the
nominal value at the stated test frequency; the tolerance code replaces the `_` in the part
number (Coilcraft also needs termination R and packaging W, as shown); SRF and Q are
minimums. Values outside 10–100 nH were not collected.

| Part (tolerance code at _) | L at test | Tolerances | SRF min | Q min at | Source |
|---|---|---|---|---|---|
| 0603CS-10NX_RW | 10 nH at 250 MHz | G 2 %, H 3 %, J 5 % | 4800 MHz | 31 at 250 MHz | [CC-0603CS] p. 2 |
| 0603CS-11NX_RW | 11 nH at 250 MHz | G 2 %, H 3 %, J 5 % | 4000 MHz | 30 at 250 MHz | [CC-0603CS] p. 2 |
| 0603CS-12NX_RW | 12 nH at 250 MHz | G 2 %, H 3 %, J 5 % | 4000 MHz | 35 at 250 MHz | [CC-0603CS] p. 2 |
| 0603CS-15NX_RW | 15 nH at 250 MHz | G 2 %, H 3 %, J 5 % | 4000 MHz | 35 at 250 MHz | [CC-0603CS] p. 2 |
| 0603CS-16NX_RW | 16 nH at 250 MHz | G 2 %, H 3 %, J 5 % | 3300 MHz | 34 at 250 MHz | [CC-0603CS] p. 2 |
| 0603CS-18NX_RW | 18 nH at 250 MHz | G 2 %, H 3 %, J 5 % | 3100 MHz | 35 at 250 MHz | [CC-0603CS] p. 2 |
| 0603CS-22NX_RW | 22 nH at 250 MHz | G 2 %, H 3 %, J 5 % | 3000 MHz | 38 at 250 MHz | [CC-0603CS] p. 2 |
| 0603CS-23NX_RW | 23 nH at 250 MHz | G 2 %, H 3 %, J 5 % | 2850 MHz | 38 at 250 MHz | [CC-0603CS] p. 2 |
| 0603CS-24NX_RW | 24 nH at 250 MHz | G 2 %, H 3 %, J 5 % | 2650 MHz | 36 at 250 MHz | [CC-0603CS] p. 2 |
| 0603CS-27NX_RW | 27 nH at 250 MHz | G 2 %, H 3 %, J 5 % | 2800 MHz | 40 at 250 MHz | [CC-0603CS] p. 2 |
| 0603CS-30NX_RW | 30 nH at 250 MHz | G 2 %, H 3 %, J 5 % | 2250 MHz | 37 at 250 MHz | [CC-0603CS] p. 2 |
| 0603CS-33NX_RW | 33 nH at 250 MHz | G 2 %, H 3 %, J 5 % | 2300 MHz | 40 at 250 MHz | [CC-0603CS] p. 2 |
| 0603CS-36NX_RW | 36 nH at 250 MHz | G 2 %, H 3 %, J 5 % | 2080 MHz | 37 at 250 MHz | [CC-0603CS] p. 2 |
| 0603CS-39NX_RW | 39 nH at 250 MHz | G 2 %, H 3 %, J 5 % | 2200 MHz | 40 at 250 MHz | [CC-0603CS] p. 2 |
| 0603CS-43NX_RW | 43 nH at 250 MHz | G 2 %, H 3 %, J 5 % | 2000 MHz | 38 at 250 MHz | [CC-0603CS] p. 2 |
| 0603CS-47NX_RW | 47 nH at 200 MHz | G 2 %, H 3 %, J 5 % | 2000 MHz | 38 at 200 MHz | [CC-0603CS] p. 2 |
| 0603CS-51NX_RW | 51 nH at 200 MHz | G 2 %, H 3 %, J 5 % | 1900 MHz | 35 at 200 MHz | [CC-0603CS] p. 2 |
| 0603CS-56NX_RW | 56 nH at 200 MHz | G 2 %, H 3 %, J 5 % | 1900 MHz | 38 at 200 MHz | [CC-0603CS] p. 2 |
| 0603CS-68NX_RW | 68 nH at 200 MHz | G 2 %, H 3 %, J 5 % | 1700 MHz | 37 at 200 MHz | [CC-0603CS] p. 2 |
| 0603CS-72NX_RW | 72 nH at 150 MHz | G 2 %, H 3 %, J 5 % | 1700 MHz | 34 at 150 MHz | [CC-0603CS] p. 2 |
| 0603CS-82NX_RW | 82 nH at 150 MHz | G 2 %, H 3 %, J 5 % | 1700 MHz | 34 at 150 MHz | [CC-0603CS] p. 2 |
| 0603CS-R10X_RW | 100 nH at 150 MHz | G 2 %, H 3 %, J 5 % | 1400 MHz | 34 at 150 MHz | [CC-0603CS] p. 2 |
| LQW18AN10N_00D | 10 nH at 100 MHz | G 2 %, J 5 % | 6000 MHz | 35 at 250 MHz | [MU-LQW18AN-00] p. 2 |
| LQW18AN11N_00D | 11 nH at 100 MHz | G 2 %, J 5 % | 6000 MHz | 35 at 250 MHz | [MU-LQW18AN-00] p. 2 |
| LQW18AN12N_00D | 12 nH at 100 MHz | G 2 %, J 5 % | 6000 MHz | 35 at 250 MHz | [MU-LQW18AN-00] p. 2 |
| LQW18AN13N_00D | 13 nH at 100 MHz | G 2 %, J 5 % | 6000 MHz | 35 at 250 MHz | [MU-LQW18AN-00] p. 2 |
| LQW18AN15N_00D | 15 nH at 100 MHz | G 2 %, J 5 % | 6000 MHz | 40 at 250 MHz | [MU-LQW18AN-00] p. 2 |
| LQW18AN16N_00D | 16 nH at 100 MHz | G 2 %, J 5 % | 5500 MHz | 40 at 250 MHz | [MU-LQW18AN-00] p. 2 |
| LQW18AN18N_00D | 18 nH at 100 MHz | G 2 %, J 5 % | 5500 MHz | 40 at 250 MHz | [MU-LQW18AN-00] p. 2 |
| LQW18AN20N_00D | 20 nH at 100 MHz | G 2 %, J 5 % | 4900 MHz | 40 at 250 MHz | [MU-LQW18AN-00] p. 2 |
| LQW18AN22N_00D | 22 nH at 100 MHz | G 2 %, J 5 % | 4600 MHz | 40 at 250 MHz | [MU-LQW18AN-00] p. 2 |
| LQW18AN24N_00D | 24 nH at 100 MHz | G 2 %, J 5 % | 3800 MHz | 40 at 250 MHz | [MU-LQW18AN-00] p. 2 |
| LQW18AN27N_00D | 27 nH at 100 MHz | G 2 %, J 5 % | 3700 MHz | 40 at 250 MHz | [MU-LQW18AN-00] p. 2 |
| LQW18AN30N_00D | 30 nH at 100 MHz | G 2 %, J 5 % | 3300 MHz | 40 at 250 MHz | [MU-LQW18AN-00] p. 2 |
| LQW18AN33N_00D | 33 nH at 100 MHz | G 2 %, J 5 % | 3200 MHz | 40 at 250 MHz | [MU-LQW18AN-00] p. 2 |
| LQW18AN36N_00D | 36 nH at 100 MHz | G 2 %, J 5 % | 2900 MHz | 40 at 250 MHz | [MU-LQW18AN-00] p. 2 |
| LQW18AN39N_00D | 39 nH at 100 MHz | G 2 %, J 5 % | 2800 MHz | 40 at 250 MHz | [MU-LQW18AN-00] p. 2 |
| LQW18AN43N_00D | 43 nH at 100 MHz | G 2 %, J 5 % | 2700 MHz | 40 at 200 MHz | [MU-LQW18AN-00] p. 2 |
| LQW18AN47N_00D | 47 nH at 100 MHz | G 2 %, J 5 % | 2600 MHz | 38 at 200 MHz | [MU-LQW18AN-00] p. 2 |
| LQW18AN51N_00D | 51 nH at 100 MHz | G 2 %, J 5 % | 2500 MHz | 38 at 200 MHz | [MU-LQW18AN-00] p. 2 |
| LQW18AN56N_00D | 56 nH at 100 MHz | G 2 %, J 5 % | 2400 MHz | 38 at 200 MHz | [MU-LQW18AN-00] p. 3 |
| LQW18AN62N_00D | 62 nH at 100 MHz | G 2 %, J 5 % | 2300 MHz | 38 at 200 MHz | [MU-LQW18AN-00] p. 3 |
| LQW18AN68N_00D | 68 nH at 100 MHz | G 2 %, J 5 % | 2200 MHz | 38 at 200 MHz | [MU-LQW18AN-00] p. 3 |
| LQW18AN72N_00D | 72 nH at 100 MHz | G 2 %, J 5 % | 2100 MHz | 34 at 150 MHz | [MU-LQW18AN-00] p. 3 |
| LQW18AN75N_00D | 75 nH at 100 MHz | G 2 %, J 5 % | 2050 MHz | 34 at 150 MHz | [MU-LQW18AN-00] p. 3 |
| LQW18AN82N_00D | 82 nH at 100 MHz | G 2 %, J 5 % | 2000 MHz | 34 at 150 MHz | [MU-LQW18AN-00] p. 3 |
| LQW18AN91N_00D | 91 nH at 100 MHz | G 2 %, J 5 % | 1900 MHz | 34 at 150 MHz | [MU-LQW18AN-00] p. 3 |
| LQW18ANR10_00D | 100 nH at 100 MHz | G 2 %, J 5 % | 1800 MHz | 34 at 150 MHz | [MU-LQW18AN-00] p. 3 |
| LQW18AN10N_80D | 10 nH at 100 MHz | G 2 %, J 5 % | 4750 MHz | 38 at 250 MHz | [MU-LQW18AN-80] p. 2 |
| LQW18AN11N_80D | 11 nH at 100 MHz | G 2 %, J 5 % | 4750 MHz | 40 at 250 MHz | [MU-LQW18AN-80] p. 2 |
| LQW18AN12N_80D | 12 nH at 100 MHz | G 2 %, J 5 % | 5000 MHz | 37 at 250 MHz | [MU-LQW18AN-80] p. 2 |
| LQW18AN13N_80D | 13 nH at 100 MHz | G 2 %, J 5 % | 5000 MHz | 37 at 250 MHz | [MU-LQW18AN-80] p. 2 |
| LQW18AN15N_80D | 15 nH at 100 MHz | G 2 %, J 5 % | 4600 MHz | 38 at 250 MHz | [MU-LQW18AN-80] p. 2 |
| LQW18AN16N_80D | 16 nH at 100 MHz | G 2 %, J 5 % | 4600 MHz | 40 at 250 MHz | [MU-LQW18AN-80] p. 2 |
| LQW18AN17N_80D | 17 nH at 100 MHz | G 2 %, J 5 % | 4600 MHz | 40 at 250 MHz | [MU-LQW18AN-80] p. 2, 3 |
| LQW18AN18N_80D | 18 nH at 100 MHz | G 2 %, J 5 % | 4600 MHz | 40 at 250 MHz | [MU-LQW18AN-80] p. 3 |
| LQW18AN19N_80D | 19 nH at 100 MHz | G 2 %, J 5 % | 4600 MHz | 40 at 250 MHz | [MU-LQW18AN-80] p. 3 |
| LQW18AN22N_80D | 22 nH at 100 MHz | G 2 %, J 5 % | 3450 MHz | 40 at 250 MHz | [MU-LQW18AN-80] p. 3 |
| LQW18AN23N_80D | 23 nH at 100 MHz | G 2 %, J 5 % | 3450 MHz | 40 at 250 MHz | [MU-LQW18AN-80] p. 3 |
| LQW18AN24N_80D | 24 nH at 100 MHz | G 2 %, J 5 % | 3450 MHz | 40 at 250 MHz | [MU-LQW18AN-80] p. 3 |
| LQW18AN25N_80D | 25 nH at 100 MHz | G 2 %, J 5 % | 3600 MHz | 40 at 250 MHz | [MU-LQW18AN-80] p. 3 |
| LQW18AN27N_80D | 27 nH at 100 MHz | G 2 %, J 5 % | 3600 MHz | 40 at 250 MHz | [MU-LQW18AN-80] p. 3 |
| LQW18AN28N_80D | 28 nH at 100 MHz | G 2 %, J 5 % | 3600 MHz | 40 at 250 MHz | [MU-LQW18AN-80] p. 3 |
| LQW18AN30N_80D | 30 nH at 100 MHz | G 2 %, J 5 % | 2880 MHz | 40 at 250 MHz | [MU-LQW18AN-80] p. 3 |
| LQW18AN31N_80D | 31 nH at 100 MHz | G 2 %, J 5 % | 3150 MHz | 40 at 250 MHz | [MU-LQW18AN-80] p. 3 |
| LQW18AN33N_80D | 33 nH at 100 MHz | G 2 %, J 5 % | 3150 MHz | 40 at 250 MHz | [MU-LQW18AN-80] p. 3 |
| LQW18AN34N_80D | 34 nH at 100 MHz | G 2 %, J 5 % | 3000 MHz | 40 at 250 MHz | [MU-LQW18AN-80] p. 3 |
| LQW18AN36N_80D | 36 nH at 100 MHz | G 2 %, J 5 % | 3000 MHz | 37 at 250 MHz | [MU-LQW18AN-80] p. 3 |
| LQW18AN37N_80D | 37 nH at 100 MHz | G 2 %, J 5 % | 3000 MHz | 37 at 250 MHz | [MU-LQW18AN-80] p. 3 |
| LQW18AN39N_80D | 39 nH at 100 MHz | G 2 %, J 5 % | 3280 MHz | 40 at 250 MHz | [MU-LQW18AN-80] p. 3 |
| LQW18AN41N_80D | 41 nH at 100 MHz | G 2 %, J 5 % | 3280 MHz | 40 at 250 MHz | [MU-LQW18AN-80] p. 3 |
| LQW18AN43N_80D | 43 nH at 100 MHz | G 2 %, J 5 % | 2780 MHz | 40 at 250 MHz | [MU-LQW18AN-80] p. 3 |
| LQW18AN44N_80D | 44 nH at 100 MHz | G 2 %, J 5 % | 2780 MHz | 40 at 250 MHz | [MU-LQW18AN-80] p. 3 |
| LQW18AN47N_80D | 47 nH at 100 MHz | G 2 %, J 5 % | 2700 MHz | 32 at 200 MHz | [MU-LQW18AN-80] p. 3 |
| LQW18AN48N_80D | 48 nH at 100 MHz | G 2 %, J 5 % | 2700 MHz | 32 at 200 MHz | [MU-LQW18AN-80] p. 3 |
| LQW18AN51N_80D | 51 nH at 100 MHz | G 2 %, J 5 % | 2700 MHz | 32 at 200 MHz | [MU-LQW18AN-80] p. 3 |
| LQW18AN52N_80D | 52 nH at 100 MHz | G 2 %, J 5 % | 2750 MHz | 35 at 200 MHz | [MU-LQW18AN-80] p. 3 |
| LQW18AN56N_80D | 56 nH at 100 MHz | G 2 %, J 5 % | 2600 MHz | 38 at 200 MHz | [MU-LQW18AN-80] p. 3, 4 |
| LQW18AN58N_80D | 58 nH at 100 MHz | G 2 %, J 5 % | 2400 MHz | 35 at 200 MHz | [MU-LQW18AN-80] p. 4 |
| LQW18AN68N_80D | 68 nH at 100 MHz | G 2 %, J 5 % | 2380 MHz | 37 at 200 MHz | [MU-LQW18AN-80] p. 4 |
| LQW18AN69N_80D | 69 nH at 100 MHz | G 2 %, J 5 % | 2380 MHz | 37 at 200 MHz | [MU-LQW18AN-80] p. 4 |
| LQW18AN72N_80D | 72 nH at 100 MHz | G 2 %, J 5 % | 2330 MHz | 34 at 150 MHz | [MU-LQW18AN-80] p. 4 |
| LQW18AN73N_80D | 73 nH at 100 MHz | G 2 %, J 5 % | 2280 MHz | 28 at 150 MHz | [MU-LQW18AN-80] p. 4 |
| LQW18AN75N_80D | 75 nH at 100 MHz | G 2 %, J 5 % | 2280 MHz | 28 at 150 MHz | [MU-LQW18AN-80] p. 4 |
| LQW18AN78N_80D | 78 nH at 100 MHz | G 2 %, J 5 % | 2280 MHz | 28 at 150 MHz | [MU-LQW18AN-80] p. 4 |
| LQW18AN82N_80D | 82 nH at 100 MHz | G 2 %, J 5 % | 2230 MHz | 34 at 150 MHz | [MU-LQW18AN-80] p. 4 |
| LQW18AN83N_80D | 83 nH at 100 MHz | G 2 %, J 5 % | 2230 MHz | 34 at 150 MHz | [MU-LQW18AN-80] p. 4 |
| LQW18AN91N_80D | 91 nH at 100 MHz | G 2 %, J 5 % | 1900 MHz | 33 at 150 MHz | [MU-LQW18AN-80] p. 4 |
| LQW18AN94N_80D | 94 nH at 100 MHz | G 2 %, J 5 % | 1750 MHz | 34 at 150 MHz | [MU-LQW18AN-80] p. 4 |
| LQW18ANR10_80D | 100 nH at 100 MHz | G 2 %, J 5 % | 1750 MHz | 34 at 150 MHz | [MU-LQW18AN-80] p. 4 |
| LQW15AN10N_80D | 10 nH at 100 MHz | G 2 %, J 5 % | 6000 MHz | 31 at 250 MHz | [MU-LQW15AN-80] p. 6 |
| LQW15AN11N_80D | 11 nH at 100 MHz | G 2 %, J 5 % | 6200 MHz | 32 at 250 MHz | [MU-LQW15AN-80] p. 6 |
| LQW15AN12N_80D | 12 nH at 100 MHz | G 2 %, J 5 % | 5200 MHz | 30 at 250 MHz | [MU-LQW15AN-80] p. 6, 7 |
| LQW15AN13N_80D | 13 nH at 100 MHz | G 2 %, J 5 % | 5200 MHz | 30 at 250 MHz | [MU-LQW15AN-80] p. 7 |
| LQW15AN14N_80D | 14 nH at 100 MHz | G 2 %, J 5 % | 5200 MHz | 31 at 250 MHz | [MU-LQW15AN-80] p. 7 |
| LQW15AN15N_80D | 15 nH at 100 MHz | G 2 %, J 5 % | 5500 MHz | 31 at 250 MHz | [MU-LQW15AN-80] p. 7 |
| LQW15AN16N_80D | 16 nH at 100 MHz | G 2 %, J 5 % | 5000 MHz | 31 at 250 MHz | [MU-LQW15AN-80] p. 7 |
| LQW15AN17N_80D | 17 nH at 100 MHz | G 2 %, J 5 % | 5000 MHz | 30 at 250 MHz | [MU-LQW15AN-80] p. 7 |
| LQW15AN18N_80D | 18 nH at 100 MHz | G 2 %, J 5 % | 5200 MHz | 30 at 250 MHz | [MU-LQW15AN-80] p. 7 |
| LQW15AN19N_80D | 19 nH at 100 MHz | G 2 %, J 5 % | 5000 MHz | 30 at 250 MHz | [MU-LQW15AN-80] p. 7 |
| LQW15AN20N_80D | 20 nH at 100 MHz | G 2 %, J 5 % | 4500 MHz | 30 at 250 MHz | [MU-LQW15AN-80] p. 7 |
| LQW15AN21N_80D | 21 nH at 100 MHz | G 2 %, J 5 % | 4500 MHz | 30 at 250 MHz | [MU-LQW15AN-80] p. 7 |
| LQW15AN22N_80D | 22 nH at 100 MHz | G 2 %, J 5 % | 4500 MHz | 30 at 250 MHz | [MU-LQW15AN-80] p. 7 |
| LQW15AN23N_80D | 23 nH at 100 MHz | G 2 %, J 5 % | 4500 MHz | 29 at 250 MHz | [MU-LQW15AN-80] p. 7 |
| LQW15AN24N_80D | 24 nH at 100 MHz | G 2 %, J 5 % | 4000 MHz | 31 at 250 MHz | [MU-LQW15AN-80] p. 7 |
| LQW15AN25N_80D | 25 nH at 100 MHz | G 2 %, J 5 % | 4100 MHz | 31 at 250 MHz | [MU-LQW15AN-80] p. 7 |
| LQW15AN26N_80D | 26 nH at 100 MHz | G 2 %, J 5 % | 4100 MHz | 29 at 250 MHz | [MU-LQW15AN-80] p. 7 |
| LQW15AN27N_80D | 27 nH at 100 MHz | G 2 %, J 5 % | 4000 MHz | 30 at 250 MHz | [MU-LQW15AN-80] p. 7 |
| LQW15AN30N_80D | 30 nH at 100 MHz | G 2 %, J 5 % | 3800 MHz | 30 at 250 MHz | [MU-LQW15AN-80] p. 7 |
| LQW15AN33N_80D | 33 nH at 100 MHz | G 2 %, J 5 % | 3600 MHz | 30 at 250 MHz | [MU-LQW15AN-80] p. 7 |
| LQW15AN36N_80D | 36 nH at 100 MHz | G 2 %, J 5 % | 3500 MHz | 30 at 250 MHz | [MU-LQW15AN-80] p. 7 |
| LQW15AN39N_80D | 39 nH at 100 MHz | G 2 %, J 5 % | 3400 MHz | 28 at 250 MHz | [MU-LQW15AN-80] p. 7 |
| LQW15AN43N_80D | 43 nH at 100 MHz | G 2 %, J 5 % | 3400 MHz | 30 at 250 MHz | [MU-LQW15AN-80] p. 7 |
| LQW15AN47N_80D | 47 nH at 100 MHz | G 2 %, J 5 % | 3200 MHz | 25 at 200 MHz | [MU-LQW15AN-80] p. 7 |
| LQW15AN51N_80D | 51 nH at 100 MHz | G 2 %, J 5 % | 2900 MHz | 25 at 200 MHz | [MU-LQW15AN-80] p. 7 |
| LQW15AN53N_80D | 53 nH at 100 MHz | G 2 %, J 5 % | 2900 MHz | 25 at 200 MHz | [MU-LQW15AN-80] p. 7, 8 |
| LQW15AN56N_80D | 56 nH at 100 MHz | G 2 %, J 5 % | 2900 MHz | 25 at 200 MHz | [MU-LQW15AN-80] p. 8 |
| LQW15AN68N_80D | 68 nH at 100 MHz | G 2 %, J 5 % | 2500 MHz | 25 at 200 MHz | [MU-LQW15AN-80] p. 8 |
| LQW15AN75N_80D | 75 nH at 100 MHz | G 2 %, J 5 % | 2400 MHz | 25 at 200 MHz | [MU-LQW15AN-80] p. 8 |

## VHF iron-powder toroids (mixes 0, 10, 17)

**Result: not offered.** A VHF toroid needs both a guaranteed A_L tolerance and a published
SRF or self-capacitance basis for a wound core. No Micrometals document gives the second for
any mix, and mix 0 also fails the first.

| Mix | Material | A_L tolerance (wording) | SRF or self-capacitance basis |
|---|---|---|---|
| 0 | `-0` phenolic, non-magnetic, reference µ 1 | "AL tolerance Ref Only", test winding "N/A" on every part datasheet (34 parts); catalog "N/A" | none |
| 10 | `-10` carbonyl iron, reference µ 6 | "AL tolerance ±5%" on every part datasheet (27 parts); catalog column "Typical AL Tolerance (%)" ±5 | none |
| 17 | `-17` carbonyl iron, reference µ 4 | "AL tolerance ±5%" (30 of 31 parts; T22-17A prints N/A); catalog "Typical" ±5 | none |

- Evidence: [MM-CAT-2023] p. 12 (material table: "-0 1 N/A Phenolic", "-10 6 ±5 Carbonyl Iron
  … 83", "-17 4 ±5 Carbonyl Iron … 170"), p. 45 ("Typ." A_L tolerance row; "The cores are
  manufactured to the AL Values listed"); part datasheets [MM-DS], for example T50-0 ("AL
  tolerance Ref Only"), T37-17 and T50-10 ("AL tolerance ±5%").
- The search for an SRF basis covered 92 part datasheets, both material datasheets
  [MM-MIX10, MM-MIX17] and the 88-page 2023 catalog: none mentions SRF, resonance or
  capacitance. The 1997 Q-curve catalog [MM-QCURVE-1997] has one generic plot of winding
  capacitance against number of layers, with no core, units or accuracy; Q curves and the
  catalog's "Max Frequency" (83 MHz for mix 10, 170 MHz for mix 17) are application guidance,
  not an SRF basis.
- The ±5 % applies to the stated test winding (10 to 100 turns, depending on the core),
  mostly at 1 MHz (a few sizes at 10 kHz or 1 kHz). The catalog warns that "Iron powder cores tested with a small number of turns which
  are not evenly distributed will produce higher inductance readings than expected" (p. 45).
  At nominal A_L the acceptance inductances (20–75 nH) need about 1.2 to 24 turns, depending
  on the core.
- Part datasheets examined [MM-DS] (each was searched for SRF, resonance and capacitance, and
  its A_L tolerance wording was read). Each entry gives the core and its "AL value (nominal)"
  in nH/turn²; the guarantee type is the mix's wording in the table above. Names omit the mix:
  under mix 0, T12A means T12-0A.
  - mix 0 (34): T5 0.16, T7 0.3, T10 0.24, T12 0.24, T12A 0.13, T16 0.3, T16D 0.3, T20 0.35,
    T20D 0.35, T20F 0.48, T22 0.71, T22A 0.51, T25 0.45, T25D 0.9, T27 0.45, T30 0.6, T37 0.49,
    T44 0.65, T44D 1.4, T50 0.64, T51 2.6, T60 0.88, T68 0.75, T72 1.5, T80 0.85, T94 1.06,
    T106 1.9, T130 1.5, T157 1.8, T184 3, T201 4.2, T300 1.5, T400 2.4 and T400D 4.8;
  - mix 10 (27): T5 0.7, T7 0.9, T10 0.8, T10B 1.25, T12 1.2, T12A 0.72, T12B 1, T16 1.3,
    T20 1.6, T22 3.2, T22A 2.2, T25 1.9, T25A 1.46, T27 2.2, T30 2.5, T37 2.5, T44 3.3, T50 3.1,
    T60 4, T68 3.2, T80 3.2, T94 5.8, T106 8.5, T106B 11.1, T130 6.83, T157 8.2 and T184 13.8
    (T225-10 is listed in
    the product finder, but its datasheet URL was refused);
  - mix 17 (31): T5 0.42, T7 0.6, T10 0.5, T12 0.75, T16 0.8, T20 1, T22 2, T22A N/A, T25 1.2,
    T27 1.3, T30 1.6, T37 1.5, T44 1.85, T44D 3.7, T50 1.8, T60 2.6, T68 2.1, T68A 2.8, T68D 4.2,
    T68E 5.7, T72 4.5, T80 2.2, T80D 4.4, T94 2.9, T106 5.1, T106B 6.6, T130 4, T157 5.3,
    T184 8.7, T225 5 and T400D 14.4.
- **Exclusion reason (for output):** "VHF toroids are not offered: the core maker publishes no
  self-resonance or winding-capacitance data, so the inductance near the band cannot be
  checked."

## Air-core coils

**Result: not offered.** An air coil is offered only inside the range over which its
inductance and self-capacitance models were validated against measurements. The acceptance
designs need about 2–6 spaced turns. For inductance there is one published comparison with
measurements there (one coil radius; the formula reads 2–3 % high). For self-capacitance no
model is validated there, and none gives an upper bound, so the SRF screen cannot be applied.

| Model | Quantity | Stated accuracy | Validated range | End condition |
|---|---|---|---|---|
| Wheeler 1928 [WHEELER-1928] eq. (2) | L | "correct to within 1 per cent for coils with b > 0.8 a", relative to NBS Circular 74 formulas, not measurements | the author warns accuracy is lost "when there are too few turns, when the spacing between turns is too great" | — |
| Rosa 1906 [ROSA-1906]; Rosa & Grover 1912 [ROSA-GROVER-1912] eq. (81) | L | exact for coaxial round-wire rings at low frequency | idealised: no pitch, no leads. Rosa & Grover (p. 148) compare it with Drude's 1902 measurements of one coil radius with 2, 4, 6 and 9 spaced turns: 3.10, 1.85, 2.08 and 0.68 % above the measured values | not stated |
| Lundin 1985 [LUNDIN-1985] | L | error < 3 × 10⁻⁶ relative to the exact current-sheet formula | ideal current sheet only | — |
| Knight 2016 [KNIGHT-SOLENOIDS] | L | round-wire corrections "usually less than 2%" | the "calculation vs. measurement" section is empty ("work in progress"); summation methods lose accuracy as pitch angle grows | — |
| Medhurst 1947 [MEDHURST-1947] | C_self = H·D | "5% or better" with lead correction | 10 to about 636 turns, D 0.675–6.36 cm, l/D 0.163–29.2, up to 30 MHz; for one closely wound two-turn coil the formula read 8.5 % low | one end earthed |
| Knight 2016 [KNIGHT-SELFRES] eq. (5.3) | in-circuit C_L | standard deviation 2.1 % of the fit to Medhurst's data | Medhurst's range only; reads low against Coilcraft guaranteed data | fitted to one-end-earthed data |
| Grandi et al. 1999 [GRANDI-1999] | C_self | predicted 12–23 % low | stacks of 2–10 rings, 10 kHz–1 MHz | not stated |
| Payne 2014 [PAYNE-2014] | SRF | 0.2 % and 0.6 % | two coils (75 and 18 turns) | 75 turns: one end earthed (λ/4); 18 turns: free coil (λ/2) |

- No model gives an upper bound on self-capacitance; the evaluated ones either estimate the
  centre or predict low.
- **222 and 440 MHz.** The 440 MHz limit (0.251 pF) is below the smallest self-capacitance
  inside Medhurst's measured range (0.46 × 0.675 cm ≈ 0.31 pF, before leads; an illustration at
  the edge of the range). Neither band can be shown to meet its limit with a validated model.
- Commercial air-core SMD coils (for example Coilcraft Midi Spring 1812SMS, 22–47 nH, SRF min
  2.1–3.2 GHz [CC-MIDI-SPRING]) do publish guaranteed SRF minimums. They are orderable parts
  with fixture-tested limits, not hand-wound coils, so they would belong with the sourced chip
  parts if added later.
- **Exclusion reason (for output):** "Air-core coils are not offered: no published
  self-capacitance model is validated for coils of a few spaced turns, so their self-resonance
  cannot be checked."

## Trimmer capacitors

A trimmer fits a tank only when its guaranteed range contains the required interval, so it
needs a guaranteed upper bound on its minimum capacitance and a guaranteed lower bound on its
maximum. Ranges printed only as "x to y", as bare values or as typical values do not qualify.

**Qualifying families** (both ends stated as bounds; all current on the maker's site):

| Family | Range wording | Range measured at | Q or loss as stated | SRF as stated | Mounting, voltage | Source |
|---|---|---|---|---|---|---|
| Vishay BFC2 808, Ø5, 7.5 and 10 mm film | "GUARANTEED MAX. Cmin. / MIN. Cmax. AT 200 kHz"; "Each capacitor is tested for minimum Cmax." | 200 kHz | maximum tan δ at Cmax, at 1 MHz for every part and at 100 MHz for most; some parts have no 100 MHz figure | "MIN. fres AT Cmax." for most parts; some have none | radial through-hole; 150 or 250 VDC; "Maximum 10 cycles … performance is not guaranteed if rotated beyond 10 cycles" | [VIS-28526], [VIS-28527], [VIS-28528] pp. 1, 3 |
| Exxelia AT 0300 R2, AT 1300 R2, AT 03HV00 R2 (SMD chip) | "From below 1.5 … To above 3.0" with "+50%/-0" on the maximum | not stated | graph only; AT 03HV: Q 500 minimum at 1 MHz, Cmax | "Typical Self-Resonance Frequency at CMax" (typical) | SMD, reflow; 100 VDC (AT 03HV 350 VDC); revision 02/26 | [EXX-CHIP-V3] pp. 2, 5 |
| Exxelia AT 9402G, AT 9410G (SMD thin), AT 23XXG (SMD hermetic) | "From below 0.5 … To above 2.5" | not stated | "Typical Q@100 MHz, CMax" (typical) | none | SMD; 250 VDC; revision 02/26 | [EXX-THIN-V2] pp. 6–7; [EXX-AT23XXG] p. 2 |
| Suntan TSC3S (SMD) | "Capacitance(pF Min) 1.5 MAX"; "Capacitance(pF Max) 3.0+30-0%" | not stated | "Q Value (at 1 Mhz, C max)" minimum | none | SMD; 100 VDC; sheet undated | [SUN-TSC3S] p. 1 |
| Knowles Voltronics glass and quartz piston trimmers (S, H, TF, TM/QM, TP/QP) | "From below minimum to above maximum value listed for each part. Capacitance measured at 1 MHz." | 1 MHz | "Q (Min.) at 1 MHz" | none | through-hole, panel and surface mount (for example SM10–SM40, 1.5–10 to 1.5–40 pF, Q 800 minimum at 1 MHz); 125–1250 DCWV | [KNO-CAT-R5] pp. 41–42 and the part tables that follow |
| Knowles Voltronics K air trimmers | "Capacitance Range (pF) From Below To Above" | not stated on that page | typical Q only (p. 19) | none | through-hole; 125 or 250 DCWV | [KNO-CAT-R5] pp. 19, 26 |
| Knowles Voltronics K_HV PTFE trimmers | "From Below To Above" | not stated on that page | Q at 100 MHz at maximum rated C, measured with no terminals; not labelled minimum | none | 250 or 1000 DCWV | [KNO-CAT-R5] p. 33 |

**Per-part data** for the Vishay, Exxelia and Suntan TSC3S parts. "Cmin ≤" and "Cmax ≥" are
the guaranteed bounds. Vishay states a maximum tan δ at Cmax; the Q in brackets is 1/tan δ,
rounded down. "—" means the sheet gives no value. The Knowles glass, quartz and K parts are tabulated
per part in [KNO-CAT-R5].

| Part numbers | Cmin ≤ | Cmax ≥ | Q as stated | SRF as stated | Dielectric | Working V | Source |
|---|---|---|---|---|---|---|---|
| BFC280822158 | 0.35 pF | 1.5 pF | tan δ ≤ 10 × 10⁻⁴ at 1 MHz (Q ≥ 1000) | — | PTFE | 150 V | [VIS-28526] p. 3 |
| BFC280824508 | 1.2 pF | 5 pF | tan δ ≤ 10 × 10⁻⁴ at 1 MHz (Q ≥ 1000) | — | PP | 150 V | [VIS-28526] p. 3 |
| BFC280820508, BFC280823508 | 1.5 pF | 5 pF | tan δ ≤ 25 × 10⁻⁴ at 100 MHz (Q ≥ 400) | min 700 MHz at Cmax | PP | 150 V | [VIS-28526] p. 3 |
| BFC280824708 | 1.5 pF | 7 pF | tan δ ≤ 10 × 10⁻⁴ at 1 MHz (Q ≥ 1000) | — | PP | 150 V | [VIS-28526] p. 3 |
| BFC280820109, BFC280823109 | 3 pF | 10 pF | tan δ ≤ 25 × 10⁻⁴ at 100 MHz (Q ≥ 400) | min 500 MHz at Cmax | PP | 150 V | [VIS-28526] p. 3 |
| BFC280820159, BFC280823159 | 3 pF | 15 pF | tan δ ≤ 25 × 10⁻⁴ at 100 MHz (Q ≥ 400) | min 400 MHz at Cmax | PP | 150 V | [VIS-28526] p. 3 |
| BFC280820209, BFC280823209 | 4 pF | 20 pF | tan δ ≤ 25 × 10⁻⁴ at 100 MHz (Q ≥ 400) | min 300 MHz at Cmax | PP | 150 V | [VIS-28526] p. 3 |
| BFC280820279, BFC280823279 | 4 pF | 27 pF | tan δ ≤ 25 × 10⁻⁴ at 100 MHz (Q ≥ 400) | min 300 MHz at Cmax | PP | 150 V | [VIS-28526] p. 3 |
| BFC280811558, BFC280800004, BFC280851558 | 1.4 pF | 5.5 pF | tan δ ≤ 25 × 10⁻⁴ at 100 MHz (Q ≥ 400) | min 850 MHz at Cmax | PE | 250 V | [VIS-28527] p. 3 |
| BFC280800018 | 2 pF | 9 pF | tan δ ≤ 15 × 10⁻⁴ at 100 MHz (Q ≥ 666.6) | min 400 MHz at Cmax | PTFE | 250 V | [VIS-28527] p. 3 |
| BFC280811109, BFC280800005, BFC280851109 | 2 pF | 10 pF | tan δ ≤ 25 × 10⁻⁴ at 100 MHz (Q ≥ 400) | min 480 MHz at Cmax | PP | 250 V | [VIS-28527] p. 3 |
| BFC280811159 | 2 pF | 15 pF | tan δ ≤ 25 × 10⁻⁴ at 100 MHz (Q ≥ 400) | min 450 MHz at Cmax | PP | 250 V | [VIS-28527] p. 3 |
| BFC280800016 | 2 pF | 18 pF | tan δ ≤ 15 × 10⁻⁴ at 100 MHz (Q ≥ 666.6) | min 350 MHz at Cmax | PTFE | 250 V | [VIS-28527] p. 3 |
| BFC280811006 | 2.5 pF | 20 pF | tan δ ≤ 160 × 10⁻⁴ at 1 MHz (Q ≥ 62.5) | min 250 MHz at Cmax | PET | 250 V | [VIS-28527] p. 3 |
| BFC280811229, BFC280800006, BFC280851229 | 2.5 pF | 22 pF | tan δ ≤ 25 × 10⁻⁴ at 100 MHz (Q ≥ 400) | min 350 MHz at Cmax | PP | 250 V | [VIS-28527] p. 3 |
| BFC280811339 | 3 pF | 33 pF | tan δ ≤ 10 × 10⁻⁴ at 1 MHz (Q ≥ 1000) | min 300 MHz at Cmax | PP | 250 V | [VIS-28527] p. 3 |
| BFC280811409 | 3 pF | 40 pF | tan δ ≤ 10 × 10⁻⁴ at 1 MHz (Q ≥ 1000) | min 300 MHz at Cmax | PP | 250 V | [VIS-28527] p. 3 |
| BFC280831159, BFC280832159 | 2.5 pF | 15 pF | tan δ ≤ 25 × 10⁻⁴ at 100 MHz (Q ≥ 400) | min 420 MHz at Cmax | PP | 150 V | [VIS-28528] p. 3 |
| BFC280831229, BFC280832229 | 3 pF | 22.5 pF | tan δ ≤ 25 × 10⁻⁴ at 100 MHz (Q ≥ 400) | min 200 MHz at Cmax | PP | 150 V | [VIS-28528] p. 3 |
| BFC280831409, BFC280832409 | 5.5 pF | 40 pF | tan δ ≤ 25 × 10⁻⁴ at 100 MHz (Q ≥ 400) | min 200 MHz at Cmax | PP | 150 V | [VIS-28528] p. 3 |
| BFC280801029, BFC280801006 | 5.5 pF | 50 pF | tan δ ≤ 25 × 10⁻⁴ at 100 MHz (Q ≥ 400) | min 170 MHz at Cmax | PTFE | 150 V | [VIS-28528] p. 3 |
| BFC280801001, BFC280831659, BFC280832659 | 5.5 pF | 65 pF | tan δ ≤ 25 × 10⁻⁴ at 100 MHz (Q ≥ 400) | min 170 MHz at Cmax | PP | 150 V | [VIS-28528] p. 3 |
| AT 0303 R2, AT 1303 R2 | 1.5 pF | 3 pF | graph only | typical 2000 / 2300 MHz at Cmax | ceramic | 100 V | [EXX-CHIP-V3] p. 2 |
| AT 0306 R2, AT 1306 R2 | 2 pF | 6 pF | graph only | typical 1400 / 1600 MHz at Cmax | ceramic | 100 V | [EXX-CHIP-V3] p. 2 |
| AT 0310 R2, AT 1310 R2 | 2 pF | 10 pF | graph only | typical 1100 / 1200 MHz at Cmax | ceramic | 100 V | [EXX-CHIP-V3] p. 2 |
| AT 0315 R2, AT 1315 R2 | 3 pF | 15 pF | graph only | typical 900 / 1000 MHz at Cmax | ceramic | 100 V | [EXX-CHIP-V3] p. 2 |
| AT 0320 R2, AT 1320 R2 | 4.5 pF | 20 pF | graph only | typical 800 / 900 MHz at Cmax | ceramic | 100 V | [EXX-CHIP-V3] p. 2 |
| AT 0330 R2, AT 1330 R2 | 5.5 pF | 30 pF | graph only | typical 600 / 700 MHz at Cmax | ceramic | 100 V | [EXX-CHIP-V3] p. 2 |
| AT 0340 R2, AT 1340 R2 | 8 pF | 40 pF | graph only | typical 400 / 500 MHz at Cmax | ceramic | 100 V | [EXX-CHIP-V3] p. 2 |
| AT 03HV03 R2 | 1.5 pF | 3 pF | min 500 at 1 MHz | typical 2000 MHz at Cmax | ceramic | 350 V | [EXX-CHIP-V3] p. 5 |
| AT 03HV06 R2 | 2 pF | 6 pF | min 500 at 1 MHz | typical 1400 MHz at Cmax | ceramic | 350 V | [EXX-CHIP-V3] p. 5 |
| AT 03HV10 R2 | 2 pF | 10 pF | min 500 at 1 MHz | typical 1100 MHz at Cmax | ceramic | 350 V | [EXX-CHIP-V3] p. 5 |
| AT 03HV15 R2 | 3 pF | 15 pF | min 500 at 1 MHz | typical 900 MHz at Cmax | ceramic | 350 V | [EXX-CHIP-V3] p. 5 |
| AT 03HV20 R2 | 4.5 pF | 20 pF | min 500 at 1 MHz | typical 800 MHz at Cmax | ceramic | 350 V | [EXX-CHIP-V3] p. 5 |
| AT 9402G-0, AT 9402G-0 SL1 | 0.5 pF | 2.5 pF | typical 3000 at 100 MHz | — | ceramic | 250 V | [EXX-THIN-V2] p. 6 |
| AT 9402G-1, AT 9402G-1 SL1 | 1 pF | 5 pF | typical 1000 at 100 MHz | — | ceramic | 250 V | [EXX-THIN-V2] p. 6 |
| AT 9402G-2, AT 9402G-2 SL1 | 2.5 pF | 10 pF | typical 1000 at 100 MHz | — | ceramic | 250 V | [EXX-THIN-V2] p. 6 |
| AT 9402G-4, AT 9402G-4 SL1 | 3 pF | 12 pF | typical 500 at 100 MHz | — | ceramic | 250 V | [EXX-THIN-V2] p. 6 |
| AT 9402G-6, AT 9402G-6 SL1 | 8 pF | 25 pF | typical 300 at 100 MHz | — | ceramic | 250 V | [EXX-THIN-V2] p. 6 |
| AT 9402G-8, AT 9402G-8 SL1 | 5 pF | 15 pF | typical 750 at 100 MHz | — | ceramic | 250 V | [EXX-THIN-V2] p. 6 |
| AT 9402G-9, AT 9402G-9 SL1 | 7 pF | 18 pF | typical 500 at 100 MHz | — | ceramic | 250 V | [EXX-THIN-V2] p. 6 |
| AT 9410G-0, AT 9410G-0 SL1 | 1 pF | 4.5 pF | typical 1000 at 100 MHz | — | ceramic | 250 V | [EXX-THIN-V2] p. 7 |
| AT 9410G-1, AT 9410G-1 SL1 | 2.5 pF | 10 pF | typical 1000 at 100 MHz | — | ceramic | 250 V | [EXX-THIN-V2] p. 7 |
| AT 9410G-2, AT 9410G-2 SL1 | 4 pF | 18 pF | typical 700 at 100 MHz | — | ceramic | 250 V | [EXX-THIN-V2] p. 7 |
| AT 9410G-3, AT 9410G-3 SL1 | 6 pF | 35 pF | typical 200 at 100 MHz | — | ceramic | 250 V | [EXX-THIN-V2] p. 7 |
| AT 9410G-4, AT 9410G-4 SL1 | 7 pF | 40 pF | typical 200 at 100 MHz | — | ceramic | 250 V | [EXX-THIN-V2] p. 7 |
| AT 9410G-5, AT 9410G-5 SL1 | 10 pF | 50 pF | typical 200 at 100 MHz | — | ceramic | 250 V | [EXX-THIN-V2] p. 7 |
| AT 9410G-25, AT 9410G-25 SL1 | 5 pF | 25 pF | typical 200 at 100 MHz | — | ceramic | 250 V | [EXX-THIN-V2] p. 7 |
| AT 2320G-0 | 0.6 pF | 2.5 pF | typical >3000 at 100 MHz | — | ceramic | 250 V | [EXX-AT23XXG] p. 2 |
| AT 2320G-1 | 1 pF | 5 pF | typical >1000 at 100 MHz | — | ceramic | 250 V | [EXX-AT23XXG] p. 2 |
| AT 2320G-2 | 2.5 pF | 10 pF | typical >1000 at 100 MHz | — | ceramic | 250 V | [EXX-AT23XXG] p. 2 |
| AT 2320G-3 | 7.5 pF | 18 pF | typical >500 at 100 MHz | — | ceramic | 250 V | [EXX-AT23XXG] p. 2 |
| AT 2340G-4 | 8.5 pF | 22 pF | typical >300 at 100 MHz | — | ceramic | 250 V | [EXX-AT23XXG] p. 2 |
| TSC3S503T1R | 1.5 pF | 3 pF | min 300 at 1 MHz | — | ceramic | 100 V | [SUN-TSC3S] p. 1 |
| TSC3S506T1R | 2 pF | 6 pF | min 500 at 1 MHz | — | ceramic | 100 V | [SUN-TSC3S] p. 1 |
| TSC3S510T1R | 3 pF | 10 pF | min 500 at 1 MHz | — | ceramic | 100 V | [SUN-TSC3S] p. 1 |
| TSC3S520T1R | 5.8 pF | 20 pF | min 200 at 1 MHz | — | ceramic | 100 V | [SUN-TSC3S] p. 1 |
| TSC3S530T1R | 8 pF | 28.5 pF | min 200 at 1 MHz | — | ceramic | 100 V | [SUN-TSC3S] p. 1 |

A part fits only when its guaranteed interval contains the required interval: a tank that needs
5 pF at the low end cannot use, for example, AT 0330 R2 (Cmin up to 5.5 pF), AT 0340 R2 (8 pF) or
TSC3S520T1R (5.8 pF).

**Not qualifying:**

- **Suntan TSC3, TSC5 and TSC7:** the first page of each datasheet carries a "DISCONTINUED"
  badge [SUN-TSC3, SUN-TSC5, SUN-TSC7]. Their ranges are stated as bounds, but they are not
  offered for new builds.
- **Knowles JZ and JR** (the usual replacement for Murata TZ): the maximum is guaranteed
  ("−0 %"), but the minimum is printed as a bare value; the catalog [KNO-CAT-R5] p. 6 and
  outline drawing V-70513 [KNO-V70513] put the +50 %/−0 % tolerance on the maximum only.
  Excluded until Knowles states a bound on the minimum.
- **Murata TZ series** (TZR1, TZY2, TZC3, TZW4, TZB4): withdrawn. Murata's notice dated
  Jun. 26, 2018 covers "all Trimmer Capacitors (TZ***)", with last shipment due Mar. 31, 2021
  [MUR-EOL-2018, a distributor-hosted copy of Murata's notice]. Its catalog also says "This
  catalog has only typical specifications" [MUR-T13E].
- **No longer published by the maker:** Kyocera AVX CTZ (absent from kyocera-avx.com; only a
  2008 distributor copy exists) and Sprague-Goodman (spraguegoodman.com no longer resolves).
- **Range not stated as bounds** ("x to y" or bare Cmin/Cmax columns): Knowles Thin-Trim,
  Cera-Trim, Seal-Trim, air and Giga-Trim sapphire lines; Exxelia AT 9401G, air, sapphire and
  PTFE lines; Tronser sapphire, zirconia, air-tube and FilmTrim. Bourns makes no trimmer
  capacitors.

**What this means for tank trimmers.** Every guaranteed range is measured at 200 kHz or
1 MHz, or at an unstated frequency. At VHF a trimmer's series inductance raises its effective
capacitance. A Vishay minimum SRF bounds that inductance only at Cmax
(L ≤ 1/((2π·f_res,min)²·Cmax,min), derived); using the bound at other settings assumes the
inductance does not grow as the trimmer is turned down, and no sheet states that. So no
family supports a guaranteed fit at VHF without a labelled assumption, and no qualifying SMD
family guarantees Q or SRF at VHF.

## Coverage of the acceptance designs

**Part model.** A chip inductor with catalog value L_m measured at f_m and guaranteed minimum
SRF is L0 in parallel with C_self, where L0 = L_m(1 − (f_m/SRF)²) and
C_self = 1/((2π·SRF)²·L0). Its effective inductance is L(f) = L0 / (1 − (f/SRF)²), which
reproduces L_m at f_m. Spot check with 0603CS-24NXGRW (24 nH at 250 MHz, SRF min 2.65 GHz):
L0 = 23.786 nH, C_self = 0.1516 pF, L(250 MHz) = 24.000 nH.

**Screen.** Over the whole check window:
- drift L(f)/L(f_m) − 1 at the minimum SRF stays within ±5 %, including below f_m where it is
  negative. A real part's SRF is at or above the minimum, so its drift is no larger.
- with L_m at both tolerance endpoints, the effective inductance stays within 10 % of the
  target, combined in henries (so 5 % tolerance plus 5 % drift is 10.25 % and fails). Within
  this model, a part's inductance at each frequency lies between its value at the minimum SRF
  and the catalog value with no drift (SRF far above the minimum), so both limits are checked
  at both window ends. Checking only the minimum SRF understates the error when the window lies
  below f_m: 0603CS-56NXGRW at +2 % reaches 57.12 nH with no drift, +4.78 % of 54.5148 nH,
  against +4.25 % at the minimum SRF.

These bounds are conditional on the parallel-LC model and on inputs measured in the
manufacturer's fixture. On a board the SRF differs: Coilcraft states that "the true SRF of
any inductor always depends on the specific characteristics of the circuit board to which it
is mounted" [CC-SRF-NOTE]. Layout capacitance is not part of this screen.

Qualifying parts are ranked by the smallest worst-case error, then by part number. "Achieved
L" is the nominal part's effective inductance at the top of the window, at the minimum SRF.
The counts are tolerance variants in the catalog rows above that pass the screen.

| Design and inductor | Chip inductor (recommended catalog) | Error budget: mismatch; tolerance (of target); drift (of catalog L, minimum SRF to none); worst ends | Achieved L | VHF toroid | Air coil |
|---|---|---|---|---|---|
| LP 146 MHz, 74.7381 nH | **LQW15AN75NG80D** (18 qualify) | +0.35 %; ±2.01 %; −0.17 to +0.20 %; −1.83 to +2.56 % | 75.148 nH; C_self 0.0587 pF | no SRF basis | no validated model for 2–6 turns |
| LP 222 MHz, 49.1521 nH | **LQW18AN48NG80D** (20) | −2.34 %; ±1.95 %; −0.14 to +0.54 %; −4.43 to +0.15 % | 48.260 nH; C_self 0.0725 pF | no SRF basis | no validated model |
| LP 440 MHz, 24.7995 nH | **LQW15AN25NG80D** (17) | +0.81 %; ±2.02 %; −0.06 to +1.10 %; −1.27 to +3.96 % | 25.276 nH; C_self 0.0603 pF | no SRF basis | no validated model; C_self limit 0.251 pF below the validated range |
| BP 146 MHz, 54.5148 nH (as designed) | **0603CS-56NXGRW** (18) | +2.72 %; ±2.05 %; −1.11 to 0 %; −0.45 to +4.78 % | 55.718 nH; C_self 0.1267 pF | no SRF basis | no validated model |
| BP 146 MHz with `--tank-inductance 21nH` | **LQW15AN21NG80D** (11) | 0 %; ±2.00 %; −0.05 to +0.06 %; −2.05 to +2.06 % | 21.012 nH; C_self 0.0596 pF | no SRF basis | no validated model |
| BP 146 MHz with `--tank-inductance 20nH` | **LQW18AN20NG00D** (9) | 0 %; ±2.00 %; −0.04 to +0.05 %; −2.04 to +2.05 % | 20.010 nH; C_self 0.0528 pF | no SRF basis | no validated model |

- Every inductor of every acceptance design has a qualifying chip inductor. The band-pass
  coupling advice can reach 1 pF with 21 nH (in the catalog only LQW15AN21N_80D supplies that
  value) or with 20 nH (LQW18AN20N_00D or LQW15AN20N_80D); 22 nH gives 0.957 pF and fails.
- Close misses show the budget at work: 0603CS-47NXJRW fails 49.15 nH at −10.07 %, and
  LQW15AN26NJ80D fails 24.80 nH at +11.30 %.

## Decisions

| Kind | Decision | Designs covered | Reason |
|---|---|---|---|
| Chip inductors | **Go** | all four | guaranteed tolerance, SRF minimum and Q minimum for exact parts; every design qualifies |
| VHF toroids (mixes 0, 10, 17) | **No-go** | none | no SRF or self-capacitance basis published; mix 0 A_L tolerance is reference-only |
| Air-core coils | **No-go** | none | no self-capacitance model validated for 2–6 spaced turns, and none gives an upper bound; inductance has one measured comparison (one coil radius, 2–3 % high) |

Chip inductors are the only inductor kind added for VHF/UHF. Legacy HF toroids (mixes 2 and
6) are unaffected and keep their "SRF not checked" status.

**Open questions from the design brief, answered:**

1. *Is any air-coil model validated for 2–6 spaced turns, so that air coils can serve 222 and
   440 MHz?* No. The inductance formula has one measured comparison for 2–9 turns (one coil
   radius, 2–3 % high), but no self-capacitance model is validated for so few turns, and none
   gives an upper bound (Air-core coils above). Air coils are not offered on any band.
2. *Does any VHF toroid have a sourced SRF basis?* No (VHF iron-powder toroids above), so VHF
   toroids are excluded.
3. *Is there a source for the per-part layout stray?* No (Layout stray above); 0.2 pF stays a
   labelled assumption.
4. *Which trimmer families publish guaranteed ranges and SRF at a stated setting?*
   Guaranteed ranges, current: Vishay BFC2 808, Exxelia AT 0300/1300 R2, AT 03HV00 R2,
   AT 9402G, AT 9410G and AT 23XXG, Suntan TSC3S, and Knowles Voltronics glass, quartz, K air and
   K_HV (Suntan TSC3, TSC5 and TSC7 are discontinued). SRF at a stated setting: only Vishay
   guarantees one, a minimum at Cmax, and not for every part; Exxelia gives a typical SRF at
   Cmax. Neither bounds the inductance at other settings (Trimmer capacitors above).

## Source index

SHA-256 values identify the copy read on 2026-11-19; a manufacturer may republish a document
under the same URL.

| ID | Title | Revision or date | URL | SHA-256 |
|---|---|---|---|---|
| MU-GRM | Murata per-part Reference Sheets, GRM1885C1H…A01 (33 pages each; Rated Value p. 2, Specifications and Test Methods p. 3) | "as of" Jun. 17 or Jun. 24, 2026 per part | `https://pim.murata.com/asset/pim4/ceramicCapacitorSMD/<part>-01A-EN_PDF_CERAMICCAPACITORSMD` | see below |
| MU-GJM-47 | Murata GJM1555C1H470JB01 Reference Sheet | as of Apr. 15, 2026 | same pattern, part GJM1555C1H470JB01 | 7b2675c23e605038a1d797b724e49e543b41cad3100d9409c64383fb773263ac |
| MU-GRM-102F-2012 | Murata Reference Sheet, GRM1885C1H102FA01 (1000 pF, F code; distributor-hosted copy) | as of Mar. 31, 2012 | https://www.farnell.com/datasheets/1747444.pdf | 8d9ab28de61d508d0c3cc21c5048b3ce6019c683a5555e1dc6ebbc87a729bfdb |
| MU-GJM-LINEUP | Murata, GJM Series lineup (web page) | undated | https://www.murata.com/en-us/products/capacitor/ceramiccapacitor/overview/lineup/smd/gjm | e4fc78df6aec696a8a1caa42af7dff52616a79306d7abf4f90860d194a739562 |
| MU-FAQ-CATALOG | Murata FAQ, "Is there a catalog for ceramic capacitors?" | undated | https://www.murata.com/en-us/support/faqs/capacitor/ceramiccapacitor/other/0004 | 1df7d5e38206e99f4574c7e134cbe0511019ea3a6a0df7a48f496611d51749a1 |
| MU-SIM-COND | Murata SimSurfing MLCC Characteristics Viewer, "Measurement Conditions" | Sep. 2022 | https://ds.murata.com/simsurfing_data/pdf/en-us/mlcc/sim_mlcc_measuringcond_e.pdf | 487b3281b6015f8c865d502c594e12f07cf0bccdeeefcd042cd068c6a0e51027 |
| JT-MOUNT | Johanson Technology, "Simulating the Effect of Mounting on SRF and S-Parameters for High Frequency Multi-Layer Ceramic Capacitors" | May 9, 2000 | https://www.johansontechnology.com/downloads/technotes/simulating-the-effect-of-mounting-on-srf-and-s-parameters-for-high-frequency-multi-layer-ceramic-capacitors.pdf | cb26723faaeb400dffc119729e795619514445ebc4ee495c9e4ef4085757ba89 |
| VI-TN0004 | Vishay, VSE-TN0004 "Frequency Response of Thin Film Chip Resistors" | Rev. 04-May-06 | https://www.vishay.com/docs/49427/vse-tn00.pdf | 9862d3b58e4d770f49fc6953cfcf84d77ba6e71ce36f893ea1901ecae59ad572 |
| CC-0603CS | Coilcraft, "Chip Inductors – 0603CS (1608)" | Documents 195-1 and 195-2, revised 06/26/24 | https://www.coilcraft.com/getmedia/022eb894-7253-40d0-b07c-650d362fc80e/0603cs.pdf | 8f69766c73cd8aeda094d0cfdd9aa6e143d586b09414a15c1f201655754cda46 |
| MU-LQW18AN-00 | Murata reference specification, LQW18AN_00 | Spec No. JELF243A_0024AC-01 | https://pim.murata.com/asset/pim4/inductor/JELF243A-0024_PDF_INDUCTOR | be795e7f314706838324684ee7d5f5694f8c68ee5a3351556dae6190fded697a |
| MU-LQW18AN-80 | Murata reference specification, LQW18AN_80 | Spec No. JELF243A_0102L-01 | https://pim.murata.com/asset/pim4/inductor/JELF243A-0102_PDF_INDUCTOR | 12e6e209d9d063424c94dc2946205f62846311c1eee2e36c36c3ac3efa126c26 |
| MU-LQW15AN-80 | Murata reference specification, LQW15AN_80 | Spec No. JELF243A_0100K-01 | https://pim.murata.com/asset/pim4/inductor/JELF243A-0100_PDF_INDUCTOR | 2bca847ecc569c11674d6af7ab390ed19be23467d925f48e04e7800825cb0a7c |
| CC-SRF-NOTE | Coilcraft, "Measuring Self Resonant Frequency" (application note, web page) | Document 363 | https://www.coilcraft.com/en-us/resources/application-notes/measuring-self-resonant-frequency/ | 0b5ffb4781aaf8b952adefd048b68ab45a25147198d30630af684bfa91e8e0f6 |
| CC-0603HC | Coilcraft 0603HC (1608) | Doc 218-1, Revised 08/08/22 | https://www.coilcraft.com/getmedia/070cbd0e-93e3-43a3-a7ac-08bbbb3db32b/0603hc.pdf | bbe647b4726ad143cd24fdf3858b61d497e8edefc65bda6ffc480ecd9d4d6e86 |
| CC-0604HQ | Coilcraft 0604HQ (1610) | Doc 285-1, Revised 07/22/21 | https://www.coilcraft.com/getmedia/0719743d-cfb7-4d4d-9e58-bb01a615ada6/0604hq.pdf | ef5c633bd293dc109014b4488cba8ed0c538b739c1ae649233a565f0e3fac401 |
| CC-0805HQ | Coilcraft 0805HQ (2012) | Doc 197-1, Revised 08/08/22 | https://www.coilcraft.com/getmedia/d1c77d59-e9b0-44a7-81e0-f46e468b0410/0805hq.pdf | 33b7c5a503d3d7b98a8b9b788ca50aa3e2a996d2f00c5c75c985df359f705dcb |
| CC-0805HT | Coilcraft 0805HT (2012) | Doc 168-1, Revised 08/08/22 | https://www.coilcraft.com/getmedia/78c6e03c-4cbf-4883-b3bd-a6f68c27e168/0805ht.pdf | 6ec228bf9272881b7c1b94e885961ed303c2e8fc4628ddd793f876dff0d74d8f |
| CC-1008CS | Coilcraft 1008CS (2520) | Doc 101-2, Revised 08/05/22 | https://www.coilcraft.com/getmedia/9b59774c-05d4-40c5-99c9-417bb8e881ea/1008cs.pdf | 691856064efde2aee75226d4ed300f279e19a02f9d1c5f0a15ce76c4e1f3ce29 |
| CC-1008CT | Coilcraft 1008CT (2520) | Doc 102-1, Revised 08/05/22 | https://www.coilcraft.com/getmedia/0b09d855-216b-45ef-80eb-60c83c03faea/1008ct.pdf | 009fddfdc825b625c08caa8e0dbc7f02aae4ef4a477d9a94daa4e0b3e887cf3a |
| CC-1008HQ | Coilcraft 1008HQ (2520) | Doc 190-1, Revised 08/08/22 | https://www.coilcraft.com/getmedia/d309e334-bba7-474c-baad-e9acd748f87a/1008hq.pdf | 40bd11b56ec108637ec79adced96f397611972226d92ecc9a812b9ee3a1a98a9 |
| CC-1008HT | Coilcraft 1008HT (2520) | Doc 169-1, Revised 08/08/22 | https://www.coilcraft.com/getmedia/b92e7006-01e6-4f1e-ab6f-0773da92e9ea/1008ht.pdf | 7c5dc338f11873d4e3205370b606604e1ab12f8b635121b3e2082e6879998027 |
| CC-1206CS | Coilcraft 1206CS (3216) | Doc 104-1, Revised 08/08/22 | https://www.coilcraft.com/getmedia/0d2d6445-1567-49d3-b969-9190d57aa771/1206cs.pdf | dbe88c3f1d63059f24a1b070ec68739884a7b8e05a1e2857d34635a58c1c5089 |
| CC-0603HP | Coilcraft 0603HP (1608) | Doc 537-2, Revised 08/08/22 | https://www.coilcraft.com/getmedia/624a615f-2f4d-4200-95a6-61764a49bbc8/0603hp.pdf | d8bbe394d16c640df3586c9f6f27160b71bd96591862843efacffee85355f0d4 |
| CC-0402CS | Coilcraft 0402CS (1005) | Doc 198-2, Revised 08/06/21 | https://www.coilcraft.com/getmedia/f6cf468d-46eb-4342-9245-4b8b34f8d1bb/0402cs.pdf | 6478a7bfdc83983c98f481f1e33d59486bfc4f375399e0f5161b51e5ad6ffb2c |
| CC-0402HP | Coilcraft 0402HP (1005) | Doc 526-2, Revised 12/20/23 | https://www.coilcraft.com/getmedia/54459dcc-b821-4a9d-b91e-0416ea86a9b2/0402hp.pdf | 2f5c071c4face227bcdfee9d5beb22ebc63848ca5ccca1fb7b3aa39e6ecb1822 |
| CC-0805CS | Coilcraft 0805CS (2012) | Doc 100-1/100-2, Revised 08/05/22 | https://www.coilcraft.com/getmedia/dd5f20e4-1ff7-43df-8317-b693eb2dce3e/0805cs.pdf | fccf2b1840d888222bd553cb4d73ef84a9d1a66a9f641e66c53fc11da2dd09fe |
| CC-0805HP | Coilcraft 0805HP (2012) | Doc 1362-1, Revised 04/11/22 | https://www.coilcraft.com/getmedia/c30565bc-9cf5-4393-9380-6f782e4b4cd8/0805hp.pdf | 020e798b3976cf149b0193218e0811d7206dbf21f95a9395a9a08d7643314898 |
| CC-0403HQ | Coilcraft 0403HQ | Doc 300-1, Revised 12/01/21 | https://www.coilcraft.com/getmedia/69c5aa91-3ca0-4922-874d-581cd4e27e62/0403hq.pdf | 4cc1a11078027b5f5f04a0bb414a69f08152990b69b33a941de0e8da701fbd48 |
| CC-0402DC | Coilcraft 0402DC | Doc 1153-2, Revised 11/09/23 | https://www.coilcraft.com/getmedia/b3553702-9a56-4386-b513-fcddf8709240/0402dc.pdf | a61dfff73ba0e33a63a83459cd443709c438faadd488e11cfcaac0ffdf3bd682 |
| CC-0603DC | Coilcraft 0603DC | Doc 1605-2, Revised 05/03/22 | https://www.coilcraft.com/getmedia/f3d98f97-cbe2-41fa-b3a9-518f674e881e/0603dc.pdf | 3b40b48e08d64892bc6b54b721052431e872f5ee7830c13ca74ecc4845852938 |
| MU-LQW15AN-00 | Murata LQW15AN_00 reference specification | JELF243A_0050AE-01 | https://pim.murata.com/asset/pim4/inductor/JELF243A-0050_PDF_INDUCTOR | e0fb471cbca51e7b3b248d0f6eef23ded2eec1d3fb3e2b9bd602f008856faccf |
| MU-LQW15AW-80 | Murata LQW15AW_80 reference specification | JELF243A_0161E-01 | https://pim.murata.com/asset/pim4/inductor/JELF243A-0161_PDF_INDUCTOR | cee1c4a802525ff9bb57fd375453610918a2412b90fb823120e47535b94acbfb |
| MU-LQW18AN-10 | Murata LQW18AN_10 reference specification | JELF243A_0026U-01 | https://pim.murata.com/asset/pim4/inductor/JELF243A-0026_PDF_INDUCTOR | d55e431bffc965654324c849457ad3ac8398ba130bd706b3af5de2cf5a181884 |
| MU-LQW18AS-00 | Murata LQW18AS_00 reference specification | JELF243A_0111G-01 | https://pim.murata.com/asset/pim4/inductor/JELF243A-0111_PDF_INDUCTOR | 084d5fec5731f8b4464f172677f60ddfdb752525e0ce2fdce0fb2f3f96d6fb18 |
| MU-LQW18AS-0C | Murata LQW18AS_0C reference specification | JELF243A_0167E-01 | https://pim.murata.com/asset/pim4/inductor/JELF243A-0167_PDF_INDUCTOR | 492867f98f87d44fafbb2eb1831b1353c4e6f55d595e98a377adc12428b48a8d |
| MU-LQW2BAN-00 | Murata LQW2BAN_00 reference specification | JELF243A_0115F-01 | https://pim.murata.com/asset/pim4/inductor/JELF243A-0115_PDF_INDUCTOR | e55f02c80f80a6c326fe34f7c1d2615eac8618afe01cc1a37cb77b90dd2acfa5 |
| MU-LQW2BAS-00 | Murata LQW2BAS_00 reference specification | JELF243A_0084S-01 | https://pim.murata.com/asset/pim4/inductor/JELF243A-0084_PDF_INDUCTOR | 14be59c93b02020e0b27f42dea32a5686f1c5b756f9e2b284bf28994a46dbe2e |
| MU-LQW2BAS-0C | Murata LQW2BAS_0C reference specification | JELF243A-0181A-01 | https://pim.murata.com/asset/pim4/inductor/JELF243A-0181_PDF_INDUCTOR | b2216477e20411194efd67446ce899615629b61b766d5fdaabca2be19970e43d |
| MU-LQW2UAS-00 | Murata LQW2UAS_00 reference specification | JELF243A_0085N-01 | https://pim.murata.com/asset/pim4/inductor/JELF243A-0085_PDF_INDUCTOR | 619b249b8bdac8dea72c37379cb94018fe7b7b6f7ba5651d574d58d6d5df8d47 |
| MU-LQW2UAS-0C | Murata LQW2UAS_0C reference specification | JELF243A_0173F-01 | https://pim.murata.com/asset/pim4/inductor/JELF243A-0173_PDF_INDUCTOR | 93eded4e4a6523ba105abef3638ec497812f63ca776853568458971fe90dfbd6 |
| MU-LQW15CN-00 | Murata LQW15CN_00 | JELF243A_0087R-01 | https://pim.murata.com/asset/pim4/inductor/JELF243A-0087_PDF_INDUCTOR | 7f5a4e156e02410f13769c69144bb66ebef27ea0377beff9c779ae9f84164c4b |
| MU-LQW18CN-00 | Murata LQW18CN_00 | JELF243A_0082N-01 | https://pim.murata.com/asset/pim4/inductor/JELF243A-0082_PDF_INDUCTOR | 45b0ac5a7469a139f9f269bbfa6b9354d231de6c0705669edf0965638f14b0ad |
| JO-WW | Johanson Technology, RF Inductors – WireWound Inductors (catalog pp. 89–94) | no revision printed (PDF dated 2025-06-27) | https://www.johansontechnology.com/docs/4524/wirewound-inductors-datasheet.pdf | 5fd58fac5f61ec997b538c2c6e556ec6bc4cee168e0ef59cb26b4db95228d880 |
| CC-MIDI-SPRING | Coilcraft, "Midi Spring Air Core Inductors" | Document 184, revised 12/02/21 | https://coilcraft.com/getmedia/c6fe1f83-b176-469d-a071-e2edb068fef2/midi.pdf | e8ce1b27f9bea4630e9531c73fa777b2a6acfc8dc414bc4b45ecfc3bf6a42ce3 |
| MM-CAT-2023 | Micrometals, Iron Powder Products Catalog (88 pp.) | 2023 (PDF dated 2023-12-21) | https://s3.amazonaws.com/micrometals-production/filer_public/f4/da/f4da63c8-44fc-4d87-a290-bf3f5c8ae2de/micrometals_2023_catalog-final_122123.pdf | b7908837a938f4f90e2192b4d0c877c649f7b369357e6006d359ae36f1d2c881 |
| MM-MIX10 | Micrometals, Mix -10 material datasheet | Rev. 2023-Dec-15 | https://s3.amazonaws.com/micrometals-production/filer_public/b7/06/b706a4bb-7be2-459a-aa3e-26c439f74ec8/mix-10-datasheet.pdf | 5d5cb66122051fc9800d1e997b3a6190177b3db190cf136530132cbde8288ebf |
| MM-MIX17 | Micrometals, Mix -17 material datasheet | Rev. 2023-Dec-15 | https://s3.amazonaws.com/micrometals-production/filer_public/f4/b5/f4b57390-3bd0-477a-9fff-c62a10e7d5ab/mix-17-datasheet.pdf | 8c7b2d6f574bc36aa95d8fabadc98ef9255c261c8078e21bac77c3e5b04fc323 |
| MM-DS | Micrometals part datasheets, e.g. T50-0, T37-17, T50-10 | per part (2019–2025) | `https://datasheets.micrometals.com/<part>-DataSheet.pdf` | T50-0 cfb6098d5b05d061ca064bba44c4bd266cd586c0289a2bf7098fe9617a988a09; T37-17 59817fc2b5709dce7e8882b27b531ba905fb4e94b642b3d1c6655a9d5381adac; T50-10 50a50664b2cedf39deced8557956e4b12eb918635ce88a0e68b759b722ca1b3d |
| MM-QCURVE-1997 | Micrometals, Q-Curves for Iron Powder Cores (hosted by Acal BFi) | Issue G, 12/97 | https://www.acalbfi.com/media/pdf/q_curve_catalog_issue_h.pdf | ab10ae5a17507bd49602300a9681b7431165223a1e437b20eba2849dd5f0ec29 |
| WHEELER-1928 | H. A. Wheeler, "Simple Inductance Formulas for Radio Coils", Proc. IRE 16(10), pp. 1398–1400 | 1928 | https://worldradiohistory.com/Archive-IRE/20s/IRE-1928-10.pdf | bf45c82a2b6b371d6d7216cc6da4eb6121cb892ce8a189cbdd6662bc24bd3748 |
| ROSA-1906 | E. B. Rosa, "Calculation of the Self-Inductance of Single-Layer Coils", Bull. Bur. Stand. 2(2), pp. 161–187 | 1906 | https://nvlpubs.nist.gov/nistpubs/bulletin/02/nbsbulletinv2n2p161_A2b.pdf | 6348c036d65a5e413e5c1bbbcd41d3f9121dfae427f20a50630bc54af8bc7989 |
| ROSA-GROVER-1912 | E. B. Rosa and F. W. Grover, "Formulas and Tables for the Calculation of Mutual and Self-Inductance (Revised)", Bull. Bur. Stand. 8(1) | 1912 | https://nvlpubs.nist.gov/nistpubs/bulletin/08/nbsbulletinv8n1p1_A2b.pdf | 73ec4b101d78494bb4d6d10312bc04df5313e678a27b008bd27e6bdadf85ff82 |
| LUNDIN-1985 | R. Lundin, "A Handbook Formula for the Inductance of a Single-Layer Circular Coil", Proc. IEEE 73(9), pp. 1428–1429 | 1985 | https://lup.lub.lu.se/record/144380/file/625001.pdf | fd3ea7e609f70e7cb7b2865622469b383d9a5bc679f41f9184b1ad60c98a95d5 |
| KNIGHT-SOLENOIDS | D. W. Knight, "An introduction to the art of Solenoid Inductance Calculation", v0.20 (self-published, archived copy) | 2016-02-04 | https://web.archive.org/web/20240823100519id_/https://g3ynh.info/zdocs/magnetics/Solenoids.pdf | 8c4b58e5e451c5365458c5e442468f4186d23c81969b359e4898e96ac8be061b |
| KNIGHT-SELFRES | D. W. Knight, "The self-resonance and self-capacitance of solenoid coils", v1.00 (self-published, archived copy) | 2016-05-04 | https://web.archive.org/web/20220308051006id_/https://www.g3ynh.info/zdocs/magnetics/appendix/self_res/self-res.pdf | fcdb1e1a2610b5fb7b8dd38443cba4a06f7b3b01fe70f7d67de9490cc71d9de3 |
| MEDHURST-1947 | R. G. Medhurst, "H.F. Resistance and Self-Capacitance of Single-Layer Solenoids", Wireless Engineer 24, pp. 35–43 and 80–92 | Feb. and Mar. 1947 | https://worldradiohistory.com/UK/Experimental-Wireless/40s/Wireless-Engineer-1947-02.pdf and https://www.worldradiohistory.com/UK/Experimental-Wireless/40s/Wireless-Engineer-1947-03.pdf | a5d65ba89521b8e71ddc8c744ca0bb286a46037e2f2cd9ed6ae20165a6af5b15; 166d53cb97dec9d3a04f9597b256355a845e8bd3967807819a727fb575f253d8 |
| GRANDI-1999 | G. Grandi, M. K. Kazimierczuk, A. Massarini and U. Reggiani, "Stray Capacitances of Single-Layer Solenoid Air-Core Inductors", IEEE Trans. Ind. Appl. 35(5), pp. 1162–1168 (author copy, archived) | 1999 | https://web.archive.org/web/20260518113320id_/http://www.die.ing.unibo.it/pers/grandi/papers/ia99.pdf | 28d6777e8a96346ecef5b54a7f36434b2d63b4fec0fe0dce068d07f5da585415 |
| PAYNE-2014 | A. Payne, "Self Resonance in Coils and the self-capacitance myth", Issue 1 (self-published, archived copy) | July 2014 | https://web.archive.org/web/20160321082721id_/http://g3rbj.co.uk/wp-content/uploads/2014/07/Self-Resonance-in-Coils.pdf | 57a916120a87163cc6204818174dffbf334b10291c4609f7f0f8ef75de68bc78 |
| VIS-28526 | Vishay, BFC2 808 Ø5 mm film trimmers | Rev. 06-Sep-2024 | https://www.vishay.com/docs/28526/bfc2808-5mm.pdf | d225b366554b6308e5c62fb1c1ba37b4d1e9addb28ce159dea76e36b11c021f6 |
| VIS-28527 | Vishay, BFC2 808 Ø7.5 mm film trimmers | Rev. 06-Sep-2024 | https://www.vishay.com/docs/28527/bfc2808-75mm.pdf | b9e82c88e1dee6ddf8a0fcda2c12f8db678e6c141a4c171dbdfa0183d72330c5 |
| VIS-28528 | Vishay, BFC2 808 Ø10 mm film trimmers | Rev. 06-Sep-2024 | https://www.vishay.com/docs/28528/bfc2808-10mm.pdf | 990befa3a81913206c6ca2495f59f1000d17e88c0984ac6c9eb393712daaaeca |
| EXX-CHIP-V3 | Exxelia, SMD chip trim ceramic trimmer capacitors AT 0300 R2, AT 1300 R2, AT 03HV00 R2 | Revision 02/26 | https://exxelia.com/storage/exxelia-assets-prod/datasheets/chip-trimmers-v3.pdf | 73d78f18dc810b73d5df2915a7ba08fdf5c3d0b8f6d22ba607e0cb397bfd3745 |
| EXX-THIN-V2 | Exxelia, SMD thin trimmers AT 9401G, AT 9402G, AT 9410G | Revision 02/26 | https://exxelia.com/storage/exxelia-assets-prod/datasheets/thin-trimmers-v2.pdf | 18a40dcb7c250117de478c47443919cc2160d0f823debbcbecd4b2c99dd74e9e |
| EXX-AT23XXG | Exxelia, SMD hermetic ceramic trimmer capacitors AT 23XXG | Revision 02/26 | https://exxelia.com/storage/exxelia-assets-prod/datasheets/smd-hermetic-ceramic-trimmer-capacitors-at-23xxg-series-datasheet.pdf | 702d0427c7a1a8a4ae9525a324016af148eedb24ba1e5b97a7dae8a6b4589103 |
| SUN-TSC3S | Suntan, TSC3S ceramic trimmer capacitor | undated | https://www.suntan.com.hk/pdf/Ceramic-Trimmer-Capacitors/TSC3S.pdf | 42f404fc2859cf9b4ab0e62eac21b55b71cc3f22f3b92e89ab861817f678ccb4 |
| SUN-TSC3 | Suntan, TSC3 ceramic trimmer capacitor | undated | https://www.suntan.com.hk/pdf/Ceramic-Trimmer-Capacitors/TSC3.pdf | c8a06d5123a5981ca44c1af4b2151a541ef8ae67b0b7debcd311b95c8b9d616f |
| SUN-TSC5 | Suntan, TSC5 ceramic trimmer capacitor | undated | https://www.suntan.com.hk/pdf/Ceramic-Trimmer-Capacitors/TSC5.pdf | 6f4e1bfe9406b0296d5fa83805ce9a3052ddf22b141471d0f6d8383ba2b25fe9 |
| SUN-TSC7 | Suntan, TSC7 ceramic trimmer capacitor | undated | https://www.suntan.com.hk/pdf/Ceramic-Trimmer-Capacitors/TSC7.pdf | e546a996aa14859baf1071655de472cf8da7efd2825996f120b7219db780950e |
| KNO-CAT-R5 | Knowles, "Trimmers and Non-Magnetic Components" catalog | R5 (PDF dated 2024-08-22) | https://www.knowlescapacitors.com/getmedia/fae461ef-e086-4f0e-af62-725f9d523a26/KNO_Trimmer_Catalog_R5-sm | d35f9117ff63df80fcf8f87ea2a942e01f632feb7cdada63a5fcfc5621516242 |
| KNO-V70513 | Knowles Voltronics, outline drawing V-70513, JZ high-voltage series | Rev. C, 03/29/22 | https://www.knowlescapacitors.com/getattachment/Products/Capacitors/Trimmer/Half-Turn/JZ-Series/Knowles-JZ-Series-V-70513-JZ_High-Voltage-(1).pdf?lang=en-US | c3ad369a6fd83144008c3cda4b11bce1fd94f2110e4e6d960d8704fee9d87607 |
| MUR-T13E | Murata, Ceramic Trimmer Capacitors, Cat. No. T13E | Sep. 1, 2017 | https://www.murata.com/~/media/webrenewal/support/library/catalog/products/capacitor/trimmer/t13e.ashx?la=en-us | 1c42646b0c55b289dee4c7ea5a1890c2f32dc1bade1be8d7f0eeb285786aaa89 |
| MUR-EOL-2018 | Murata, Product Withdrawal Notice, Ceramic Trimmer Capacitor TZ Series, DM-TA17-002 (distributor-hosted copy) | Jun. 26, 2018 | https://www.farnell.com/datasheets/2629422.pdf | 02e2f04faafc7338f7aba40d741a473db3d4467569f6e0916faf05ca6740df3b |

GRM1885C1H…A01 reference sheets read [MU-GRM]:

| Part | Date | SHA-256 |
|---|---|---|
| GRM1885C1HR50BA01 | as of Jun. 24, 2026 | b6e524b2d6efff891c4cfccbb9e638257cadb831119f3a367004fdb327a36cf5 |
| GRM1885C1H1R0CA01 | as of Jun. 17, 2026 | b6dc743db5c455c3c332ce55de73fde46b28c4aa5ad602e3b207afc0a8b25197 |
| GRM1885C1H4R3CA01 | as of Jun. 24, 2026 | 01a57c47a2f547f672aa42d124ea39f50b964a044097589b85fe7f65dd30f4c7 |
| GRM1885C1H4R4WA01 | as of Jun. 24, 2026 | 27f36ff8a8a5768fbbc17eff34a088f2e4bef76426747e101ece9a22be8a1824 |
| GRM1885C1H5R1DA01 | as of Jun. 24, 2026 | 7c1d392b426a2b41508fd920682357b838ec746ea1b16361c15362d601a5d0e1 |
| GRM1885C1H9R1DA01 | as of Jun. 24, 2026 | 03b03666bfa6701cb46965529dc8e704ca4e0ace3f11a90a5152dd94a77d1951 |
| GRM1885C1H100GA01 | as of Jun. 17, 2026 | e6950bf95a3560e7fb15f5589c80a50a421e4fb7c750276ed359b786934dbcd1 |
| GRM1885C1H100JA01 | as of Jun. 17, 2026 | cdf2518f4ebb1a89a4c6f74ebe19cd47c6174bf239896bf36d1823614dd928e9 |
| GRM1885C1H130JA01 | as of Jun. 17, 2026 | 80e1c596b2053dd04cd3bc6841cb827b32797413280e9a39c09bdedd8dcde195 |
| GRM1885C1H101JA01 | as of Jun. 17, 2026 | e40c8952c496ec7a35306361e4c7a0ee0413d2cc351c621d2d4c8468301881ed |
| GRM1885C1H911GA01 | as of Jun. 24, 2026 | 111387298f6c1c5896930ea9374b3fd6a464e0a1d71b2803947e1a46f8c49aa2 |
| GRM1885C1H102JA01 | as of Jun. 17, 2026 | 7d35f9fb419533bcff55f0d8a3c9944cb1ccd776ff6993b3505244aef18e9add |
| GRM1885C1H112JA01 | as of Jun. 17, 2026 | f8b89d2e26e75149ae3bdda3c525728c4fad4f13e63f01bd3a3d4f9f4a12ee12 |
| GRM1885C1H103JA01 | as of Jun. 17, 2026 | 3f5a339eb51502df7716dfd2d4c4e6d33e837abc0df5cb8e4fc1e6e275d09790 |
