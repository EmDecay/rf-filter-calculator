"""Where the build's results are qualified, and what is predicted with the parasitic model.

Every built chip inductor stays within its SRF drift and design allowances over a range of
frequencies; the build reports the range they share. A high-pass build finds its reference
peak, half-power threshold and cutoff only up to the top of that range (never below twice
the cutoff). A chosen-parts result outside the range is labelled "predicted with the
parasitic model, not qualified"; ideal results are never labelled. Without a part whose SRF
is checked (toroid windings, calculated values) nothing changes.
"""

from __future__ import annotations

import dataclasses
import json

import pytest

from filter_lib.design import DesignRequest, design
from filter_lib.shared.build_output_formatting import (
    PARASITIC_PREDICTION,
    format_build_analysis_block,
)
from filter_lib.shared.build_output_payloads import build_analysis_fields
from filter_lib.shared.build_response import (
    build_frequency_grid,
    evaluation_ports,
    highpass_passband_top,
    measure_circuit,
)
from filter_lib.shared.build_simulation import analyze_build
from filter_lib.shared.build_types import BuildConfig
from filter_lib.shared.circuit_builders import build_named_circuit
from tests.cli_parity_helpers import cli_stdout

FAST = BuildConfig(grid_points=51)


def _untrimmed_build(request: DesignRequest):
    """The build of ``request`` with each tank as its standard-value choice, no trimmer.

    The band-pass measurement scenarios below were found on such builds, whose tanks are
    not tuned: their tolerance cases (and a narrow band's nominal build) are detuned. A
    design now tunes each tank with a trimmer, so the scenarios keep their circuits by
    building the same parts without the tank sizing.
    """
    outcome = design(dataclasses.replace(request, run_build_analysis=False))
    parts = dataclasses.replace(outcome.parts, tanks={})
    return outcome, analyze_build(outcome.result, "bandpass", request.realization, parts=parts)


# 25.2 nH shunt inductors at 125 MHz: LQW15AN25NG80D, within its allowances to 900 MHz.
HP_CHIPS = DesignRequest(
    "highpass",
    "butterworth",
    "pi",
    125e6,
    19.792033717615695,
    3,
    realization=FAST,
    run_build_analysis=True,
)
# 91 nH at 400 MHz: LQW18AN91NG00D, within its allowances only to 425.9 MHz, while the
# chosen parts' -3 dB cutoff is at 429.2 MHz.
LP_BEYOND = DesignRequest(
    "lowpass",
    "chebyshev",
    "pi",
    400e6,
    200.0,
    5,
    ripple_db=0.5,
    realization=FAST,
    run_build_analysis=True,
)


def test_highpass_figures_stop_at_the_top_of_the_qualified_range():
    result = {"freq_hz": 125e6}
    freqs = [12.5e6, 1.25e9]

    assert highpass_passband_top(result, "lowpass", freqs, (0.0, 9e8)) is None
    assert highpass_passband_top(result, "highpass", freqs, None) is None
    # A range that reaches the sweep's end changes nothing.
    assert highpass_passband_top(result, "highpass", freqs, (0.0, 2e9)) is None
    assert highpass_passband_top(result, "highpass", freqs, (0.0, 9e8)) == 9e8
    # Never below twice the cutoff, the window every part was checked over.
    assert highpass_passband_top(result, "highpass", freqs, (0.0, 2.4e8)) == 2.5e8


def test_a_highpass_build_with_chips_measures_only_inside_the_qualified_range():
    outcome = design(HP_CHIPS)
    analysis = outcome.build_analysis

    assert analysis.qualified_range_hz == (0.0, pytest.approx(900.0e6, rel=1e-3))
    top = analysis.passband_top_hz
    assert top == analysis.qualified_range_hz[1]
    for measurement in (analysis.calculated, analysis.nominal_build):
        assert measurement.reference_peak_frequency_hz <= top
        assert measurement.f_low < top
    for case in analysis.cases:
        assert case.measurement.reference_peak_frequency_hz <= top
    # The whole sweep would put the ideal circuit's peak at the sweep's end instead.
    result = outcome.result
    freqs = build_frequency_grid(result, "highpass", FAST.grid_points)
    source, load = evaluation_ports(result, "highpass", FAST)
    circuit = build_named_circuit(result, "highpass")
    whole = measure_circuit(circuit, result, "highpass", freqs, source, load)
    limited = measure_circuit(circuit, result, "highpass", freqs, source, load, top)
    assert whole.reference_peak_frequency_hz > top
    assert limited == analysis.calculated


def test_the_highpass_build_states_its_passband_top_and_qualified_range():
    lines = format_build_analysis_block(design(HP_CHIPS).build_analysis)
    text = " ".join(" ".join(lines).split())

    assert (
        "Passband = from the requested cutoff up to 900 MHz, including both; a high-pass "
        "build takes its peak and half-power threshold only where its chip inductors are "
        "qualified."
    ) in text
    assert (
        "Qualified range: DC to 900 MHz, where every chip inductor stays within its "
        f"allowances; results outside it are {PARASITIC_PREDICTION}."
    ) in text
    assert "each chip inductor at its own tolerance (±2%)." in text


@pytest.mark.parametrize("category", ["lowpass", "highpass"])
def test_an_hf_build_without_a_checked_part_is_not_limited(category):
    outcome = design(
        DesignRequest(
            category, "butterworth", "pi", 14e6, 50.0, 5, realization=FAST, run_build_analysis=True
        )
    )
    analysis = outcome.build_analysis

    assert analysis.qualified_range_hz is None and analysis.passband_top_hz is None
    text = "\n".join(format_build_analysis_block(analysis))
    assert "Qualified range" not in text and PARASITIC_PREDICTION not in text
    assert "L ±10%." in text
    payload = build_analysis_fields(outcome.result, analysis)
    assert payload["nominal_build"]["qualified_range_hz"] is None
    assert payload["nominal_build"]["measurement"]["outside_qualified_range"] == []


def test_a_chosen_parts_result_outside_the_range_is_labelled_not_qualified():
    outcome = design(LP_BEYOND)
    analysis = outcome.build_analysis
    low, high = analysis.qualified_range_hz

    assert outcome.parts.inductor("L1").build_pick.part_name == "LQW18AN91NG00D"
    assert analysis.calculated.f_high < high < analysis.nominal_build.f_high
    lines = format_build_analysis_block(analysis)
    chosen = lines.index(next(line for line in lines if line.startswith("Chosen parts:")))
    assert f"-3 dB cutoff {PARASITIC_PREDICTION}" in lines[chosen + 2]
    # The ideal circuit's figures are never labelled.
    ideal = next(line for line in lines if line.startswith("Ideal values:"))
    assert lines[lines.index(ideal) + 1].strip().startswith("peak gain")
    payload = build_analysis_fields(outcome.result, analysis)
    assert payload["simulated"]["measurement"]["model"] == "ideal"
    assert "outside_qualified_range" not in payload["simulated"]["measurement"]
    nominal = payload["nominal_build"]["measurement"]
    assert nominal["model"] == "chosen_parts"
    assert nominal["outside_qualified_range"] == ["cutoff_hz"]
    assert payload["nominal_build"]["qualified_range_hz"] == [low, high]


def test_the_spread_row_says_which_values_lie_outside_the_range():
    lines = format_build_analysis_block(design(LP_BEYOND).build_analysis)

    cutoff = next(i for i, line in enumerate(lines) if line.startswith("  -3 dB cutoff:"))
    assert " ".join(line.strip() for line in lines[cutoff + 1 : cutoff + 3]) == (
        f"some cases outside the qualified range: {PARASITIC_PREDICTION}"
    )
    assert all(len(line) <= 96 for line in lines)


# 100 nH shunt chips at 100 MHz, 68.4 ohm, tested at 685 ohm ports with ±20% inductors: the
# chips are within their allowances only from 99.79 MHz, so the all-high case's highest
# gain (92.5 MHz on the whole sweep) lies below the qualified range.
HP_LOW_EDGE = DesignRequest(
    "highpass",
    "butterworth",
    "pi",
    100e6,
    68.416,
    3,
    realization=BuildConfig(
        grid_points=51,
        source_resistance_ohm=685.0,
        load_resistance_ohm=685.0,
        inductor_tolerance_pct=20.0,
    ),
    run_build_analysis=True,
)


def test_a_highpass_build_takes_its_peak_only_inside_the_qualified_range():
    analysis = design(HP_LOW_EDGE).build_analysis
    low, high = analysis.qualified_range_hz

    assert low == pytest.approx(99.7857e6, rel=1e-5)
    assert analysis.peak_range_hz == (low, analysis.passband_top_hz)
    for case in analysis.cases:
        measurement = case.measurement
        assert low <= measurement.reference_peak_frequency_hz <= high
        assert low <= measurement.peak_frequency_hz <= high
    # The all-high case's cutoff crossing is still found, below the range, and labelled.
    corner = next(case for case in analysis.cases if case.case_id == "coherent:high")
    assert corner.measurement.f_low < low
    assert corner.measurement.outside_range("highpass", (low, high)) == ("cutoff_hz",)


def test_every_reported_frequency_of_a_chosen_parts_result_is_classified():
    # bp bw top -f 400MHz -b 12MHz -n 3 --tank-inductance 91nH: chips qualified to 425.9 MHz,
    # and detuned cases whose figures reach past it. (An open end at the sweep's end is
    # checked in test_a_band_pass_center_and_bandwidth_follow_an_edge_outside_the_range.)
    bandwidth_hz = 12e6
    request = DesignRequest(
        "bandpass",
        "butterworth",
        "top",
        400e6,
        50.0,
        3,
        bandwidth_hz=bandwidth_hz,
        resonator_inductance=91e-9,
        realization=FAST,
        run_build_analysis=True,
    )
    outcome, analysis = _untrimmed_build(request)
    low, high = analysis.qualified_range_hz
    payload = build_analysis_fields(outcome.result, analysis)
    records = {
        item["case_id"]: item["measurement"] for item in payload["tolerance_analysis"]["cases"]
    }

    flagged = 0
    for case in analysis.cases:
        measurement = case.measurement
        first, last = measurement.sweep_hz
        spans = [
            (first if a is None else a, last if b is None else b)
            for a, b in measurement.threshold_regions
        ]
        beyond = any(not low <= a <= b <= high for a, b in spans)
        keys = measurement.outside_range("bandpass", (low, high))
        # Any range above -3 dB that leaves the qualified range is reported somewhere.
        assert bool(keys) >= beyond, case.case_id
        flagged += beyond
        assert records[case.case_id]["outside_qualified_range"] == list(keys)
        assert records[case.case_id]["peak_frequency_hz"] == measurement.peak_frequency_hz
    assert flagged


def test_a_band_pass_center_and_bandwidth_follow_an_edge_outside_the_range():
    from filter_lib.shared.build_types import CircuitMeasurement

    measurement = CircuitMeasurement(
        99e6,
        112e6,
        -0.1,
        False,
        reference_peak_frequency_hz=105e6,
        peak_frequency_hz=105e6,
        threshold_regions=((99e6, 112e6), (150e6, 160e6)),
        selected_region_index=0,
    )

    assert measurement.outside_range("bandpass", (0.0, 110e6)) == (
        "f_high_hz",
        "f0_hz",
        "bandwidth_hz",
        "half_power_regions",
    )
    assert measurement.outside_range("bandpass", (0.0, 200e6)) == ()
    assert measurement.outside_range("bandpass", None) == ()
    # A range left open at the sweep's end reaches it: here 440 MHz, past a 425 MHz top.
    open_ended = CircuitMeasurement(
        397e6,
        None,
        -60.0,
        True,
        reference_peak_frequency_hz=405e6,
        peak_frequency_hz=405e6,
        threshold_regions=((397e6, None),),
        selected_region_index=0,
        sweep_hz=(360e6, 440e6),
    )
    assert open_ended.outside_range("bandpass", (0.0, 425e6)) == ("open_half_power_region",)
    assert open_ended.outside_range("bandpass", (0.0, 450e6)) == ()


def test_each_spread_summary_says_whether_it_holds_a_value_outside_the_range():
    analysis = design(LP_BEYOND).build_analysis
    payload = build_analysis_fields(design(LP_BEYOND).result, analysis)

    flags = {
        item["metric"]: item["outside_qualified_range"]
        for item in payload["tolerance_analysis"]["metric_summaries"]
    }
    assert flags == {
        "peak_transducer_gain_db": False,
        "worst_passband_db": False,
        "cutoff_hz": True,
    }
    assert analysis.metrics_outside_qualified_range() == {"cutoff_hz"}


def test_the_highpass_note_and_range_print_the_same_top_and_the_peak_range_is_in_the_sweep():
    # hp bw pi 125MHz -n 3 -z 25: the chips are within their allowances to 694.279 MHz.
    request = DesignRequest(
        "highpass", "butterworth", "pi", 125e6, 25.0, 3, realization=FAST, run_build_analysis=True
    )
    analysis = design(request).build_analysis
    text = " ".join(" ".join(format_build_analysis_block(analysis)).split())

    assert analysis.passband_top_hz == pytest.approx(694.279e6, rel=1e-5)
    assert "up to 694.2 MHz, including both" in text
    assert "Qualified range: DC to 694.2 MHz" in text
    sweep_start = analysis.calculated.sweep_hz[0]
    assert analysis.peak_range_hz == (sweep_start, analysis.passband_top_hz)


def test_a_lossy_chip_build_says_its_range_is_the_lossless_model_s():
    lossy = DesignRequest(
        "lowpass",
        "chebyshev",
        "pi",
        400e6,
        200.0,
        5,
        ripple_db=0.5,
        realization=BuildConfig(grid_points=51, inductor_q=30.0),
        run_build_analysis=True,
    )
    lossless = " ".join(
        " ".join(format_build_analysis_block(design(LP_BEYOND).build_analysis)).split()
    )
    text = " ".join(" ".join(format_build_analysis_block(design(lossy).build_analysis)).split())

    phrase = "(in its lossless part model; the Q you gave is not part of this check)"
    assert phrase in text and phrase not in lossless


def test_ideal_results_stay_ideal_with_the_build_on_or_off(monkeypatch, capsys):
    argv = ("bp", "ch", "top", "-f", "146MHz", "-b", "4MHz", "-n", "3", "-r", "0.5")
    off = cli_stdout(monkeypatch, capsys, *argv)
    on = cli_stdout(monkeypatch, capsys, *argv, "--sim-build", "--analysis-points", "51")

    harmonics = [line for line in off.splitlines() if line.strip().startswith("Attenuation at")]
    assert harmonics and harmonics[0].endswith("(ideal lossless parts)")
    assert harmonics[0] in on.splitlines()
    assert PARASITIC_PREDICTION not in off
    # The response data are of the ideal circuit and never depend on the chosen parts.
    lowpass = ("lp", "ch", "pi", "146MHz", "-n", "5", "-r", "0.1", "--plot-data", "json")
    chips = cli_stdout(monkeypatch, capsys, *lowpass)
    calculated = cli_stdout(monkeypatch, capsys, *lowpass, "--inductor-suggestions", "none")
    assert chips == calculated
    assert "parasitic" not in json.dumps(json.loads(chips))


def test_the_table_section_names_the_qualified_range_of_each_chip(monkeypatch, capsys):
    text = cli_stdout(
        monkeypatch, capsys, "lp", "ch", "pi", "400MHz", "-n", "5", "-r", "0.5", "-z", "200"
    )

    assert "Within its allowances from DC to 425.9 MHz" in text


def test_a_detuned_band_pass_case_is_measured_from_its_true_peak():
    # bp bw top -f 400MHz -b 12MHz -n 3 --tank-inductance 91nH, Cp2 at its low end: the
    # response at 400 MHz is on a slope (-29.03 dB); the peak nearest the center is at
    # 387.675 MHz (-16.503 dB), and bisection on that circuit gives 384.436-391.361 MHz.
    request = DesignRequest(
        "bandpass",
        "butterworth",
        "top",
        400e6,
        50.0,
        3,
        bandwidth_hz=12e6,
        resonator_inductance=91e-9,
        realization=FAST,
        run_build_analysis=True,
    )
    _outcome, analysis = _untrimmed_build(request)
    case = next(case for case in analysis.cases if case.case_id == "one:CT2:low")
    measurement = case.measurement

    assert measurement.reference_peak_frequency_hz == pytest.approx(387.675e6, rel=1e-5)
    assert measurement.reference_peak_gain_db == pytest.approx(-16.503, abs=1e-3)
    assert measurement.f_low == pytest.approx(384.436e6, rel=1e-5)
    assert measurement.f_high == pytest.approx(391.361e6, rel=1e-5)


def test_a_narrow_band_pass_finds_its_peak_and_both_edges():
    # bp bw top -f 146.0187MHz -b 100Hz -n 3 --tank-inductance 91nH: the sweep's middle point
    # misses the exact center by 3.9e-7 Hz, more than a fraction of the 100 Hz bandwidth; a
    # fine sweep and bisection give one peak at 146,019,413.7 Hz (-63.867 dB) and edges at
    # 146,019,381.57 and 146,019,445.75 Hz.
    request = DesignRequest(
        "bandpass",
        "butterworth",
        "top",
        146.0187e6,
        50.0,
        3,
        bandwidth_hz=100.0,
        resonator_inductance=91e-9,
        realization=FAST,
        run_build_analysis=True,
    )
    measurement = _untrimmed_build(request)[1].nominal_build

    assert measurement.reference_peak_frequency_hz == pytest.approx(146_019_413.7, abs=0.5)
    assert measurement.reference_peak_gain_db == pytest.approx(-63.867, abs=1e-3)
    assert measurement.f_low == pytest.approx(146_019_381.57, abs=0.05)
    assert measurement.f_high == pytest.approx(146_019_445.75, abs=0.05)


def test_edges_measured_from_a_peak_outside_the_range_are_outside_too():
    from filter_lib.shared.build_types import CircuitMeasurement

    measurement = CircuitMeasurement(
        411e6,
        420e6,
        -1.0,
        False,
        reference_peak_frequency_hz=429e6,
        peak_frequency_hz=429e6,
        threshold_regions=((411e6, 420e6),),
        selected_region_index=0,
        sweep_hz=(380e6, 440e6),
    )

    assert measurement.outside_range("bandpass", (0.0, 425.9e6)) == (
        "f_low_hz",
        "f_high_hz",
        "f0_hz",
        "bandwidth_hz",
        "reference_peak_frequency_hz",
        "peak_frequency_hz",
    )
    # An open selected region: no center or bandwidth is reported, so none is flagged.
    open_ended = CircuitMeasurement(
        429e6,
        None,
        -1.0,
        True,
        reference_peak_frequency_hz=420e6,
        peak_frequency_hz=420e6,
        threshold_regions=((429e6, None),),
        selected_region_index=0,
        sweep_hz=(380e6, 440e6),
    )
    assert open_ended.outside_range("bandpass", (0.0, 425.9e6)) == (
        "f_low_hz",
        "open_half_power_region",
    )


def test_the_lossless_range_caveat_reaches_the_json_limitations():
    from filter_lib.shared.nominal_realization import CHIP_Q_LIMITATION

    lossy = DesignRequest(
        "lowpass",
        "chebyshev",
        "pi",
        400e6,
        200.0,
        5,
        ripple_db=0.5,
        realization=BuildConfig(grid_points=51, inductor_q=0.5),
        run_build_analysis=True,
    )
    outcome = design(lossy)
    payload = build_analysis_fields(outcome.result, outcome.build_analysis)

    assert "does not include that Q" in CHIP_Q_LIMITATION
    assert CHIP_Q_LIMITATION in payload["nominal_build"]["limitations"]


def test_a_dip_the_grid_missed_splits_the_range_and_is_not_converged():
    # bp ch top -f 400MHz -b 800kHz -n 5 -r 0.5 --tank-inductance 91nH, ports at 0.5 ohm: with
    # Cp2 low, an evaluation inside the one reported range was below its threshold; bisection
    # gives two ranges, 5.49 and 5.48 kHz wide.
    request = DesignRequest(
        "bandpass",
        "chebyshev",
        "top",
        400e6,
        50.0,
        5,
        ripple_db=0.5,
        bandwidth_hz=800e3,
        resonator_inductance=91e-9,
        realization=BuildConfig(source_resistance_ohm=0.5, load_resistance_ohm=0.5),
        run_build_analysis=True,
    )
    case = next(c for c in _untrimmed_build(request)[1].cases if c.case_id == "one:CT2:low")
    regions = case.measurement.threshold_regions

    assert len(regions) == 2
    assert [high - low for low, high in regions] == [
        pytest.approx(5.494e3, abs=5.0),
        pytest.approx(5.482e3, abs=5.0),
    ]


def test_a_band_of_microhertz_finds_both_peaks_around_its_dip():
    # bp bw top -f 146.0187MHz -b 0.0003Hz -n 2 --tank-inductance 91nH at 10 ohm ports: the
    # center is a dip (-8.3 dB) between two 0 dB peaks about 104 microhertz away.
    request = DesignRequest(
        "bandpass",
        "butterworth",
        "top",
        146.0187e6,
        50.0,
        2,
        bandwidth_hz=0.0003,
        resonator_inductance=91e-9,
        realization=BuildConfig(
            grid_points=51, source_resistance_ohm=10.0, load_resistance_ohm=10.0
        ),
        run_build_analysis=True,
    )
    ideal = design(request).build_analysis.calculated

    assert abs(ideal.reference_peak_frequency_hz - 146.0187e6) == pytest.approx(1.04e-4, abs=5e-6)
    assert ideal.reference_peak_gain_db == pytest.approx(0.0, abs=1e-3)
    assert len(ideal.threshold_regions) == 2
    assert all(
        high - low == pytest.approx(4.4e-5, abs=2e-6) for low, high in ideal.threshold_regions
    )


def test_every_range_measured_from_an_outside_peak_is_outside():
    from filter_lib.shared.build_types import CircuitMeasurement

    measurement = CircuitMeasurement(
        428e6,
        430.7e6,
        -30.0,
        False,
        reference_peak_frequency_hz=429.4e6,
        peak_frequency_hz=429.4e6,
        threshold_regions=((388.6e6, 388.7e6), (428e6, 430.7e6)),
        selected_region_index=1,
        sweep_hz=(380e6, 440e6),
    )

    assert "half_power_regions" in measurement.outside_range("bandpass", (0.0, 425.9e6))


def test_a_narrow_band_s_edges_print_apart(monkeypatch, capsys):
    text = cli_stdout(
        monkeypatch,
        capsys,
        "bp",
        "bw",
        "top",
        "-f",
        "146.0187MHz",
        "-b",
        "100Hz",
        "-n",
        "3",
        "--tank-inductance",
        "91nH",
        "--sim-build",
        "--analysis-points",
        "51",
    )

    # The tanks are tuned with trimmers, so the chosen parts' band is centred on 146.0187 MHz.
    chosen = next(line for line in text.splitlines() if line.startswith("Chosen parts:"))
    assert "edges 146.018650478 MHz / 146.018749522 MHz" in chosen
