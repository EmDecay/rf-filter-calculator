# Project Changelog

## 2026-04-24 (Follow-up) — Chebyshev BP 3dB Semantics & Wizard Corrections

Fixes to core filter semantics and wizard display logic, with comprehensive regression testing.

**Key Fixes**:
1. **Chebyshev BP 3dB semantics** — User-supplied `bw` is now true -3dB BW (not ripple-edge BW). New `chebyshev_3db_deviation(order, ripple_db)` helper in `bandpass/transfer.py` computes scaling factor `delta_3dB = cosh(acosh(1/ε)/n)`. Synthesis divides `fbw` by this factor; magnitude plot scales `delta` up by same factor. Butterworth/Bessel unaffected (already land at -3dB).
2. **Wizard HP inductor parallel math** — `format_eseries_recs` now takes `parallel_mode` parameter (`"additive"` for caps, `"harmonic"` for inductors). Wizard now correctly passes `parallel_mode="harmonic"` for HP/LP/BP inductor combos. Was using additive math (incorrect) before.
3. **NaN/infinity validation hardening** — Public float parameters across `lp_hp_base_calculations.py`, `bandpass/calculations.py`, `bandpass/transfer.py`, `transfer_functions.py` now reject NaN/inf with: `if not math.isfinite(x) or x <= 0: raise ValueError("X must be positive and finite")`. Kept "must be positive" substring for regex test compatibility. Also: `frequency_sweep` and `generate_frequency_points` reject `points < 2`.
4. **Wizard export format preselect** — `ResultsScreen` now calls `_preselect_export_format()` on mount to honor user's Output Options export format choice (json/csv/txt).
5. **Regression test suite** — New `test_codex_review_fixes.py` (426 LOC, 40 tests) covering Chebyshev BP 3dB semantics, wizard HP harmonic parallel, NaN/inf validation, export format preselect.

**Test Stats**: 1086 tests (+40), 94% coverage.

---

## 2026-04-24 — Coverage Pass + Bandpass / Validation Hardening

Coverage expansion: 826 → 1046 tests (+220, ~27% growth), 78% → 94% coverage. Four new test modules (189 tests) + expanded existing modules covering CLI coverage gaps, transfer function dispatch, wizard screen navigation, input validation, and event handlers.

**Test Suite Growth**:
- `test_cli_coverage_gaps.py` (45 tests) - CLI main(), subcommand wiring, validation error paths (negative frequency/impedance/ripple rejected with clear errors)
- `test_transfer_and_shared_edges.py` (24 tests) - HP transfer alias dispatch (ch/bs/bw/unknown), E-series edge cases, toroid validation
- `test_wizard_screens_coverage.py` (91 tests) - FilterScreenNavigationMixin, WelcomeScreen, OutputOptionsScreen, ResultsScreen, LP/HP/BP `_calculate` validation via Mock(spec=RadioSet/Input/...) pattern
- `test_wizard_event_handlers_and_final_edges.py` (29 tests) - Input.Submitted handlers, `_on_filter_type_changed`, csv export, wizard entry point, toroid iteration branch

**Wizard Screen Coverage**: Screens now 68-82% covered via Mock pattern + `type(screen).app = property(...)` harness (previously claimed "not covered / interactive"). Full `compose()`/`on_mount` coverage deferred (requires Textual pilot harness).

**Bandpass & Validation**:
- Bandpass true -3 dB edges via quadratic formula (commit e1a7c3a) — source: `bandpass.calculations.compute_bandpass_3db_edges`, uses `f_low = f0²/f_high` dodge catastrophic cancellation for wide BW
- Even-order Chebyshev rejection in LP/HP/BP CLI + wizard (commit 0829ee6) — equal source/load terminations require odd order
- Filter-type alias canonicalization (commit a92d073) — `shared/cli_aliases.py::FILTER_TYPE_ALIASES` single source of truth; dispatch uses `shared/transfer_response_dispatch.py::_canonicalize_filter_type`
- Input validation: negative frequency/impedance/ripple rejected with clear errors

**Testing Patterns**:
- CLI subcommand testing via `_lp_args`/`_hp_args`/`_bp_args` Namespace builders (see `test_cli_coverage_gaps.py`)
- Wizard screen testing via Mock(spec=RadioSet) + `type(screen).app = property(lambda s: app)` override
- JSON coverage report export: `uv run pytest tests/ --cov=filter_lib --cov-report=json:/tmp/rf-cov.json`
- Total runtime: ~0.5s

**Module Coverage Updates**:
- `cli/__init__.py`, `cli/toroid_flags.py`, `cli/wizard_cmd.py`: 100%
- `shared/cli_helpers.py`, `shared/toroid_selection.py`: 100%
- `wizard/filter_screen_navigation_mixin.py`, `wizard/interactive.py`, `wizard/widgets/__init__.py`: 100%
- Wizard screens (lowpass, highpass, bandpass, welcome, output_options, results): 68-82%

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
