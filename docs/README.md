# RF Filter Calculator Documentation

Command-line tool for calculating LC filter component values. Designed for RF engineers and amateur radio operators.

## Documentation Index

- [Quick Start Guide](quick-start.md) - Get up and running quickly
- [User Guide](user-guide.md) - Complete usage reference
- [Filter Theory](filter-theory.md) - Background on filter types and topologies
- [Tips & Best Practices](tips-and-best-practices.md) - Get the most out of the tool
- [Caveats & Known Issues](caveats-and-known-issues.md) - Edge cases and limitations
- [Sample Output](sample-output.md) - Example outputs for all filter types
- [Testing Guide](testing.md) - Test suite documentation and coverage
- [Textual Wizard Patterns](textual-wizard-patterns.md) - Developer guide to wizard screen architecture

## Features

- **Filter Types**: Lowpass (Pi/T), Highpass (Pi/T), Bandpass (coupled resonator)
- **Response Types**: Butterworth, Chebyshev, Bessel
- **Preferred-Value Selection**: Auditable E12/E24/E96 capacitor policy; E-series is value density, not tolerance
- **Realized-Build Analysis**: Selected physical branches, explicit exact fallbacks, finite-Q loss, deterministic corners, and optional seeded screening
- **Verified Bandpass Results**: Calibrated Top-C synthesis with per-design response status rather than a blanket support claim
- **Screened Toroid Candidates**: Primary-sourced integer turns and winding capacity, with RF-Q/SRF/power limitations stated explicitly
- **Outputs**: Table, strict JSON, rectangular CSV, response data, ASCII plots, and generic exact or nominal-build SPICE decks
- **Interactive Wizard**: Guided design and build-analysis controls with safe export behavior

## Requirements

- Python 3.10 or higher
- `textual` library (for interactive TUI wizard)
- The development dependency group supplies pytest, coverage, and Ruff

## Installation

Requires [uv](https://docs.astral.sh/uv/).

```bash
git clone https://github.com/EmDecay/rf-filter-calculator.git
cd rf-filter-calculator
uv sync
```

For development (includes pytest):

```bash
uv sync --group dev
```

Run the tool:

```bash
uv run filter-calc lowpass butterworth pi 10MHz
```
