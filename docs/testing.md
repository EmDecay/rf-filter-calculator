# Testing Guide

**Last updated:** October 7, 2026
**Applies to:** RF Filter Calculator 2.2.0

## Quality gates

The repository has more than 4,500 collected pytest cases. CI requires at least 90% line
coverage and runs the complete suite on Python 3.10, 3.11, 3.12, and 3.13. A skipped test
is reported as a skip; failures, lint errors, format errors, and coverage shortfalls are
not hidden.

Run the same primary gates locally. The coverage gate assumes the `web` extra is
installed; without it the web tests skip themselves and `filter_lib/web/` counts as
uncovered.

```bash
uv sync --locked --group dev --extra web
uv run --locked ruff check .
uv run --locked ruff format --check .
uv run --locked pytest tests/ -m runtime_budget
uv run --locked pytest tests/ -m "not runtime_budget" \
  --cov=filter_lib \
  --cov-report=term-missing \
  --cov-fail-under=90
```

Tests marked `runtime_budget` assert wall-clock limits on the application itself. Coverage
tracing slows them down, so they run in their own pass without `--cov`; every other test runs
under the coverage gate. `--strict-markers` is on, so a misspelled marker fails collection.

For a quick count without executing tests:

```bash
uv run --locked pytest --collect-only -q
```

## Narrow-first workflow

Run the smallest relevant file or test first, then broaden when a shared contract changed:

```bash
# One file
uv run pytest tests/test_bandpass_calculations.py

# One class or test
uv run pytest tests/test_eseries_matching.py::TestRecommendationPolicy

# Related feature cluster
uv run pytest \
  tests/test_response_accuracy.py \
  tests/test_build_simulation.py \
  tests/test_build_output.py \
  tests/test_spice_export.py

# Full suite and coverage before handoff
uv run pytest tests/ -m runtime_budget
uv run pytest tests/ -m "not runtime_budget" --cov=filter_lib --cov-report=term-missing --cov-fail-under=90
```

Do not weaken assertions or exclude code merely to restore a green gate. A numeric bug
should normally get a regression that reproduces the original values.

## What the suite covers

### Synthesis and public APIs

- Butterworth, Chebyshev, and Bessel LP/HP ladder values against published Matthaei and
  Zverev prototype tables, plus exact impedance/frequency scaling and LP/HP duality
- Each normalized prototype, evaluated as an independent ABCD ladder, against the closed-form
  Butterworth, Chebyshev equal-ripple, and Bessel-polynomial responses
  ([test_prototype_ladder_responses.py](../tests/test_prototype_ladder_responses.py))
- Pi/T topology placement and public tuple return contracts
- Chebyshev formula-based g-values over `(0, 3]` dB, including minimum-subnormal ripple
- Top-C series-coupled bandpass synthesis, end coupling, tank compensation, and custom
  tank impedance/inductance
- Public type/range validation, including bool rejection and finite-result behavior at
  floating-point extremes

### Independent bandpass verification

The bandpass tests do not rely only on synthesis internals. They build the produced
passive circuit, run a dense nodal sweep, locate the center-connected −3 dB region and
outer skirts, and compare measured center, bandwidth, shape, ripple, and stopband points.

An exhaustive 128-cell study spans:

- Butterworth and Bessel orders 2–9;
- Chebyshev odd orders 3, 5, 7, and 9;
- multiple fractional bandwidths and Chebyshev ripple values.

The matrix locks the documented validated/outside/unsupported classifications and checks
that each individual result reports its own status.

The matrix verifier shares the production netlist builder and solver, and the calibration
loop can absorb a first-order synthesis error. For both reasons, it is not the only check
on part values.
[test_bandpass_independent_circuit_accuracy.py](../tests/test_bandpass_independent_circuit_accuracy.py)
evaluates the exported components with its own ABCD cascade. It requires both −3 dB edges
within 1e-4 and the 0.01% FBW response to match closed-form Butterworth, Chebyshev, and
Bessel prototypes. It also checks exact frequency and impedance scaling and every
measured field of `synthesis_validation`.

### Physical realization

- E12/E24/E96 preferred-value search and deterministic selection policy, including the
  exact 10:1 pair limit, the balanced tie-break, and correctly rounded part and pair values
- one-part preference, material two-part improvement threshold, and sub-1 pF expert action
- toroid primary-source eligibility, frequency guidance, integer-turn error, winding
  capacity, deterministic ranking, and empty-candidate behavior
- truthful fallbacks when a nominal part or screened winding is unavailable

### Circuit and build analysis

- exact and nominal named circuit construction
- unequal source/load transducer power gain
- scale-normalized nodal solution across normal, extreme, and subnormal impedances; the
  high-precision fallback's branch magnitudes against a 50-digit reference
  ([test_circuit_decimal_fallback_precision.py](../tests/test_circuit_decimal_fallback_precision.py))
- accepted component-Q and port-resistance ranges: inclusive bounds, rejection beyond them,
  and analysis runtime at each bound
  ([test_physical_input_limits.py](../tests/test_physical_input_limits.py))
- category-aware LP/HP cutoff and BP center/bandwidth measurements
- Q-derived series loss at an explicit reference frequency
- deterministic tolerance corners and repeatable seeded bounded samples
- build-output truthfulness: actual physical elements, fallback disclosure, loss model,
  generated case counts, and limits

### Output contracts

- table wording for calculated, estimated, and simulated quantities
- strict JSON rejection of non-finite values and stable machine-field semantics
- rectangular quoted CSV, including warning text containing commas
- exact and nominal-build generic SPICE topology/value consistency
- analytic LP/HP and nodal BP response-data schemas
- CLI rejection of accepted-but-ignored or contradictory flags
- JSON, CSV, quiet, raw, and table output carrying the calculation API's values for the same
  design ([test_output_value_agreement.py](../tests/test_output_value_agreement.py))
- a representative grid that touches every CLI option for each filter kind: valid commands
  exit 0 with well-formed output, and invalid or extreme input exits 1 or 2 with a one-line
  message and no traceback ([test_cli_input_robustness.py](../tests/test_cli_input_robustness.py))
- every `uv run filter-calc` example in the README and `docs/` runs cleanly as written
  ([test_cli_documented_examples.py](../tests/test_cli_documented_examples.py)). A new or
  edited example must stay runnable; syntax templates with `<...>` or `[...]` are skipped,
  and so are `wizard` and `web` lines, which never return.

SPICE tests verify the generated generic deck structurally and numerically against the
internal named circuit. An external simulator is not a test-suite dependency.

### Response accuracy regressions

[test_response_accuracy.py](../tests/test_response_accuracy.py) uses a separate cascaded
ABCD two-port calculation to check the produced circuit, including explicit series loss and
unequal ports. It covers missed requested-edge loss, narrow-band literal −3 dB crossings,
disconnected tolerance responses, the named local peak, finite refinement budgets, and the
actual sampling prescribed by SPICE exports. It also preserves the distinction between
calibration validity, harmonic rejection, and Cohn approximation agreement.

Use this file first for changes to response measurement. The synthesis support matrix remains
in its existing verification tests; improving measurement must not silently relax that matrix.
Numerical comparisons are simulations, not measured hardware or an external-SPICE run.

### Wizard and lifecycle

- parameter validation and state propagation
- category forms, output/build controls, and help labels
- real Textual pilot navigation where event-loop behavior matters, including mounted keyboard
  journeys through each design screen
  ([test_wizard_design_screen_journeys.py](../tests/test_wizard_design_screen_journeys.py)).
  These prove widget ids, default selections, and focus chains that the direct-handler tests
  stub out.
- wizard tables, component exports, response sidecars, and realized-build JSON equal the CLI
  output for the same design, with every field moved off its default so a dropped or
  swapped field fails ([test_wizard_cli_parity.py](../tests/test_wizard_cli_parity.py))
- designs the forms accept but the math cannot realize become visible error outcomes
  ([test_wizard_failure_surfacing.py](../tests/test_wizard_failure_surfacing.py))
- calculation revisioning: stale, cancelled, or popped-screen workers cannot publish
- failure clearing, pending-save blocking, component export preselection, and independent
  response sidecars

### Design service and web UI

- the shared request, synthesis, rendering, and export path equals the calculators and live
  CLI output ([test_design_service.py](../tests/test_design_service.py),
  [test_design_render_and_export.py](../tests/test_design_render_and_export.py))
- every web document, download, and result text is byte-identical to live CLI output for
  designs with every field off its default
  ([test_web_equivalence.py](../tests/test_web_equivalence.py))
- invalid web input returns 400 with the CLI's message, escaped in HTML
  ([test_web_errors.py](../tests/test_web_errors.py))
- timeouts return 503, cancel build analysis, queue excess requests, and leave no pool
  threads; exports write no files ([test_web_execution.py](../tests/test_web_execution.py))
- cross-site submissions and foreign `Host` names are refused before any work runs
  ([test_web_request_guard.py](../tests/test_web_request_guard.py))
- the SVG plot draws exactly the response-data samples
  ([test_web_svg_plot.py](../tests/test_web_svg_plot.py))
- pages, form parsing, `filter-calc web`, and importing the CLI without FastAPI
  (`test_web_pages.py`, `test_web_form_parsing.py`, `test_web_cmd.py`,
  `test_web_optional_import.py`)

Web tests call `pytest.importorskip("fastapi")` and share `tests/web_helpers.py`; CLI
comparisons go through `tests/cli_parity_helpers.py`. A browser is not a test dependency.

### Packaging and CI

- dynamic version and project metadata
- wheel/sdist contents, including `toroid_core_data.json`, `styles.tcss`, and the web
  templates and static files
- the web dependencies stay an optional extra, and an installed wheel without it prints the
  `filter-calc web` install hint
- installed-wheel CLI/API smoke checks from an isolated environment
- locked dependency resolution

## Coverage reports

Terminal report:

```bash
uv run pytest tests/ --cov=filter_lib --cov-report=term-missing
```

JSON report for analysis:

```bash
uv run pytest tests/ \
  --cov=filter_lib \
  --cov-report=json:/tmp/rf-filter-coverage.json
```

HTML report:

```bash
uv run pytest tests/ --cov=filter_lib --cov-report=html
open htmlcov/index.html       # macOS
```

The project targets useful branch and contract coverage, not an artificial 100% number.
New code should keep the repository above the enforced floor and should directly exercise
its meaningful success and failure paths.

## Multi-version checks

CI is authoritative for all four supported Python versions. Locally, uv can select an
installed interpreter explicitly. `uv run --python X.Y` rebuilds the project's `.venv` for
that interpreter, and syncs only what the command asks for, so pass `--extra web` (or the web
tests skip) and point `UV_PROJECT_ENVIRONMENT` at a directory outside the repository to keep
your main environment intact:

```bash
UV_PROJECT_ENVIRONMENT=/tmp/rf-filter-py310 uv run --python 3.10 --locked --extra web pytest tests/
UV_PROJECT_ENVIRONMENT=/tmp/rf-filter-py313 uv run --python 3.13 --locked --extra web pytest tests/
```

Do not update the lock file during a verification-only run. Use `uv lock --check` to
confirm it matches `pyproject.toml`.

## Distribution verification

```bash
uv build
RF_FILTER_DIST_DIR="$PWD/dist" uv run pytest tests/test_packaging.py
python tests/wheel_smoke.py dist/*.whl
```

The smoke script installs the wheel into a temporary isolated environment and exercises
the installed command and package data rather than importing the source checkout.

## Adding tests

- Name files `test_<behavior>.py` and tests `test_<observable_contract>`.
- Prefer reference values, identities, or independently computed expectations over
  repeating the implementation formula.
- Parameterize boundary families instead of copying nearly identical tests.
- Assert both the result and the claim: status fields, warnings, units, and output labels
  are part of an engineering calculator's correctness.
- For randomized screening, always supply a fixed seed and assert repeatability; do not
  describe bounded samples as yield or Monte Carlo statistics.
- Keep fixtures small and real. Avoid mocks where a fast deterministic calculation can be
  exercised directly.
- `pytest.approx(x, rel=r)` still applies a default absolute tolerance of 1e-12, which
  swamps the relative check for picofarad, nanohenry, and near-zero values. Pass
  `rel=..., abs=0` for small magnitudes. Passing `abs` alone disables `rel` entirely.
- Install class-level stubs, such as a wizard screen's `app` property, with `monkeypatch` so
  they are undone. A leaked stub makes later tests pass or fail depending on order.
- Mutation spot-check a new test group by breaking the code under test once. Run with
  `PYTHONDONTWRITEBYTECODE=1` and clear `__pycache__` afterward; a same-size edit restored
  within one second can otherwise reuse a stale `.pyc`.

## CI workflow

`.github/workflows/ci.yml` contains four jobs:

1. **Ruff quality** — lint and format check.
2. **Python matrix** — all tests on 3.10–3.13 with the `web` extra. Tests marked `runtime_budget` (build-analysis,
   calibration, and extreme-input runtime checks) run first without coverage
   instrumentation, so their wall-clock limits measure application runtime; the remaining
   suite (`-m "not runtime_budget"`) enforces the coverage gate.
3. **Core install** — the suite on Python 3.10 without the `web` extra (web tests skip),
   plus the exact `filter-calc web` install hint and exit code.
4. **Build and smoke distributions** — build, inspect, install, smoke, and upload
   artifacts after the other jobs pass.

The workflow uses read-only repository permissions and cancels an older in-progress run
for the same ref. Third-party actions are pinned to full commit SHAs, with the release
in a trailing comment; when updating an action, change the SHA and the comment together. It performs CI and artifact upload; it does not deploy a release.

## Troubleshooting

- If imports resolve to the wrong checkout, use `uv run python -c 'import filter_lib; print(filter_lib.__file__)'`.
- If coverage is unexpectedly low, confirm the command includes `--cov=filter_lib` and
  that tests are not being run from an installed copy outside the checkout.
- If a failure appears only under one Python version, reproduce with `uv run --python X.Y
  --locked ...` before changing compatibility code.
- If a Textual pilot hangs, run the single pilot with `-vv -s` and inspect worker
  completion/state revisioning; do not replace it with arbitrary sleeps.
