# Project Changelog

## 2026-04-23 — Toroid Inductor Recommendations (GH-6)

Automatic iron-powder T-series toroid core + winding recommendations for every
inductor produced by LP / HP / BP calculations.

- Vendored 43-core iron-powder T-series database (mixes 0/1/2/3/6/7/10/17).
- Per inductor: top 3 recs ranked by accuracy, tie-broken by temp coefficient, then core OD.
- Reports integer turn count, AWG, actual L after N rounding (signed error %),
  ±5% A_L-tolerance L range, Pythagorean wire length, DC resistance,
  DC-based Q upper bound, core dimensions.
- Frequency gating excludes cores whose published range does not cover the design freq.
- Mechanical wire-fit gating (0.9 fill × 1.07 enamel factors) excludes infeasible windings.
- Bandpass emits a single shared block labelled `L_resonant (applies to L1…Ln)`.
- JSON (LP/HP): `toroid_recommendations` array per inductor.
- JSON (BP): top-level `resonator_toroid_recommendations`.
- CSV: 10 new columns (`ToroidCore`, `ToroidMix`, `ToroidTurns`, `ToroidAWG`,
  `ToroidActualL_uH`, `ToroidErrorPct`, `ToroidWireLength_mm`, `ToroidDCR_mohm`,
  `ToroidQ_DC_Upper`, `ToroidTempCoeff_ppm`).
- CLI flags: `--no-toroids` (format-agnostic opt-out; restores pre-feature schema);
  `--toroid-compact` (1-line-per-rec text output).
- Accuracy contract: A_L stored in nH/turn² internally; regression-tested against
  the research doc's unit-mismatched `N = 100·√(L/A_L)` form (e.g. T68-2 @ 2.5 µH
  correctly returns N=21, not 66).
- Q labelled "DC est, upper bound" — core loss and AC skin effect not modelled.
- 93 new tests; all 732 existing tests still pass (total 825).

### Deferred for future work

FT/FB/BLN ferrite, AC resistance w/ skin effect, SRF estimate, core-loss
modeling, saturation/B-field, temperature derating in L range, multi-toroid
stacking, per-inductor AWG override.
