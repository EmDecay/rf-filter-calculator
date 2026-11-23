# System Architecture

**Last updated:** November 20, 2026
**Applies to:** RF Filter Calculator 3.0.0 (unreleased)

## Overview

The calculator has four distinct concerns: ideal synthesis, physical-part realization,
circuit evaluation, and presentation. Keeping those concerns separate is important: a
calculated value, a selected catalog value, and a simulated lossy build are related, but
they are not interchangeable claims.

```text
CLI · Textual wizard · web UI      (each parses its own input into a DesignRequest)
        │
        ▼
design(request, should_cancel)     filter_lib.design; the request is validated on creation
        │
        ├─ synthesize ─────────────── LP/HP ladder or Top-C BP (cancellable)
        │
        ├─ resolve_parts ──────────── ResolvedParts on DesignResult.parts (cancellable):
        │                               capacitor choices; per inductor, each kind's
        │                               suggestions and the part the build uses;
        │                               band-pass tanks as fixed part + trimmer
        │
        ├─ advise_coupling ────────── band-pass only, when a coupler has no part ≥ 1 pF:
        │                               reruns synthesize + resolve_parts per trial
        │                               (cancellable between trials)
        │
        ├─ optional build simulation ─ named passive circuit from the parts, trimmers
        │                               tuned; loss + tolerance cases, each retuned
        │                               (cancellable)
        ▼
DesignResult ──► table / strict JSON / CSV / generic SPICE / response data
                 (every renderer reads its parts from DesignResult.parts)
```

The package entry point is `filter_lib.cli:main`; the repository-level
`filter-calc.py` file is only a source-checkout shim. With no arguments, the entry point
starts the Textual wizard; `filter-calc web` serves the browser UI.

## Shared design service

`filter_lib/design/` is the only orchestration path. Every surface builds a
`DesignRequest`, calls `design()`, and hands the `DesignResult` to `render_lines`,
`export_spice`, or `export_response_data`. No surface calls a calculator, a category
formatter, or the build analysis directly.

The request is the one carrier of everything that decides the parts: the standard capacitor
series (`eseries`, `None` for no standard values), the sub-pF switch, the capacitor grade, the
tolerance override, the assumed stray, the inductor suggestion detail
(`inductor_suggestions`) and build choice (`build_inductors`), the build settings
(`realization`) and whether to run the build simulation (`run_build_analysis`). `design()`
synthesizes, then resolves every chosen part once (`design/part_resolution.py::resolve_parts`)
into a `ResolvedParts` (`shared/resolved_parts.py`): the `MatchPolicy`, each capacitor's
choice, each inductor's suggestions by kind with the part the build uses, and, for a
band-pass design with standard values, each tank's fixed-part-plus-trimmer sizing. A band-pass
design whose coupling capacitors have no part of 1 pF or more then gets its tank-inductance
advice (`design/coupling_advice.py`), whose trials rerun `synthesize` and `resolve_parts`
(never `design()`, so there is no recursion). The `DesignResult` holds the request, the
calculator dict, those `parts`, the advice and the optional build analysis. Formatters, both SPICE decks and the build take `parts` and never select a part,
so the table, JSON, CSV, the build and the chosen-parts deck cannot disagree;
`part_resolution.py` is the only caller of a part selection function
(`tests/test_part_resolution.py`).

`design(request, should_cancel=…)` passes the check to synthesis (before it starts, and for
band-pass before each circuit evaluation of the calibration and response check), to part
resolution (before each part), and to the build (before each case). A true check raises
`DesignCancelled` (`shared/cancellation.py`; the build's `BuildAnalysisCancelled` is a
subclass), which is deliberately not a `ValueError`. A
chosen-parts SPICE deck uses `realization` without running the tolerance cases. The CLI builds
the whole request before calling `design()`; the wizard keeps the result it shows and reuses it
for a saved file only when that file's request is equal, designing any other file in its save
worker.

The service exists so that a third surface did not mean a third copy of the
orchestration. Before it, the CLI handlers and the wizard each sequenced synthesis, build
analysis, and formatting, and kept identical results only through parity tests. Each
surface still owns its input parsing and its defaults (the web shows the SVG plot by
default; the wizard and the CLI show no plot unless asked), and maps them to
`RenderOptions`. Cross-field rules that every surface must enforce (Chebyshev ripple and
order, the build-simulation output modes, `--allow-sub-pf` needing an E-series) live in
`DesignRequest` and `RenderOptions`, so all three report them with the same message.
Messages shared by surfaces outside those classes are module constants (see
[code standards](code-standards.md#user-facing-text)).

The CLI keeps a few things outside the service on purpose: argparse usage errors for
contradictory flags and `--explain`.

### Option applicability

The wizard and the web offer the same options with the same labels, defaults, and order, and
disable a control that cannot apply to the chosen output instead of ignoring it or refusing the
submission. Which options apply is one rule,
[`design/option_applicability.py`](../filter_lib/design/option_applicability.py):
`inapplicable_options(OutputChoices)` returns `{option: reason}` for the eleven options
(`eseries`, `allow_sub_pf`, `capacitor_grade`, `capacitor_tolerance`, `stray_capacitance`,
`inductor_detail`, `plot`, `raw`, `build`, `build_inductors`, `loss_q`); `OutputChoices`
carries the `inductor_detail`, because a forced inductor kind needs suggestions to build with.
It restates, in the interfaces' words, exactly the combinations the CLI refuses
(`shared/cli_output_validation.py`, `shared/cli_bandpass_output_validation.py`,
`RenderOptions`); a test checks every combination against the CLI validators. A disabled control
counts as unset, which is what leaving out the CLI flag means.

`document_options(choices, document, applied=…, visible=…)` decides which options another
document of the same design uses. Each document follows the rules of one output format
(`DOCUMENT_FORMATS`: design JSON and the chosen-parts SPICE deck follow JSON; CSV, the
calculated-values deck, and response data follow CSV), plus any rules of its own: the
calculated-values deck uses no standard capacitors, so it leaves out the E-series and the
capacitor grade, tolerance, stray and sub-pF options (`document_reasons`,
`document_own_options`). A disabled control's visible value is
added to each document it applies to, so Values only with E-series None downloads JSON as
`--format json --no-match`, never with a substituted E24. The web downloads
(`web/download_inputs.py`) and the wizard's saved files (`wizard/state_design_inputs.py`) both
call it. A new option or rule belongs here, never in one interface.

The build simulation's Q reference frequency label, help, and parser are shared the same way in
`design/q_reference_frequency.py`, and the inductor controls' labels and help in
`design/inductor_option_inputs.py`.

## Command layer

`filter_lib/cli/` contains the root parser, one handler per design category
(`lowpass_cmd.py` and `highpass_cmd.py` share `ladder_command.py`; `bandpass_cmd.py`),
`wizard_cmd.py`, and `web_cmd.py`.

The handlers share parser construction and compatibility validation from
`filter_lib/shared/cli_*.py`. Validation is mode-aware. For example, an explicit
E-series request is rejected when the selected output cannot represent it;
`--inductor-suggestions full`/`compact` are rejected outside table output; `--build-inductors`
needs a build or a chosen-parts deck, and a forced kind needs suggestions; and exact SPICE rejects build/Q flags
that cannot change that deck. This prevents accepted-but-ignored options. All three
subcommands accept `-f`, `--frequency`, and `--freq`, and check `-n` in `run()` with
`require_count` and the shared count message rather than with argparse choices.
`--spice-realization` accepts `calculated` and `chosen-parts`, stored as `exact` and
`nominal-build` at parse time (`shared/cli_aliases.py::SPICE_REALIZATION_ALIASES`).

The normal command flow is:

1. Parse aliases, frequencies, impedances, component counts, and optional build inputs.
2. Reject contradictory or unsupported combinations.
3. Build a `DesignRequest` and call `filter_lib.design`.
4. Route to the requested output or optional build analysis through the same package.
5. Convert expected validation failures to concise CLI errors without a traceback.

## Ideal synthesis

### Lowpass and highpass

`filter_lib/lowpass/` and `filter_lib/highpass/` are public facades around shared ladder
logic in `shared/lp_hp_base_calculations.py` and
`shared/lp_hp_base_transfer_functions.py`.

Public calculation functions preserve the historical return shape. Lowpass returns
capacitors first; highpass returns inductors first, because the LP→HP transform swaps the
component roles:

```python
capacitors, inductors, order = lowpass.calculate_butterworth(
    cutoff_hz=10e6,
    impedance=50.0,
    num_components=5,
    topology="pi",
)
```

The element lists contain Farads and Henries. `filter_lib.design` adds the filter metadata
and builds the result dictionary every surface renders.

Butterworth and Bessel use their normalized prototypes; Chebyshev g-values are computed
from formula for ripple in `(0, 3]` dB. Equal-termination Chebyshev ladders require odd
order. For LP/HP, the requested Chebyshev cutoff is the ripple-band edge rather than the
−3 dB frequency.

Component scaling is performed with overflow-aware logarithmic forms when a direct
`2*pi*f`, product, or quotient could overflow even though the final component value is
representable.

### Bandpass

`filter_lib/bandpass/calculations.py` and `transfer.py` remain compatibility facades.
The implementation is split by responsibility:

- `input_validation.py`, `numeric_validation.py` — public input contracts
- `g_values.py`, `resonator_math.py`, `coupling_math.py` — prototype, tank, Q, and
  coupling mathematics
- `top_c_synthesis.py` — raw Top-C series-coupled circuit
- `top_c_calibration.py` — adjusts internal tank frequency and synthesis FBW so the
  ideal circuit meets both requested −3 dB edges
- `response_sweep.py`, `passband_measurement.py`, `response_verification.py` — independent
  nodal sweep and per-design response checks
- `bandpass_design.py`, `design_result.py` — orchestration and result metadata
- `model_diagnostics.py` — informational harmonic samples and Cohn/circuit center-loss comparison

Only Top-C series coupling is supported. Each result distinguishes the requested
frequency specification from internal calibrated parameters and carries per-design
synthesis-validation metadata. Validation checks the connected −3 dB region, both outer
skirts, center/bandwidth, response shape, ripple where applicable, and representative
near-stopband points. Far-stopband diagnostics do not change these gates. The published support matrix contains 128 studied combinations; the
individual result, not a blanket family claim, determines whether a design passes the
response check (`Response Check:` in the table; `response_validation_status` in JSON).
Solver failures in `top_c_calibration.py` raise `TopCCalibrationError`; `bandpass_design.py`
re-raises one plain `ValueError` from `calibration_failure_message` with the solver reason on
`__cause__`.

`--qu` is the resonator Qu: unloaded Q of each resonator, inductor and capacitor losses
together. Separate `--ql` and `--qc` (resonator inductor Q and capacitor Q) combine as
`1/Qu = 1/(inductor Q) + 1/(capacitor Q)`. The Cohn insertion-loss
value is an estimate; the build simulation with part losses (Q) is a separate circuit
calculation.

## Physical realization

`shared/eseries.py` treats E12/E24/E96 as values per decade, never as component
tolerance. Capacitor selection (`shared/capacitor_choice.py`) is deterministic and exact:

- tolerances come from the sourced grade table (`shared/capacitor_grades.py`, Murata
  GRM1885C1H…A01, standard or tight grade; an override can only loosen it);
- each candidate's interval is nominal ± tolerance, plus the assumed stray for a pair; its
  score is the larger endpoint error; the best single and best pair come from an exhaustive
  search over the values the sourced table lists; a pair wins only by at least 0.5 percentage
  points; ties go to the single, then the smaller ratio, then the lower value;
- a choice whose parts the sourced table does not list keeps the nominal rule (single within 1%,
  else a pair) and is reported as `tolerance_not_sourced` with an assumed tolerance;
- below 1 pF, report `expert_override_required` and retain the calculated value rather
  than silently substituting a part, unless `DesignRequest.allow_sub_pf` is set
  (`--allow-sub-pf`, wizard/web **Allow capacitors below 1 pF**).

`component_realization.py` and `nominal_realization.py` turn that choice into named
physical branches, each with its own tolerance, plus a fixed `CSTRAY_<part>` capacitor across
each pair for the assumed stray. They read every part from `ResolvedParts`; where it holds no
part (no eligible preferred value, or no inductor suggestion for the chosen build kind), the
realization records an exact calculated fallback explicitly, with the reason.

### Inductor suggestions

Every inductor kind produces the same record, `shared/inductor_suggestion.py::InductorSuggestion`:
kind, rank, part name, target and achieved inductance, tolerance, the basis of its
self-resonance check (`guaranteed_minimum`, `model`, or `not_checked`), an error budget,
source, the kind's own build details, and warnings. `KindSuggestions` holds one kind's ranked
suggestions for one inductor or the limit that failed. Kinds are always listed in the fixed
order toroid, air coil, chip (`INDUCTOR_KINDS`); `auto` builds the first kind with a part,
and a forced kind builds its best suggestion or the calculated value with that kind's reason.
Each kind keeps its own selector and detail lines; ordering, the build, the table section
(`shared/inductor_display.py`), JSON, and CSV use only the record. HF toroids and chip
inductors are offered: air-core coils return their fixed reason, and above every toroid core's
rated range the toroid reason adds the VHF exclusion. Those texts are worded in
[component-data-sources.md](component-data-sources.md), which records why.

#### Chip inductor suggestions and the SRF screen

`shared/chip_selection.py` screens every part of the packaged catalog
(`chip_inductor_data.json` through `shared/chip_inductor_data.py`) with `shared/srf_screen.py`,
the one screen for a kind with a checked SRF. Part resolution passes it the design's check
window (`srf_screen.check_window`: low-pass DC to the cutoff, band-pass DC to the upper −3 dB
edge, high-pass the cutoff to twice the cutoff). A suggestion with a checked SRF carries its
part model (`L0` with `C_self`) and its allowance range; the build realizes it as `L0` with a
fixed `CSELF_<inductor>` capacitor, `ResolvedParts.qualified_range_hz()` intersects the built
parts' ranges, and the build labels a chosen-parts landmark outside that range and limits a
high-pass build's figures to it (`build_response.highpass_passband_top`).

#### Toroid winding suggestions

The vendored database contains legacy records for inspection, but automatic suggestions are
limited to T25-6, T50-2, and T68-2 because those entries have primary-source dimensional,
`A_L`, material-frequency, and winding-capacity data. Screening covers:

- published frequency guidance;
- integer-turn inductance and nominal error within published `A_L` tolerance;
- manufacturer winding-capacity limits where available;
- wire length and DC resistance as construction diagnostics.

It does **not** check RF Q, SRF, core loss, saturation, heating, or power handling, so its
SRF basis is `not_checked`. The wire-DCR reactance-ratio ceiling is published as
`wire_dcr_reactance_ratio_ceiling` and is not presented as predicted RF Q; the deprecated
`q_dc_upper_bound` name no longer appears in the JSON suggestion record.

## Circuit and build analysis

The shared circuit stack is intentionally independent of display formatting:

- `circuit_model.py` — named passive branches, ports, and circuit metadata
- `circuit_builders.py` — category-specific exact circuits
- `nominal_realization.py` — the chosen parts from `ResolvedParts` and explicit fallbacks
- `build_loss_models.py` — converts Q at a stated reference frequency to series loss
- `tolerance_screening.py` — fixed tolerance cases and optional seeded extra random cases
- `nodal_solver.py` and `branch_admittance.py` — passive AC solution
- `build_response.py` and `response_refinement.py` — evaluated build landmarks and convergence evidence
- `response_measurement.py` — existing array-based synthesis/calibration measurement helpers
- `build_output*.py` — table/JSON contracts
- `circuit_display_names.py` — bandpass circuit names → table names for readable text and the
  SPICE `* names:` comment
- `spice_export.py` — generic passive decks

The nodal solver evaluates transducer power gain with independently specified positive
finite source and load resistances. It normalizes admittances in log-polar form, so very
large/small but valid scales do not fail merely because a reciprocal conductance or
angular frequency cannot be materialized directly. Beyond the float range, a port
conductance larger than every branch is handled exactly in float: its row is divided and
its node eliminated last. Any other case goes to the adaptive Decimal solver. Precision
is never capped, because a capped solve would return wrong numbers rather than fail.
Instead, [physical_input_limits.py](../filter_lib/shared/physical_input_limits.py) bounds
component Q and port resistances to values a lumped filter can contain, which keeps every
accepted analysis within seconds.

The tolerance cases are a bounded engineering check. They include the fixed cases (all
parts low, all high, each part low and high alone) plus repeatable extra random cases when
requested. It is not a Monte
Carlo yield estimate, a proof of the mathematical worst case, or a replacement for
measurement.

Measurements are category-aware: LP/HP report one cutoff; BP reports lower/upper edges,
center, and bandwidth. A one-sided LP/HP response is not mislabeled as a bandpass-style
center/bandwidth result.

The refinement layer owns evaluated extrema, connected regions and bracketed crossings;
calibration retains its independently tested array-based helpers and acceptance thresholds.
This separation repairs reporting without retuning synthesis to satisfy its own measurement.
The CLI, wizard, and web UI all render tables through `filter_lib.design.render_lines`, which
builds the whole BP table, threshold table included, from `bandpass.display.format_table_lines`
and LP/HP tables from `shared/lp_hp_display.py`. A second renderer previously let the wizard
drift from the CLI.
See [measurement semantics and numerical policy](user-guide.md#interpreting-response-measurements).

## Output contracts

The output mode is selected before formatting:

| Mode | Contract |
|---|---|
| Table | Human-readable calculated values, standard-value choices, warnings, and optional plots/build simulation |
| JSON | Strict JSON; non-finite values are rejected rather than emitted as `NaN`/`Infinity` |
| CSV | RFC-style quoted rows produced by `csv.writer`; warnings containing commas remain rectangular |
| SPICE | Generic passive deck, `exact` (calculated values) or `nominal-build` (chosen parts); prints load-node voltage and documents the transducer-gain formula |
| `--plot-data` | Standalone analytic LP/HP or nodal BP response data with a shared schema |

Exact SPICE contains calculated components only (`* values: calculated, lossless (exact)`).
Nominal-build SPICE uses the chosen parts, optional Q-derived series loss, and explicit
calculated fallbacks (`* values: chosen parts (nominal-build)`, one `* part used:` line each). The
internal solver and SPICE exporter consume the same named circuit representation.

## Wizard architecture

`filter_lib/wizard/` uses independent Textual `Screen` subclasses and a centralized
`FilterState`:

```text
Welcome → category form → Output options → Results
```

The state stores design inputs, the visible value of every output and build control, and
the latest calculation outcome. Output options disables controls from the shared
applicability rule as choices change; the result uses only the options that apply, and saved
files use `document_options` like the web downloads. Results calculations run in a worker.
Each run receives a revision; stale, cancelled, or post-pop workers cannot overwrite a newer
state. A failure clears previous exportable results.

Component export selection is independent of the optional response-data sidecar, which
leaves out resonator Q. The Results screen cannot save while calculation is pending, and the
CSV choice is disabled, with its reason, when the result includes the build simulation
(that compound result has table and JSON contracts only) or resonator Q.

## Web architecture

`filter_lib/web/` is a FastAPI application served by uvicorn, with Jinja2 templates and
HTMX for partial page updates. `filter-calc web` imports it only inside the command, so
the core install never needs the `web` extra.

- **Request flow.** Form fields (named after the CLI flags) are parsed with the CLI's
  parsers and defaults into a `DesignRequest` and `RenderOptions`; the result panel shows
  `render_lines` text, downloads come from the same export functions, and the SVG plot is
  drawn from `response_series`, the sweep behind `--plot-data`.
- **Options and downloads.** `web/option_states.py` evaluates the shared applicability
  rule for all 64 combinations of the page's five deciding choices and embeds the table in
  the page, so `static/app.js` only looks answers up and disables controls with their
  reasons; the rule is never restated in JavaScript. A disabled control is not submitted;
  its visible value is sent as `visible.<name>`. The result keeps the submitted fields as a
  snapshot form, and every download posts that snapshot, so downloads describe the result
  shown; the page shows a stale notice when the form no longer matches it.
  `download_fields` applies each visible value to the downloads that can use it. The server
  still refuses a hand-made request that sets an option the rule disables.
- **Execution.** Calculations run on a bounded thread pool (two workers by default) so
  the event loop stays free. Each request waits up to 60 seconds; on expiry its
  cancellation flag is set and the request returns 503. `design()` polls that flag, so a
  band-pass calibration, part resolution, or build simulation stops at its next check
  and its result is dropped; a ladder synthesis is one closed-form step, checked before it
  starts. Shutdown flags running work and joins the pool threads.
- **Exposure.** The server binds to loopback by default, has no authentication, stores
  nothing, and writes no files. `request_guard.py` accepts submissions only from the
  page's own origin (`Sec-Fetch-Site`, else `Origin` against `Host`), which blocks
  cross-site request forgery. It also refuses any `Host` other than a loopback name or
  the specific bind address, which blocks DNS rebinding; a wildcard bind (`0.0.0.0`)
  cannot know its names and skips that check. Every response, including unexpected
  500s, carries the CSP, and HTMX runs with eval and swapped-script execution off. Scripts that send neither header are
  accepted; they are not a browser acting for someone else. Pages load only same-origin assets (HTMX is vendored) under
  a self-only Content Security Policy, and output is inserted as escaped text. It is not
  hardened for hosting.

Framework choice: FastAPI with server-rendered HTMX keeps one language and one validation
path, and the CLI's text output can be shown verbatim. A React single-page app was
rejected because it adds a Node toolchain and a second validation layer. Running the
calculator in the browser through Pyodide was rejected because bandpass calibration and
the tolerance cases already take seconds natively. Streamlit and NiceGUI were rejected as
heavy dependencies that would own the page layout.

## Numeric and validation contract

Public numeric inputs reject booleans, wrong types, non-finite values, and non-positive
values where the quantity must be positive. A finite input is accepted when the required
derived result is representable; logarithmic helpers avoid rejecting it solely because an
intermediate product overflows or underflows. If a required component or serialized value
cannot be represented as a positive finite float, the API raises `ValueError` with a
descriptive range error.

Formatting never turns a positive subnormal value into a displayed zero. When no useful
SI-prefixed form exists, it falls back to scientific notation in the base unit.

## Packaging and CI

The version is read dynamically from `filter_lib.__version__`. Setuptools includes the
toroid JSON database, the Textual stylesheet, and the web templates and static files in
both the wheel and source distribution. The web dependencies are the optional `web`
extra.

GitHub Actions runs on pushes and pull requests to `main`:

1. Ruff lint and format check on Python 3.14.
2. The full test suite with the `web` extra on the oldest supported Python (3.11).
3. The full test suite with the `web` extra and the 90% coverage gate on the newest
   supported Python (3.14).
4. Wheel and source-distribution build, archive inspection, an installed-wheel smoke test
   without the `web` extra (including the `filter-calc web` install hint), and artifact
   upload.

CI tests only the oldest and newest supported Python; see
[Supported Python Versions](code-standards.md#supported-python-versions).

This is continuous integration and artifact production; the workflow does not deploy a
release.

## Extension rules

- Add synthesis behavior behind the category calculation layer, not in display code.
- Add a new physical realization through the named circuit model so analysis and SPICE
  stay aligned, and a new part kind as an inductor-suggestion selector called only from
  `design/part_resolution.py`.
- Extend output schemas additively unless a versioned breaking change is intentional.
- Add new wizard inputs to `FilterState`, validation, CLI-equivalent build configuration,
  and lifecycle tests together.
- A new surface or input goes through `filter_lib.design`; put a rule every surface must
  enforce in `DesignRequest` or `RenderOptions`, not in one surface.
- Decide whether a wizard or web option applies only through
  `design/option_applicability.py`; extend that rule instead of adding a check in one UI.
- Accompany new accuracy claims with reference cases and independent response checks.
