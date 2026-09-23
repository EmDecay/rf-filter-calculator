# Project Changelog

## Unreleased — 2026-09-22 — Dead Code Cleanup

### Removed

- Library API: unused helpers are removed from `filter_lib.shared` submodules. Some have an
  exact equivalent, some only an alternative, and some no replacement:
  - `toroid_core_data.list_sources`: no replacement. Look up individual source IDs with
    `get_source`.
  - `ToroidCore.source_for(group)`: pass `dict(core.field_sources).get(group)` to
    `get_source` when it is not `None`. `field_sources` holds `(field_group, source_id)`
    pairs, not source records, and an unrecorded group has no entry, where the old method
    returned `None`.
  - `ToroidRecommendation.ranking_key`: no replacement. `recommend_cores` already returns
    candidates in ranked order.
  - `MechanicalFit.wire_length_m`: use `wire_length_mm * 1e-3`, which is exactly how the
    field was computed.
  - `numeric.require_integer`: no replacement.
  - `MatchedSimSummary.deprecated`: no replacement needed. The `--sim-matched` JSON still
    reports `"deprecated": true`.
  - Removing the `wire_length_m` and `deprecated` fields shifts the positional order of the
    later `MechanicalFit` and `MatchedSimSummary` fields. Callers that construct either
    dataclass should pass those fields by keyword.
  - `strict_json.strict_json_dumps`: use `dumps_strict`, the function it aliased.
  - `branch_admittance.branch_admittance`: no replacement. `solve_s21` and
    `solve_transducer_power_gain` compute branch admittances internally.
  - `matched_simulation.simulate_pair`: no exact replacement. `run_matched_simulation`
    measures the calculated and nominal builds through build-realization analysis.
  - `topology_diagrams.print_pi_topology_diagram` and `print_t_topology_diagram`: `print()`
    the result of the matching `format_*_topology_diagram` function, which gives identical
    output.
  - `transfer_response_dispatch.make_bp_response_db`: for the same ideal-prototype response,
    call `bandpass.ideal_response.magnitude_db(f, f0, bw, order, filter_type, ripple_db)`
    with a canonical filter-type name; it does not accept aliases such as `bw` or `ch`.
    `make_bp_netlist_response_db(result)` is a different model: it returns the simulated
    response of the synthesized circuit.
- `python -m filter_lib.wizard.app` is removed; run `filter-calc` or `filter-calc wizard`.
- Unused private aliases in the `bandpass.calculations`, `build_simulation`, and
  `netlist_simulation` compatibility facades are removed; import the implementation modules
  directly.

### Input and API contracts

- `--format spice` and `--sim-build` with a cutoff near the float maximum (for example
  `1.7976931348623157e307`) now exit with `Error: frequency span must be positive and finite`
  instead of an `OverflowError` traceback.
- `solve_transducer_power_gain`, `solve_s21`, and the transducer-gain evaluator raise
  `ValueError: output voltage magnitude must be finite` instead of `OverflowError` when the
  output voltage magnitude exceeds the float range.
- Loading the packaged toroid data rejects overflowing number literals such as `1e999`,
  non-finite core fields, and a negative A_L tolerance.

## Unreleased — 2026-09-22 — Source Bug Remediation

### Input and API contracts

- Frequency, impedance, and inductance parsing now reports an exponent beyond the decimal
  range (for example `1e1000000000`) as `must be positive and finite`. It previously raised
  an internal `decimal.Overflow`: a traceback at the CLI and an unhandled error in the wizard.
- LP/HP `frequency_response` accepts every `FILTER_TYPE_ALIASES` key, adding `b` and `c`,
  through the shared canonicalizer. An unknown type now raises the shared message
  `Unknown filter type '<name>'; expected one of butterworth, chebyshev, bessel ...`.
- Harmonic (inductor) parallel pairs below about 1e-308 no longer collapse to 0.0 with a
  −100 % error. The value is computed on exactly scaled parts, so every selection in the
  normal range is bit-for-bit unchanged.
- `export_response_json` raises `ValueError` instead of `TypeError` for non-JSON metadata keys
  or values.

### Output formatting

- `--plot-data csv` writes each frequency as the shortest decimal that round-trips to the same
  binary64 value (`1000000.0`, `1096478.196143185`). This replaces the `%.6g` format from
  2.0.0, which merged distinct narrow-band frequencies. A 1 GHz / 100 kHz bandpass sweep now
  has 601 distinct, increasing CSV frequencies that equal the JSON `frequency_hz` values.
- No output prints a negative zero. Response data, E-series error cells, toroid turn errors,
  build peak and half-power values, and `--sim-matched` deltas now show `0.00` (or `+0.00`
  where a sign is always shown) instead of `-0.00`. In the E-series table, an error that
  rounds to zero now prints `(0.0%)` whatever its sign, where a tiny positive error used to
  print `(+0.0%)`.
- A derived user Qu (for example from `--ql 180 --qc 500`) prints as `Qu=132.4` instead of
  `Qu=132.3529411764706`. Compact values such as `100`, `12345`, or `1e+06` print as
  before. A precise Qu keeps at least four significant digits and all of its integer digits,
  and more only when needed to keep two different Qu values distinct. The
  `Loss-model complete-resonator unloaded Q` line and its `Derived from QL=… and QC=…` values
  follow the same rule, so `--qu 12345` prints `12345` rather than `1.234e+04`, and a widened
  Qu reads the same on both lines. JSON keys and values are unchanged.

### ASCII plots

- Both renderers and both full-plus-zoom pair renderers skip non-positive frequencies before
  ranging the log axis. An input with no positive frequency returns a single
  `No data to plot`. The LP/HP renderer previously raised `math domain error`, and the
  bandpass renderer pinned its axis at 1 Hz. A NaN, infinite, or non-numeric frequency raises
  `Plot frequencies must be finite real numbers`.
- Empty columns inside the plotted span are filled with the response interpolated in
  log-frequency. The default 51-point LP/HP sweep no longer leaves a blank column near the
  right edge. Narrow peaks keep their full height.
- The passband-detail view is omitted when no sample reaches its window, instead of drawing
  an empty grid.

### Wizard

- The ripple fields apply the same `0 < ripple <= 3.0 dB` rule and messages as the Next button,
  so a legal ripple below 0.01 dB is no longer styled invalid. The order and resonator fields
  accept only integers 2–9, so `3.5` is styled invalid before Next rejects it.

### Toroid candidates

- Table output (CLI and wizard, full and compact) now states once per section that RF Q,
  core loss, SRF, saturation, thermal rise, and power handling are not assessed. JSON and CSV
  already carried this per candidate and are unchanged.
- Wire length uses the reported datasheet wire diameter (AWG 14 on T68-2: 1.600 mm, not the
  formula's 1.628 mm). For example, the realized-build substitution line
  `on T68-2, 12 turns of AWG 14` now shows `277 mm` instead of `278 mm`. Build JSON
  `wire_length_mm` changes to match.
- Geometry-estimate DCR uses IACS annealed copper (1.724e-8 Ω·m), the basis of AWG tables,
  instead of 1.68e-8 Ω·m. Manufacturer-table DCR is unchanged.
- The A_L tolerance note is derived from the candidates shown instead of hard-coded as ±5 %.
  When candidates differ, the note refers to each candidate's L range line. A section with
  no candidates omits the note.

### Performance and messages

- `--sim-matched` measures only the calculated and nominal circuits instead of running and
  discarding the full tolerance screening. For a 14.175 MHz / 350 kHz three-resonator
  bandpass, the analysis dropped from 3.18 s to 0.12 s (26×; CLI wall time 3.25 s to 0.26 s).
  Measured values are bit-identical; only the negative-zero formatting above changes the text.
- Build measurements validate each circuit once, not at every frequency. For the same design,
  `--sim-build` analysis dropped from 1.77 s to 1.36 s (1.30×), with bit-identical measurements.
- A bandpass bandwidth below the binary64 resolution of f0 now reports `bandpass bandwidth is
  too small relative to f0 to form a sweep span`. `frequency span must be finite` remains for
  an overflowing span.
- Usage errors use a singular verb for one flag (`--capacitor-tolerance requires --sim-build or
  --format spice`, `... affects tolerance analysis ...`).

## Unreleased — 2026-09-22 — Test Suite Audit

- Tests now check component values and responses against published prototype tables and
  independent closed-form or ABCD calculations, rather than repeating implementation formulas
  or asserting only counts, types, and non-empty output.
- Test files named after audits or coverage passes were dissolved into behavior-named files,
  and duplicated tests were removed after confirming no line lost its only coverage.
- Small-magnitude `pytest.approx` comparisons now set `abs=0`; the default 1e-12 absolute
  tolerance had made several picofarad and near-zero checks vacuous.
- Wizard direct-handler stubs are installed with `monkeypatch`, which fixes an order-dependent
  test. New mounted Textual journeys cover each design screen's widgets and focus chain.
- Runtime-budget tests carry a registered `runtime_budget` marker. CI and the documented local
  gates select them by marker instead of by hard-coded test ids, and `--strict-markers` is on.
- The deprecated `--sim-matched` compatibility tests share their expensive simulations, which
  cut about two minutes from a coverage run.

## Unreleased — 2026-09-22 — Wizard Toroid Output

- Wizard table output for lowpass, highpass, and bandpass now includes the screened toroid
  winding candidates. It previously omitted them even though wizard JSON and CSV output
  included them. The saved text file follows the on-screen output.
- Output Options adds **Toroid Winding Detail**: Full (default, up to three candidates, as
  `--toroid-full`) or Compact (one line for the best candidate, as `--toroid-compact`).
- Realized-build substitution lines now show winding wire gauge and length, for example
  `on T68-2, 12 turns of AWG 14 (278 mm)`. Build JSON substitution records add `wire_awg`
  and `wire_length_mm`, which are `null` when no screened winding was used. This applies to
  both the CLI `--sim-build` and the wizard.
- CLI table and toroid output are unchanged. CLI and wizard now share one toroid-section
  formatter.

## Unreleased — 2026-09-07 — Response Measurement Accuracy

- Build analysis now evaluates requested passband boundaries, refines extrema and half-power
  crossings, and checks successive meshes for convergence. Every tolerance case uses the same
  policy. Unresolved cases and out-of-window skirts remain visible with explicit summary omissions.
- Reported bandwidth identifies its local reference peak and selected connected region;
  disconnected regions and global peak gain remain separate quantities.
- BP plots and response exports use bandwidth-relative windows with center/edge landmarks.
  CLI and wizard share evaluated threshold tables; passband detail also zooms horizontally.
  Narrow-band labels retain enough digits to distinguish the skirts.
- BP SPICE exports use a bounded bandwidth/order-aware linear sweep. LP/HP retain their
  logarithmic sweep. External-SPICE execution is not a bundled test dependency.
- Top-C validation explicitly covers passband and near-stopband behavior. Actual lossless
  circuit harmonic samples and Cohn/equivalent-loss center comparisons are informational;
  synthesis formulas, solver and existing acceptance gates are retained.
- Precise user Q values retain distinct loss-estimate keys instead of colliding with a standard
  example through compact-number formatting.
- Added independent ABCD circuit regression coverage and updated interpretation, theory,
  caveats, architecture, testing and sample-output documentation.

## 2.1.0 — 2026-07-19 — Accuracy, Build, and Release Remediation

This release turns calculated values, physical-part choices, simulations, and limitations into
separate auditable contracts.

### Accuracy and numerical behavior

- Replaced formula-only Top-C claims with per-design calibration and independent netlist
  verification of both −3 dB skirts, connected/outer regions, passband shape, Chebyshev ripple,
  and representative stopband samples. Results expose `response_validation_status`; known
  unrealizable cells fail cleanly.
- Added independent bandpass tank reactance/inductance controls and explicit complete-resonator
  versus component-Q semantics. Extreme-but-representable calculations now use stable
  log-domain, cancellation-resistant, Decimal-scaled, and adaptive Decimal-nodal paths.
- Public numeric APIs consistently reject booleans, wrong types, NaN/infinity, invalid ranges,
  impossible allocations, and non-finite final results with `ValueError` rather than leaking
  interpreter exceptions.
- Explicit `--fl`/`--fh` values are preserved in `requested_parameters` and build `target`
  metadata; reconstructed calculated edges agree within floating precision.

### Buildability and output truthfulness

- Replaced implicit nearest-value behavior with a deterministic capacitor policy: prefer a
  single within 1%, choose a parallel pair only for at least 0.5 percentage-point improvement,
  and require expert action below 1 pF. Table, wizard, JSON, CSV, build, and SPICE surfaces state
  the selection or explicit fallback.
- Added `--sim-build`: selected physical branches, exact fallbacks, constant-series-loss models,
  separate evaluation ports, deterministic tolerance corners, and optional seeded bounded
  samples. Output labels this as simulation—not measurement, yield, probability, or guaranteed
  worst case. `--sim-matched` remains a deprecated compatibility alias.
- Added generic exact and nominal-build SPICE decks from the same named circuits used internally.
  The CLI defaults to `nominal-build`; comments distinguish load voltage from transducer gain.
- Restricted automatic toroid candidates to exact primary-source-verified T25-6, T50-2, and
  T68-2 records. Reports preserve provenance and published winding capacity while explicitly
  declining RF-Q, SRF, core-loss, saturation, thermal, and power claims.
- JSON is strict and finite, CSV is rectangular and policy-auditable, response exporters validate
  every sample, and contradictory/ignored CLI and wizard option combinations now fail visibly.

### Wizard, packaging, and verification

- Added wizard build-analysis controls, detached calculation snapshots, revision-guarded worker
  publication, stale-worker cancellation, failure-safe export, UTF-8/CSV-safe saves, and clear
  Design Another/Export/Quit actions.
- Split synthesis, verification, realization, solver, output, and wizard responsibilities into
  focused modules while retaining supported public facades.
- Package metadata now requires Python 3.10+, ships runtime data, and reports version 2.1.0.
  CI uses current pinned major actions, runs Ruff and coverage-gated tests on Python 3.10–3.13,
  inspects wheel/sdist contents, and smoke-tests the installed wheel.
- The suite now contains more than 2,000 tests with a 90% CI line-coverage floor, including a
  maintained 128-cell bandpass study, solver analytic references, machine-output contracts,
  packaging checks, and real Textual pilot flows.

---

## 2026-07-06 — Math-Audit Remediation + Matched-Value Simulation

**BREAKING**: Chebyshev LP/HP ripple parameter now capped at 3.0 dB (was no upper bound in LP/HP CLI, wizard and bandpass already had the cap). Ripple value of 3.5 dB now errors "Ripple must be at most 3.0 dB" instead of accepting it.

**Chebyshev cutoff convention (display + docs)**: Chebyshev LP/HP table output now prints under the header: "Note: Chebyshev cutoff = ripple-band edge (attenuation = ripple at fc); see threshold table for the -3 dB frequency." Butterworth/Bessel LP/HP do NOT print this note. Bandpass `bw` remains true -3 dB BW. [filter-theory.md](filter-theory.md), [project-overview-pdr.md](project-overview-pdr.md), and README already got targeted edits in earlier phases.

**Bandpass insertion-loss estimate (Cohn 1959)**: New table line: "Est. insertion loss (Cohn): X.X dB @ Qu=100, X.X dB @ Qu=250" (plus user's `--qu` value when given, optional flag). Formula: `IL ≈ 4.343·Σgᵢ/(fbw_synth·Qu)` dB. JSON adds top-level `il_estimates` mapping (e.g. {"100": 3.47, "250": 1.39}); `q_min` unchanged. Bandpass result dict also gained `fbw_synth` field.

**Relabeled Q-safety text**: Old line "Minimum Component Q:" relabeled to "Minimum usable Q (severe loss at this value):" in both LP/HP/BP CLI table output and wizard, matching the design intent.

**Toroid wire-length correction**: Per-turn wire-radius term changed from 4·r_wire to 2π·r_wire (corner arcs sum to a full circle). Wire lengths/DCR values in any doc examples are now a few % higher; turn counts and core rankings unchanged. E.g. T50-2 N=10 AWG22 is now ≈170 mm (was ≈163).

**Bessel bandpass phase caveat (docs only)**: LP→BP transform does not preserve flat group delay. Already added to [caveats-and-known-issues.md](caveats-and-known-issues.md) ("Bessel Bandpass Group Delay" section) and [filter-theory.md](filter-theory.md).

**New `--sim-matched` flag**: Re-simulates the circuit with capacitors replaced by their recommended E-series matches (single or parallel, whichever |error| is smaller; parallel combos simulated as combined value), inductors kept exact. Prints a "Matched-Value Simulation (E24)" comparison block after table output: LP/HP show -3 dB cutoff + worst passband dev with Exact, Matched, Delta columns; BP shows Center f0 / -3 dB BW / Lower edge / Upper edge / Worst passband dev. `--sim-matched --no-match` is a usage error. JSON adds additive `matched_sim` key. New module: `filter_lib/shared/matched_simulation.py`.

**Test Stats**: 1274 tests passing, 95% coverage.

---

## 2026-06-12 — Validation Hardening + Test Strengthening

- **`--version` fallback**: CLI falls back to `filter_lib.__version__` when distribution metadata is unavailable, so source-checkout runs don't fail during parser construction; `__version__` corrected to 2.0.0.
- **Wizard ripple validation**: all three parameter screens reject non-finite (NaN/inf) Chebyshev ripple before storing it in filter state, with regression coverage.
- **Test strengthening**: stronger assertions and added coverage across bandpass, E-series, CLI, and netlist-simulation tests; unreachable defensive guards removed from `eseries.py`, `lp_hp_base_transfer_functions.py`, and `plot_threshold_analysis.py`.

**Test Stats**: 1227 tests passing, 94% coverage.

---

## 2026-06-12 — Capacitors-Only E-Series Matching

**BREAKING**: E-series matching now applies to capacitors only. Inductor standard-match
data has been removed from JSON and CSV export surfaces, including wizard exports;
text table output now directs inductors to be wound to value using the toroid
recommendations.

Also in this consolidation: LP/HP rendering (CLI and wizard) now goes through one shared
module. The wizard component table consequently adopts the CLI's primary-component-first
column order — lowpass T and highpass Pi tables now list Inductors in the left column
(previously the wizard always showed Capacitors first). Internal export surfaces deleted:
`filter_lib.shared.filter_result`, `filter_lib.wizard.validation`, `filter_lib.wizard.widgets`.

---

## 2026-06-12 — Unified Response-Export Schema + Wizard Plot Export

**BREAKING (clean break, user-decided)**: `--plot-data json|csv` now emits one unified schema for LP/HP/BP from `shared/response_export.py` (the three divergent implementations in `shared/transfer_functions.py`, `bandpass/transfer.py`, and `shared/plot_data_export.py` are deleted).

Old → new JSON key mapping (what `--plot-data json` actually emitted before):
- LP/HP: top-level `filter_type`/`cutoff_hz`/`order`/`ripple_db` → nested `filter` block: `category`, `response_type`, `order`, `cutoff_hz`, `topology`, `ripple_db` (Chebyshev only). `data` unchanged.
- BP: previously a flat object — `filter_type` → `filter.response_type`; `f0_hz` → `filter.f0_hz`; `bandwidth_hz` → `filter.bw_hz`; `order` → `filter.order`; `data` unchanged. `filter.category` and `filter.coupling` are new keys. (None ripple was already omitted.)
- CSV: header `frequency_hz,magnitude_db` unchanged; magnitudes stay 2-decimal; BP frequencies change from raw float repr (`14175000.0`) to `%.6g` (`1.4175e+07`), matching LP/HP.
- Library API: the separate `filter_lib.bandpass.export_response_json/csv` functions (nested `{"filter": {type, response, n_resonators}, "frequency_response": [{freq_hz}]}` shape, `freq_hz` CSV header — never wired to the CLI) are deleted; use `filter_lib.shared.response_export`.

**New**:
- Wizard Save now honors the Output Options "Export Plot Data" choice: a second `{category}-{timestamp}-response.{json|csv}` file is written next to the component file (LP/HP from the analytic response; BP from the netlist-simulated sweep). Save notifications show absolute paths for every file written.
- Single `chebyshev_polynomial` implementation (cos/cosh magnitude form, numerically stable outside the passband) in `shared/transfer_functions.py`; the bandpass duplicate is deleted, equivalence-tested against the classic recurrence.

**Test Stats**: 1206 tests passing.

---

## 2.0.0 — 2026-06-12 — Breaking CLI Cleanup + Chebyshev G-Value Unification

One coordinated breaking release so the CLI surface changes land once.

**BREAKING CHANGES**:
1. **`-t` short flag removed** from all three subcommands. `--type` remains; new `-T` short flag for `--topology` on lowpass/highpass. Bandpass keeps `-c/--coupling` unchanged.
2. **`--verify` removed** from `bandpass` — its three self-checks are covered by the unit test suite.
3. **`CHEBYSHEV_G_VALUES` lookup table deleted** (`shared/constants.py`); `bandpass.get_chebyshev_g_values` now computes g-values via `shared/chebyshev_g_calculator` for **arbitrary ripple in (0, 3.0]** (was limited to 0.1/0.5/1.0 dB). The `filter_lib.bandpass.CHEBYSHEV_G_VALUES` re-export is gone.
4. **Default resonator count is 3** (was 2) so the default works with Chebyshev (odd order required).
5. **Toroid table output defaults to top-1 core per inductor** (was top-3). New `--toroid-full` flag restores top-3 in table output; JSON always carries top-3 (CSV rows carry the best match).
6. **Missing required args now exit 2 with a usage line** (argparse error including a working example) instead of `Error: ...` with exit 1.
7. **Supplying `-r/--ripple` with butterworth/bessel warns on stderr** ("ripple is only used by Chebyshev; ignoring") and proceeds. Bandpass ripple is range-validated: `0 < r <= 3.0`.

**New**:
- `wizard` (alias `w`) registered as an explicit subcommand (no-arg invocation still launches it).
- `--version` on the root parser (reads package metadata).
- Exact dB→neper constant `40/ln(10)` in the Chebyshev calculator (was hardcoded 17.37); g-values now match published tables to <1e-4.
- Help text: frequency flags explain the k/M/G suffixes ("m is MHz, not milli"); bandpass `-b` documents true −3 dB bandwidth semantics; epilog examples all execute as written.

**Test Stats**: 1201 tests passing.

---

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
