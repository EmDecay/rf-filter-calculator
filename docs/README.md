# RF Filter Calculator Documentation

Calculates LC filter component values for RF engineers and amateur radio operators. Use it from the command line, in a guided terminal wizard, or in a local web page; all three share one engine and give identical results.

## Documentation Index

- [Quick Start Guide](quick-start.md) - Get up and running quickly
- [User Guide](user-guide.md) - Complete usage reference
- [Web UI](user-guide.md#web-ui) - Browser interface, form-field to CLI-flag table, downloads, and local-only behaviour
- [Response Measurement Interpretation](user-guide.md#interpreting-response-measurements) - Convergence, peak references, separate −3 dB ranges, and approximation limits
- [Filter Theory](filter-theory.md) - Background on filter types and topologies
- [Tips & Best Practices](tips-and-best-practices.md) - Get the most out of the tool
- [Caveats & Known Issues](caveats-and-known-issues.md) - Edge cases and limitations
- [Sample Output](sample-output.md) - Example outputs for all filter types
- [Testing Guide](testing.md) - Test suite documentation and coverage
- [Textual Wizard Patterns](textual-wizard-patterns.md) - Developer guide to wizard screen architecture

## Features

- **Filter Types**: Low-pass (Pi/T), High-pass (Pi/T), Band-pass (coupled resonators)
- **Response Types**: Butterworth, Chebyshev, Bessel
- **Standard Capacitor Values**: E12/E24/E96 with one stated choice rule per capacitor; the E-series sets values per decade, not tolerance. `--allow-sub-pf` also chooses values below 1 pF
- **Build Simulation**: The chosen parts (standard capacitors and toroid windings, or the calculated value where no part was chosen), optional part losses (Q), fixed tolerance cases, and optional repeatable extra random cases
- **Checked Band-Pass Results**: Top-C designs with a per-design response check rather than a blanket support claim
- **Toroid Winding Suggestions**: Primary-sourced whole-turn windings that fit the core, with what is and is not checked stated explicitly
- **Outputs**: Table, strict JSON, rectangular CSV, response data, ASCII plots, and generic SPICE decks (calculated values or chosen parts)
- **Interactive Wizard**: Guided design and build-simulation controls with safe export behavior
- **Web UI**: Local browser page with the CLI's output text, an SVG response graph, and byte-identical downloads (optional `web` dependencies)

## Requirements

- Python 3.10 or higher
- `textual` library (for interactive TUI wizard)
- Optional `web` dependencies for the browser UI: FastAPI, uvicorn, Jinja2, and python-multipart (`uv sync --extra web`, or `pip install "rf-filter-calculator[web]"` for an installed package)
- The development dependency group supplies pytest, coverage, and Ruff

## Installation

Requires [uv](https://docs.astral.sh/uv/).

```bash
git clone https://github.com/EmDecay/rf-filter-calculator.git
cd rf-filter-calculator
uv sync
```

For the web UI, add the optional `web` extra; for development (pytest, Ruff), add the dev group:

```bash
uv sync --extra web
uv sync --group dev --extra web
```

Run the tool:

```bash
uv run filter-calc lowpass butterworth pi 10MHz   # command line
uv run filter-calc                                # interactive wizard
uv run filter-calc web                            # web UI at http://127.0.0.1:8765/
```
