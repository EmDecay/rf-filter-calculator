# Testing Guide

**Last updated:** July 19, 2026
**Applies to:** RF Filter Calculator 2.1.0

## Quality gates

The repository has more than 2,000 collected pytest cases. CI requires at least 90% line
coverage and runs the complete suite on Python 3.10, 3.11, 3.12, and 3.13. A skipped test
is reported as a skip; failures, lint errors, format errors, and coverage shortfalls are
not hidden.

Run the same primary gates locally:

```bash
uv sync --locked --group dev
uv run --locked ruff check .
uv run --locked ruff format --check .
uv run --locked pytest tests/ \
  --cov=filter_lib \
  --cov-report=term-missing \
  --cov-fail-under=90
```

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
  tests/test_build_simulation.py \
  tests/test_build_output.py \
  tests/test_spice_export.py

# Full suite and coverage before handoff
uv run pytest tests/ --cov=filter_lib --cov-report=term-missing --cov-fail-under=90
```

Do not weaken assertions or exclude code merely to restore a green gate. A numeric bug
should normally get a regression that reproduces the original values.

## What the suite covers

### Synthesis and public APIs

- Butterworth, Chebyshev, and Bessel LP/HP ladder values and scaling laws
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

### Physical realization

- E12/E24/E96 preferred-value search and deterministic selection policy
- one-part preference, material two-part improvement threshold, and sub-1 pF expert action
- toroid primary-source eligibility, frequency guidance, integer-turn error, winding
  capacity, deterministic ranking, and empty-candidate behavior
- truthful fallbacks when a nominal part or screened winding is unavailable

### Circuit and build analysis

- exact and nominal named circuit construction
- unequal source/load transducer power gain
- scale-normalized nodal solution across normal, extreme, and subnormal impedances
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

SPICE tests verify the generated generic deck structurally and numerically against the
internal named circuit. An external simulator is not a test-suite dependency.

### Wizard and lifecycle

- parameter validation and state propagation
- category forms, output/build controls, and help labels
- real Textual pilot navigation where event-loop behavior matters
- calculation revisioning: stale, cancelled, or popped-screen workers cannot publish
- failure clearing, pending-save blocking, component export preselection, and independent
  response sidecars

### Packaging and CI

- dynamic version and project metadata
- wheel/sdist contents, including `toroid_core_data.json` and `styles.tcss`
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
installed interpreter explicitly:

```bash
uv run --python 3.10 --locked pytest tests/
uv run --python 3.13 --locked pytest tests/
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

## CI workflow

`.github/workflows/ci.yml` contains three jobs:

1. **Ruff quality** — lint and format check.
2. **Python matrix** — full suite with coverage on 3.10–3.13.
3. **Build and smoke distributions** — build, inspect, install, smoke, and upload
   artifacts after quality/tests pass.

The workflow uses read-only repository permissions and cancels an older in-progress run
for the same ref. It performs CI and artifact upload; it does not deploy a release.

## Troubleshooting

- If imports resolve to the wrong checkout, use `uv run python -c 'import filter_lib; print(filter_lib.__file__)'`.
- If coverage is unexpectedly low, confirm the command includes `--cov=filter_lib` and
  that tests are not being run from an installed copy outside the checkout.
- If a failure appears only under one Python version, reproduce with `uv run --python X.Y
  --locked ...` before changing compatibility code.
- If a Textual pilot hangs, run the single pilot with `-vv -s` and inspect worker
  completion/state revisioning; do not replace it with arbitrary sleeps.
