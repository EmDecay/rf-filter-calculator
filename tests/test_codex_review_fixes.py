"""Regression tests locking in the Codex-review fixes:

- #1 CRITICAL/HIGH: Chebyshev bandpass now honours ``bw`` as true -3 dB BW.
- #2 HIGH: Wizard HP inductor E-series parallel recommendation uses harmonic math.
- #3 LOW: Butterworth transfer function no longer OverflowErrors on extreme ratios.
- #4 MEDIUM: Sweep generators reject points/num_points < 2 with a clear ValueError.
- #5 MEDIUM: LP/HP/BP validators reject NaN/inf explicitly.
- #6 LOW: ``filter-calc bp --verify`` works under ``python -O`` (no asserts).
- #7 LOW: ResultsScreen pre-selects export format from state.
"""

from __future__ import annotations

import math
from unittest.mock import Mock

import pytest
from textual.widgets import RadioButton, RadioSet

from filter_lib.bandpass import calculate_bandpass_filter
from filter_lib.bandpass.transfer import (
    chebyshev_3db_deviation,
    frequency_sweep,
    magnitude_db,
)
from filter_lib.bandpass.transfer import (
    generate_frequency_points as bp_generate_frequency_points,
)
from filter_lib.cli.bandpass_cmd import _run_verification
from filter_lib.shared.lp_hp_base_transfer_functions import (
    highpass_butterworth_response,
    lowpass_butterworth_response,
)
from filter_lib.shared.transfer_functions import generate_frequency_points
from filter_lib.wizard.screens.results import ResultsScreen
from filter_lib.wizard.state import FilterState

# ---------------------------------------------------------------------------
# #1 Chebyshev bandpass 3 dB BW semantics
# ---------------------------------------------------------------------------


class TestChebyshev3dBBandwidthSemantics:
    """User supplies ``bw`` as -3 dB BW. Synthesis + response plot honour that."""

    @pytest.mark.parametrize("ripple_db, order", [(0.1, 3), (0.5, 3), (0.5, 5), (1.0, 5)])
    def test_delta_3db_is_greater_than_1(self, ripple_db, order):
        """Chebyshev 3-dB deviation is always >= 1 (ripple edge is narrower than 3 dB)."""
        scale = chebyshev_3db_deviation(order, ripple_db)
        assert scale > 1.0

    def test_delta_3db_rejects_non_positive_ripple(self):
        with pytest.raises(ValueError, match="ripple_db must be positive"):
            chebyshev_3db_deviation(3, 0)

    def test_magnitude_at_user_bw_edge_is_minus_3db(self):
        """At f = f0 + bw/2 (approx), Chebyshev magnitude is now -3 dB, not -ripple."""
        f0 = 14.175e6
        bw = 350e3
        order = 3
        ripple_db = 0.5
        # Solve for f_high where delta=1 in user's bw frame:
        # f^2 - bw*f - f0^2 = 0 -> f_high = (bw + sqrt(bw^2 + 4 f0^2))/2
        disc = math.sqrt(bw * bw + 4 * f0 * f0)
        f_high = (bw + disc) / 2.0
        f_low = f0 * f0 / f_high

        db_high = magnitude_db(f_high, f0, bw, order, "chebyshev", ripple_db)
        db_low = magnitude_db(f_low, f0, bw, order, "chebyshev", ripple_db)
        target_db = 10.0 * math.log10(0.5)  # -3.0103 dB
        assert db_high == pytest.approx(target_db, abs=1e-9)
        assert db_low == pytest.approx(target_db, abs=1e-9)

    def test_chebyshev_ripple_edge_interior_to_3db_edges(self):
        """The ripple-edge Hz-BW is narrower than the 3-dB Hz-BW by delta_3dB."""
        f0 = 14.175e6
        bw = 350e3
        order = 3
        ripple_db = 0.5
        scale = chebyshev_3db_deviation(order, ripple_db)
        # Ripple edge: where response equals exactly -ripple_db
        # After fix, that sits at delta_user = 1/scale (i.e., a narrower Hz span)
        # Solve f^2 - (bw/scale)*f - f0^2 = 0 -> narrower BW in Hz
        narrow_bw = bw / scale
        disc = math.sqrt(narrow_bw * narrow_bw + 4 * f0 * f0)
        f_high_ripple = (narrow_bw + disc) / 2.0
        db = magnitude_db(f_high_ripple, f0, bw, order, "chebyshev", ripple_db)
        assert db == pytest.approx(-ripple_db, abs=1e-9)

    def test_synthesis_qe_scales_with_delta_3db(self):
        """Chebyshev Qe should be tighter than Butterworth (narrower ripple BW)."""
        bw_args = dict(f0=14.175e6, bw=350e3, z0=50, n_resonators=3, coupling="top")
        bw_result = calculate_bandpass_filter(filter_type="butterworth", **bw_args)
        ch_result = calculate_bandpass_filter(filter_type="chebyshev", ripple_db=0.5, **bw_args)

        # For equal fbw, Chebyshev Qe tightens by delta_3dB
        scale = chebyshev_3db_deviation(3, 0.5)
        ratio = ch_result["qe_in"] / bw_result["qe_in"]
        # ratio = (g1_ch * scale / fbw) / (g1_bw / fbw) = g1_ch / g1_bw * scale
        g1_ch = ch_result["g_values"][0]
        g1_bw = bw_result["g_values"][0]
        expected_ratio = (g1_ch / g1_bw) * scale
        assert ratio == pytest.approx(expected_ratio, rel=1e-9)

    def test_butterworth_synthesis_unchanged(self):
        """Butterworth delta_3dB = 1 so coupling/Qe formulas are unchanged."""
        result = calculate_bandpass_filter(
            f0=14.175e6,
            bw=350e3,
            z0=50,
            n_resonators=5,
            filter_type="butterworth",
            coupling="top",
        )
        fbw = 350e3 / 14.175e6
        # Butterworth g1 = 2·sin(pi/(2n)) for prototype with g0=g_{n+1}=1
        g1 = result["g_values"][0]
        assert result["qe_in"] == pytest.approx(g1 / fbw, rel=1e-12)

    def test_bessel_synthesis_unchanged(self):
        """Bessel is pre-normalized to delta=1 → -3 dB so no scaling applied."""
        result = calculate_bandpass_filter(
            f0=14.175e6,
            bw=350e3,
            z0=50,
            n_resonators=3,
            filter_type="bessel",
            coupling="top",
        )
        fbw = 350e3 / 14.175e6
        g1 = result["g_values"][0]
        assert result["qe_in"] == pytest.approx(g1 / fbw, rel=1e-12)


# ---------------------------------------------------------------------------
# #2 Wizard HP inductor parallel mode
# ---------------------------------------------------------------------------


class TestWizardFormatEseriesRecsParallelMode:
    def test_format_eseries_recs_accepts_parallel_mode(self):
        """format_eseries_recs threads parallel_mode through to match_component."""
        from filter_lib.shared.formatting import format_inductance
        from filter_lib.wizard.formatting_helpers import format_eseries_recs

        # Harmonic mode for inductors — routes through harmonic combo search.
        lines_harmonic = format_eseries_recs(
            [2.5e-6, 1.0e-6], "L", "Inductor", "E24", format_inductance, parallel_mode="harmonic"
        )
        assert any("Inductor" in line for line in lines_harmonic)

        # Additive mode for caps remains the default.
        lines_additive = format_eseries_recs(
            [100e-12, 150e-12], "C", "Capacitor", "E24", format_inductance
        )
        assert any("Capacitor" in line for line in lines_additive)

    def test_hp_calculator_passes_harmonic_for_inductors(self):
        """The wizard HP calculation path requests harmonic parallel matching."""
        import inspect

        from filter_lib.wizard import filter_type_calculators

        src = inspect.getsource(filter_type_calculators.calculate_highpass)
        # Crude but effective: the src must now mention harmonic in the E-series block
        assert 'parallel_mode="harmonic"' in src


# ---------------------------------------------------------------------------
# #3 Butterworth overflow robustness
# ---------------------------------------------------------------------------


class TestButterworthOverflowClamped:
    def test_lowpass_extreme_ratio_saturates_to_zero(self):
        """Ratio so huge ratio^(2n) overflows — response clamped to 0 instead of raising."""
        # freq far above cutoff; order 9 → ratio^18. freq/cutoff > 10^18 overflows.
        mag = lowpass_butterworth_response(1e30, 1.0, order=9)
        assert mag == 0.0

    def test_highpass_extreme_inverted_ratio_saturates_to_zero(self):
        """HP with freq far below cutoff — ratio = cutoff/freq is extreme; saturates."""
        mag = highpass_butterworth_response(1e-30, 1.0, order=9)
        assert mag == 0.0

    def test_butterworth_moderate_ratio_still_correct(self):
        """Regression: ordinary usage still returns the standard Butterworth response."""
        # At cutoff, Butterworth is -3.0103 dB (magnitude = 1/sqrt(2)).
        mag = lowpass_butterworth_response(10e6, 10e6, order=5)
        assert mag == pytest.approx(1.0 / math.sqrt(2), abs=1e-9)


# ---------------------------------------------------------------------------
# #4 Sweep generators reject invalid point counts
# ---------------------------------------------------------------------------


class TestSweepGeneratorsRejectSmallPointCounts:
    def test_legacy_generate_frequency_points_rejects_one_point(self):
        with pytest.raises(ValueError, match=">= 2"):
            generate_frequency_points(10e6, num_points=1)

    def test_legacy_generate_frequency_points_rejects_zero_points(self):
        with pytest.raises(ValueError, match=">= 2"):
            generate_frequency_points(10e6, num_points=0)

    def test_legacy_generate_frequency_points_accepts_two_points(self):
        pts = generate_frequency_points(10e6, num_points=2)
        assert len(pts) == 2

    def test_bandpass_frequency_sweep_rejects_one_point(self):
        with pytest.raises(ValueError, match=">= 2"):
            frequency_sweep(14.175e6, 350e3, 3, "butterworth", points=1)

    def test_bandpass_generate_frequency_points_rejects_one_point(self):
        with pytest.raises(ValueError, match=">= 2"):
            bp_generate_frequency_points(14.175e6, 350e3, points=1)


# ---------------------------------------------------------------------------
# #5 NaN / inf rejected in validators
# ---------------------------------------------------------------------------


class TestValidatorsRejectNanInf:
    def test_lp_hp_cutoff_rejects_nan(self):
        from filter_lib.shared.lp_hp_base_calculations import _validate_lp_hp_inputs

        with pytest.raises(ValueError, match="finite"):
            _validate_lp_hp_inputs(float("nan"), 50.0, 3)

    def test_lp_hp_cutoff_rejects_inf(self):
        from filter_lib.shared.lp_hp_base_calculations import _validate_lp_hp_inputs

        with pytest.raises(ValueError, match="finite"):
            _validate_lp_hp_inputs(float("inf"), 50.0, 3)

    def test_lp_hp_impedance_rejects_nan(self):
        from filter_lib.shared.lp_hp_base_calculations import _validate_lp_hp_inputs

        with pytest.raises(ValueError, match="finite"):
            _validate_lp_hp_inputs(10e6, float("nan"), 3)

    def test_bandpass_rejects_nan_f0(self):
        with pytest.raises(ValueError, match="finite"):
            calculate_bandpass_filter(
                f0=float("nan"),
                bw=350e3,
                z0=50,
                n_resonators=3,
                filter_type="butterworth",
                coupling="top",
            )

    def test_bandpass_rejects_inf_bw(self):
        with pytest.raises(ValueError, match="finite"):
            calculate_bandpass_filter(
                f0=14.175e6,
                bw=float("inf"),
                z0=50,
                n_resonators=3,
                filter_type="butterworth",
                coupling="top",
            )

    def test_bandpass_rejects_nan_z0(self):
        with pytest.raises(ValueError, match="finite"):
            calculate_bandpass_filter(
                f0=14.175e6,
                bw=350e3,
                z0=float("nan"),
                n_resonators=3,
                filter_type="butterworth",
                coupling="top",
            )

    def test_generate_frequency_points_rejects_nan_f0(self):
        with pytest.raises(ValueError, match="finite"):
            generate_frequency_points(float("nan"))

    def test_bandpass_rejects_nan_q_safety(self):
        """Codex second-pass follow-up: q_safety NaN was previously silent."""
        with pytest.raises(ValueError, match="q_safety.*finite"):
            calculate_bandpass_filter(
                f0=14.175e6,
                bw=350e3,
                z0=50,
                n_resonators=3,
                filter_type="butterworth",
                coupling="top",
                q_safety=float("nan"),
            )

    def test_bandpass_rejects_inf_q_safety(self):
        with pytest.raises(ValueError, match="q_safety.*finite"):
            calculate_bandpass_filter(
                f0=14.175e6,
                bw=350e3,
                z0=50,
                n_resonators=3,
                filter_type="butterworth",
                coupling="top",
                q_safety=float("inf"),
            )

    def test_bandpass_chebyshev_rejects_nan_ripple(self):
        with pytest.raises(ValueError, match="ripple_db.*finite"):
            calculate_bandpass_filter(
                f0=14.175e6,
                bw=350e3,
                z0=50,
                n_resonators=3,
                filter_type="chebyshev",
                coupling="top",
                ripple_db=float("nan"),
            )

    def test_compute_bandpass_3db_edges_rejects_nan(self):
        from filter_lib.bandpass import compute_bandpass_3db_edges

        with pytest.raises(ValueError, match="finite"):
            compute_bandpass_3db_edges(float("nan"), 350e3)
        with pytest.raises(ValueError, match="finite"):
            compute_bandpass_3db_edges(14.175e6, float("inf"))

    def test_lowpass_chebyshev_rejects_nan_ripple(self):
        """Codex 3rd-pass follow-up: LP Chebyshev ripple_db needs the same guard as BP."""
        from filter_lib.lowpass import calculate_chebyshev

        with pytest.raises(ValueError, match="ripple_db.*finite"):
            calculate_chebyshev(10e6, 50.0, float("nan"), num_components=3, topology="pi")

    def test_lowpass_chebyshev_rejects_inf_ripple(self):
        from filter_lib.lowpass import calculate_chebyshev

        with pytest.raises(ValueError, match="ripple_db.*finite"):
            calculate_chebyshev(10e6, 50.0, float("inf"), num_components=3, topology="pi")

    def test_highpass_chebyshev_rejects_nan_ripple(self):
        from filter_lib.highpass import calculate_chebyshev

        with pytest.raises(ValueError, match="ripple_db.*finite"):
            calculate_chebyshev(10e6, 50.0, float("nan"), num_components=3, topology="t")


# ---------------------------------------------------------------------------
# #6 --verify uses real checks, not asserts
# ---------------------------------------------------------------------------


class TestVerifyCommandUsesRealChecks:
    def test_verify_runs_to_success(self, capsys):
        """_run_verification completes cleanly."""
        _run_verification()
        assert "Verification passed" in capsys.readouterr().out

    def test_verify_contains_no_assert_statements(self):
        """Belt-and-suspenders: source of _run_verification has no bare `assert`."""
        import inspect

        from filter_lib.cli import bandpass_cmd

        src = inspect.getsource(bandpass_cmd._run_verification)
        # Strip comments/docstrings crudely; look for an assert-keyword line.
        for line in src.splitlines():
            stripped = line.strip()
            if stripped.startswith("#") or stripped.startswith('"""'):
                continue
            assert not stripped.startswith("assert "), f"found assert: {line!r}"


# ---------------------------------------------------------------------------
# #7 ResultsScreen pre-selects export format from state
# ---------------------------------------------------------------------------


class TestResultsScreenPreselectsExportFormat:
    def _make_screen_with_state(self, export_format):
        screen = ResultsScreen()
        state = FilterState()
        state.export_format = export_format
        app = Mock()
        app.filter_state = state
        type(screen).app = property(lambda _self: app)  # type: ignore[misc]
        return screen

    def _mock_radio_set(self, buttons):
        rs = Mock(spec=RadioSet)
        rs.query = Mock(return_value=buttons)
        return rs

    def _make_button(self, btn_id):
        btn = Mock(spec=RadioButton)
        btn.id = btn_id
        btn.value = False
        return btn

    @pytest.mark.parametrize(
        "export_format, expected_target",
        [
            ("json", "export-json"),
            ("csv", "export-csv"),
            (None, "export-txt"),
        ],
    )
    def test_preselect_sets_correct_button(self, export_format, expected_target):
        screen = self._make_screen_with_state(export_format)
        buttons = [self._make_button(i) for i in ("export-txt", "export-json", "export-csv")]
        radio_set = self._mock_radio_set(buttons)
        screen.query_one = lambda *_a, **_k: radio_set  # type: ignore[assignment]

        screen._preselect_export_format()

        for btn in buttons:
            assert btn.value is (btn.id == expected_target)

    def test_preselect_swallows_lookup_error(self):
        """If the RadioSet isn't mounted yet, pre-select is a no-op."""
        screen = self._make_screen_with_state("json")

        def raising(*_a, **_k):
            raise LookupError("not mounted")

        screen.query_one = raising  # type: ignore[assignment]
        # No exception propagates
        screen._preselect_export_format()
