"""The assumed stray across a parallel pair, in the build simulation and SPICE.

It is one fixed capacitor across the pair's terminals, named with a ``C`` prefix so a SPICE
reader sees a capacitor. The tolerance cases never vary it, so adding it changes neither
the case list nor the seeded draws of the real parts.
"""

from __future__ import annotations

import pytest

from filter_lib.bandpass import calculate_bandpass_filter
from filter_lib.design import DesignRequest, design, export_spice
from filter_lib.shared.build_simulation import BuildConfig, analyze_build, realize_nominal_build
from filter_lib.shared.eseries import MatchPolicy

FAST = BuildConfig(grid_points=51, sample_count=4, seed=11, use_toroid_candidates=False)


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


@pytest.mark.parametrize(
    "request_fields",
    [
        {"category": "lowpass", "topology": "pi", "frequency_hz": 146e6, "order": 5},
        {
            "category": "bandpass",
            "topology": "top",
            "frequency_hz": 14.2e6,
            "bandwidth_hz": 350e3,
            "order": 3,
        },
    ],
    ids=["lowpass", "bandpass"],
)
def test_spice_deck_holds_the_solver_branches_with_their_kinds(request_fields):
    outcome = design(DesignRequest(filter_type="butterworth", impedance=50.0, **request_fields))
    realization = realize_nominal_build(
        outcome.result, outcome.category, BuildConfig(), eseries="E24", policy=outcome.match_policy
    )

    deck = _spice_elements(export_spice(outcome, "nominal_build"))

    elements = realization.circuit.elements
    assert [row[0] for row in deck] == [element.name for element in elements]
    for (name, node1, node2, value), element in zip(deck, elements, strict=True):
        # SPICE reads an element's kind from its first letter.
        assert name[0] == element.kind
        assert (node1, node2) == (element.node1, element.node2)
        assert value == pytest.approx(element.value, rel=1e-11)
    strays = [element for element in elements if element.fixed]
    assert strays and all(element.name.startswith("CSTRAY_") for element in strays)
    assert all(element.value == pytest.approx(0.2e-12, rel=1e-12, abs=0) for element in strays)


def test_tolerance_cases_leave_the_stray_unchanged_and_vary_only_real_parts():
    result = calculate_bandpass_filter(14.2e6, 350e3, 50, 3, "butterworth", "top")

    analysis = analyze_build(result, "bandpass", FAST)

    strays = {e.name for e in analysis.nominal_realization.circuit.elements if e.fixed}
    parts = {e.name for e in analysis.nominal_realization.circuit.elements if not e.fixed}
    assert strays
    for case in analysis.cases:
        varied = {name for name, _factor in case.component_factors}
        assert varied == parts
        assert not varied & strays


def test_adding_the_stray_moves_no_case_or_seeded_draw_of_the_real_parts():
    result = calculate_bandpass_filter(14.2e6, 350e3, 50, 3, "butterworth", "top")

    with_stray = analyze_build(result, "bandpass", FAST)
    without = analyze_build(result, "bandpass", FAST, policy=MatchPolicy(stray_capacitance_f=0))

    assert not any(e.fixed for e in without.nominal_realization.circuit.elements)
    assert [case.case_id for case in with_stray.cases] == [case.case_id for case in without.cases]
    assert [case.component_factors for case in with_stray.cases] == [
        case.component_factors for case in without.cases
    ]


def test_a_zero_stray_adds_no_element():
    outcome = design(
        DesignRequest("lowpass", "butterworth", "pi", 146e6, 50.0, 5, stray_capacitance_f=0.0)
    )

    deck = export_spice(outcome, "nominal_build")

    assert "CSTRAY_" not in deck
    assert "C1A " in deck  # 13.47 pF is still a pair


def test_a_fixed_element_keeps_its_value_even_when_a_factor_names_it():
    from filter_lib.shared.tolerance_screening import perturb_circuit

    result = calculate_bandpass_filter(14.2e6, 350e3, 50, 3, "butterworth", "top")
    circuit = realize_nominal_build(result, "bandpass", FAST).circuit
    stray = next(element for element in circuit.elements if element.fixed)

    perturbed = perturb_circuit(circuit, ((stray.name, 2.0),))

    assert next(e for e in perturbed.elements if e.name == stray.name).value == stray.value
