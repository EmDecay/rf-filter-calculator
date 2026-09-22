"""Screening and ranking of primary-sourced toroid winding candidates."""

import dataclasses
from dataclasses import FrozenInstanceError

import pytest

from filter_lib.shared import toroid_selection
from filter_lib.shared.toroid_core_data import get_core
from filter_lib.shared.toroid_selection import find_core_candidates, recommend_cores

NOT_ASSESSED_WARNING = (
    "RF Q, core loss, SRF, saturation, thermal rise, and power handling are not assessed."
)


def _summary(recs):
    return [(rec.core.name, rec.winding.n_turns, rec.winding.error_pct) for rec in recs]


def test_accuracy_band_outranks_turn_count():
    """1.3 µH at 10 MHz (all three parts in range).

    T25-6: 22 turns -> 1.3068 µH (+0.52%, within 1%).
    T68-2: 15 turns -> 1.2825 µH (-1.35%); T50-2: 16 turns -> 1.2544 µH (-3.51%).
    The ≤1% candidate ranks first despite needing the most turns.
    """
    recs = recommend_cores(1.3e-6, 10e6)

    assert _summary(recs) == [
        ("T25-6", 22, pytest.approx(0.5231, abs=1e-4)),
        ("T68-2", 15, pytest.approx(-1.3462, abs=1e-4)),
        ("T50-2", 16, pytest.approx(-3.5077, abs=1e-4)),
    ]
    # Public explanation of the order: (accuracy band, winding practicality, turns, ...).
    assert [rec.ranking_key[:3] for rec in recs] == [(0, 0, 22), (1, 0, 15), (1, 0, 16)]
    assert recs[0].ranking_key[3:] == (6.48, pytest.approx(0.5231, abs=1e-4), "T25-6")


def test_fewer_turns_outrank_smaller_error_within_an_accuracy_band():
    """0.9604 µH at 10 MHz: T50-2 is exact at 14 turns, T68-2 is +0.30% at 13 turns.

    Both are within 1%, so the easier 13-turn winding ranks first; T25-6
    (19 turns, +1.49%) falls in the next band.
    """
    assert _summary(recommend_cores(0.9604e-6, 10e6)) == [
        ("T68-2", 13, pytest.approx(0.3020, abs=1e-4)),
        ("T50-2", 14, pytest.approx(0.0, abs=1e-9)),
        ("T25-6", 19, pytest.approx(1.4890, abs=1e-4)),
    ]


def test_top_n_truncates_the_ranked_list_without_padding_unqualified_cores():
    ranked = _summary(recommend_cores(1.3e-6, 10e6, top_n=3))

    assert _summary(recommend_cores(1.3e-6, 10e6, top_n=1)) == ranked[:1]
    assert _summary(recommend_cores(1.3e-6, 10e6, top_n=2)) == ranked[:2]
    # Only three parts are eligible; a larger request is not a guarantee.
    assert _summary(recommend_cores(1.3e-6, 10e6, top_n=10)) == ranked
    # 0.56 µH at 14.175 MHz: only T68-2 (10 turns, +1.79%) is within its ±5% A_L
    # tolerance; T25-6 (-5.5%) and T50-2 (+5.9%) are not offered as fillers.
    assert _summary(recommend_cores(0.56e-6, 14.175e6, top_n=3)) == [
        ("T68-2", 10, pytest.approx(1.7857, abs=1e-4))
    ]


@pytest.mark.parametrize(
    ("freq_hz", "expected"),
    [
        (1.9e6, set()),
        (5e6, {"T50-2", "T68-2"}),
        (40e6, {"T25-6"}),
        (60e6, set()),
    ],
)
def test_candidates_are_limited_to_published_frequency_guidance(freq_hz, expected):
    """Mix 2 (T50-2, T68-2) covers 2–30 MHz; mix 6 (T25-6) covers 10–50 MHz."""
    names = {rec.core.name for rec in recommend_cores(1e-6, freq_hz, top_n=10)}

    assert names == expected


def test_unverified_legacy_exact_match_is_never_offered():
    """T37-2 (A_L 4.0) realizes 1.024 µH exactly with 16 turns but is unverified."""
    assert get_core("T37-2").al_nh_per_turn2 * 1e-9 * 16**2 == pytest.approx(1.024e-6)

    names = {rec.core.name for rec in recommend_cores(1.024e-6, 10e6, top_n=10)}

    assert names <= {"T25-6", "T50-2", "T68-2"}
    assert "T37-2" not in names


def test_sub_one_turn_target_is_offered_only_within_al_tolerance_of_one_turn():
    """One T50-2 turn is 4.9 nH: +2.08% from 4.8 nH (accepted), +6.5% from 4.6 nH (rejected)."""
    [rec] = recommend_cores(4.8e-9, 10e6)
    assert (rec.core.name, rec.winding.n_turns) == ("T50-2", 1)
    assert rec.winding.error_pct == pytest.approx((4.9 / 4.8 - 1) * 100)

    assert recommend_cores(4.6e-9, 10e6) == []


@pytest.mark.parametrize("target", [5e-324, 1e-9, 10e-9])
def test_targets_with_integer_turn_error_beyond_al_tolerance_have_no_candidate(target):
    """At 10 nH the best option is T25-6 with 2 turns = 10.8 nH (+8%), beyond ±5%."""
    assert recommend_cores(target, 10e6) == []


def test_published_full_winding_capacity_is_a_hard_limit():
    """T25-6 (the only part covering 40 MHz) holds at most 760 turns of AWG 44."""
    [at_capacity] = recommend_cores(2.7e-9 * 760**2, 40e6)
    assert (at_capacity.winding.n_turns, at_capacity.mechanical.awg) == (760, 44)
    assert at_capacity.mechanical.capacity_status == "manufacturer_full_winding"

    # N_ideal = 760.9: 761 turns is the closest winding but exceeds the table.
    assert recommend_cores(2.7e-9 * 760.9**2, 40e6) == []
    # Far beyond capacity, including targets whose turn count is astronomically large.
    assert recommend_cores(2.7e-9 * 800**2, 40e6) == []
    assert find_core_candidates(1e300, 10e6) == []


def test_candidate_reports_wire_only_ratio_and_explicit_non_assessments():
    """T68-2, 12 turns (0.8208 µH) at 5 MHz on AWG 14 at 2.4 mΩ.

    ωL/Rdc = 2π·5e6·0.8208e-6 / 0.0024 = 10,744.
    """
    [rec, _] = recommend_cores(0.8208e-6, 5e6)

    assert (rec.core.name, rec.winding.n_turns, rec.mechanical.awg) == ("T68-2", 12, 14)
    assert rec.wire_dcr_reactance_ratio_ceiling == pytest.approx(10744.25, abs=0.01)
    assert rec.q_dc_upper_bound == rec.wire_dcr_reactance_ratio_ceiling
    assert rec.design_freq_hz == 5e6
    assert (rec.candidate_status, rec.frequency_status) == (
        "screened_candidate",
        "within_published_guidance",
    )
    assert (rec.q_status, rec.srf_status, rec.power_status) == ("not_assessed",) * 3
    assert rec.warnings == (NOT_ASSESSED_WARNING,)


def test_unsourced_capacity_estimate_warns_but_does_not_exclude(monkeypatch):
    estimated = dataclasses.replace(
        toroid_selection.fit_wire(get_core("T50-2"), 10, awg=36),
        fits=False,
        capacity_status="estimated",
        capacity_source_id=None,
    )
    monkeypatch.setattr(toroid_selection, "fit_wire", lambda *_args, **_kwargs: estimated)

    recs = recommend_cores(1e-6, 10e6)

    assert recs
    assert all(rec.mechanical is estimated for rec in recs)
    assert recs[0].warnings == (
        NOT_ASSESSED_WARNING,
        "Mechanical capacity is a geometry estimate and was not used as an exclusion.",
    )


def test_screen_results_are_immutable():
    rec = recommend_cores(1.3e-6, 10e6, top_n=1)[0]

    for record, field in (
        (rec, "q_status"),
        (rec.winding, "n_turns"),
        (rec.mechanical, "awg"),
        (rec.core, "al_nh_per_turn2"),
    ):
        with pytest.raises(FrozenInstanceError):
            setattr(record, field, None)


@pytest.mark.parametrize(
    ("target", "frequency", "message"),
    [
        (0.0, 10e6, "l_target_h must be positive"),
        (-1e-6, 10e6, "l_target_h must be positive"),
        (True, 10e6, "l_target_h must be positive"),
        ("1e-6", 10e6, "l_target_h must be positive"),
        (10**400, 10e6, "l_target_h must be positive"),
        (1e-6, 0.0, "design_freq_hz must be positive"),
        (1e-6, -1e6, "design_freq_hz must be positive"),
        (1e-6, True, "design_freq_hz must be positive"),
        (1e-6, "10MHz", "design_freq_hz must be positive"),
        (1e-6, float("nan"), "design_freq_hz must be positive"),
    ],
)
def test_screen_rejects_non_positive_or_non_real_inputs(target, frequency, message):
    with pytest.raises(ValueError, match=message):
        recommend_cores(target, frequency)


@pytest.mark.parametrize("top_n", [0, -1, True, 1.5])
def test_screen_requires_positive_integer_top_n(top_n):
    with pytest.raises(ValueError, match="top_n must be >= 1 and an integer"):
        recommend_cores(1e-6, 10e6, top_n=top_n)


@pytest.mark.parametrize("resistance", [0.0, -0.001])
def test_legacy_q_dc_upper_bound_is_infinite_without_positive_resistance(resistance):
    """The retained compatibility helper keeps its non-positive-resistance contract."""
    assert toroid_selection._q_dc_upper_bound(1e-6, 10e6, resistance) == float("inf")
