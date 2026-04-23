"""Tests for toroid selection and ranking (Phase 4)."""

import pytest

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


def test_recommend_cores_freq_gate_applied():
    """Every returned core must cover the design frequency in its published range."""
    recs = recommend_cores(1e-6, 10e6)
    for r in recs:
        assert r.core.freq_min_hz <= 10e6 <= r.core.freq_max_hz


def test_recommend_cores_negative_l_raises():
    with pytest.raises(ValueError):
        recommend_cores(-1, 10e6)


def test_recommend_cores_negative_freq_raises():
    with pytest.raises(ValueError):
        recommend_cores(1e-6, -1)


def test_recommend_cores_top_n_must_be_positive():
    with pytest.raises(ValueError):
        recommend_cores(1e-6, 10e6, top_n=0)


def test_recommend_cores_sorted_by_error_ascending():
    """Primary sort key is |error_pct| ascending."""
    recs = recommend_cores(1e-6, 10e6, top_n=10)
    errors = [abs(r.winding.error_pct) for r in recs]
    assert errors == sorted(errors)


def test_recommendation_has_q_dc():
    """ToroidRecommendation carries a finite positive DC Q upper-bound."""
    recs = recommend_cores(1e-6, 10e6)
    assert recs  # must be non-empty for this freq
    for r in recs:
        assert isinstance(r, ToroidRecommendation)
        assert r.q_dc_upper_bound > 0
        assert r.q_dc_upper_bound != float("inf")


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
