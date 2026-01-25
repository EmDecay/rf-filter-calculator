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

## Features

- **Filter Types**: Lowpass (Pi), Highpass (T), Bandpass (coupled resonator)
- **Response Types**: Butterworth, Chebyshev, Bessel
- **E-Series Matching**: E12/E24/E96 standard values with parallel combinations
- **ASCII Plots**: Terminal-based frequency response visualization
- **Multiple Outputs**: Table, JSON, CSV formats
- **Interactive Wizard**: Guided filter design mode

## Requirements

- Python 3.10 or higher
- `questionary` library (for interactive wizard interface)
- `pytest` (for running tests)

## Installation

```bash
git clone https://github.com/EmDecay/rf-filter-calculator.git
cd rf-filter-calculator
pip install -r requirements.txt
chmod +x filter-calc.py
```

Or install as a package:

```bash
pip install -e .
filter-calc lowpass butterworth 10MHz
```
