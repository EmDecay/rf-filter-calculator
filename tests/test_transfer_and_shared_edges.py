"""Coverage-gap tests for transfer-function edges, E-series edge cases, and
toroid-selection input validation."""

from __future__ import annotations

import pytest

from filter_lib.highpass.transfer import frequency_response as hp_frequency_response
from filter_lib.shared.eseries import (
    _normalize,
    find_closest_single,
    find_parallel_combo,
    match_component,
)
from filter_lib.shared.lp_hp_base_transfer_functions import (
    highpass_bessel_response,
    highpass_butterworth_response,
    highpass_chebyshev_response,
)
from filter_lib.shared.toroid_core_data import get_core
from filter_lib.shared.toroid_inductance import solve_winding
from filter_lib.shared.toroid_selection import (
    ToroidRecommendation,
    _q_dc_upper_bound,
    recommend_cores,
)
from filter_lib.shared.toroid_wire import MechanicalFit

# ---------------------------------------------------------------------------
# Highpass transfer function alias dispatch (covers `ch` and `bs` aliases)
# ---------------------------------------------------------------------------


class TestHighpassFrequencyResponseAliases:
    def test_chebyshev_alias_ch(self):
        freqs = [1e6, 10e6, 100e6]
        out = hp_frequency_response("ch", freqs, 10e6, order=3, ripple_db=0.5)
        assert len(out) == 3
        # DC-adjacent: very attenuated; at cutoff: ~ -3 dB region
        assert out[0] < -10

    def test_bessel_alias_bs(self):
        freqs = [1e6, 10e6, 100e6]
        out = hp_frequency_response("bs", freqs, 10e6, order=3)
        assert len(out) == 3
        assert out[0] < -3  # well below cutoff

    def test_butterworth_alias_bw(self):
        out = hp_frequency_response("bw", [10e6, 20e6], 10e6, order=3)
        # At cutoff, Butterworth is ~ -3 dB
        assert abs(out[0] - (-3.01)) < 1.0

    def test_unknown_filter_type_raises(self):
        with pytest.raises(ValueError, match="Unknown filter type"):
            hp_frequency_response("elliptic", [10e6], 10e6, order=3)


# ---------------------------------------------------------------------------
# HP base transfer at DC: all three kernels must return 0.0 (blocks DC)
# ---------------------------------------------------------------------------


class TestHighpassDCRejection:
    def test_butterworth_returns_zero_at_dc(self):
        assert highpass_butterworth_response(0.0, 10e6, 3) == 0.0

    def test_chebyshev_returns_zero_at_dc(self):
        assert highpass_chebyshev_response(0.0, 10e6, 3, ripple_db=0.5) == 0.0

    def test_bessel_returns_zero_at_dc(self):
        assert highpass_bessel_response(0.0, 10e6, 3) == 0.0


# ---------------------------------------------------------------------------
# eseries.py: edge cases
# ---------------------------------------------------------------------------


class TestESeriesEdges:
    def test_find_closest_single_rejects_unknown_series(self):
        with pytest.raises(ValueError, match="Unknown series"):
            find_closest_single(100e-12, "E48")

    def test_find_parallel_combo_rejects_unknown_series(self):
        with pytest.raises(ValueError, match="Unknown series"):
            find_parallel_combo(100e-12, "E48")

    def test_normalize_rejects_non_positive(self):
        with pytest.raises(ValueError, match="must be positive"):
            _normalize(0.0)
        with pytest.raises(ValueError, match="must be positive"):
            _normalize(-1e-9)

    def test_normalize_handles_mantissa_ge_10_boundary(self):
        """For values exactly on a decade boundary, mantissa adjustment must fire."""
        # Any finite value > 0 should normalize to mantissa in [1, 10)
        m, _ = _normalize(9.999999e-10)
        assert 1.0 <= m < 10.0
        m, _ = _normalize(1.0)
        assert 1.0 <= m < 10.0
        m, _ = _normalize(1e12)
        assert 1.0 <= m < 10.0

    def test_find_parallel_combo_harmonic_mode_for_inductor(self):
        """Inductor (large value) should route through harmonic-parallel code path."""
        result = find_parallel_combo(10e-6, "E24", mode="harmonic")
        # The harmonic branch may still return None for well-matched singles, but
        # the call must succeed without error and route through the harmonic code.
        assert result is None or len(result) == 3

    def test_find_parallel_combo_explicit_harmonic_for_large_inductor(self):
        """Explicit harmonic mode works for large inductor values."""
        result = find_parallel_combo(100e-6, "E24", mode="harmonic")
        assert result is None or len(result) == 3

    def test_find_parallel_combo_explicit_additive_for_small_capacitor(self):
        """Explicit additive mode works for small capacitor values."""
        result = find_parallel_combo(47e-12, "E24", mode="additive")
        assert result is None or len(result) == 3

    def test_find_parallel_combo_rejects_missing_mode(self):
        """Mode is required; the magnitude-based auto inference was removed."""
        import pytest

        with pytest.raises(ValueError, match="additive"):
            find_parallel_combo(47e-12, "E24")

    def test_match_component_returns_single_when_parallel_gives_no_improvement(self):
        """When the parallel branch finds nothing, the returned match has parallel=None."""
        # Exact E24 value: no need for parallel combo
        match = match_component(47e-12, "E24", parallel_mode="additive")
        assert match.target == 47e-12
        assert match.single_value > 0
        # Parallel may or may not be populated; just ensure API contract
        if match.parallel is None:
            assert match.parallel_value is None
            assert match.parallel_error_pct is None


# ---------------------------------------------------------------------------
# toroid_selection.py: input validation + Q=inf when R_dc is zero
# ---------------------------------------------------------------------------


class TestToroidSelectionValidation:
    def test_recommend_cores_rejects_non_positive_l(self):
        with pytest.raises(ValueError, match="l_target_h must be positive"):
            recommend_cores(0.0, 10e6)
        with pytest.raises(ValueError, match="l_target_h must be positive"):
            recommend_cores(-1e-6, 10e6)

    def test_recommend_cores_rejects_non_positive_freq(self):
        with pytest.raises(ValueError, match="design_freq_hz must be positive"):
            recommend_cores(1e-6, 0.0)
        with pytest.raises(ValueError, match="design_freq_hz must be positive"):
            recommend_cores(1e-6, -1e6)

    def test_recommend_cores_rejects_top_n_less_than_one(self):
        with pytest.raises(ValueError, match="top_n must be >= 1"):
            recommend_cores(1e-6, 10e6, top_n=0)

    def test_q_dc_upper_bound_returns_inf_for_zero_resistance(self):
        assert _q_dc_upper_bound(1e-6, 10e6, 0.0) == float("inf")

    def test_q_dc_upper_bound_returns_inf_for_negative_resistance(self):
        assert _q_dc_upper_bound(1e-6, 10e6, -0.001) == float("inf")

    def test_recommend_cores_returns_valid_results_for_hf_target(self):
        """Integration smoke: HF target at 7 MHz must yield at least one recommendation."""
        recs = recommend_cores(1e-6, 7e6, top_n=3)
        assert all(isinstance(r, ToroidRecommendation) for r in recs)
        # For a 1 µH target in 7 MHz range the data set should yield recs
        assert len(recs) >= 1


# ---------------------------------------------------------------------------
# toroid_inductance.solve_winding: expose the physical one-turn floor
# ---------------------------------------------------------------------------


class TestSolveWindingEdge:
    def test_solve_winding_exposes_one_turn_for_tiny_target(self):
        """Choosing a large-A_L core with a tiny L target drives N_ideal below 0.5."""
        # Pick any real core, then give a ridiculously small L target
        core = get_core("T106-2")  # A_L = 13.5 nH/turn^2
        # 1 fH target => N_ideal = sqrt(1e-15 / 13.5e-9) ≈ 2.7e-4 turns
        result = solve_winding(1e-15, core)
        assert result.n_turns == 1
        assert result.l_actual_h == pytest.approx(core.al_nh_per_turn2 * 1e-9)
        assert result.error_pct > 1e6
        assert [option.n_turns for option in result.turn_options] == [1]

    def test_solve_winding_gives_valid_solution_for_normal_target(self):
        core = get_core("T50-2")
        result = solve_winding(1e-6, core)
        assert result is not None
        assert result.n_turns >= 1
        assert result.l_actual_h > 0


# ---------------------------------------------------------------------------
# ToroidRecommendation + MechanicalFit hashability/equality smoke (frozen dataclasses)
# ---------------------------------------------------------------------------


class TestFrozenDataclassContracts:
    def test_mechanical_fit_is_frozen(self):
        fit = MechanicalFit(
            awg=22,
            wire_diameter_mm=0.65,
            n_max=30,
            fits=True,
            wire_length_mm=500.0,
            wire_length_m=0.5,
            dc_resistance_ohm=0.05,
        )
        # Frozen dataclasses raise FrozenInstanceError (a subclass of AttributeError)
        from dataclasses import FrozenInstanceError

        with pytest.raises(FrozenInstanceError):
            fit.awg = 24  # type: ignore[misc]
