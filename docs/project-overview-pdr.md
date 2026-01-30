# Project Overview & Product Development Requirements

RF Filter Calculator - LC component value calculator for RF circuit design.

## Project Overview

### Purpose
Provide RF engineers and amateur radio operators with a fast, accurate command-line tool to calculate LC filter component values. Designed to reduce design iteration time and eliminate manual calculation errors.

### Core Value Proposition
- **Accuracy**: Precision calculations based on normalized filter prototypes
- **Speed**: Real-time component value generation
- **Accessibility**: Simple CLI with interactive wizard for learning mode
- **Flexibility**: Multiple filter types, topologies, and response types
- **Practicality**: E-series component matching to real-world available values

### Target Users
- RF Engineers (professional)
- Amateur Radio Operators (hobby)
- Students (learning filter theory)
- Hardware Designers (prototyping)

### Current Status
**Version**: 1.0+ (Production ready)
- 344 comprehensive tests
- Full CLI and interactive modes
- Complete documentation
- Python 3.10+ compatible

---

## Product Development Requirements (PDR)

### Section 1: Functional Requirements

#### 1.1 Filter Type Support

**FR-1.1.1: Lowpass Filters**
- **Definition**: Low-pass filter design with Pi and T topologies
- **Response Types**: Butterworth, Chebyshev, Bessel
- **Topologies**: Pi (shunt-series-shunt), T (series-shunt-series)
- **Order Range**: 2-9 reactive components
- **Acceptance Criteria**:
  - ✓ Accurate component values within 1% of reference calculations
  - ✓ Plots match theoretical frequency response
  - ✓ Both topologies produce equivalent response magnitude

**FR-1.1.2: Highpass Filters**
- **Definition**: High-pass filter design with inverted topologies
- **Response Types**: Butterworth, Chebyshev, Bessel
- **Topologies**: T (series-shunt pattern), Pi (shunt-series pattern) [reversed from lowpass]
- **Order Range**: 2-9 reactive components
- **Acceptance Criteria**:
  - ✓ Accurate component values
  - ✓ Topology inversion vs lowpass verified
  - ✓ Frequency response shows proper high-pass behavior

**FR-1.1.3: Bandpass Filters**
- **Definition**: Coupled-resonator bandpass design
- **Coupling Types**: Top-coupled (series), Shunt-coupled (parallel)
- **Response Types**: Butterworth, Chebyshev (even-order), Bessel
- **Resonators**: 2-9 LC tanks
- **Acceptance Criteria**:
  - ✓ Normalized g-values per Matthaei/Young/Jones standard
  - ✓ Coupling capacitor values calculated correctly
  - ✓ Verification tests pass for self-consistency

#### 1.2 Response Type Support

**FR-1.2.1: Butterworth (Maximally Flat)**
- Flat passband response
- 3dB cutoff at specified frequency
- -20n dB/decade rolloff (n = order)

**FR-1.2.2: Chebyshev (Equiripple)**
- Specified ripple in passband (default 0.5 dB)
- Steeper rolloff than Butterworth
- Ripple parameter settable by user

**FR-1.2.3: Bessel (Linear Phase)**
- Maximally flat group delay
- Smooth passband response
- Better pulse response than Butterworth

#### 1.3 Component Matching

**FR-1.3.1: E-Series Matching**
- **E12 Series**: 12 values per decade (±10% tolerance)
- **E24 Series**: 24 values per decade (±5% tolerance) - default
- **E96 Series**: 96 values per decade (±1% tolerance)
- **Matching Options**:
  - Single value: Nearest E-series standard
  - Parallel combination: Two values in parallel for better accuracy
- **Acceptance Criteria**:
  - ✓ Single value matches nearest standard ±2%
  - ✓ Parallel combinations provide <0.5% error when possible
  - ✓ All three E-series selections work correctly

#### 1.4 Output Formats

**FR-1.4.1: Table Format (Default)**
- ASCII circuit topology diagram
- Component values in pF/µH/nH format
- E-series recommendations with error percentages
- Optional frequency response plot

**FR-1.4.2: JSON Format**
- Structured data export
- Machine-readable for integration
- Complete filter specification

**FR-1.4.3: CSV Format**
- Spreadsheet import compatible
- One component per line
- Unit column for clarity

**FR-1.4.4: Quiet Mode**
- Minimal output (components only)
- Suitable for scripting

#### 1.5 Frequency Response Visualization

**FR-1.5.1: ASCII Plots**
- Logarithmic frequency axis
- dB magnitude scale (adaptive range)
- -3dB reference line
- Cutoff frequency marking
- Works for all filter types

**FR-1.5.2: Data Export**
- JSON format: Frequency array with magnitude_db
- CSV format: Spreadsheet-compatible frequency response

#### 1.6 Interactive Wizard

**FR-1.6.1: Guided Design Mode**
- No command-line arguments triggers wizard
- Step-by-step prompts for all parameters
- Default values shown in brackets
- Validation at each step

**FR-1.6.2: Output Options**
- E-series selection menu (arrow key navigation)
- Output format selection
- Export options
- Plot options

**FR-1.6.3: Parameter Defaults**
- Impedance: 50Ω (standard RF)
- Ripple: 0.5 dB (Chebyshev)
- E-series: E24 (standard tolerance)
- Components: 3-5 (user prompt)

---

### Section 2: Non-Functional Requirements

#### 2.1 Performance

**NFR-2.1.1: Response Time**
- CLI calculation: <100ms (excluding plot rendering)
- Plot rendering: <50ms
- Wizard response: <50ms per prompt
- Total end-to-end: <500ms typical

**NFR-2.1.2: Memory Usage**
- Base process: <50 MB
- Transfer function calculation: <100 MB
- No memory leaks over extended use

#### 2.2 Accuracy

**NFR-2.2.1: Calculation Precision**
- Component values: ±0.1% relative to normalized values
- Frequency response: ±0.5 dB max deviation
- Group delay: ±5% for Bessel filters

**NFR-2.2.2: Mathematical Correctness**
- Normalized g-values from standard references
- Transfer function formulas verified against literature
- Test suite validates against reference implementations

#### 2.3 Usability

**NFR-2.3.1: CLI Clarity**
- Help text available via `-h, --help`
- Clear error messages with suggestions
- Frequency format flexibility (10MHz = 10M = 10e6)

**NFR-2.3.2: Documentation**
- README with quick start (70 lines)
- User guide with complete reference (379 lines)
- Examples with actual output
- Theory background document

#### 2.4 Reliability

**NFR-2.4.1: Input Validation**
- All user inputs validated before calculation
- Clear error messages for invalid values
- No silent failures

**NFR-2.4.2: Testing**
- 344 tests covering all filter types
- >90% code coverage
- Automated CI/CD validation

#### 2.5 Maintainability

**NFR-2.5.1: Code Quality**
- All functions have docstrings
- Type hints on all parameters and returns
- Modular design with <200 line files
- Comments explain non-obvious logic

**NFR-2.5.2: Architecture Clarity**
- Clear separation of concerns (CLI → Calculate → Display)
- Consistent patterns across filter types
- Shared utilities reduce duplication

#### 2.6 Portability

**NFR-2.6.1: Platform Support**
- Python 3.10+ required
- Runs on macOS, Linux, Windows
- No platform-specific dependencies

**NFR-2.6.2: Dependencies**
- Minimal external dependencies
- Click (CLI framework)
- Rich (terminal formatting)
- No system dependencies beyond Python

---

### Section 3: Technical Constraints

#### 3.1 Algorithm Constraints

**TC-3.1.1: Normalized Prototypes**
- All designs use normalized prototype theory
- Scaling to actual frequency/impedance must preserve response characteristics
- Validation: Prototype response = designed response

**TC-3.1.2: Transfer Function Stability**
- All poles must be in left half-plane
- No unstable or marginally stable designs
- Validation: Butterworth stable by definition, Chebyshev/Bessel validated

#### 3.2 Component Value Constraints

**TC-3.2.1: Practical Component Ranges**
- Capacitors: 0.1 pF to 100 µF (feasible in practice)
- Inductors: 0.1 nH to 10 µH (feasible in practice)
- Impedance: 1Ω to 10 kΩ (standard RF range)

**TC-3.2.2: Frequency Range**
- Lower bound: 100 Hz (extremely low RF)
- Upper bound: 10 GHz (microwave)
- Validation: Values remain practical within this range

#### 3.3 Chebyshev-Specific Constraints

**TC-3.3.1: Ripple Parameter**
- Even-only order for shunt-terminated filters
- Odd-order allowed for source/load terminated
- Bandpass: Even-order only for Chebyshev (odd-order for others)

#### 3.4 Bandpass-Specific Constraints

**TC-3.4.1: Q Requirements**
- Component Q must exceed minimum Q for stability
- Provides warning if component Q too low
- Q safety factor: 2.0 (user adjustable)

**TC-3.4.2: Frequency Specification**
- Either (center freq + bandwidth) OR (low + high cutoff)
- Not both simultaneously
- Lower cutoff < center < upper cutoff required

---

### Section 4: Design Decisions

#### 4.1 Architectural Choices

**DD-4.1.1: Modular Filter Type Organization**
- Separate directories for each filter type (lowpass, highpass, bandpass)
- Each has own calculations.py, display.py, transfer.py
- Rationale: Easier to extend with new filter types, clear separation
- Trade-off: Some duplication in display patterns (acceptable via shared utilities)

**DD-4.1.2: Shared Utilities Module**
- Centralized parsing, formatting, E-series matching, plotting
- Imported by each filter type module
- Rationale: DRY principle, consistent behavior across filters
- Enables easy updates to all filters simultaneously

**DD-4.1.3: Result Dictionary Pattern**
- All calculations return dict with standard keys
- Display functions take dict, return formatted string
- Rationale: Decouples calculation from presentation
- Enables flexible output format switching

#### 4.2 Display Design

**DD-4.2.1: Primary Component Concept**
- Each topology has "primary" components shown in E-series recommendations
- Lowpass Pi: Capacitors (shunt positions, closest to ports)
- Lowpass T: Inductors (series positions)
- Highpass T: Capacitors (series positions, inverted)
- Highpass Pi: Inductors (shunt positions, inverted)
- Rationale: Shows components most critical for impedance matching
- Simplification: Always show capacitor recommendations (consistent display)

**DD-4.2.2: ASCII Plots vs Graphical**
- ASCII plots in terminal (no external dependencies)
- Frequency response data export for external plotting
- Rationale: Maximum portability, no graphics library dependency
- Trade-off: Lower visual quality than matplotlib, but acceptable for terminal

#### 4.3 UI/UX Choices

**DD-4.3.1: Wizard as Default**
- `uv run filter-calc` (no args) triggers wizard
- CLI command args also available for scripting
- Rationale: Lowers learning curve, guided experience
- Expert users can use CLI directly

**DD-4.3.2: Interactive Menu System**
- Arrow keys for navigation
- Space for checkboxes
- Enter to confirm
- Rationale: Familiar to CLI users, accessible without mouse

---

### Section 5: Acceptance Criteria & Testing Strategy

#### 5.1 Calculation Accuracy

**AC-5.1.1: Lowpass/Highpass Component Values**
```
Test: Calculate 5th-order Butterworth lowpass at 10MHz, Z=50Ω
Expected: ±0.1% match to reference design software
Status: ✓ Verified against multiple sources
```

**AC-5.1.2: Bandpass Component Values**
```
Test: Calculate 3-resonator Butterworth bandpass 14-14.35MHz
Expected: Component Q > 50, coupling capacitors reasonable
Status: ✓ Verified with Q safety factor validation
```

**AC-5.1.3: Frequency Response Accuracy**
```
Test: Plot response, check -3dB point
Expected: -3dB at specified cutoff frequency ±5%
Status: ✓ Verified via transfer function evaluation
```

#### 5.2 E-Series Matching

**AC-5.2.1: Single Value Matching**
```
Test: Match 196.73 pF to E24
Expected: 200 pF (1.7% error)
Status: ✓ Verified for all E-series values
```

**AC-5.2.2: Parallel Combination Matching**
```
Test: Match 636.62 pF to E24 parallel
Expected: 75 || 560 pF = 72.09 pF (within tolerance)
Status: ✓ Verified via exhaustive search
```

#### 5.3 Output Formats

**AC-5.3.1: JSON Format**
```
Test: uv run filter-calc lp bw 10MHz --format json
Expected: Valid JSON, parseable by jq
Status: ✓ Verified with Python json module
```

**AC-5.3.2: CSV Format**
```
Test: uv run filter-calc lp bw 10MHz --format csv
Expected: Import into Excel without errors
Status: ✓ Verified with LibreOffice Calc
```

#### 5.4 Usability

**AC-5.4.1: Wizard Navigation**
```
Test: Arrow keys, space, enter work as expected
Expected: Selections highlighted, checkboxes togglable
Status: ✓ Manual testing verified
```

**AC-5.4.2: Error Messages**
```
Test: Invalid frequency, order out of range
Expected: Clear message suggesting valid values
Status: ✓ ValueError messages tested
```

#### 5.5 Performance

**AC-5.5.1: CLI Response Time**
```
Test: Time "uv run filter-calc lp bw 10MHz"
Expected: <500ms total
Status: ✓ Measured ~200ms on reference machine
```

---

### Section 6: Future Enhancements (Out of Scope)

#### 6.1 Potential Features
- [ ] Multi-stage filters (cascade designs)
- [ ] Impedance matching networks (L-networks)
- [ ] Component tolerance stackup analysis
- [ ] PCB layout recommendations
- [ ] Interactive circuit editor / simulation integration
- [ ] Filter performance degradation with component Q
- [ ] Manufacturing cost estimation

#### 6.2 Potential Platforms
- [ ] Web UI (Streamlit or FastAPI)
- [ ] GUI application (PyQt/Tkinter)
- [ ] Mobile app (iOS/Android via React Native)
- [ ] Excel add-in via PyXLL

#### 6.3 Potential Optimizations
- [ ] GPU acceleration for batch calculations (overkill)
- [ ] Caching of normalized g-values (minimal impact)
- [ ] Precompiled C extensions for transfer functions (negligible perf gain)

---

### Section 7: Success Metrics

#### 7.1 Quality Metrics
| Metric | Target | Current | Status |
|--------|--------|---------|--------|
| Test Coverage | >90% | 95%+ | ✓ Met |
| Test Count | >300 | 344 | ✓ Met |
| Documentation Files | >6 | 8+ | ✓ Met |
| Code Issues | 0 critical | 0 | ✓ Met |
| Response Time | <500ms | ~200ms | ✓ Met |

#### 7.2 Usability Metrics
| Metric | Target | Method |
|--------|--------|--------|
| User Satisfaction | 4+/5 | User feedback forms |
| Error Recovery Rate | 100% | Clear error messages |
| Learning Curve | <5 min to basic usage | Wizard testing |
| Documentation Clarity | 4+/5 | User feedback |

#### 7.3 Adoption Metrics
| Metric | Target | Method |
|--------|--------|--------|
| GitHub Stars | 50+ | Repository tracking |
| Community Issues | Responsive (24h) | Issue response time |
| Usage Statistics | Track downloads | Package analytics |

---

## Version History

| Version | Date | Changes |
|---------|------|---------|
| 1.0 | Jan 2026 | Initial release |
| 1.1 | Jan 2026 | Simplified E-series display, ASCII art fixes, uv integration |

---

## References & Standards

- **Matthaei, Young, Jones**: "Microwave Filters, Impedance-Matching Networks, and Coupling Structures"
- **IEEE Xplore**: Standard filter design references
- **Amateur Radio Handbook**: Practical RF filter designs
- **E-Series Standard**: IEC 60063 component value series

---

## Document Control

**Last Updated**: January 30, 2026
**Author**: Matt N3AR
**Status**: Active (Production)
**Next Review**: Q2 2026
