"""A chip inductor's self-capacitance in the build simulation and the chosen-parts deck.

Each chip inductor is built as its ``L0`` with a fixed ``CSELF_`` capacitor across it,
which together give the catalog value at the test frequency. The same branches appear in
the chosen-parts SPICE deck, the tolerance cases never vary them, and the tolerance
corners are stress cases of that fixed branch: they leave the part's guaranteed envelope
(``docs/component-data-sources.md``, Coverage).
"""

from __future__ import annotations

import math

import pytest

from filter_lib.design import DesignRequest, design, export_spice
from filter_lib.shared.build_analysis import STRESS_CASE_LIMITATION
from filter_lib.shared.build_simulation import BuildConfig, analyze_build, realize_nominal_build
from filter_lib.shared.circuit_display_names import display_component_name
from filter_lib.shared.nominal_realization import SELF_CAPACITANCE_LIMITATION
from filter_lib.shared.tolerance_screening import perturb_circuit

FAST = BuildConfig(grid_points=51)
LP_440 = DesignRequest("lowpass", "chebyshev", "pi", 440e6, 50.0, 5, ripple_db=0.1)


def _spice_elements(deck: str) -> list[tuple[str, int, int, float]]:
    """``(name, node 1, node 2, value)`` of every part line of a deck."""
    rows = []
    for line in deck.splitlines():
        if not line or line.startswith(("*", ".")) or line.startswith(("VINPUT", "RSOURCE")):
            continue
        name, node1, node2, value = line.split()
        if name.startswith(("RLOAD", "RLOSS")):
            continue
        rows.append((name, int(node1), int(node2), float(value)))
    return rows


def _effective_inductance(l_h: float, c_f: float, frequency_hz: float) -> float:
    """The inductance an L in parallel with a C presents at ``frequency_hz``."""
    return l_h / (1 - (2 * math.pi * frequency_hz) ** 2 * l_h * c_f)


@pytest.mark.parametrize(
    "request_",
    [
        LP_440,
        DesignRequest(
            "bandpass", "chebyshev", "top", 146e6, 50.0, 3, ripple_db=0.5, bandwidth_hz=4e6
        ),
    ],
    ids=["lowpass", "bandpass"],
)
def test_the_deck_holds_the_solver_s_self_capacitance_branches(request_):
    outcome = design(request_)
    realization = realize_nominal_build(
        outcome.result, outcome.category, BuildConfig(), parts=outcome.parts
    )

    deck = _spice_elements(export_spice(outcome, "nominal_build"))

    elements = realization.circuit.elements
    assert [row[0] for row in deck] == [element.name for element in elements]
    for (_name, node1, node2, value), element in zip(deck, elements, strict=True):
        assert (node1, node2) == (element.node1, element.node2)
        assert value == pytest.approx(element.value, rel=1e-11, abs=0)
    inductors = [element for element in elements if element.kind == "L"]
    branches = {element.name: element for element in elements if element.name.startswith("CSELF_")}
    assert sorted(branches) == sorted(f"CSELF_{inductor.name}" for inductor in inductors)
    for inductor in inductors:
        branch = branches[f"CSELF_{inductor.name}"]
        pick = outcome.parts.inductor(inductor.name).build_pick
        assert branch.fixed and branch.tolerance is None
        assert (branch.node1, branch.node2) == (inductor.node1, inductor.node2)
        assert branch.value == pick.part_model.self_capacitance_f
        assert inductor.value == pick.part_model.l0_h
        # L0 with its self-capacitance gives the catalog value at the test frequency.
        part = pick.build.part
        assert _effective_inductance(
            inductor.value, branch.value, part.test_frequency_hz
        ) == pytest.approx(part.inductance_h, rel=1e-12)


def test_the_self_capacitance_is_named_and_explained_where_it_is_used():
    outcome = design(LP_440)

    deck = export_spice(outcome, "nominal_build")

    assert display_component_name("CSELF_LT2") == "L2 self-capacitance"
    assert "* part used: L1 chip inductor " in deck
    assert "self-capacitance=6.03" in deck
    assert "* self-capacitance: CSELF_L1 is this inductor's self-capacitance" in deck
    assert "each chip inductor's self-capacitance" in deck
    # The names comment lists parts only, never the fixed branches.
    assert "CSELF_" not in "".join(line for line in deck.splitlines() if "* names:" in line)


def test_the_tolerance_cases_never_vary_the_self_capacitance():
    outcome = design(LP_440)

    analysis = analyze_build(outcome.result, "lowpass", FAST, parts=outcome.parts)

    elements = analysis.nominal_realization.circuit.elements
    fixed = {element.name for element in elements if element.fixed}
    assert {"CSELF_L1", "CSELF_L2"} <= fixed
    for case in analysis.cases:
        assert not {name for name, _factor in case.component_factors} & fixed
    assert SELF_CAPACITANCE_LIMITATION in analysis.limitations
    assert STRESS_CASE_LIMITATION in analysis.limitations


def test_each_chip_inductor_s_cases_use_its_own_tolerance_unless_one_is_entered():
    outcome = design(LP_440)

    own = realize_nominal_build(outcome.result, "lowpass", FAST, parts=outcome.parts)
    entered = realize_nominal_build(
        outcome.result,
        "lowpass",
        BuildConfig(grid_points=51, inductor_tolerance_pct=7.0),
        parts=outcome.parts,
    )

    def tolerances(realization):
        return {e.name: e.tolerance for e in realization.circuit.elements if e.kind == "L"}

    assert tolerances(own) == {"L1": 0.02, "L2": 0.02}
    assert tolerances(entered) == {"L1": 0.07, "L2": 0.07}
    substitution = next(s for s in own.substitutions if s.logical_name == "L1")
    assert (substitution.tolerance_pct, substitution.own_tolerance) == (2.0, True)


def test_the_tolerance_corners_are_stress_cases_outside_the_guaranteed_envelope():
    # LQW15AN25NG80D (25 nH ±2% at 100 MHz, SRF min 4.1 GHz) at 440 MHz. With the
    # self-capacitance fixed from the nominal L0, each corner leaves the envelope the screen
    # qualifies: at the 100 MHz test frequency the envelope is exactly 24.5-25.5 nH; at the
    # 440 MHz top of the window its upper limit is 25.78176 nH.
    outcome = design(LP_440)
    circuit = realize_nominal_build(outcome.result, "lowpass", FAST, parts=outcome.parts).circuit
    model = outcome.parts.inductor("L1").build_pick.part_model
    branch = next(element for element in circuit.elements if element.name == "CSELF_L1")

    def corner(sign: float, frequency_hz: float) -> float:
        perturbed = perturb_circuit(circuit, (("L1", 1 + sign * 0.02),))
        inductor = next(element for element in perturbed.elements if element.name == "L1")
        return _effective_inductance(inductor.value, branch.value, frequency_hz)

    def envelope(frequency_hz: float) -> tuple[float, float]:
        drift = model.drift(frequency_hz)
        return 25e-9 * 0.98 * (1 + min(0, drift)), 25e-9 * 1.02 * (1 + max(0, drift))

    low_100, high_100 = envelope(100e6)
    assert (low_100, high_100) == (pytest.approx(24.5e-9, rel=1e-12), pytest.approx(25.5e-9))
    assert corner(-1, 100e6) == pytest.approx(24.499708e-9, rel=1e-7)
    assert corner(+1, 100e6) == pytest.approx(25.500304e-9, rel=1e-7)
    assert corner(-1, 100e6) < low_100 and corner(+1, 100e6) > high_100
    low_440, high_440 = envelope(440e6)
    assert high_440 == pytest.approx(25.78176e-9, rel=1e-6)
    assert corner(+1, 440e6) == pytest.approx(25.78777e-9, rel=1e-6)
    assert corner(+1, 440e6) > high_440
    # Above the test frequency the low corner's drift lifts it inside the envelope.
    assert low_440 <= corner(-1, 440e6) <= high_440


def test_a_calculated_or_toroid_inductor_has_no_self_capacitance_branch():
    outcome = design(DesignRequest("lowpass", "butterworth", "pi", 10e6, 50.0, 5))

    deck = export_spice(outcome, "nominal_build")

    assert "CSELF_" not in deck
    assert "self-capacitance" not in deck
