"""Accuracy regressions checked with independent two-port circuit arithmetic."""

import math
from dataclasses import replace

import pytest

from filter_lib.bandpass.bandpass_design import calculate_bandpass_filter
from filter_lib.bandpass.display import format_insertion_loss_line, format_validation_scope_lines
from filter_lib.bandpass.formatters import format_json
from filter_lib.bandpass.response_sweep import netlist_frequency_sweep
from filter_lib.shared import response_refinement
from filter_lib.shared.build_response import build_frequency_grid, measure_circuit
from filter_lib.shared.build_types import BuildConfig, CircuitMeasurement, ScreeningCase
from filter_lib.shared.circuit_builders import build_named_circuit
from filter_lib.shared.nominal_realization import realize_nominal_build
from filter_lib.shared.plot_threshold_analysis import find_db_thresholds, format_threshold_table
from filter_lib.shared.response_refinement import refine_crossing, refine_response
from filter_lib.shared.spice_export import export_spice_deck
from filter_lib.shared.tolerance_screening import perturb_circuit, summarize_cases


def _bp(bw=200e3, order=9, family="butterworth", **kwargs):
    return calculate_bandpass_filter(10e6, bw, 50, order, family, "top", **kwargs)


def _abcd_gain(circuit, frequency, rs=50, rl=50):
    """Cascade series/shunt two-ports, independently of nodal solver code."""
    omega = 2 * math.pi * frequency
    node, previous = circuit.in_node, None
    a, b, c, d = 1 + 0j, 0j, 0j, 1 + 0j

    def impedance(element):
        reactance = (
            1j * omega * element.value if element.kind == "L" else 1 / (1j * omega * element.value)
        )
        return element.series_resistance_ohm + reactance

    while True:
        y = sum(1 / impedance(e) for e in circuit.elements if {e.node1, e.node2} == {node, 0})
        a, c = a + b * y, c + d * y
        if node == circuit.out_node:
            break
        next_nodes = {
            e.node2 if e.node1 == node else e.node1
            for e in circuit.elements
            if node in (e.node1, e.node2) and 0 not in (e.node1, e.node2)
        } - {previous}
        assert len(next_nodes) == 1
        following = next_nodes.pop()
        series = [e for e in circuit.elements if {e.node1, e.node2} == {node, following}]
        z = 1 / sum(1 / impedance(e) for e in series)
        b, d = a * z + b, c * z + d
        previous, node = node, following
    gain = 4 * rs * rl / abs(a * rl + b + c * rs * rl + d * rs) ** 2
    return 10 * math.log10(gain)


def _independent_root(fn, left, right, threshold):
    start_above = fn(left) >= threshold
    assert start_above != (fn(right) >= threshold)
    for _ in range(50):
        mid = (left + right) / 2
        if (fn(mid) >= threshold) == start_above:
            left = mid
        else:
            right = mid
    return (left + right) / 2


@pytest.mark.parametrize("points", [51, 601, 5001])
def test_high_order_worst_gain_includes_exact_endpoints_and_refined_skirts(points):
    result = _bp()
    circuit = build_named_circuit(result, "bandpass")
    measured = measure_circuit(
        circuit, result, "bandpass", build_frequency_grid(result, "bandpass", points), 50, 50
    )
    endpoint = min(_abcd_gain(circuit, result[key]) for key in ("f_low", "f_high"))
    assert measured.measurement_converged
    assert measured.worst_passband_db == pytest.approx(endpoint, abs=0.001)
    assert endpoint == pytest.approx(-3.0033913198, abs=1e-6)
    for edge in (measured.f_low, measured.f_high):
        assert _abcd_gain(circuit, edge) == pytest.approx(measured.threshold_db, abs=0.001)

    def response(frequency):
        return _abcd_gain(circuit, frequency)

    low = _independent_root(response, 9.8e6, 10e6, measured.threshold_db)
    high = _independent_root(response, 10e6, 10.2e6, measured.threshold_db)
    assert measured.bw == pytest.approx(high - low, abs=0.04)


def test_perturbed_high_order_filter_reports_separate_regions_and_local_reference():
    result = _bp()
    nominal = realize_nominal_build(result, "bandpass", BuildConfig()).circuit
    perturbed = perturb_circuit(
        nominal, tuple((e.name, 0.9 if e.name == "LT1" else 1.0) for e in nominal.elements)
    )
    measured = measure_circuit(
        perturbed, result, "bandpass", build_frequency_grid(result, "bandpass", 51), 50, 50
    )
    assert measured.measurement_converged
    assert len(measured.threshold_regions) == 2
    assert measured.selected_region_index == 1
    assert measured.center_in_selected_region is False
    assert measured.reference_peak_gain_db < measured.peak_transducer_gain_db - 0.1
    assert measured.threshold_regions[0][1] < measured.threshold_regions[1][0]
    for edge in (measured.f_low, measured.f_high):
        assert _abcd_gain(perturbed, edge) == pytest.approx(measured.threshold_db, abs=0.001)
    assert measured.worst_passband_db < -69


@pytest.mark.parametrize("family,order", [("chebyshev", 5), ("bessel", 4)])
def test_lossy_unequal_port_measurements_agree_with_independent_circuit(family, order):
    result = _bp(bw=500e3, order=order, family=family)
    circuit = realize_nominal_build(
        result,
        "bandpass",
        BuildConfig(inductor_q=100, capacitor_q=500, use_toroid_candidates=False),
    ).circuit
    measured = measure_circuit(
        circuit, result, "bandpass", build_frequency_grid(result, "bandpass", 51), 25, 100
    )
    assert measured.measurement_converged
    for edge in (measured.f_low, measured.f_high):
        assert _abcd_gain(circuit, edge, 25, 100) == pytest.approx(measured.threshold_db, abs=0.001)
    dense = [
        _abcd_gain(circuit, result["f_low"] + result["bw"] * i / 2000, 25, 100) for i in range(2001)
    ]
    assert measured.worst_passband_db == pytest.approx(min(dense), abs=0.001)


def test_refinement_resolves_interior_dip_and_reports_budget_exhaustion():
    def response(f):
        return -(((f - 10) / 3) ** 2) - 4 * math.exp(-(((f - 10.4) / 0.2) ** 2))

    grid = [1 + i / 10 for i in range(181)]
    resolved = refine_response(response, grid, (9, 11), reference_frequency=10, frequency_scale=2)
    assert resolved.converged
    assert resolved.worst_db < -4
    assert len(resolved.regions) == 2
    exhausted = refine_response(response, grid, (9, 11), frequency_scale=2, max_passes=1)
    assert not exhausted.converged


def test_refinement_keeps_meshing_while_worst_passband_gain_changes():
    """A 1 dB dip between initial grid points changes the worst gain on the second mesh."""

    def response(f):
        return -math.exp(-(((f - 2.5) / 0.05) ** 2))

    two_meshes = refine_response(response, [1, 2, 3, 4, 5], (1, 5), frequency_scale=4, max_passes=2)
    three_meshes = refine_response(response, [1, 2, 3, 4, 5], (1, 5), frequency_scale=4)

    assert not two_meshes.converged
    assert three_meshes.converged
    assert three_meshes.worst_db == pytest.approx(-1.0, rel=1e-12, abs=0)


@pytest.mark.parametrize(
    ("edge_shift_fraction", "agrees"), [(0.9e-5, True), (1.1e-5, False)], ids=["inside", "outside"]
)
def test_successive_meshes_agree_only_within_the_band_edge_tolerance(edge_shift_fraction, agrees):
    """Band edges must match to 1e-5 of the frequency scale before refinement stops."""
    scale = 4.0
    previous = refine_response(
        lambda f: -((f - 3) ** 2), [1, 2, 3, 4, 5], (2, 4), frequency_scale=scale
    )
    low, high = previous.regions[0]
    current = replace(previous, regions=((low, high + edge_shift_fraction * scale),))

    assert response_refinement._agrees(previous, current, scale) is agrees


def test_screening_summaries_omit_unresolved_measurements():
    good = CircuitMeasurement(9, 11, -3, False, 0)
    cases = (
        ScreeningCase("good", (), good),
        ScreeningCase(
            "unresolved", (), replace(good, measurement_converged=False, worst_passband_db=-100)
        ),
    )
    summaries = summarize_cases(cases, "bandpass")
    assert all(
        s.included_cases == 1 and s.omitted_cases == 1 and s.unresolved_cases == 1
        for s in summaries
    )
    assert next(s for s in summaries if s.metric == "worst_passband_db").minimum == -3


@pytest.mark.parametrize("points", [600, 601])
def test_narrow_band_plot_includes_landmarks_and_evaluated_literal_three_db(points):
    result = _bp(bw=10e3, order=3)
    circuit = build_named_circuit(result, "bandpass")
    sweep = netlist_frequency_sweep(result, points=points)
    freqs, values = map(list, zip(*sweep))
    assert len(sweep) == points
    assert all(result[key] in freqs for key in ("f0", "f_low", "f_high"))

    def response(f):
        return _abcd_gain(circuit, f)

    refined = refine_response(
        response,
        freqs,
        (result["f_low"], result["f_high"]),
        reference_frequency=result["f0"],
        frequency_scale=result["bw"],
        drop_db=3,
    )
    thresholds = find_db_thresholds(
        list(refined.frequencies),
        list(refined.response_db),
        filter_type="bandpass",
        reference_frequency=result["f0"],
        relative_to_peak=True,
        response_fn=response,
        frequency_tolerance_hz=0.001,
    )
    low, high = thresholds[-3]
    expected_low = _independent_root(response, 9.99e6, 10e6, refined.reference_db - 3)
    expected_high = _independent_root(response, 10e6, 10.01e6, refined.reference_db - 3)
    assert high - low == pytest.approx(expected_high - expected_low, abs=0.002)
    assert high - low == pytest.approx(10e3, rel=0.002)
    text = format_threshold_table(thresholds, "bandpass")
    assert f"{low:.9g} Hz" in text and f"{high:.9g} Hz" in text


@pytest.mark.parametrize(
    "bw,order,family",
    [
        (10e3, 3, "butterworth"),
        (50e3, 3, "butterworth"),
        (350e3, 3, "butterworth"),
        (200e3, 9, "chebyshev"),
    ],
)
def test_exported_spice_grid_resolves_passband_and_peak(bw, order, family):
    result = _bp(bw=bw, order=order, family=family)
    circuit = build_named_circuit(result, "bandpass")
    deck = export_spice_deck(result, "bandpass")
    _, kind, count, start, stop = next(
        line for line in deck.splitlines() if line.startswith(".ac ")
    ).split()
    assert kind == "lin"
    count, start, stop = int(count), float(start), float(stop)
    assert count < 25000
    frequencies = [start + (stop - start) * i / (count - 1) for i in range(count)]
    in_band = [f for f in frequencies if result["f_low"] <= f <= result["f_high"]]
    assert len(in_band) >= 128 * order - 1
    assert max(_abcd_gain(circuit, f) for f in in_band) > -0.001
    assert (stop - start) / (count - 1) < bw / (100 * order)


def test_harmonic_response_exposes_actual_top_c_rejection_without_changing_gate():
    result = _bp(bw=1e6, order=3)
    assert result["response_validation_status"] == "validated"
    assert result["synthesis_validation"]["far_stopband_validated"] is False
    sample = result["harmonic_response"]["samples"][0]
    assert sample["transducer_gain_db"] == pytest.approx(-47.65952875, abs=1e-6)
    assert "no rejection mask" in "\n".join(format_validation_scope_lines(result))
    assert '"harmonic_response"' in format_json(result, include_toroids=False)


@pytest.mark.parametrize(
    "bw,loss,status",
    [(250e3, 6.791953, "agrees_at_center"), (10e3, 61.733011, "poor_approximation_at_center")],
)
def test_cohn_estimate_is_compared_with_finite_q_center_loss(bw, loss, status):
    result = _bp(bw=bw, order=3, qu=100)
    check = result["loss_estimate_validation"]["comparisons"]["100"]
    assert check["status"] == status
    assert -check["lossy_center_gain_db"] == pytest.approx(loss, abs=0.001)
    assert check["estimate_minus_circuit_db"] == pytest.approx(
        result["il_estimates"]["100"] - check["circuit_added_center_loss_db"]
    )
    assert "small-loss approximation" in format_insertion_loss_line(result)


@pytest.mark.parametrize(
    "options",
    [
        {"max_passes": 0},
        {"max_passes": 5},
        {"max_passes": True},
        {"frequency_scale": 0},
        {"frequency_scale": math.inf},
        {"drop_db": 0},
        {"drop_db": math.nan},
        {"reference_frequency": -1},
    ],
)
def test_refinement_rejects_invalid_accuracy_controls(options):
    with pytest.raises(ValueError):
        refine_response(lambda f: -f, [1, 2, 3], (1, 2), **({"frequency_scale": 1} | options))


@pytest.mark.parametrize(
    "grid,band", [([1, 1, 2], (1, 2)), ([1], (1, 2)), ([0, 1], (1, 2)), ([1, 2], (2, 1))]
)
def test_refinement_rejects_invalid_frequency_domains(grid, band):
    with pytest.raises(ValueError):
        refine_response(lambda f: -f, grid, band, frequency_scale=1)


def test_crossing_equality_invalid_brackets_and_nonfinite_responses():
    assert refine_crossing(lambda f: -f, 1, 2, -1, 1e-6) == 1
    assert refine_crossing(lambda f: -f, 1, 2, -2, 1e-6) == 2
    with pytest.raises(ValueError, match="bracket"):
        refine_crossing(lambda f: -f, 1, 2, -3, 1e-6)
    with pytest.raises(ValueError, match="finite and ordered"):
        refine_crossing(lambda f: -f, 2, 1, -1.5, 1e-6)
    with pytest.raises(ValueError, match="finite and ordered"):
        refine_crossing(lambda f: -f, 1, 2, -1.5, 0)
    with pytest.raises(ValueError, match="finite"):
        refine_crossing(lambda f: math.nan, 1, 2, -1, 1e-6)
    with pytest.raises(ValueError, match="crossing response must be finite"):
        refine_crossing(lambda f: -f if f in (1, 2) else math.nan, 1, 2, -1.5, 1e-6)
    with pytest.raises(ValueError, match="finite"):
        refine_response(lambda f: math.inf, [1, 2], (1, 2), frequency_scale=1)


def test_censored_lowpass_skirt_remains_missing_after_refinement():
    refined = refine_response(lambda f: -0.01 * f, [1, 2, 3], (1, 2), frequency_scale=1)
    assert refined.converged
    assert refined.regions == ((None, None),)


def test_precise_user_q_does_not_collide_with_standard_loss_example():
    result = _bp(bw=500e3, order=3, qu=100.00001)
    assert set(result["il_estimates"]) == {"100", "250", "100.00001"}
    checks = result["loss_estimate_validation"]["comparisons"]
    assert checks["100"]["resonator_qu"] == 100
    assert checks["100.00001"]["resonator_qu"] == 100.00001
    assert result["il_estimates"]["100"] > result["il_estimates"]["100.00001"]


def test_horizontal_bandpass_detail_samples_a_smaller_window_and_center():
    from filter_lib.bandpass.ideal_response import magnitude_db
    from filter_lib.shared.plot_zoom_pairs import render_bandpass_plot_pair

    result = _bp(bw=10e3, order=3)
    sweep = netlist_frequency_sweep(result, points=61)
    sampled = []

    def response(f):
        sampled.append(f)
        return magnitude_db(f, result["f0"], result["bw"], 3, "butterworth")

    plot = render_bandpass_plot_pair(sweep, result["f0"], result["bw"], response_fn=response)
    assert "Passband Detail" in plot
    assert len(sampled) == 2 * len(sweep)
    assert result["f0"] in sampled
    assert max(sampled) - min(sampled) == pytest.approx(2 * result["bw"], rel=1e-8)
    assert min(sampled) > sweep[0][0] and max(sampled) < sweep[-1][0]


def test_sub_hertz_threshold_labels_remain_distinct_and_table_stays_rectangular():
    table = format_threshold_table({-3: [9999999.9995, 10000000.0005]}, "bandpass")
    row = next(line for line in table.splitlines() if "-3 dB" in line)
    _, _, low, high, _ = row.split("│")
    assert low.strip() != high.strip()
    assert float(low.split()[0]) == pytest.approx(9999999.9995, abs=1e-8, rel=0)
    assert float(high.split()[0]) == pytest.approx(10000000.0005, abs=1e-8, rel=0)
    assert (
        len({len(line) for line in table.splitlines() if line.startswith(("│", "┌", "├", "└"))})
        == 1
    )


@pytest.mark.parametrize("tolerance", [0, -1, math.inf, math.nan, True])
def test_threshold_evaluation_rejects_invalid_accuracy_tolerance(tolerance):
    with pytest.raises(ValueError, match="frequency_tolerance_hz"):
        find_db_thresholds(
            [1, 2], [0, -6], response_fn=lambda f: 6 - 6 * f, frequency_tolerance_hz=tolerance
        )
