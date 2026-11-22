"""Every chosen part is resolved once, in ``design()``, and every output reads it.

Covers the suggestion record and its kind order, which part "best" shows and the build
uses, the reasons a kind has no part, the capacitor choices, cancellation of synthesis and
part resolution, and that no module outside ``filter_lib/design`` selects a part.
"""

from __future__ import annotations

import ast
import dataclasses
from pathlib import Path

import pytest

from filter_lib.design import DesignCancelled, DesignRequest, design, synthesize
from filter_lib.design.part_resolution import (
    NO_SUGGESTION_NOTE,
    SUGGESTIONS_NOT_USED_NOTE,
    resolve_parts,
    resolve_parts_for,
)
from filter_lib.shared.build_types import BuildAnalysisCancelled
from filter_lib.shared.chip_selection import no_qualifying_chip_reason
from filter_lib.shared.eseries import MatchPolicy, match_component
from filter_lib.shared.inductor_suggestion import (
    AIR_COIL_EXCLUSION,
    FORCED_KIND_NEEDS_SUGGESTIONS_MESSAGE,
    INDUCTOR_KINDS,
    MAX_SUGGESTIONS_PER_KIND,
    NO_QUALIFYING_SUGGESTION,
    SRF_NOT_CHECKED,
    SUGGESTIONS_NOT_USED,
    VHF_TOROID_EXCLUSION,
    ErrorBudget,
    InductorSuggestion,
    KindSuggestions,
)
from filter_lib.shared.srf_screen import LIMIT_ALLOWANCE, CheckWindow, PartModel
from filter_lib.shared.toroid_selection import find_core_candidates, no_suitable_core_reason

PACKAGE = Path(__file__).resolve().parents[1] / "filter_lib"


def _ladder(**overrides) -> DesignRequest:
    values = dict(
        category="lowpass",
        filter_type="butterworth",
        topology="pi",
        frequency_hz=10e6,
        impedance=50.0,
        order=5,
    )
    values.update(overrides)
    return DesignRequest(**values)


def _vhf(**overrides) -> DesignRequest:
    """The 2 m low-pass of the acceptance designs: no toroid is rated for 146 MHz."""
    return _ladder(filter_type="chebyshev", frequency_hz=146e6, ripple_db=0.1, **overrides)


# The 10 MHz ladder's inductors (about 1 µH) are far above the chip catalog.
HF_CHIP_REASON = no_qualifying_chip_reason(frozenset({LIMIT_ALLOWANCE}), CheckWindow(0.0, 10e6))


def _bandpass(**overrides) -> DesignRequest:
    values = dict(
        category="bandpass",
        filter_type="butterworth",
        topology="top",
        frequency_hz=14.2e6,
        impedance=50.0,
        order=3,
        bandwidth_hz=500e3,
    )
    values.update(overrides)
    return DesignRequest(**values)


# -- The record and its order ----------------------------------------------------------


def test_every_inductor_lists_each_kind_in_the_fixed_order():
    parts = design(_ladder()).parts

    assert sorted(parts.inductors) == ["L1", "L2"]
    for inductor in parts.inductors.values():
        assert tuple(group.kind for group in inductor.kinds) == INDUCTOR_KINDS


def test_hf_toroids_match_the_screen_with_the_not_checked_srf_basis():
    outcome = design(_ladder())
    inductor = outcome.parts.inductor("L1")
    toroids = inductor.kind("toroid")
    screened = find_core_candidates(
        outcome.result["inductors"][0], 10e6, top_n=MAX_SUGGESTIONS_PER_KIND
    )

    assert [item.part_name for item in toroids.suggestions] == [c.core.name for c in screened]
    assert [item.rank for item in toroids.suggestions] == list(range(1, len(screened) + 1))
    for suggestion, candidate in zip(toroids.suggestions, screened, strict=True):
        assert suggestion.achieved_h == candidate.winding.l_actual_h
        assert suggestion.target_h == outcome.result["inductors"][0]
        assert suggestion.srf_basis == SRF_NOT_CHECKED
        assert suggestion.status == candidate.candidate_status
        # The core's A_L tolerance applies to the achieved inductance; the budget
        # states it as a percentage of the target.
        assert suggestion.tolerance_pct == candidate.core.al_tolerance_pct
        assert suggestion.error_budget == ErrorBudget(
            nominal_mismatch_pct=candidate.winding.error_pct,
            tolerance_pct=candidate.core.al_tolerance_pct
            * candidate.winding.l_actual_h
            / suggestion.target_h,
            srf_drift_pct=None,
        )
        assert suggestion.source.publisher == "Micrometals, Inc."
    assert toroids.reason_none is None


def test_the_budget_s_terms_add_up_to_the_winding_s_true_worst_case():
    # 14.175 MHz, 75 ohm, n=7: L1's first winding is +4.99 % from its target, and its
    # +-5 % A_L range is +-5.25 % of the target, so the upper end is +10.24 %.
    outcome = design(_ladder(frequency_hz=14.175e6, impedance=75.0, order=7))
    best = outcome.parts.inductor("L1").best
    budget = best.error_budget
    upper = best.achieved_h * (1 + best.tolerance_pct / 100) / best.target_h - 1
    lower = best.achieved_h * (1 - best.tolerance_pct / 100) / best.target_h - 1

    assert best.part_name == "T50-2"
    assert budget.nominal_mismatch_pct == pytest.approx(4.99314, abs=5e-6)
    assert budget.tolerance_pct == pytest.approx(5.24966, abs=5e-6)
    assert budget.nominal_mismatch_pct + budget.tolerance_pct == pytest.approx(
        upper * 100, rel=1e-12, abs=0
    )
    assert budget.nominal_mismatch_pct - budget.tolerance_pct == pytest.approx(
        lower * 100, rel=1e-12, abs=0
    )


def test_kinds_never_offered_state_their_sourced_reasons():
    inductor = design(_ladder()).parts.inductor("L1")

    assert inductor.kind("air-coil") == KindSuggestions("air-coil", reason_none=AIR_COIL_EXCLUSION)


def test_a_chip_inductor_far_from_the_catalog_names_the_allowance_that_failed():
    inductor = design(_ladder()).parts.inductor("L1")

    assert inductor.kind("chip") == KindSuggestions("chip", reason_none=HF_CHIP_REASON)
    assert HF_CHIP_REASON == (
        "No chip inductor qualifies: every part in the built-in chip catalog (10.00 nH to "
        "100.00 nH) misses this inductance by more than ±10% once its tolerance and SRF "
        "drift are counted (checked from DC to 10 MHz)."
    )


def test_suggestions_are_listed_by_kind_then_rank():
    inductor = design(_ladder()).parts.inductor("L1")

    assert inductor.suggestions == inductor.kind("toroid").suggestions


def test_no_rated_core_names_the_frequency_and_the_vhf_exclusion():
    inductor = design(_vhf()).parts.inductor("L1")
    reason = inductor.kind("toroid").reason_none

    assert reason == f"No built-in toroid core is rated for 146 MHz. {VHF_TOROID_EXCLUSION}"
    # The chip inductors are then the only suggestions, and "best" is the first of them.
    assert inductor.suggestions == inductor.kind("chip").suggestions
    assert inductor.best == inductor.kind("chip").suggestions[0]


def test_a_rated_core_that_misses_in_whole_turns_names_that_limit():
    # 5 ohm, 10 MHz, n=3: every rated core fits a single layer, but each whole-turn
    # winding misses 0.1592 uH by more than its 5 % A_L tolerance (+8.57 %, +10.84 %,
    # -10.46 %).
    outcome = design(_ladder(impedance=5.0, order=3))

    reason = outcome.parts.inductor("L1").kind("toroid").reason_none
    assert reason == (
        "No suitable toroid core in the built-in list: no core rated for this frequency "
        "reaches this inductance within its A_L tolerance using whole turns. Choose a core "
        "manually."
    )


def test_a_winding_that_fits_no_rated_core_names_that_limit():
    # 0.1 H at 30 MHz needs more turns than any rated core's winding table holds.
    parts = resolve_parts_for(
        {"freq_hz": 30e6, "capacitors": [1e-12], "inductors": [1e-1], "order": 2, "topology": "pi"},
        "lowpass",
    )

    assert parts.inductor("L1").kind("toroid").reason_none == (
        "No suitable toroid core in the built-in list: the winding that reaches this "
        "inductance does not fit any core rated for this frequency. Choose a core manually."
    )


def test_cores_rejected_for_both_limits_name_both():
    reason = no_suitable_core_reason(frozenset({"inductance", "fit"}))

    assert reason == (
        "No suitable toroid core in the built-in list: each core rated for this frequency "
        "either misses this inductance by more than its A_L tolerance using whole turns or "
        "cannot fit the winding. Choose a core manually."
    )


@pytest.mark.parametrize(
    "build",
    [
        dict(kind="ferrite", rank=1),
        dict(rank=0),
        dict(srf_basis="typical"),
        dict(achieved_h=0.0),
        dict(tolerance_pct=-1.0),
        dict(tolerance_pct=float("nan")),
        dict(tolerance_pct=100.0),
        # A model qualifies only with its stated accuracy.
        dict(srf_basis="model"),
        # Only the legacy toroid windings may leave the SRF not checked.
        dict(kind="chip"),
    ],
    ids=[
        "kind",
        "rank",
        "srf-basis",
        "inductance",
        "negative-tolerance",
        "nan-tolerance",
        "full-tolerance",
        "model-without-accuracy",
        "unchecked-chip",
    ],
)
def test_the_record_refuses_values_outside_its_contract(build):
    values = dict(
        kind="toroid",
        rank=1,
        part_name="T50-2",
        target_h=1e-6,
        achieved_h=1e-6,
        tolerance_pct=5.0,
        srf_basis=SRF_NOT_CHECKED,
        error_budget=ErrorBudget(0.0, 5.0),
        source=None,
        build=None,
        status="screened_candidate",
    )
    values.update(build)

    with pytest.raises(ValueError):
        InductorSuggestion(**values)


@pytest.mark.parametrize(
    "budget",
    [
        dict(nominal_mismatch_pct=float("inf")),
        dict(tolerance_pct=-0.1),
        dict(tolerance_pct=float("nan")),
        dict(srf_drift_pct=(1.0, -1.0)),
        dict(srf_drift_pct=(0.0, float("nan"))),
    ],
    ids=["mismatch", "negative-tolerance", "nan-tolerance", "drift-order", "nan-drift"],
)
def test_the_error_budget_refuses_values_outside_its_contract(budget):
    values = dict(nominal_mismatch_pct=1.0, tolerance_pct=5.0)
    values.update(budget)

    with pytest.raises(ValueError):
        ErrorBudget(**values)


def _checked(suggestion, **changes):
    """A toroid suggestion recast as a chip whose SRF is checked, plus ``changes``."""
    budget = dataclasses.replace(suggestion.error_budget, srf_drift_pct=(-0.5, 1.5))
    values = dict(
        kind="chip",
        srf_basis="guaranteed_minimum",
        error_budget=budget,
        part_model=PartModel(suggestion.achieved_h, 100e6, 2e9),
        allowance_range_hz=(0.0, 500e6),
    )
    values.update(changes)
    return dataclasses.replace(suggestion, **values)


def test_a_checked_srf_with_its_evidence_is_a_valid_record():
    suggestion = design(_ladder()).parts.inductor("L1").best

    assert _checked(suggestion).srf_basis == "guaranteed_minimum"
    model = _checked(suggestion, srf_basis="model", srf_accuracy="±5% against measurements")
    assert model.srf_accuracy == "±5% against measurements"


@pytest.mark.parametrize(
    "changes, message",
    [
        (dict(srf_basis="model", srf_accuracy=" "), "stated accuracy"),
        (dict(source=None), "source of its guarantees"),
        (dict(error_budget=ErrorBudget(1.0, 5.0)), "SRF drift is listed exactly"),
        (dict(part_model=None), "part model is given exactly"),
        (dict(allowance_range_hz=None), "allowance range is given exactly"),
        (dict(allowance_range_hz=(5e8, 1e8)), "finite \\(lowest, highest\\) pair"),
    ],
    ids=["blank-accuracy", "no-source", "no-drift", "no-model", "no-range", "reversed-range"],
)
def test_a_checked_srf_needs_its_evidence(changes, message):
    suggestion = design(_ladder()).parts.inductor("L1").best

    with pytest.raises(ValueError, match=message):
        _checked(suggestion, **changes)


def test_an_unchecked_srf_lists_no_drift():
    suggestion = design(_ladder()).parts.inductor("L1").best
    budget = ErrorBudget(1.0, 5.0, (0.0, 1.0))

    with pytest.raises(ValueError, match="SRF drift is listed exactly"):
        dataclasses.replace(suggestion, error_budget=budget)


@pytest.mark.parametrize("drift", [False, [0.0, 1.0], (0.0,)], ids=["bool", "list", "short"])
def test_the_drift_must_be_a_pair(drift):
    with pytest.raises(ValueError, match="finite \\(lowest, highest\\) pair"):
        ErrorBudget(0.0, 0.0, drift)  # type: ignore[arg-type]


def test_a_kind_has_either_suggestions_or_a_reason():
    with pytest.raises(ValueError):
        KindSuggestions("toroid")
    with pytest.raises(ValueError):
        KindSuggestions("chip", reason_none="x", suggestions=(None,))  # type: ignore[arg-type]


# -- The build pick and "best" -----------------------------------------------------------


def test_auto_builds_the_first_suggestion_in_the_fixed_order():
    inductor = design(_ladder()).parts.inductor("L1")

    assert inductor.build_pick == inductor.kind("toroid").suggestions[0]
    assert inductor.best is inductor.build_pick
    assert inductor.build_status == inductor.build_pick.status
    assert inductor.build_note is None


def test_auto_without_any_suggestion_builds_the_calculated_value():
    # 500 ohm at 146 MHz: no toroid is rated there, and 747 nH is above the chip catalog.
    inductor = design(_vhf(impedance=500.0)).parts.inductor("L1")

    assert inductor.build_pick is None
    assert inductor.build_status == NO_QUALIFYING_SUGGESTION
    assert inductor.build_note == NO_SUGGESTION_NOTE


def test_calculated_keeps_suggestions_and_best_shows_the_first_in_order():
    inductor = design(_ladder(build_inductors="calculated")).parts.inductor("L1")

    assert inductor.build_pick is None
    assert inductor.build_status == SUGGESTIONS_NOT_USED
    assert inductor.build_note == SUGGESTIONS_NOT_USED_NOTE
    assert inductor.best == inductor.kind("toroid").suggestions[0]


def test_none_leaves_suggestions_out_and_builds_the_calculated_value():
    parts = design(_ladder(inductor_suggestions="none")).parts
    inductor = parts.inductor("L1")

    assert not parts.shows_suggestions
    assert inductor.kinds == ()
    assert inductor.best is None
    assert inductor.build_status == SUGGESTIONS_NOT_USED


def test_a_forced_kind_with_a_part_builds_that_part():
    inductor = design(_ladder(build_inductors="toroid")).parts.inductor("L1")

    assert inductor.build_pick == inductor.kind("toroid").suggestions[0]


@pytest.mark.parametrize(
    "kind, reason", [("air-coil", AIR_COIL_EXCLUSION), ("chip", HF_CHIP_REASON)]
)
def test_a_forced_kind_without_a_part_builds_the_calculated_value_and_says_why(kind, reason):
    inductor = design(_ladder(build_inductors=kind)).parts.inductor("L1")

    assert inductor.build_pick is None
    assert inductor.build_status == NO_QUALIFYING_SUGGESTION
    assert inductor.build_note == reason
    # "best" is then the first suggestion in the fixed order.
    assert inductor.best == inductor.kind("toroid").suggestions[0]


def test_forced_toroid_at_vhf_gives_the_toroid_reason():
    inductor = design(_vhf(build_inductors="toroid")).parts.inductor("L1")

    assert inductor.build_note == inductor.kind("toroid").reason_none


def test_band_pass_resonators_share_one_screened_inductance():
    parts = design(_bandpass()).parts

    assert sorted(parts.inductors) == ["LT1", "LT2", "LT3"]
    kinds = {id(parts.inductor(name).kinds) for name in parts.inductors}
    assert len(kinds) == 1


# -- Capacitors ---------------------------------------------------------------------------


def test_capacitor_choices_are_the_policy_s_choices_by_circuit_name():
    request = _ladder(capacitor_grade="tight", eseries="E12")
    outcome = design(request)
    policy = outcome.match_policy

    assert policy == MatchPolicy(grade="tight")
    assert sorted(outcome.parts.capacitors) == ["C1", "C2", "C3"]
    for index, value in enumerate(outcome.result["capacitors"]):
        expected = match_component(value, "E12", parallel_mode="additive", policy=policy)
        assert outcome.parts.capacitor(f"C{index + 1}") == expected


def test_band_pass_capacitors_are_keyed_by_their_circuit_names():
    parts = design(_bandpass()).parts

    assert sorted(parts.capacitors) == ["CIN", "CK1", "CK2", "COUT", "CT1", "CT2", "CT3"]


def test_no_series_chooses_no_capacitor():
    parts = design(_ladder(eseries=None)).parts

    assert parts.capacitors == {}
    with pytest.raises(ValueError, match="No standard capacitor values"):
        parts.capacitor("C1")


def test_resolve_parts_uses_the_request_s_settings():
    request = _ladder(build_inductors="calculated", inductor_suggestions="full")
    outcome = design(request)

    assert resolve_parts(request, outcome.result) == outcome.parts
    assert outcome.parts.inductor_detail == "full"
    assert outcome.parts.build_inductors == "calculated"


def test_the_resolver_refuses_what_the_request_refuses():
    result = design(_ladder()).result

    with pytest.raises(ValueError) as error:
        resolve_parts_for(result, "lowpass", inductor_detail="none", build_inductors="chip")
    assert str(error.value) == FORCED_KIND_NEEDS_SUGGESTIONS_MESSAGE
    with pytest.raises(ValueError, match="zero-argument callable"):
        resolve_parts_for(result, "lowpass", should_cancel=True)  # type: ignore[arg-type]


@pytest.mark.parametrize(
    "settings, message",
    [
        (dict(eseries=None, policy=MatchPolicy(grade="tight")), "needs an E-series"),
        (dict(eseries=None, policy=MatchPolicy(allow_sub_pf=True)), "needs an E-series"),
        (dict(policy=False), "MatchPolicy"),
        (dict(eseries="E6"), "E12, E24, or E96"),
    ],
    ids=["grade-without-series", "sub-pf-without-series", "not-a-policy", "unknown-series"],
)
def test_the_resolver_refuses_a_policy_the_request_refuses(settings, message):
    result = design(_ladder()).result

    with pytest.raises(ValueError, match=message):
        resolve_parts_for(result, "lowpass", **settings)


def test_a_build_refuses_another_design_s_parts():
    from filter_lib.shared.build_types import BuildConfig
    from filter_lib.shared.nominal_realization import realize_nominal_build
    from filter_lib.shared.resolved_parts import PARTS_FROM_ANOTHER_DESIGN_MESSAGE

    hf = design(_ladder(order=3))
    vhf = design(_ladder(order=3, frequency_hz=146e6))

    with pytest.raises(ValueError) as error:
        realize_nominal_build(vhf.result, "lowpass", BuildConfig(), parts=hf.parts)
    assert str(error.value) == PARTS_FROM_ANOTHER_DESIGN_MESSAGE
    assert realize_nominal_build(vhf.result, "lowpass", BuildConfig(), parts=vhf.parts)


def test_suggestions_off_screen_nothing(monkeypatch):
    calls = []
    monkeypatch.setattr(
        "filter_lib.design.part_resolution.suggest_toroids",
        lambda *args: calls.append(args) or pytest.fail("a toroid was screened"),
    )

    parts = design(_ladder(inductor_suggestions="none")).parts

    assert calls == []
    assert parts.inductor("L1").kinds == ()


def test_band_pass_synthesis_refuses_a_check_that_cannot_be_called():
    from filter_lib.bandpass import calculate_bandpass_filter

    with pytest.raises(ValueError, match="zero-argument callable"):
        calculate_bandpass_filter(14.2e6, 500e3, 50.0, 3, "butterworth", "top", should_cancel=True)


# -- Request rules -------------------------------------------------------------------------


@pytest.mark.parametrize("kind", ["toroid", "air-coil", "chip"])
def test_a_forced_kind_needs_suggestions(kind):
    with pytest.raises(ValueError) as error:
        _ladder(inductor_suggestions="none", build_inductors=kind)

    assert str(error.value) == FORCED_KIND_NEEDS_SUGGESTIONS_MESSAGE


@pytest.mark.parametrize("choice", ["auto", "calculated"])
def test_auto_and_calculated_work_without_suggestions(choice):
    assert _ladder(inductor_suggestions="none", build_inductors=choice).build_inductors == choice


@pytest.mark.parametrize(
    "field, value, message",
    [
        ("inductor_suggestions", "most", "Inductor suggestions must be best"),
        ("inductor_suggestions", None, "Inductor suggestions must be best"),
        ("build_inductors", "ferrite", "Build inductors must be auto"),
        ("build_inductors", True, "Build inductors must be auto"),
    ],
)
def test_unknown_inductor_choices_are_refused(field, value, message):
    with pytest.raises(ValueError, match=message):
        _ladder(**{field: value})


@pytest.mark.parametrize("detail", ["best", "full", "compact"])
def test_table_only_details_give_the_same_documents(detail):
    assert _ladder(inductor_suggestions=detail).without_table_detail() == _ladder()


def test_none_is_not_a_table_only_detail():
    request = _ladder(inductor_suggestions="none")

    assert request.without_table_detail() == request


# -- Cancellation ---------------------------------------------------------------------------


def _after(calls: int):
    """A cancellation check that reports true on its ``calls``-th poll, and counts polls."""
    polls = [0]

    def check() -> bool:
        polls[0] += 1
        return polls[0] >= calls

    return check, polls


@pytest.mark.parametrize("request_", [_ladder(), _bandpass()], ids=["ladder", "bandpass"])
def test_synthesis_stops_before_it_starts(request_):
    check, polls = _after(1)

    with pytest.raises(DesignCancelled):
        synthesize(request_, should_cancel=check)
    assert polls == [1]


def test_band_pass_calibration_polls_between_circuit_evaluations(monkeypatch):
    calls = []
    monkeypatch.setattr(
        "filter_lib.design.design_service.resolve_parts",
        lambda *args: calls.append(args) or pytest.fail("part resolution ran"),
    )
    check, polls = _after(4)

    with pytest.raises(DesignCancelled):
        design(_bandpass(), should_cancel=check)
    assert polls == [4]
    assert calls == []


def test_band_pass_synthesis_polls_before_every_circuit_evaluation(monkeypatch):
    from filter_lib.bandpass import top_c_calibration

    evaluations = [0]
    real = top_c_calibration._synthesize_top_c_raw

    def counting(*args, **kwargs):
        evaluations[0] += 1
        return real(*args, **kwargs)

    monkeypatch.setattr(top_c_calibration, "_synthesize_top_c_raw", counting)
    polls = [0]

    def never() -> bool:
        polls[0] += 1
        return False

    synthesize(_bandpass(), should_cancel=never)

    # Once before synthesis, once before each calibration evaluation, once before the
    # response check.
    assert evaluations[0] > 1
    assert polls[0] == evaluations[0] + 2


def test_part_resolution_polls_before_each_part():
    outcome = design(_ladder())
    check, polls = _after(3)

    with pytest.raises(DesignCancelled):
        resolve_parts_for(outcome.result, "lowpass", should_cancel=check)
    assert polls == [3]


def test_design_rejects_a_check_that_cannot_be_called():
    with pytest.raises(ValueError, match="zero-argument callable"):
        design(_ladder(), should_cancel=True)  # type: ignore[arg-type]


def test_a_cancelled_build_is_a_cancelled_design():
    assert issubclass(BuildAnalysisCancelled, DesignCancelled)
    assert not issubclass(DesignCancelled, ValueError)


# -- Only design/ selects parts --------------------------------------------------------------

# Selection entry points, and the selector modules that call them inside a selection
# (``match_component`` hands capacitors to ``choose_capacitor``; ``suggest_toroids`` runs
# the toroid screen).
SELECTORS = {
    "match_component": set(),
    "choose_capacitor": {"shared/eseries.py"},
    "find_core_candidates": {"shared/toroid_selection.py"},
    "recommend_cores": set(),
    "suggest_toroids": set(),
}


def _callers(name: str) -> set[str]:
    callers = set()
    for path in PACKAGE.rglob("*.py"):
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
            if isinstance(node, ast.Call):
                func = node.func
                called = func.id if isinstance(func, ast.Name) else getattr(func, "attr", None)
                if called == name:
                    callers.add(path.relative_to(PACKAGE).as_posix())
    return callers


@pytest.mark.parametrize("name", sorted(SELECTORS))
def test_only_part_resolution_selects_parts(name):
    assert _callers(name) <= {"design/part_resolution.py", *SELECTORS[name]}
