# Code Standards and Architecture Guidelines

**Last updated:** November 20, 2026

This document records the conventions that matter for the current calculator. Follow the
repository-level `CLAUDE.md`, then these project-specific rules and nearby code patterns.

## Priorities

1. Correct electrical behavior and truthful limitations.
2. Simple, readable code with explicit contracts.
3. Compatibility unless a deliberate release changes a public contract.
4. Performance only where measurement shows it matters.

Do not make a numerical test pass by weakening an engineering invariant, hiding a failure,
or substituting a mock result for real circuit behavior.

## Python Style

- Python modules and functions use `snake_case`; classes use `PascalCase`; constants use
  `UPPER_SNAKE_CASE`.
- Write for the oldest supported Python (3.11; see
  [Supported Python Versions](#supported-python-versions)), including `T | None` and `A | B`
  rather than legacy `Optional[T]`/`Union[A, B]` spellings.
- Ruff is authoritative: target `py311`, line length 100, rules `E`, `F`, `I`, `UP`, and
  `B`, with the exceptions recorded in `pyproject.toml`.
- Keep imports in standard-library, third-party, then local groups.
- Comments explain invariants, units, limitations, or non-obvious choices—not the syntax.
- Public functions need useful type hints and docstrings. Document units at the boundary.

Run:

```bash
uv run ruff check .
uv run ruff format --check .
```

## Supported Python Versions

The project supports every CPython release that has not reached end of life and for which
all locked dependencies, including the `web` extra, ship wheels. As of November 2026 that is
**3.11, 3.12, 3.13, and 3.14**.

- **Oldest:** the oldest CPython release that has not reached end of life (see the
  [CPython release status](https://devguide.python.org/versions/)). New releases arrive each
  October, and the oldest one leaves support then too; 3.11 reaches end of life in October
  2027. Dropping a release does not strand users of the documented `uv sync` install: uv
  downloads a supported interpreter when the system Python is too old.
- **Newest:** the newest CPython release for which every locked dependency ships wheels and
  the suite passes. A new release joins once `uv lock --upgrade` brings in those wheels.
  pydantic-core, which FastAPI uses, is usually the last to arrive: Python 3.15 shipped in
  October 2026, but the locked pydantic-core has no 3.15 wheels yet. Do not add an
  allowed-to-fail CI job for a release that is not ready; it costs CI time and gets ignored.
- **Where the range is stated:** `requires-python` names the oldest release, the trove
  classifiers list every supported release, the Ruff `target-version` matches the oldest,
  and `.github/workflows/ci.yml` tests the oldest and the newest.
  `tests/test_packaging.py::test_supported_python_range_is_stated_consistently` fails if
  those disagree. When the range moves, also search `README.md`, `CLAUDE.md`, and `docs/`
  for the old version number.
- **CI tests only the oldest and the newest release.** The code is pure Python, with no
  compiled extensions and no version-specific branches, so breakage comes from one of the two
  ends: something the oldest release lacks (a standard-library API that Ruff cannot flag), or
  a behavior change in the newest (Python 3.13 changed how argparse prints a shared metavar).
  The earlier four-version matrix never caught a failure that the oldest and newest jobs
  would have missed. Revisit this rule if the project adds compiled extensions,
  version-conditional code, or dependencies that ship different builds per Python release.

## Calculation Contracts

LP/HP calculation functions return a tuple whose first two items follow the category: lowpass
returns capacitors first, highpass returns inductors first (the LP→HP transform swaps the
component roles):

```python
capacitors, inductors, order = lowpass.calculate_butterworth(
    cutoff_hz, impedance, num_components, topology
)
inductors, capacitors, order = highpass.calculate_butterworth(
    cutoff_hz, impedance, num_components, topology
)
```

`filter_lib.design` assembles the ladder result dictionaries for every surface (CLI, wizard,
and web UI). Bandpass synthesis returns a
dictionary because it carries calibrated component values, requested/internal parameters,
Q-model metadata, warnings, and per-design validation evidence.

Keep these meanings distinct:

- LP/HP Chebyshev cutoff is the ripple-band edge.
- Butterworth/Bessel LP/HP cutoff is the −3 dB point.
- Bandpass bandwidth is the true requested −3 dB skirt-to-skirt bandwidth.
- Equal source/load termination is a synthesis assumption. Separate build-analysis ports
  change evaluation, not synthesis.
- `q_min` is a compatibility heuristic. It is not a build guarantee.

## Numeric Validation

Public numeric boundaries reject booleans, wrong types, NaN/infinity, arbitrary-size integers
outside binary64, and invalid signs with a stable `ValueError`. Do not use bare
`math.isfinite(value)` as a type check: booleans pass it, strings leak `TypeError`, and very large
Python integers leak `OverflowError`.

Use a shared validator or finite-real predicate:

```python
from filter_lib.shared.numeric import is_finite_real

if not is_finite_real(value) or value <= 0:
    raise ValueError("value must be positive and finite")
```

For a simple positive or non-negative boundary, prefer `require_positive_finite` or
`require_nonnegative_finite` so the error contract stays consistent.

Integer inputs require an exact non-boolean `int`; do not silently truncate floats. Validate
arrays element-by-element before zipping or serializing them. A public invalid-input path must
not leak `TypeError`, `OverflowError`, `ZeroDivisionError`, or non-standard JSON.

For multiplicative formulas, avoid rejecting valid final values because an intermediate
overflows or underflows. Prefer log-domain scaling, cancellation-resistant identities, or
decimal parsing when unit suffixes compensate for an extreme textual exponent. Reject the
request cleanly when the final result is not positive finite binary64.

## Filter and Circuit Architecture

The maintained boundaries are:

- `filter_lib/lowpass/` and `filter_lib/highpass/`: public calculation/display/response
  adapters over shared prototype logic.
- `filter_lib/bandpass/`: Top-C synthesis, calibration, independent shape verification,
  ideal response, and display adapters.
- `filter_lib/shared/`: parsing, prototypes, E-series policy, named circuits, nodal solving,
  realization, loss/tolerance analysis, export, plotting, the inductor suggestion record, and
  toroid screening.
- `filter_lib/design/`: the one request → synthesis → part resolution → render/export path
  that every surface calls; cross-surface input rules live in `DesignRequest` and
  `RenderOptions`.
- `filter_lib/cli/`: argument definitions and thin command orchestration.
- `filter_lib/wizard/`: Textual screens, shared state, calculation workers, and export.
- `filter_lib/web/`: the optional FastAPI web UI: form parsing, bounded execution, request
  guard, SVG plot, and templates. Imported only by `filter-calc web`.

Keep calibrated synthesis separate from validation. The bandpass calibration sweep may place
the skirts; `response_verification.py` independently checks skirts, connected regions, shape,
and near-stopband samples. Do not replace `response_validation_status` with a
blanket support claim.

Preserve the separation between synthesis acceptance and reporting accuracy. Harmonic samples
and approximation comparisons are informational. Measurement changes need independent circuit
references, convergence evidence, and explicit unresolved/region semantics; see
[accuracy regressions](../tests/test_response_accuracy.py).

Named circuits are the common physical contract for the build simulation and SPICE. A chosen
parallel capacitor remains two branches. A part that is unavailable or refused by the selection
rule is an explicit exact fallback with warnings (shown as "calculated value used"), never a
fabricated physical part. Bandpass SPICE element names (`CT1`, `LT1`, `CK1`, `CIN`, `COUT`) stay
as they are; human-readable text maps them to the table names with
`shared/circuit_display_names.py::display_component_name`, and decks carry a `* names:` comment.

## E-Series Policy

E12/E24/E96 names describe how many standard values there are per decade, not tolerance.
Automatic standard-value selection applies to capacitors only, by the worst-case interval rule
in `shared/capacitor_choice.py`:

- tolerances come from one sourced grade table, `shared/capacitor_grade_data.json` (Murata
  GRM1885C1H…A01, loaded by `shared/capacitor_grades.py` through `shared/packaged_data.py`);
  a change to it updates `docs/component-data-sources.md` in the same change;
- a candidate's interval is nominal − tolerance to nominal + tolerance, plus the assumed stray
  for a pair; its score is the larger endpoint error; the best single and best pair come from
  an exhaustive search over the E-series values the sourced table lists, in exact `Fraction`
  arithmetic; a pair wins only by at least 0.5 percentage points (inclusive), and never on an
  equal score; ties go to the single, then the smaller ratio, then the lower value; pairs stay
  within 10:1;
- an override can only loosen a guarantee: tolerance = max(override % × value, sourced
  tolerance); a part whose tolerance is not smaller than its value is ineligible;
- a choice the nominal rule makes from parts the sourced table does not list keeps that rule (single
  within `LEGACY_SINGLE_WITHIN_PCT`, else a pair 0.5 points closer), with status
  `tolerance_not_sourced` and an assumed 5% (or the override); never present it as sourced;
- below 1 pF, choose nothing unless `DesignRequest.allow_sub_pf` is set (CLI `--allow-sub-pf`,
  wizard/web **Allow capacitors below 1 pF**); the warning names that option.

Surfaces set the series, the sub-pF switch, the grade, the tolerance override, the stray and
the two inductor options on `DesignRequest` only; `design()` resolves one `MatchPolicy` from
them (`design/part_resolution.py::resolve_match_policy`) and every chosen part once
(`resolve_parts`), and stores them as `ResolvedParts` on `DesignResult.parts`. Nothing else
builds a `MatchPolicy`, a `ResolvedParts` or a `DesignResult`
(`tests/test_part_policy_carrier.py`), and only `design/part_resolution.py` calls a part
selection function (`match_component`, and each inductor kind's selector such as
`suggest_toroids`); `tests/test_part_resolution.py` enforces it. Formatters, both SPICE decks
and the build take `parts` and read from it, so table, JSON, CSV, wizard, web UI, nominal
realization, and SPICE agree on the selected result. A test with a hand-made result resolves
parts with `tests/parts_helpers.py::parts_for`. Inductors remain calculated values with
inductor suggestions; harmonic E-series matching keeps the nominal rule.

## Inductor Suggestions

- **One record for every kind.** Each kind's selector returns `KindSuggestions` of
  `InductorSuggestion` records (`shared/inductor_suggestion.py`): kind, rank, part name, target
  and achieved inductance, tolerance, SRF basis, error budget, source, the kind's own `build`
  details, status, and warnings. Ordering, the build pick, the table section, JSON, and CSV
  read only the record; a kind adds only its selector and its own title and detail lines
  (`toroid_display.py` for toroids, `chip_display.py` for chip inductors).
- **Fixed kind order.** Kinds are always listed in `INDUCTOR_KINDS` order (toroid, air coil,
  chip), each kind's suggestions in its own rank, at most `MAX_SUGGESTIONS_PER_KIND` (3).
  `auto` builds the first suggestion in that order; "best" shows the build pick, else the first.
- **Sourced-only guarantees.** A part qualifies only on a primary-source minimum or maximum,
  never a typical value ([component-data-sources.md](component-data-sources.md#how-to-read-this-page)).
  Its SRF basis is `guaranteed_minimum`, `model` (with `srf_accuracy`), or `not_checked`; only
  the legacy HF toroids use `not_checked`, and their error budget then lists no SRF drift. A
  checked basis gives the drift, the part model the build simulates (`part_model`) and the
  `allowance_range_hz`, all three or none.
- **One SRF screen.** Every kind with a checked SRF uses `shared/srf_screen.py`: the part model
  (`L0 = L_m (1 − (f_m/SRF)²)` with `C_self` from the minimum SRF), the check window
  (`check_window`: low-pass DC to the cutoff, band-pass DC to the upper −3 dB edge, high-pass
  the cutoff to `HIGHPASS_CHECK_MULTIPLE` × the cutoff), the drift limit
  (`DRIFT_ALLOWANCE_PCT`) and the henry-based budget (`DESIGN_ALLOWANCE_PCT`) at both tolerance
  ends, both window ends and both SRF limits. Limits are compared in exact arithmetic on the
  stated decimals (a part exactly at a limit is within it), always with the maker's guaranteed
  tolerance; an extreme design makes its parts fail, never aborts. The budget's terms are in
  percent of the target, each drift term taken at the tolerance end it adds to, so
  `ErrorBudget.worst_case_pct` is their exact total. Chip inductors (`chip_selection.py`,
  `chip_inductor_data.py`) rank by the smallest worst case, then part number; the minimum Q is
  shown, never ranked. The packaged catalog matches the evidence page's table
  (`tests/test_chip_inductor_data.py`), and the acceptance designs match its coverage table
  (`tests/test_vhf_acceptance_coverage.py`).
- **Say why a kind has no part.** `KindSuggestions.reason_none` states the limit that failed
  and names the kind, so reasons read without labels. A kind that is never offered states why
  in the words of `docs/component-data-sources.md` (`VHF_TOROID_EXCLUSION`,
  `AIR_COIL_EXCLUSION`); change the text and that page together. A chip inductor's reason
  (`chip_selection.no_qualifying_chip_reason`) names the allowance, the drift limit or both, and
  the frequencies checked.

Toroid screening uses only exact parts marked primary-source verified in
`toroid_core_data.json`. Legacy records remain inspectable but are not auto-selected. Preserve
source IDs and field provenance whenever data changes. It may evaluate material-frequency
guidance, whole turns, nominal error, published winding capacity, wire length, and DC
resistance. Output calls the result a "suggestion" and must not present it as a prediction of
RF Q, SRF, core loss, saturation, heating, or power handling
(`toroid_selection.NOT_ASSESSED_WARNING`).

## Build Simulation and SPICE

`BuildConfig`, nominal realization, and tolerance screening are public contracts (shown to users
as the build simulation, the chosen parts, and the tolerance cases). `DesignRequest.realization`
holds the build settings a chosen-parts deck or a build needs; `run_build_analysis` alone runs
the tolerance cases, so making a SPICE deck never runs them:

- chosen parts come from `ResolvedParts` (`parts=`); exact fallbacks remain auditable and say
  why (an inductor with no suggestion of the chosen kind gives that kind's reason);
- each part varies by its own tolerance (`CircuitElement.tolerance`): a capacitor by its
  grade's (or the larger override; the assumed tolerance where not sourced), an inductor by
  `BuildConfig.inductor_tolerance_pct` (unset: a part with a checked SRF by its own guaranteed
  tolerance, `component_realization.inductor_tolerance`; 10% for toroid windings and
  calculated values);
- the assumed stray across a pair is a `fixed` capacitor across the pair's terminals named
  `CSTRAY_<part>` (`circuit_display_names.STRAY_PREFIX`, shown as "<part> stray"); fixed
  elements are never varied, so they change neither the case list nor the seeded draws, and a
  stray of 0 adds no element. Every element name starts with the letter of its kind
  (`CircuitElement` refuses any other), so a SPICE reader sees what the solver sees;
- a suggestion with a part model (a chip inductor) is built as its `L0` with a `fixed`
  capacitor `CSELF_<inductor>` across it (`circuit_display_names.SELF_CAPACITANCE_PREFIX`,
  shown as "<inductor> self-capacitance"), the same in the build and the chosen-parts deck and
  never varied; the tolerance cases are then stress cases of that fixed branch
  (`build_analysis.STRESS_CASE_LIMITATION`), never qualified values;
- `ResolvedParts.qualified_range_hz()` is where every built part with a checked SRF stays within
  its allowances (each end rounded inward so it passes the exact screen; printed ranges round
  inward too); `CircuitMeasurement.outside_range` checks every frequency a chosen-parts result
  reports (edges or cutoff and the center and bandwidth from them, the reference peak, the peak
  gain's frequency, other half-power regions), which are labelled
  `build_output_formatting.PARASITIC_PREDICTION` (JSON `outside_qualified_range`); ideal results
  never are. A high-pass build measures only up to `build_response.highpass_passband_top` and
  takes its peak and threshold only inside `highpass_peak_range`. With no such part (toroid
  windings, calculated values) nothing is limited or labelled. An entered inductor Q applies to
  a chip's inductance branch alone (`nominal_realization.CHIP_Q_LIMITATION`);
- a band-pass tank with a fitting split (`ResolvedParts.tanks`, sized once in
  `part_resolution` by `shared/tank_trimmers.size_tanks`) is built as its fixed part(s), one
  `fixed` `CSTRAY_CT<i>` of the assumed stray times the number of fixed parts, and the trimmer
  `CTRIM_CT<i>` (`circuit_display_names.TRIMMER_PREFIX`, "Cp<i> trimmer"): a `fixed` capacitor
  carrying the series inductance its fit assumes (`CircuitElement.series_inductance_h`, simulated
  in its own branch and written to SPICE as `LTRIM_CT<i>` in series through `NSERIES…`). Its
  knob setting is solved by `shared/tank_tuning.tune` so the node susceptance
  (`shared/tank_susceptance.node_susceptance`: other tank nodes shorted, ports at their
  resistance, every branch with its Q) equals the calculated design's at the calibrated tank
  frequency; each tolerance case keeps its untuned measurement and adds `ScreeningCase.tuning`
  (settings with `in_range`, tuned measurement). Sizing uses the design alone: its equal
  terminations, the losses of its resonator Q (`build_loss_models.loss_model` with default build
  settings), each inductor's first suggestion (`InductorParts.default_pick`, whatever the build's
  inductor choice) and the parts' own or
  assumed tolerances, so every output of a design lists the same split; the build re-derives
  each trimmer's range under its own Q (`tank_tuning.plan_trimmer`) and flags what it cannot
  reach. A fit always rests on the
  stated series inductance and is never called guaranteed; a need with an assumed input
  tolerance is conditional and names it (`tank_trimmers.*_assumption`);
- Q is converted to constant series resistance at a stated reference frequency;
- a custom loss reference without an effective Q is rejected;
- fixed tolerance cases and seeded extra random cases are not measurements, probabilities,
  yields, or guaranteed worst cases;
- all reported gain is transducer power gain with explicit source/load ports.

Generic SPICE export has two realizations: `exact` and `nominal_build` (the CLI default). The
printed `vm(load)` trace is load voltage, not gain in dB; deck comments state the transducer
gain expression.

## User-Facing Text

Help, errors, output, wizard, and web text use one plain term per concept: build simulation,
ideal values, chosen parts, parts used, calculated value used, tolerance cases, extra random
tolerance cases, inductor suggestions (toroid windings, air-core coils, chip inductors),
error budget, response check, part losses (Q), resonator Qu,
resonator inductor Q and resonator capacitor Q, order (LP/HP `-n`), response type, insertion
loss, top-coupled, simulation source/load resistance, frequency points, values only, and
standard capacitor values. Do not reintroduce "realized", "nominal build", "screened candidate",
"expert override", "tolerance corners", or "validated envelope" in human-readable text, and do
not label the resonator inductor or capacitor Q as "QL"/"QC" (filter texts use QL for loaded Q).
JSON keys, JSON enum values, CSV columns, flag names, and choice values (`nominal-build`,
`exact`) are machine contracts and keep their names. A plainer CLI spelling is an additive alias
resolved at parse time (`--spice-realization calculated`/`chosen-parts` via
`shared/cli_aliases.py::SPICE_REALIZATION_ALIASES`), so validation and output only ever see the
canonical value.

A rule enforced on more than one surface has one message constant or helper; import it instead
of restating the text. Examples: `design/render_options.py` (`BUILD_NEEDS_ESERIES_MESSAGE`,
`BUILD_NEEDS_TABLE_OR_JSON_MESSAGE`, `BUILD_NOT_WITH_VALUES_ONLY_MESSAGE`,
`SUB_PF_NEEDS_ESERIES_MESSAGE`, `shows_design_warnings`), `shared/eseries.py`
(`SUB_PF_OPTION_LABEL`, `SUB_PF_CLI_FLAG`, `sub_pf_warning`, `CAPACITOR_GRADE_LABEL`,
`CAPACITOR_TOLERANCE_LABEL`, `STRAY_CAPACITANCE_LABEL`, `CAPACITOR_TOLERANCE_RANGE_MESSAGE`,
the `*_HELP` texts), `design/capacitor_policy_inputs.py` (the wizard and web labels, help and
field parsers for the grade, tolerance and stray), `shared/display_helpers.py`
(`not_sourced_note`), `shared/nominal_realization.py` (`stray_limitation`),
`shared/physical_input_limits.py` (`STRAY_CAPACITANCE_RANGE_MESSAGE`),
`shared/capacitor_grades.py` (`require_grade`), `shared/cli_aliases.py`
(`RIPPLE_RANGE_MESSAGE`, `COMPONENT_COUNT_MESSAGE`, `chebyshev_odd_count_message`),
`bandpass/input_validation.py` (`RESONATOR_COUNT_MESSAGE`, `BANDWIDTH_NOT_BELOW_CENTER`,
`fbw_untested_warning`, `fbw_impractical_warning`), `bandpass/resonator_math.py`
(`TANK_SETTING_CONFLICT_MESSAGE`), `shared/build_types.py`
(`RESONATOR_AND_COMPONENT_Q_MESSAGE`), `shared/cli_bandpass_output_validation.py`
(`RESONATOR_Q_LABELS`, `RESONATOR_Q_CONFLICT_MESSAGE`, `RESONATOR_Q_FORMULA`),
`shared/inductor_suggestion.py` (`FORCED_KIND_NEEDS_SUGGESTIONS_MESSAGE`, which
`design/option_applicability.py` names `BUILD_INDUCTORS_NEEDS_SUGGESTIONS_MESSAGE`;
`VHF_TOROID_EXCLUSION`, `AIR_COIL_EXCLUSION`; the CLI help
`INDUCTOR_SUGGESTIONS_HELP` and `BUILD_INDUCTORS_HELP`), `shared/toroid_selection.py`
(`no_suitable_core_reason`, which names the limit that rejected the rated cores; `no_rated_core_reason`; `NOT_ASSESSED_WARNING`),
`shared/chip_selection.py` (`no_qualifying_chip_reason`, `CHIP_NOT_ASSESSED_WARNING`),
`shared/chip_display.py` (`CHIP_HEADING`, `CHIP_MODEL_LINE`, `checked_line`),
`shared/nominal_realization.py` (`SELF_CAPACITANCE_LIMITATION`, `CHIP_Q_LIMITATION`,
`TRIMMER_LIMITATION`), `shared/tank_trimmers.py` (`not_sourced_assumption`,
`no_part_assumption`, `toroid_assumption`, `calculated_inductor_assumption`),
`bandpass/trimmer_display.py` (`TANK_TRIMMERS_HEADING`, `COUPLING_ADVICE_HEADING`,
`tank_trimmer_intro`, `series_inductance_text`, `assumptions_text`),
`design/coupling_advice.py` (`advice_lines_text`, `no_candidate_reason`,
`no_value_works_reason`, `FIELD_LABEL`, `CLI_FLAG`), `shared/build_analysis.py`
(`STRESS_CASE_LIMITATION`), `shared/build_output_formatting.py` (`PARASITIC_PREDICTION`,
`qualified_range_line`, `highpass_passband_note`, `inductor_tolerance_text`),
`shared/inductor_display.py` (`format_worst_case`),
`design/part_resolution.py` (`NO_SUGGESTION_NOTE`, `SUGGESTIONS_NOT_USED_NOTE`),
`design/inductor_option_inputs.py` (the wizard and web `INDUCTOR_DETAIL_LABEL`,
`INDUCTOR_DETAIL_CHOICES`, `INDUCTOR_DETAIL_HELP`, `BUILD_INDUCTORS_LABEL`,
`BUILD_INDUCTORS_CHOICES`, and their own `BUILD_INDUCTORS_HELP`), `shared/inductor_display.py`
(`inductor_note_line`, `SECTION_NAME`), `shared/numeric.py`
(`require_count`, used with the count messages by all three subcommands, the web, and the
LP/HP and bandpass calculators),
`design/option_applicability.py` (the disabled-control reasons, such as
`TEXT_PLOT_NEEDS_TABLE_MESSAGE`, `INDUCTOR_DETAIL_NEEDS_TABLE_MESSAGE`,
`LOSS_Q_NOT_SHOWN_MESSAGE`, `EXACT_SPICE_MATCHING_MESSAGE`,
`EXACT_SPICE_BUILD_INDUCTORS_MESSAGE` and `RESPONSE_DATA_BUILD_INDUCTORS_MESSAGE`; the
capacitor grade, tolerance and stray reuse the sub-pF wording for their own labels), `design/export.py` (`NOMINAL_SPICE_NEEDS_ESERIES_MESSAGE`),
`wizard/screens/results.py` (`PREPARING_FILES_MESSAGE`, `not_saved_prefix`),
`design/q_reference_frequency.py` (`Q_FREQUENCY_LABEL`, `Q_FREQUENCY_HELP`), and
`wizard/state_design_inputs.py` (`CSV_WITH_BUILD_MESSAGE`). Error text names fields in words,
never as snake_case.

Whether a wizard or web control applies to the chosen output is decided only by
`design/option_applicability.py`, which restates the CLI's accept/refuse rules and is tested
against them. Extend that rule for a new option or combination; do not add a check, a disabled
state, or a reason text in one interface. A document with rules of its own adds them in
`_DOCUMENT_REASONS` (the calculated-values SPICE deck and the response data leave out every
option in `MATCHING_OPTIONS`); `document_reasons` and `document_own_options` expose them.
Caveats print once where they apply; JSON and CSV keep every warning entry.

## Machine-Readable Output

- JSON must pass strict serialization with no `NaN`/`Infinity` extension values.
- CSV must be rectangular and use the `csv` module for fields that can contain delimiters.
- Response exports require positive finite frequency values and finite real dB values.
- Requested synthesis targets, calculated response, chosen parts, tolerance cases,
  effective loss, and limitations stay in separate fields.
- When explicit bandpass edges are supplied, `requested_parameters` and build `target` retain
  those parsed values and record `frequency_specification = edge_frequencies`.
- Each JSON inductor component (band-pass resonator inductors too) carries
  `inductor_suggestions`, absent with `--inductor-suggestions none`: `best` (`kind` and `rank`,
  or `null`) and `kinds`, one entry per kind in the fixed order with `kind`, `suggestions` and
  `reason_none`. Each suggestion has `kind`, `rank`, `part_name`, `status`, `target_henries`,
  `achieved_henries`, `tolerance_pct`, `srf_basis`, `srf_accuracy`, `error_budget`
  (`nominal_mismatch_pct`, `tolerance_pct`, `srf_drift_pct`, `worst_case_pct`),
  `allowance_range_hz`, `source` (`publisher`, `title`, `url`), `build` (the kind's own record:
  for a toroid the screened record without `rank`, `candidate_status`, or `q_dc_upper_bound`;
  for a chip `chip_display.chip_build_payload`), and `warnings`
  (`shared/inductor_display.py::suggestion_payload`).
- CSV gives each inductor's best suggestion: the generic columns `InductorKind`, `InductorPart`, `InductorSRFBasis`, `InductorBudgetNominalPct`, `InductorBudgetTolerancePct`, `InductorBudgetSRFDriftLowPct` and `InductorBudgetSRFDriftHighPct` (the budget in percent of the
  target, the drift blank when the SRF is not checked) precede the `Toroid*` columns and then
  the `Chip*` columns, ending with `ChipModelBasis` and `ChipWarnings`
  (`CSV_INDUCTOR_HEADER`); the other kind's columns are blank, all are blank on capacitor rows
  and on inductors with no suggestion, and with `none` the inductor columns are left out.
- Build JSON `build_model` gives `build_inductor_choice` (the `--build-inductors` value),
  `suggested_inductors_used`, and `suggested_inductor_elements`. Each substitution carries
  `inductor_kind` and `part_name` (`null` for capacitors and calculated values); an inductor
  built from a suggestion has `method: "suggested_inductor"`, and one simulated at its
  calculated value has `method: "exact_fallback"` with status `suggestions_not_used`
  (suggestions off, or `calculated`) or `no_verified_candidate` (no part of the chosen kind).
  Substitutions also carry `self_capacitance_f`, `tolerance_pct` and `own_tolerance`;
  `nominal_build` carries `qualified_range_hz`, `passband_top_hz` and `peak_range_hz`; every
  measurement carries `model` and `peak_frequency_hz`, a chosen-parts one
  `outside_qualified_range`, and each spread summary `outside_qualified_range`;
  `tolerance_analysis` gives the entered `inductor_tolerance_pct` (nullable) and
  `inductor_fallback_tolerance_pct`.

## Wizard Architecture

The wizard uses independent Textual `Screen` classes and `push_screen`/`pop_screen`:

```text
Welcome → LP/HP/BP form → Output options → Results
```

`FilterWizardApp.filter_state` owns the one `FilterState` instance. Screens access
`self.app.filter_state`; `FilterState` is data, not a DOM widget, so do not query it with
`query_one`.

Current responsibilities:

- `bandpass_form.py`: BP form parsing and focus/error mapping.
- `build_options.py`: build-field labels, help, parsing, and `BuildConfig` mapping.
- `state_design_inputs.py`: which controls apply (from the shared rule), and the
  `DesignRequest`/`RenderOptions` for the result and for each saved file
  (`document_options`).
- `filter_type_calculators.py`: builds the `DesignRequest` from state and renders through
  `filter_lib.design`.
- `calculation_handler.py`: detached calculation, optional build analysis through
  `filter_lib.design`, and outcome construction.
- `export_formatting.py`: component and response export payloads, rendered by
  `filter_lib.design`.
- `screens/results.py`: background worker lifecycle, revision guard, and save UI.

Every design mutation invalidates prior output. A Results worker calculates from a deep-copied
snapshot and may publish only to the same pending revision. Unmount cancels the worker and
invalidates its result; long work must poll a cancellation check, because a thread worker
cannot be interrupted from outside (see `design(..., should_cancel=...)`, which forwards the
check to synthesis, part resolution, and the build analysis; each stops with
`DesignCancelled`). Export is enabled only after a complete successful outcome; the
build simulation must be present when requested.

Output options never refuses a combination on submit: controls that cannot apply are disabled
with the shared rule's reason, and the result treats them as unset (the CLI without that flag).
`FilterState` keeps their visible values for the saved files that can use them. A plot is
rendered inside Results; it is not an extra screen.

## File Boundaries

Split a file when doing so creates a real responsibility boundary or makes an invariant easier
to test. Avoid line-count-only refactors. Prefer focused modules for synthesis, verification,
realization, serialization, and UI parsing rather than large cross-layer routers.

## Testing

Run the narrowest relevant test first, then the broad release gates when shared contracts
change. Install the `web` extra first (`uv sync --group dev --extra web`), or the web tests
skip and the coverage gate counts `filter_lib/web/` as uncovered:

```bash
uv run pytest -q tests/test_relevant_module.py
uv run pytest -m runtime_budget
uv run pytest -m "not runtime_budget" --cov=filter_lib --cov-report=term-missing --cov-fail-under=90
uv run ruff check .
uv run ruff format --check .
uv lock --check
uv build
```

Important regression layers include:

- hand/reference calculation fixtures and topology duality;
- the 128-cell independent bandpass acceptance matrix;
- analytic and Decimal-fallback nodal-solver cases;
- strict JSON, rectangular CSV, build, and generic SPICE contracts;
- toroid provenance and winding math;
- part resolution: one record per kind, the kind order, the build pick and its reasons,
  cancellation, and that only `design/part_resolution.py` selects parts
  (`tests/test_part_resolution.py`); every 3.0.0 rename keeps its old behaviour and the old
  name is gone (`tests/test_option_migration.py`); every surface gives the same parts
  (`tests/test_part_parity.py`);
- the HF baseline corpus (`tests/test_hf_baseline.py`, generated by `tests/hf_baseline_tool.py`):
  45 HF designs whose values, capacitor choices, statuses, toroid picks, SPICE decks and build
  results may change only as listed, with a permitted kind and a reason, in
  `tests/fixtures/hf_baseline_allowed_changes.json`; never regenerate the corpus to absorb a
  change (`uv run python -m tests.hf_baseline_tool --report` lists the differences);
- capacitor choices against an independent brute force (`tests/capacitor_interval_oracle.py`);
- Textual unit tests and real `run_test()` pilot flows;
- source archive, wheel contents, and installed-wheel smoke tests;
- the oldest and the newest supported Python (see
  [Supported Python Versions](#supported-python-versions)).

Do not hide a failing gate or reduce coverage to land a change.

## Documentation

Update documentation only when behavior, setup, architecture, public contracts, or maintainer
decisions change. Verify commands execute as written, schema examples use real field names, and
claims match the final test/build evidence. Historical changelog entries remain historical;
new reality belongs in the newest release entry and current reference documents.
