"""The shared design service synthesizes exactly what the calculators return.

``filter_lib.design`` is the only orchestration path for the CLI, the wizard, and the
web UI, so its result dicts, validation messages, and build-analysis handling are
checked here against the calculators and against the CLI's own error text.
"""

from __future__ import annotations

import dataclasses
import math
import re
from collections.abc import Callable

import pytest

from filter_lib import highpass, lowpass
from filter_lib.bandpass import calculate_bandpass_filter
from filter_lib.design import (
    DesignCancelled,
    DesignRequest,
    DesignResult,
    band_from_edges,
    design,
    synthesize,
)
from filter_lib.shared.build_types import BuildAnalysisCancelled, BuildAnalysisResult, BuildConfig
from filter_lib.shared.eseries import DEFAULT_MATCH_POLICY
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
    request = dataclasses.replace(
        request_factory(), realization=FAST_BUILD, run_build_analysis=True
    )

    outcome = design(request)

    assert isinstance(outcome.build_analysis, BuildAnalysisResult)
    assert outcome.build_analysis.category == request.category
    assert outcome.build_analysis.config == FAST_BUILD
    assert outcome.result == synthesize(request)
    assert outcome.request is request


def test_build_settings_alone_do_not_run_the_build_analysis():
    """A chosen-parts deck needs the build settings, never the tolerance cases."""
    request = dataclasses.replace(_ladder("highpass", "chebyshev"), realization=FAST_BUILD)

    outcome = design(request)

    assert outcome.build_analysis is None
    assert outcome.realization == FAST_BUILD
    assert design(_ladder("highpass", "chebyshev")).realization == BuildConfig()


def _counting_check(cancel_after: int | None = None) -> tuple[list[int], Callable[[], bool]]:
    """A cancellation check that counts its polls and cancels after ``cancel_after`` of them."""
    polls = [0]

    def check() -> bool:
        polls[0] += 1
        return cancel_after is not None and polls[0] > cancel_after

    return polls, check


def test_cancellation_check_stops_the_build_analysis():
    request = _ladder("lowpass", "bessel")
    # Synthesis and part resolution poll first; cancel at the build's first poll.
    before_build, check = _counting_check()
    design(request, should_cancel=check)
    _polls, check = _counting_check(cancel_after=before_build[0])

    with pytest.raises(BuildAnalysisCancelled):
        design(
            dataclasses.replace(request, run_build_analysis=True, realization=FAST_BUILD),
            should_cancel=check,
        )


def test_cancellation_check_stops_the_design_before_synthesis():
    request = dataclasses.replace(_ladder("lowpass", "bessel"), run_build_analysis=True)

    with pytest.raises(DesignCancelled) as raised:
        design(request, should_cancel=lambda: True)

    assert not isinstance(raised.value, BuildAnalysisCancelled)


def test_check_that_never_cancels_leaves_a_design_without_build_unchanged():
    request = _ladder("lowpass", "bessel")
    polls, check = _counting_check()

    outcome = design(request, should_cancel=check)

    # Synthesis and part resolution poll the check; no build runs.
    assert polls[0] > 0
    assert outcome.build_analysis is None
    assert outcome.result == design(request).result
    assert outcome.parts == design(request).parts


def test_design_result_carries_the_request_and_its_part_policy():
    request = _ladder("lowpass", "butterworth")

    outcome = design(request)

    assert isinstance(outcome, DesignResult)
    assert (outcome.warnings, outcome.build_analysis) == ((), None)
    assert (outcome.request, outcome.eseries) == (request, "E24")
    assert outcome.match_policy == DEFAULT_MATCH_POLICY


@pytest.mark.parametrize(
    "factory, message",
    [
        (
            lambda: _ladder("lowpass", "chebyshev", ripple_db=0.0),
            "Ripple must be greater than 0 and at most 3.0 dB",
        ),
        (
            lambda: _ladder("highpass", "chebyshev", ripple_db=-1.0),
            "Ripple must be greater than 0 and at most 3.0 dB",
        ),
        (
            lambda: _ladder("lowpass", "chebyshev", ripple_db=None),
            "Ripple must be greater than 0 and at most 3.0 dB",
        ),
        (
            lambda: _ladder("lowpass", "chebyshev", ripple_db=3.5),
            "Ripple must be greater than 0 and at most 3.0 dB",
        ),
        (
            lambda: _ladder("lowpass", "chebyshev", ripple_db=math.inf),
            "Ripple must be greater than 0 and at most 3.0 dB",
        ),
        (
            lambda: _bandpass("chebyshev", ripple_db=3.01),
            "Ripple must be greater than 0 and at most 3.0 dB",
        ),
        (
            lambda: _bandpass("chebyshev", order=4),
            "Chebyshev needs an odd number of resonators (3, 5, 7, or 9) for equal source and "
            "load impedance",
        ),
        (
            lambda: _bandpass("chebyshev", ripple_db=0.0),
            "Ripple must be greater than 0 and at most 3.0 dB",
        ),
        (
            lambda: _bandpass("chebyshev", ripple_db=math.nan),
            "Ripple must be greater than 0 and at most 3.0 dB",
        ),
        (lambda: _bandpass(bandwidth_hz=None), "Bandwidth is required"),
        (lambda: _ladder("lowpass", "bessel", eseries="E7"), "E-series must be E12, E24, or E96"),
        (lambda: _ladder("lowpass", "bessel", eseries=24), "E-series must be E12, E24, or E96"),
        (
            lambda: _ladder("lowpass", "bessel", realization={"grid_points": 51}),
            "realization must be a BuildConfig or None",
        ),
        (
            lambda: _ladder("lowpass", "bessel", run_build_analysis=1),
            "run_build_analysis must be on or off",
        ),
        (lambda: _bandpass(q_safety=0.0), "Q safety factor must be positive"),
        (
            lambda: _bandpass(requested_f_low_hz=14e6),
            "Lower and upper cutoff frequencies must be supplied together",
        ),
        (lambda: _ladder("notch", "butterworth"), "Unknown filter category"),
    ],
)
def test_request_validation_messages(factory, message):
    with pytest.raises(ValueError, match=f"^{re.escape(message)}$"):
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
        (2.0, 1.0, "Lower cutoff frequency must be below the upper cutoff frequency"),
    ],
)
def test_band_edges_are_validated_before_use(low, high, message):
    with pytest.raises(ValueError, match=f"^{re.escape(message)}$"):
        band_from_edges(low, high)


def test_band_edges_give_geometric_center_and_width():
    center, width = band_from_edges(14e6, 14.35e6)

    assert center == pytest.approx(math.sqrt(14e6 * 14.35e6), rel=1e-15)
    assert width == pytest.approx(0.35e6, rel=1e-9)
