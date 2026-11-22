"""Setting each band-pass tank's trimmer, in the build and the chosen-parts SPICE deck.

The nominal build sets every trimmer so that its tank node's susceptance (with every built
branch, its Q and the ports) equals the calculated design's at the tank frequency. Each
tolerance case keeps the response with the trimmers at those settings (untuned) and the
response after retuning them within their range (tuned).
"""

from __future__ import annotations

import json
import math

import pytest

from filter_lib.design import DesignRequest, design, export_spice
from filter_lib.shared import tolerance_screening
from filter_lib.shared.build_output_payloads import build_analysis_fields
from filter_lib.shared.build_types import BuildConfig
from filter_lib.shared.circuit_model import CircuitElement, NamedCircuit
from filter_lib.shared.tank_susceptance import node_susceptance
from filter_lib.shared.tank_tuning import TrimmerPlan, TuningPlan, tune
from tests.cli_parity_helpers import cli_stdout

FAST = BuildConfig(grid_points=51)


def _two_metre(**overrides) -> DesignRequest:
    values = dict(ripple_db=0.5, bandwidth_hz=4e6, run_build_analysis=True, realization=FAST)
    values.update(overrides)
    return DesignRequest("bandpass", "chebyshev", "top", 146e6, 50.0, 3, **values)


def _residuals(analysis) -> list[float]:
    """Each tank node's susceptance less the calculated design's, in pF equivalent."""
    realization = analysis.nominal_realization
    tuning = realization.tuning
    residuals = []
    for plan in tuning.trimmers:
        built = node_susceptance(
            realization.circuit, plan.node, plan.frequency_hz, tuning.tank_nodes, tuning.ports
        )
        omega = 2 * math.pi * plan.frequency_hz
        residuals.append((built - plan.target_susceptance_s) / omega)
    return residuals


# The design's own resonator Q (--ql, --qc), which the sizing and the build both apply.
LOSSES = [{}, {"ql": 1.0}, {"qc": 20.0}]
LOSS_IDS = ["lossless", "resonator-inductor-q-1", "resonator-capacitor-q-20"]


@pytest.mark.parametrize("losses", LOSSES, ids=LOSS_IDS)
def test_the_nominal_trimmers_restore_every_tank_s_susceptance(losses):
    analysis = design(_two_metre(resonator_inductance=21e-9, **losses)).build_analysis

    assert analysis.has_trimmers
    assert all(setting.in_range for setting in analysis.nominal_realization.trimmer_settings)
    assert all(abs(value) < 1e-17 for value in _residuals(analysis)), _residuals(analysis)


def _deck_susceptance(deck: str, node: str, frequency_hz: float, tank_nodes) -> float:
    """A tank node's susceptance from the deck's own lines: every other tank node shorted,
    the source shorted (so each port is its resistance to ground), and every other node
    eliminated (Schur complement)."""
    omega = 2 * math.pi * frequency_hz
    branches = []
    for line in deck.splitlines():
        if not line or line.startswith(("*", ".", "VINPUT")):
            continue
        name, first, second, value = line.split()
        value = float(value)
        first = "0" if first == "NSOURCE" else first
        if name[0] == "R":
            admittance = 1 / value
        elif name[0] == "L":
            admittance = 1 / (1j * omega * value)
        else:
            admittance = 1j * omega * value
        branches.append((first, second, admittance))
    grounded = ({str(item) for item in tank_nodes} - {node}) | {"0"}
    nodes = [node]
    for current in nodes:
        for first, second, _admittance in branches:
            for here, there in ((first, second), (second, first)):
                if here == current and there not in nodes and there not in grounded:
                    nodes.append(there)
    index = {name: position for position, name in enumerate(nodes)}
    size = len(nodes)
    matrix = [[0j] * size for _ in range(size)]
    for first, second, admittance in branches:
        for end in (first, second):
            if end in index:
                matrix[index[end]][index[end]] += admittance
        if first in index and second in index:
            matrix[index[first]][index[second]] -= admittance
            matrix[index[second]][index[first]] -= admittance
    for pivot in range(size - 1, 0, -1):
        for row in range(pivot):
            factor = matrix[row][pivot] / matrix[pivot][pivot]
            for column in range(pivot):
                matrix[row][column] -= factor * matrix[pivot][column]
    return matrix[0][0].imag


@pytest.mark.parametrize("losses", LOSSES[:2], ids=LOSS_IDS[:2])
def test_the_deck_holds_the_tuned_settings(losses):
    outcome = design(_two_metre(resonator_inductance=21e-9, **losses))
    tuning = outcome.build_analysis.nominal_realization.tuning
    deck = export_spice(outcome, "nominal_build")

    for plan in tuning.trimmers:
        built = _deck_susceptance(deck, str(plan.node), plan.frequency_hz, tuning.tank_nodes)
        omega = 2 * math.pi * plan.frequency_hz
        # The deck prints 12 significant digits, so the residual is a rounding residue.
        assert abs(built - plan.target_susceptance_s) / omega < 1e-19, plan.tank


def test_every_case_has_its_settings_and_both_responses():
    config = BuildConfig(grid_points=51, sample_count=2, seed=7)
    outcome = design(_two_metre(realization=config))
    analysis = outcome.build_analysis
    tanks = {plan.tank for plan in analysis.nominal_realization.tuning.trimmers}

    assert {case.case_id for case in analysis.cases} >= {"nominal", "sample:0001", "sample:0002"}
    for case in analysis.cases:
        assert case.tuning is not None, case.case_id
        assert {setting.tank for setting in case.tuning.settings} == tanks
        assert all(isinstance(setting.in_range, bool) for setting in case.tuning.settings)
        assert case.tuning.measurement is not None and case.measurement is not None
    nominal = analysis.cases[0]
    assert nominal.tuning.measurement == nominal.measurement == analysis.nominal_build
    assert nominal.tuning.settings == analysis.nominal_realization.trimmer_settings
    # Retuning moves a detuned case's band back to the center; untuned it stays off.
    off = next(case for case in analysis.cases if case.case_id == "coherent:low")
    assert abs(off.tuning.measurement.f0 - 146e6) < abs(off.measurement.f0 - 146e6)
    assert analysis.tuned_metric_summaries

    payload = build_analysis_fields(outcome.result, analysis)
    cases = payload["tolerance_analysis"]["cases"]
    assert all(case["tuning"]["measurement"]["model"] == "chosen_parts" for case in cases)
    sample = next(case for case in cases if case["case_id"] == "sample:0001")
    assert len(sample["tuning"]["settings"]) == len(tanks)
    assert payload["tolerance_analysis"]["trimmers_retuned_in_each_case"] is True


def test_a_build_without_trimmers_has_no_tuning():
    analysis = design(
        DesignRequest(
            "bandpass",
            "butterworth",
            "top",
            7.1e6,
            50.0,
            3,
            bandwidth_hz=200e3,
            run_build_analysis=True,
            realization=FAST,
        )
    ).build_analysis

    assert not analysis.has_trimmers
    assert all(case.tuning is None for case in analysis.cases)
    assert analysis.tuned_metric_summaries == ()


def test_a_setting_out_of_reach_stays_at_the_range_end_and_is_flagged():
    # One tank: 10 pF at node 1, a 3-10 pF trimmer, and a target that needs 20 pF more.
    circuit = NamedCircuit(
        "bandpass",
        1,
        (
            CircuitElement("CT1", 1, 0, "C", 10e-12, logical_name="CT1"),
            CircuitElement("CTRIM_CT1", 1, 0, "C", 3e-12, fixed=True, series_inductance_h=1e-9),
            CircuitElement("LT1", 1, 0, "L", 100e-9, logical_name="LT1"),
        ),
        1,
        1,
    )
    frequency = 30e6
    omega = 2 * math.pi * frequency

    def plan(target_extra_f: float) -> TuningPlan:
        trimmer = TrimmerPlan(
            tank="CT1",
            node=1,
            trimmer_element="CTRIM_CT1",
            series_inductance_h=1e-9,
            knob_f=(3e-12, 10e-12),
            range_f=(3e-12, 10e-12),
            frequency_hz=frequency,
            target_susceptance_s=omega * (10e-12 + target_extra_f) - 1 / (omega * 100e-9),
            q=None,
            reference_hz=frequency,
        )
        return TuningPlan((trimmer,), (1,), {1: 50.0})

    high = tune(circuit, plan(20e-12))[1][0]
    low = tune(circuit, plan(1e-12))[1][0]
    reached = tune(circuit, plan(5e-12))[1][0]

    assert not high.in_range and high.setting_f == 10e-12
    assert high.required_f == pytest.approx(20e-12, rel=1e-9)
    assert not low.in_range and low.setting_f == 3e-12
    assert reached.in_range and reached.effective_f == pytest.approx(5e-12, rel=1e-12)


def test_the_table_and_json_report_the_same_tuning(monkeypatch, capsys):
    argv = ("bp", "ch", "top", "-f", "146MHz", "-b", "4MHz", "-n", "3", "-r", "0.5", "--sim-build")
    table = " ".join(cli_stdout(monkeypatch, capsys, *argv, "--analysis-points", "51").split())
    data = json.loads(
        cli_stdout(monkeypatch, capsys, *argv, "--analysis-points", "51", "--format", "json")
    )
    analysis = data["tolerance_analysis"]
    substitutions = {item["logical_name"]: item for item in data["nominal_build"]["substitutions"]}

    assert analysis["trimmer_out_of_range_cases"] == 0
    assert "every trimmer reached its setting in every case" in table
    assert "Spread after retuning the trimmers in each case:" in table
    cp1 = substitutions["CT1"]
    assert cp1["method"] == "fixed_plus_trimmer"
    nominal = cp1["trimmer"]["nominal_setting"]
    knob, effective = nominal["setting_f"] * 1e12, nominal["effective_capacitance_f"] * 1e12
    assert (
        f"trimmer BFC280820508 set to {knob:.2f} pF ({effective:.2f} pF effective at 145.974 MHz)"
    ) in table
    assert cp1["trimmer"]["series_inductance_basis"] == "bound_from_minimum_srf"


def test_a_cancel_between_a_case_s_two_measurements_returns_no_partial_case(monkeypatch):
    from filter_lib.design import DesignCancelled

    outcome = design(_two_metre(run_build_analysis=False))
    measured: list[object] = []
    real = tolerance_screening.measure_circuit

    def measure_then_cancel(*args, **kwargs):
        measured.append(args[0])
        return real(*args, **kwargs)

    monkeypatch.setattr(tolerance_screening, "measure_circuit", measure_then_cancel)
    # Cancel once the nominal case and the next case's untuned response are measured.
    with pytest.raises(DesignCancelled):
        from filter_lib.shared.build_simulation import analyze_build

        analyze_build(
            outcome.result,
            "bandpass",
            FAST,
            parts=outcome.parts,
            should_cancel=lambda: len(measured) >= 2,
        )
    assert len(measured) == 2


def test_a_build_inductor_q_the_sizing_did_not_see_is_flagged_where_it_cannot_be_tuned():
    # The split is sized for the lossless design; a build inductor Q of 1 halves the
    # inductor's susceptance, which no trimmer of that split can make up.
    config = BuildConfig(grid_points=51, inductor_q=1.0)
    analysis = design(_two_metre(resonator_inductance=21e-9, realization=config)).build_analysis

    assert not any(setting.in_range for setting in analysis.nominal_realization.trimmer_settings)
    assert analysis.out_of_range_cases() == len(analysis.cases)


def test_a_knob_that_reaches_its_series_resonance_is_tuned_on_its_capacitive_side():
    # BFC280831229 (3-22.5 pF, up to 28.08 nH) at 440 MHz passes its series resonance at
    # about 4.65 pF of knob; the 12.515 pF it must supply is at 3.3907 pF of knob, below it.
    from filter_lib.shared.tank_trimmers import (
        TankNeed,
        TankParts,
        TankSplit,
        series_inductance,
        trimmer_range_f,
    )
    from filter_lib.shared.tank_tuning import plan_trimmer
    from filter_lib.shared.trimmer_data import trimmer_parts

    trimmer = next(part for part in trimmer_parts() if part.part_name == "BFC280831229")
    inductance, _assumed = series_inductance(trimmer)
    frequency = 439.906e6
    omega = 2 * math.pi * frequency
    required = 12.51507e-12
    split = TankSplit(
        trimmer=trimmer,
        fixed_parts_f=(),
        fixed_tolerances_f=(),
        stray_f=0.0,
        series_inductance_h=inductance,
        series_inductance_assumed=False,
        trimmer_range_f=trimmer_range_f(trimmer, inductance, frequency, None, frequency),
        required_f=(required, required),
        centring_f=0.0,
    )
    tank = TankParts(
        name="CT1",
        node=1,
        tuning_frequency_hz=frequency,
        target_susceptance_s=omega * required,
        need=TankNeed(required, required),
        ports_ohm=(50.0, 50.0),
        splits=(split,),
    )
    element = CircuitElement("CT1", 1, 0, "C", required, logical_name="CT1")
    plan = plan_trimmer(tank, element, None, frequency)
    circuit = NamedCircuit(
        "bandpass",
        1,
        (
            CircuitElement(
                "CTRIM_CT1", 1, 0, "C", 3e-12, fixed=True, series_inductance_h=inductance
            ),
        ),
        1,
        1,
    )
    [setting] = tune(circuit, TuningPlan((plan,), (1,), {}))[1]

    resonance = 1 / (omega**2 * inductance)
    expected = required / (1 + omega**2 * inductance * required)
    assert resonance * 1e12 == pytest.approx(4.6508, abs=1e-3)
    assert setting.in_range
    assert setting.setting_f == pytest.approx(expected, rel=1e-12)
    assert setting.setting_f * 1e12 == pytest.approx(3.39072, abs=1e-5)
