# Full-Review Remediation Plan: Completion

**Date**: 2026-06-12 09:16
**Severity**: Medium
**Component**: All (Chebyshev g-value computation, CLI 2.0.0, response exports, wizard UX, refactoring, documentation)
**Status**: Resolved

## What Happened

Completed phases 6–11 of an 11-phase remediation cycle (phases 1–5 had landed in previous merge). Every phase shipped with review gates, and every gate caught regressions the implementation missed.

## The Brutal Truth

Simulation-gated acceptance was a tyrant that overruled three plausible analytic-only plans: shunt-C removal failed until we proved the netlist held inductance; FBW cap scaled from 15% to 10% because simulation demanded it; end-coupling placement had to match the SPICE harness exactly. Golden snapshots before the largest refactor (phase 10, -188 LOC) created a false sense of safety — they caught nothing because they *forced* discipline, not because they validated correctness. Then review found an unpinned wizard behavior change (LP-T/HP-Pi column reordering) hiding inside the "byte-identical" commit. Documented CLI examples (`lp bw 10MHz --topology t`) survived *multiple* doc passes, existing in every README and example section, *never executable* — the positional topology slot ate the frequency. Only when we built a "run every example" gate did they surface. This stings because the examples were the public API surface: users copy-paste them, trust them, and we shipped them broken for years.

## Technical Details

**Phase 6 (bd5bee7)**: Chebyshev bandpass g-values now computed by formula for 0 < ripple ≤ 3.0 dB (nested hyperbolic functions, delta-3dB scaling); deleted 0.1/0.5/1.0 dB lookup table. Tightened dB→neper constant from `20/ln(10)` to exactly `40/ln(10)` (inverse magnitude ratio). Verified against published Zverev reference values to 1e-4 tolerance; worst observed error 8.6e-5.

**Phase 7 (2887b39)**: CLI 2.0.0 breaking change: `-t` removed (was ambiguous for type/topology); `-T added (mandatory, 't'/'pi'). Missing required args now exit(2) with usage+example (not silent default). Ripple sentinel warning when unspecified. Default filter order raised 2→3. Toroid table shows top-1 match by default, `--toroid-full` for all candidates. Wizard subcommand, `--version` flag, `--verify` deleted.

**Phase 8 (43778bd)**: Three divergent response-export implementations collapsed into one schema. Wizard Save now emits both stdout plot and `-response.{json,csv}` file. Unified Chebyshev polynomial magnitude form (cos/cosh) across transfer functions. Review caught changelog documenting the wrong "old" schema (deleted library API, not what CLI emitted) and a crash path (Save with empty result).

**Phase 9 (4e14d18)**: Wizard input parsing aligned with CLI: `parse_impedance` gained bare `k`/`M` suffix support. Odd-order hints at filter-config time. Nav hints on every screen. Worker ERROR properly surfaces. Button rename: `calculate-btn` → `next-btn`.

**Phase 10 (699cf7c–a181b18)**: Largest refactor. Golden snapshots established *before* refactor (24 byte-identical at consolidation commit). Single data-driven LP/HP renderer (CLI + wizard). Capacitors-only E-series policy ("wind to value" for inductors). Single component-kind placement helper. Dead modules deleted. Net -188 production LOC. Side effect: wizard LP-T and HP-Pi column order converged to CLI primary-component-first. Pinned + changelogged.

**Phase 11 (d3360eb, 31dedf5)**: Full docs sync. Corrected HP Bessel "linear phase" claim (group delay not preserved through HP transformation). Added CLAUDE.md netlist-simulation testing convention. Caught docs draft claiming harness was SPICE; corrected to stdlib nodal analysis.

## Root Cause Analysis

The broken CLI examples persisted because example documentation was never gated on execution. Code reviews examined logic and performance; doc passes examined typos and formatting — but no stage validated that copy-pasted examples actually work. Simulation acceptance (phases 1–5) proved so effective at catching analytic mistakes that it created overconfidence in architecture choices, letting hidden wizard regressions slip through phase 10's "byte-identical" gates.

## Lessons Learned

1. **Execution gates beat review**: Golden snapshots enforced discipline but proved useless at validation. Simulation-gated acceptance caught real errors that analytic review missed. Example-execution gates catch what human doc review skips.

2. **Documentation examples are code**: They belong in a test suite. Run them on every PR. `git grep` for all examples in docs and verify each one against current CLI/API.

3. **"Byte-identical" is a false guarantee**: Refactors that don't change test inputs will pass snapshot tests while changing behavior. Golden snapshots catch *regression* of existing behavior, not *drift* in undercovered behavior.

4. **Review finds what tests miss**: Review caught three things tests never would: wrong documented schema, undercovered wizard column reordering, crash path (empty result to Save). Tests verify happy paths; review questions *why*.

5. **Formulas > lookup tables, always**: Chebyshev g-value formula made ripple a true free variable (0–3.0 dB) and cut a maintenance burden. Closed-form math is easier to verify and less brittle.

## Next Steps

- **Executable examples gate**: Add CI check that extracts all CLI examples from docs and runs them. Fail if any fail.
- **Simulation testing for future changes**: The netlist harness should run on every bandpass change, not post-hoc validation.
- **Docs sync automation**: Consider doc generation from live code (e.g., generate CLI examples from test fixtures).

---

**Status:** DONE
**Summary:** 11-phase remediation complete, main merged (3b95112), 1211 tests passing, ruff clean. Simulation gated acceptance and example-execution tests proved essential; golden snapshots created false confidence. Nothing pushed to remote.
