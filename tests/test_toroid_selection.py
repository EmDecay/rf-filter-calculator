"""Tests for toroid selection and ranking (Phase 4)."""

import pytest

from filter_lib.shared.toroid_core_data import get_core
from filter_lib.shared.toroid_selection import ToroidRecommendation, recommend_cores


def test_recommend_cores_lp_10mhz():
    """LP 10 MHz L=1.457 uH: several cores within 1% accuracy."""
    recs = recommend_cores(1.457e-6, 10e6)
    assert 1 <= len(recs) <= 3
    assert abs(recs[0].winding.error_pct) <= 1.0


def test_recommend_cores_returns_top_3_by_default():
    """Default top_n=3 returns up to 3 recs."""
    recs = recommend_cores(1e-6, 10e6)
    assert len(recs) <= 3


def test_recommend_cores_top_n_honored():
    """Explicit top_n is honored and can exceed 3."""
    recs5 = recommend_cores(1e-6, 10e6, top_n=5)
    assert len(recs5) <= 5
    assert len(recs5) >= len(recommend_cores(1e-6, 10e6))


def test_recommend_cores_out_of_range_freq_empty():
    """500 MHz exceeds every iron-powder core (max 350 MHz); returns empty list."""
    assert recommend_cores(1e-6, 500e6) == []


@pytest.mark.parametrize("target", [1e-9, 10e-9])
def test_large_integer_turn_error_is_not_an_automatic_candidate(target):
    assert recommend_cores(target, 10e6) == []


def test_subnormal_target_skips_obviously_infeasible_one_turn_candidates():
    assert recommend_cores(5e-324, 10e6) == []


def test_recommend_cores_freq_gate_applied():
    """Every returned core must cover the design frequency in its published range."""
    recs = recommend_cores(1e-6, 10e6)
    for r in recs:
        assert r.core.freq_min_hz <= 10e6 <= r.core.freq_max_hz
        assert r.core.is_auto_selectable
        assert abs(r.winding.error_pct) <= r.core.al_tolerance_pct


def test_recommend_cores_negative_l_raises():
    with pytest.raises(ValueError):
        recommend_cores(-1, 10e6)


def test_recommend_cores_negative_freq_raises():
    with pytest.raises(ValueError):
        recommend_cores(1e-6, -1)


@pytest.mark.parametrize(
    "target,frequency",
    [
        (True, 10e6),
        ("1e-6", 10e6),
        (1e-6, True),
        (1e-6, "10MHz"),
        (10**400, 10e6),
    ],
)
def test_recommend_cores_rejects_non_real_or_nonfinite_inputs(target, frequency):
    with pytest.raises(ValueError):
        recommend_cores(target, frequency)


def test_recommend_cores_top_n_must_be_positive():
    with pytest.raises(ValueError):
        recommend_cores(1e-6, 10e6, top_n=0)


def test_recommend_cores_sorted_by_practical_accuracy_bands():
    """Ranking is deterministic and favors credible winding practicality."""
    recs = recommend_cores(1e-6, 10e6, top_n=10)
    keys = [r.ranking_key for r in recs]
    assert keys == sorted(keys)


def test_recommendation_has_q_dc():
    """Only a wire-DCR reactance-ratio ceiling is computed, not RF Q."""
    recs = recommend_cores(1e-6, 10e6)
    assert recs  # must be non-empty for this freq
    for r in recs:
        assert isinstance(r, ToroidRecommendation)
        assert r.wire_dcr_reactance_ratio_ceiling > 0
        assert r.wire_dcr_reactance_ratio_ceiling != float("inf")
        assert r.q_status == "not_assessed"
        assert r.srf_status == "not_assessed"
        assert r.power_status == "not_assessed"


def test_unverified_legacy_core_is_not_auto_selected():
    recs = recommend_cores(1e-6, 10e6, top_n=20)

    assert "T37-2" not in {rec.core.name for rec in recs}


def test_unsourced_mechanical_estimate_is_not_a_hard_gate(monkeypatch):
    from filter_lib.shared import toroid_selection

    verified = get_core("T50-2")
    estimated = toroid_selection.fit_wire(verified, 10, awg=36)
    estimated = estimated.__class__(
        **{
            **estimated.__dict__,
            "fits": False,
            "capacity_status": "estimated",
            "capacity_source_id": None,
        }
    )
    monkeypatch.setattr(toroid_selection, "fit_wire", lambda *_args, **_kwargs: estimated)

    recs = toroid_selection.recommend_cores(1e-6, 10e6)
    assert recs
    assert recs[0].mechanical.capacity_status == "estimated"


def test_determinism():
    """Two calls with same inputs return identical ranking order."""
    a = recommend_cores(1.457e-6, 10e6, top_n=5)
    b = recommend_cores(1.457e-6, 10e6, top_n=5)
    assert [r.core.name for r in a] == [r.core.name for r in b]


def test_bp_14mhz_has_candidates():
    """BP 14.175 MHz ~0.56 uH has iron-powder candidates."""
    recs = recommend_cores(0.56e-6, 14.175e6)
    assert recs
    # best should be within a few percent
    assert abs(recs[0].winding.error_pct) < 5.0
