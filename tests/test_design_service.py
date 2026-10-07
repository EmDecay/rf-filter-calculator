"""The shared design service synthesizes exactly what the calculators return.

``filter_lib.design`` is the only orchestration path for the CLI, the wizard, and the
web UI, so its result dicts, validation messages, and build-analysis handling are
checked here against the calculators and against the CLI's own error text.
"""

from __future__ import annotations

import dataclasses
import math

import pytest

from filter_lib import highpass, lowpass
from filter_lib.bandpass import calculate_bandpass_filter
from filter_lib.design import (
    DesignRequest,
    DesignResult,
    band_from_edges,
    design,
    synthesize,
    with_build_analysis,
)
from filter_lib.shared.build_types import BuildAnalysisCancelled, BuildAnalysisResult, BuildConfig
from tests.cli_parity_helpers import cli_error_message

FAST_BUILD = BuildConfig(grid_points=51)


def _ladder(category: str, filter_type: str, topology: str = "pi", **overrides) -> DesignRequest:
    values = dict(
        category=category,
        filter_type=filter_type,
        topology=topology,
        frequency_hz=7.1e6,
        impedance=75.0,
        order=5,
        ripple_db=0.25,
    )
    values.update(overrides)
    return DesignRequest(**values)


def _bandpass(filter_type: str = "butterworth", **overrides) -> DesignRequest:
    values = dict(
        category="bandpass",
        filter_type=filter_type,
        topology="top",
        frequency_hz=14.175e6,
        impedance=75.0,
        order=3,
        ripple_db=0.25,
        bandwidth_hz=350e3,
    )
    values.update(overrides)
    return DesignRequest(**values)


@pytest.mark.parametrize("category, module", [("lowpass", lowpass), ("highpass", highpass)])
@pytest.mark.parametrize("filter_type", ["butterworth", "chebyshev", "bessel"])
@pytest.mark.parametrize("topology", ["pi", "t"])
def test_ladder_result_is_the_calculator_output(category, module, filter_type, topology):
    request = _ladder(category, filter_type, topology)
    calculate = getattr(module, f"calculate_{filter_type}")
    if filter_type == "chebyshev":
        first, second, order = calculate(7.1e6, 75.0, 0.25, 5, topology=topology)
    else:
        first, second, order = calculate(7.1e6, 75.0, 5, topology=topology)
    caps, inds = (first, second) if category == "lowpass" else (second, first)

    result = synthesize(request)

    assert result == {
        "filter_type": filter_type,
        "freq_hz": 7.1e6,
        "impedance": 75.0,
        "capacitors": caps,
        "inductors": inds,
        "order": order,
        "ripple": 0.25 if filter_type == "chebyshev" else None,
        "topology": topology,
    }
    # Each category keeps its historical key order, which JSON output follows.
    expected_first = "capacitors" if category == "lowpass" else "inductors"
    assert list(result)[3] == expected_first


def test_filter_type_aliases_resolve_to_canonical_names():
    request = _ladder("lowpass", "ch")

    assert request.filter_type == "chebyshev"
    assert synthesize(request)["filter_type"] == "chebyshev"


@pytest.mark.parametrize(
    "filter_type, order, overrides",
    [
        ("butterworth", 3, {}),
        ("chebyshev", 5, {"qu": 250.0}),
        ("bessel", 4, {"resonator_inductance": 1.5e-6}),
        ("butterworth", 2, {"resonator_impedance": 100.0, "ql": 150.0, "qc": 900.0}),
    ],
)
def test_bandpass_result_is_the_calculator_output(filter_type, order, overrides):
    request = _bandpass(filter_type, order=order, **overrides)

    expected = calculate_bandpass_filter(
        f0=14.175e6,
        bw=350e3,
        z0=75.0,
        n_resonators=order,
        filter_type=filter_type,
        coupling="top",
        ripple_db=0.25 if filter_type == "chebyshev" else 0.5,
        **overrides,
    )

    assert synthesize(request) == expected


def test_non_chebyshev_bandpass_ignores_the_supplied_ripple():
    assert synthesize(_bandpass(ripple_db=2.5)) == synthesize(_bandpass(ripple_db=0.5))


def test_edge_specified_bandpass_restates_the_requested_edges():
    request = _bandpass(requested_f_low_hz=14.0e6, requested_f_high_hz=14.35e6)

    requested = synthesize(request)["requested_parameters"]

    assert requested["frequency_specification"] == "edge_frequencies"
    assert (requested["f_low_hz"], requested["f_high_hz"]) == (14.0e6, 14.35e6)


def test_design_without_build_carries_bandpass_warnings():
    outcome = design(_bandpass())

    assert outcome.category == "bandpass"
    assert outcome.warnings == tuple(outcome.result["warnings"])
    assert outcome.build_analysis is None


def test_ladder_design_has_no_warnings():
    assert design(_ladder("highpass", "bessel")).warnings == ()


@pytest.mark.parametrize(
    "request_factory",
    [lambda: _ladder("lowpass", "butterworth"), lambda: _bandpass("bessel")],
    ids=["lowpass", "bandpass"],
)
def test_design_with_build_config_returns_the_analysis(request_factory):
    request = dataclasses.replace(request_factory(), build=FAST_BUILD)

    outcome = design(request)

    assert isinstance(outcome.build_analysis, BuildAnalysisResult)
    assert outcome.build_analysis.category == request.category
    assert outcome.result == synthesize(request)


def test_with_build_analysis_keeps_the_synthesized_result():
    outcome = design(_ladder("highpass", "chebyshev"))

    analyzed = with_build_analysis(outcome, FAST_BUILD)

    assert analyzed.result is outcome.result
    assert analyzed.warnings == outcome.warnings
    assert isinstance(analyzed.build_analysis, BuildAnalysisResult)


def test_cancellation_check_stops_the_build_analysis():
    request = dataclasses.replace(_ladder("lowpass", "bessel"), build=FAST_BUILD)

    with pytest.raises(BuildAnalysisCancelled):
        design(request, should_cancel=lambda: True)


def test_cancellation_check_is_not_consulted_without_build():
    def never_called() -> bool:
        raise AssertionError("synthesis must not poll the cancellation check")

    assert design(_ladder("lowpass", "bessel"), should_cancel=never_called).result


def test_design_result_defaults_to_no_warnings_or_analysis():
    outcome = DesignResult(category="lowpass", result={"order": 3})

    assert (outcome.warnings, outcome.build_analysis) == ((), None)


@pytest.mark.parametrize(
    "factory, message",
    [
        (lambda: _ladder("lowpass", "chebyshev", ripple_db=0.0), "Ripple must be positive"),
        (lambda: _ladder("highpass", "chebyshev", ripple_db=-1.0), "Ripple must be positive"),
        (lambda: _ladder("lowpass", "chebyshev", ripple_db=None), "Ripple must be positive"),
        (
            lambda: _ladder("lowpass", "chebyshev", ripple_db=3.5),
            "Ripple must be at most 3.0 dB",
        ),
        (
            lambda: _ladder("lowpass", "chebyshev", ripple_db=math.inf),
            "Ripple must be at most 3.0 dB",
        ),
        (
            lambda: _bandpass("chebyshev", ripple_db=3.01),
            "Ripple must be at most 3.0 dB",
        ),
        (
            lambda: _bandpass("chebyshev", order=4),
            "Chebyshev requires odd resonator count",
        ),
        (
            lambda: _bandpass("chebyshev", ripple_db=0.0),
            "Ripple must be positive and finite",
        ),
        (
            lambda: _bandpass("chebyshev", ripple_db=math.nan),
            "Ripple must be positive and finite",
        ),
        (lambda: _bandpass(bandwidth_hz=None), "Bandwidth is required"),
        (lambda: _bandpass(q_safety=0.0), "Q safety factor must be positive"),
        (
            lambda: _bandpass(requested_f_low_hz=14e6),
            "Lower and upper cutoff frequencies must be supplied together",
        ),
        (lambda: _ladder("notch", "butterworth"), "Unknown filter category"),
    ],
)
def test_request_validation_messages(factory, message):
    with pytest.raises(ValueError, match=f"^{message}$"):
        factory()


def test_unknown_ladder_filter_type_is_rejected_at_synthesis():
    with pytest.raises(ValueError, match="^Unknown filter type: elliptic$"):
        synthesize(_ladder("lowpass", "elliptic"))


def test_non_chebyshev_ladders_accept_any_ripple():
    assert synthesize(_ladder("lowpass", "butterworth", ripple_db=None))["ripple"] is None


@pytest.mark.parametrize(
    "argv, factory",
    [
        (("lp", "ch", "pi", "10MHz", "-r", "0"), lambda: _ladder("lowpass", "ch", ripple_db=0.0)),
        (("hp", "ch", "t", "10MHz", "-r", "4"), lambda: _ladder("highpass", "ch", ripple_db=4.0)),
        (
            ("bp", "ch", "top", "-f", "14MHz", "-b", "500kHz", "-n", "4"),
            lambda: _bandpass("ch", order=4),
        ),
        (
            ("bp", "ch", "top", "-f", "14MHz", "-b", "500kHz", "-r", "0"),
            lambda: _bandpass("ch", ripple_db=0.0),
        ),
        (
            ("bp", "bw", "top", "-f", "14MHz", "-b", "500kHz", "--q-safety", "0"),
            lambda: _bandpass(q_safety=0.0),
        ),
    ],
)
def test_request_messages_match_the_cli(monkeypatch, capsys, argv, factory):
    with pytest.raises(ValueError) as excinfo:
        factory()

    assert str(excinfo.value) == cli_error_message(monkeypatch, capsys, *argv)


def test_nan_ladder_ripple_reaches_the_calculator_check_like_the_cli(monkeypatch, capsys):
    request = _ladder("lowpass", "chebyshev", frequency_hz=10e6, impedance=50.0, order=3)
    request = dataclasses.replace(request, ripple_db=math.nan)

    with pytest.raises(ValueError) as excinfo:
        design(request)

    expected = cli_error_message(monkeypatch, capsys, "lp", "ch", "pi", "10MHz", "-r", "nan")
    assert str(excinfo.value) == expected


@pytest.mark.parametrize(
    "low, high, message",
    [
        ("1", 2.0, "Lower cutoff frequency must be positive and finite"),
        (1.0, math.inf, "Upper cutoff frequency must be positive and finite"),
        (True, 2.0, "Lower cutoff frequency must be positive and finite"),
        (2.0, 1.0, "Lower frequency must be less than upper"),
    ],
)
def test_band_edges_are_validated_before_use(low, high, message):
    with pytest.raises(ValueError, match=f"^{message}$"):
        band_from_edges(low, high)


def test_band_edges_give_geometric_center_and_width():
    center, width = band_from_edges(14e6, 14.35e6)

    assert center == pytest.approx(math.sqrt(14e6 * 14.35e6), rel=1e-15)
    assert width == pytest.approx(0.35e6, rel=1e-9)
