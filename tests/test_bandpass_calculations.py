"""Top-C bandpass synthesis: coupling math, resonators, loss estimates, and true -3 dB edges."""

import math
from decimal import Decimal
from fractions import Fraction

import pytest

from filter_lib.bandpass import calculate_bandpass_filter, compute_bandpass_3db_edges
from filter_lib.bandpass.calculations import (
    BANDPASS_EDGE_CALIBRATION_FBW_MAX,
    BANDPASS_LUMPED_MODEL_CAUTION_FBW,
    _synthesize_top_c_raw,
    calculate_coupling_capacitors,
    calculate_coupling_coefficients,
    calculate_end_coupling,
    calculate_external_q,
    calculate_min_q,
    calculate_resonator_components,
    calculate_tank_capacitors,
    combine_resonator_q,
    estimate_insertion_loss,
)
from filter_lib.bandpass.transfer import (
    chebyshev_3db_deviation,
    frequency_from_deviation,
    magnitude_bessel,
    magnitude_db,
)


class TestEndCoupling:
    """Series end-coupling capacitor sizing (realizes the external Q)."""

    def test_reference_design_values(self):
        """Butterworth n=3, f0=10 MHz, BW=1 MHz, Z0=50: Rp=500 Ω, Q=3, Ce ≈ 106.1 pF."""
        f0, z0 = 10e6, 50.0
        omega0 = 2 * math.pi * f0
        l_resonant = z0 / omega0
        qe = 1.0 / 0.1  # g1=1 (Butterworth n=3), fbw=10%
        ce, delta_c = calculate_end_coupling(qe, omega0, l_resonant, z0)
        assert ce == pytest.approx(106.1e-12, rel=0.001, abs=0)
        # Series-to-parallel conversion of the Z0–Ce branch: Cp = Ce·Q²/(1+Q²) with Q=3.
        assert delta_c == pytest.approx(ce * 9 / 10, rel=1e-12, abs=0)

    def test_transformation_identity(self):
        """Rp seen through the series cap equals Qe·ω0·L by construction."""
        f0, z0 = 14e6, 50.0
        omega0 = 2 * math.pi * f0
        l_resonant = z0 / omega0
        qe = 25.0
        ce, _ = calculate_end_coupling(qe, omega0, l_resonant, z0)
        q = 1 / (omega0 * z0 * ce)
        assert z0 * (1 + q * q) == pytest.approx(qe * omega0 * l_resonant, rel=1e-9)

    @pytest.mark.parametrize(
        "qe, q_squared_rel",
        [
            # Just above the Rp = Z0 limit, q² = Rp/Z0 − 1 is ill-conditioned: a 1e-15
            # rounding in Rp/Z0 is a 1e-6 relative change of q².
            (1.0 + 1e-9, 1e-5),
            (1.001, 1e-9),
            (1.2, 1e-9),
            (1.5, 1e-9),
            (1.999, 1e-9),
            (2.0, 1e-9),
            (2.001, 1e-9),
            (3.0, 1e-9),
            (25.0, 1e-9),
            (1e6, 1e-9),
        ],
    )
    def test_series_to_parallel_conversion_across_step_up_ratios(self, qe, q_squared_rel):
        """q² = Rp/Z0 − 1 and ΔC = Ce·q²/(1+q²) with q = 1/(ω0·Z0·Ce), including q < 1."""
        f0, z0 = 10e6, 50.0
        omega0 = 2 * math.pi * f0
        l_resonant = z0 / omega0  # makes Rp = qe * z0
        ce, delta_c = calculate_end_coupling(qe, omega0, l_resonant, z0)
        q = 1 / (omega0 * z0 * ce)
        assert q * q == pytest.approx(qe - 1.0, rel=q_squared_rel, abs=0)
        assert delta_c == pytest.approx(ce * q * q / (1 + q * q), rel=1e-9, abs=0)

    def test_low_step_up_reference_values(self):
        """Rp = 62.5 Ω from a 50 Ω port: q = 0.5, Ce = 636.62 pF, ΔC = Ce/5 = 127.32 pF."""
        f0, z0 = 10e6, 50.0
        omega0 = 2 * math.pi * f0
        ce, delta_c = calculate_end_coupling(1.25, omega0, z0 / omega0, z0)
        assert ce == pytest.approx(636.6197724e-12, rel=1e-9, abs=0)
        assert delta_c == pytest.approx(127.3239545e-12, rel=1e-9, abs=0)

    def test_infeasible_when_rp_at_or_below_z0(self):
        f0, z0 = 10e6, 50.0
        omega0 = 2 * math.pi * f0
        l_resonant = z0 / omega0  # makes Rp = qe * z0
        with pytest.raises(ValueError, match="too wide"):
            calculate_end_coupling(1.0, omega0, l_resonant, z0)
        with pytest.raises(ValueError, match="too wide"):
            calculate_end_coupling(0.5, omega0, l_resonant, z0)

    def test_result_dict_carries_symmetric_end_caps_and_retuned_tanks(self):
        result = calculate_bandpass_filter(10e6, 1e6, 50, 3, "butterworth", "top")
        assert result["c_end_in"] > 0
        assert result["c_end_in"] == pytest.approx(result["c_end_out"], rel=1e-12, abs=0)
        # End tanks are retuned (smaller than the symmetric middle tank)
        assert result["c_tank"][0] < result["c_tank"][1]
        assert result["c_tank"][-1] < result["c_tank"][1]
        assert result["c_tank"][0] == pytest.approx(result["c_tank"][-1], rel=1e-12, abs=0)


class TestCouplingAndExternalQ:
    """Cohn coupling k = FBW/sqrt(g_i·g_i+1) and equal-termination external Q = g/FBW."""

    @pytest.mark.parametrize(
        "g_values, fbw, expected_k, expected_qe",
        [
            # Butterworth n=3 prototype (1, 2, 1)
            ([1.0, 2.0, 1.0], 0.1, [0.0707106781, 0.0707106781], (10.0, 10.0)),
            ([1.0, 2.0, 1.0], 0.001, [7.071067812e-4, 7.071067812e-4], (1000.0, 1000.0)),
            ([1.0, 2.0, 1.0], 0.5, [0.3535533906, 0.3535533906], (2.0, 2.0)),
            # Asymmetric Bessel n=3 prototype: unequal couplings and end Q values
            ([0.3374, 0.9705, 2.2034], 0.05, [0.0873775162, 0.0341920832], (6.748, 44.068)),
        ],
    )
    def test_reference_values(self, g_values, fbw, expected_k, expected_qe):
        k_values = calculate_coupling_coefficients(g_values, fbw)
        qe_in, qe_out = calculate_external_q(g_values, fbw)

        assert k_values == pytest.approx(expected_k, rel=1e-9)
        assert (qe_in, qe_out) == pytest.approx(expected_qe, rel=1e-12)


class TestResonatorComponents:
    """Parallel tank L/C at f0 for the system, custom-impedance, or fixed-L choice."""

    def test_system_impedance_reference_values(self):
        """10 MHz, 50 Ω tank: L = Z0/ω0 = 795.77 nH, C = 1/(ω0·Z0) = 318.31 pF."""
        inductance, capacitance = calculate_resonator_components(10e6, 50)
        assert inductance == pytest.approx(795.7747155e-9, rel=1e-9, abs=0)
        assert capacitance == pytest.approx(318.3098862e-12, rel=1e-9, abs=0)

    @pytest.mark.parametrize(
        "choice, expected_reactance",
        [
            ({}, 50.0),
            ({"resonator_impedance": 200}, 200.0),
            ({"resonator_inductance": 2.2e-6}, 138.2300768),
        ],
    )
    def test_tank_resonates_at_f0_with_selected_reactance(self, choice, expected_reactance):
        f0 = 10e6
        inductance, capacitance = calculate_resonator_components(f0, 50, **choice)

        assert 1 / (2 * math.pi * math.sqrt(inductance * capacitance)) == pytest.approx(
            f0, rel=1e-12
        )
        assert math.sqrt(inductance / capacitance) == pytest.approx(expected_reactance, rel=1e-9)
        if "resonator_inductance" in choice:
            assert inductance == choice["resonator_inductance"]

    def test_resonator_choice_inputs_are_mutually_exclusive(self):
        with pytest.raises(ValueError, match="mutually exclusive"):
            calculate_resonator_components(
                10e6,
                50,
                resonator_impedance=100,
                resonator_inductance=1e-6,
            )

    @pytest.mark.parametrize(
        "f0, z0, choice, message",
        [
            (0.0, 50, {}, "f0 must be positive and finite"),
            (10e6, -50, {}, "z0 must be positive and finite"),
            (10e6, 50, {"resonator_impedance": 0.0}, "resonator_impedance must be positive"),
            (10e6, 50, {"resonator_inductance": math.nan}, "resonator_inductance must be positive"),
        ],
    )
    def test_rejects_invalid_resonator_inputs(self, f0, z0, choice, message):
        with pytest.raises(ValueError, match=message):
            calculate_resonator_components(f0, z0, **choice)


class TestCouplingAndTankCapacitors:
    """First-order Top-C capacitors: Cs = k·C and tanks compensated for attached Cs."""

    def test_coupling_capacitors_scale_resonant_capacitance(self):
        cs = calculate_coupling_capacitors([0.05, 0.04, 0.05], 100e-12)
        assert cs == pytest.approx([5e-12, 4e-12, 5e-12], rel=1e-12, abs=0)

    def test_single_resonator_has_no_coupling_capacitors(self):
        assert calculate_coupling_capacitors([], 100e-12) == []
        assert calculate_tank_capacitors(1, 100e-12, []) == [100e-12]

    def test_tank_capacitors_subtract_each_attached_coupling_capacitor(self):
        cp = calculate_tank_capacitors(3, 100e-12, [5e-12, 4e-12])
        # End tanks lose one coupling capacitor; the middle tank loses both.
        assert cp == pytest.approx([95e-12, 91e-12, 96e-12], rel=1e-12, abs=0)


class TestRawTopCSynthesis:
    """First-order Top-C values before calibration, worked by hand.

    Butterworth n=3 (g = 1, 2, 1), f0 = 10 MHz, FBW = 10%, 50 Ω ports:
    k = 0.1/√2, Cs = k·C, Qe = 10 so Rp = Qe·X_tank and q = √(Rp/50 − 1),
    Ce = 1/(ω0·50·q), ΔC = Ce·q²/(1+q²), Cp_end = C − Cs − ΔC, Cp_mid = C − 2·Cs.
    """

    @pytest.mark.parametrize(
        "tank_impedance, expected",
        [
            # X = 50 Ω: L = 795.775 nH, C = 318.310 pF, Rp = 500 Ω, q = 3.
            (
                None,
                {
                    "L_resonant": 795.7747155e-9,
                    "c_coupling": [22.50790790e-12] * 2,
                    "c_end_in": 106.1032954e-12,
                    "c_tank": [200.3090124e-12, 273.2940704e-12, 200.3090124e-12],
                },
            ),
            # X = 200 Ω: L = 3.1831 µH, C = 79.577 pF, Rp = 2000 Ω, q = √39.
            (
                200.0,
                {
                    "L_resonant": 3.183098862e-6,
                    "c_coupling": [5.626976976e-12] * 2,
                    "c_end_in": 50.97037441e-12,
                    "c_tank": [24.25437952e-12, 68.32351759e-12, 24.25437952e-12],
                },
            ),
        ],
    )
    def test_hand_worked_component_values(self, tank_impedance, expected):
        raw = _synthesize_top_c_raw(10e6, 0.1, 50.0, 3, [1.0, 2.0, 1.0], tank_impedance, None)

        for name, value in expected.items():
            assert raw[name] == pytest.approx(value, rel=1e-8, abs=0), name
        assert raw["c_end_out"] == raw["c_end_in"]
        assert (raw["qe_in"], raw["qe_out"]) == pytest.approx((10.0, 10.0), rel=1e-12)

    @pytest.mark.parametrize("fbw_synth", [0.0, -0.1, math.nan, math.inf, True])
    def test_rejects_invalid_prototype_bandwidth(self, fbw_synth):
        with pytest.raises(ValueError, match="fbw_synth must be positive and finite"):
            _synthesize_top_c_raw(10e6, fbw_synth, 50.0, 3, [1.0, 2.0, 1.0], None, None)


class TestSynthesisRealizabilityLimits:
    """Designs that cannot be built fail with the specific limiting component."""

    def test_chebyshev_ripple_above_ceiling_rejected(self):
        with pytest.raises(ValueError, match="at most 3.0 dB"):
            calculate_bandpass_filter(10e6, 0.5e6, 50, 3, "chebyshev", "top", ripple_db=3.5)

    @pytest.mark.parametrize(
        "bw, choice, message",
        [
            # 90% FBW: coupling capacitors alone exceed the tank capacitance.
            (9e6, {}, "derived tank capacitances must be positive"),
            # A 440 Ω tank at 10% FBW: end-coupling compensation empties both end tanks.
            (1e6, {"resonator_impedance": 440}, "tank capacitors Cp1, Cp3 would be negative"),
        ],
    )
    def test_negative_tank_capacitance_is_rejected(self, bw, choice, message):
        with pytest.raises(ValueError, match=message):
            calculate_bandpass_filter(10e6, bw, 50, 3, "butterworth", "top", **choice)

    def test_tank_impedance_just_inside_realizable_limit_still_calibrates(self):
        """Near the end-tank limit a forward calibration step is infeasible; the result
        must still calibrate to both requested edges with positive end tanks."""
        result = calculate_bandpass_filter(
            10e6, 1e6, 50, 3, "butterworth", "top", resonator_impedance=436.5
        )
        validation = result["synthesis_validation"]

        assert 0 < result["c_tank"][0] < 0.01 * result["C_resonant"]
        assert abs(validation["lower_edge_error_rel"]) <= 1e-3
        assert abs(validation["upper_edge_error_rel"]) <= 1e-3
        assert result["response_validation_status"] == "validated"


class TestInsertionLossAndQModel:
    """Cohn dissipation-loss estimate IL ≈ 4.343·Σg/(FBW_synth·Qu) dB and Q metadata."""

    def test_butterworth_n3_spot_value(self):
        """n=3 Butterworth (g = 1, 2, 1 → Σg = 4), FBW=5%, Qu=100 → 3.4744 dB."""
        assert estimate_insertion_loss([1.0, 2.0, 1.0], 0.05, 100.0) == pytest.approx(
            3.4744, rel=1e-12
        )

    @pytest.mark.parametrize(
        "g_values, fbw_synth, qu, message",
        [
            ([1.0, 2.0, 1.0], 0.05, 0.0, "Qu must be positive and finite"),
            ([1.0, 2.0, 1.0], 0.05, -1.0, "Qu must be positive and finite"),
            ([1.0, 2.0, 1.0], 0.05, math.inf, "Qu must be positive and finite"),
            ([1.0, 2.0, 1.0], 0.05, math.nan, "Qu must be positive and finite"),
            ([1.0, 2.0, 1.0], 0.0, 100.0, "fbw_synth must be positive and finite"),
            ([], 0.05, 100.0, "g_values must contain positive finite values"),
            ([1.0, -2.0, 1.0], 0.05, 100.0, "g_values must contain positive finite values"),
        ],
    )
    def test_invalid_estimate_inputs_rejected(self, g_values, fbw_synth, qu, message):
        with pytest.raises(ValueError, match=message):
            estimate_insertion_loss(g_values, fbw_synth, qu)

    def test_result_dict_standard_estimates(self):
        """il_estimates carries the standard Qu=100/250 entries; q_min unchanged."""
        result = calculate_bandpass_filter(10e6, 0.5e6, 50, 3, "butterworth", "top")
        assert set(result["il_estimates"]) == {"100", "250"}
        expected_100 = 4.343 * sum(result["g_values"]) / (result["fbw_synth"] * 100.0)
        assert result["il_estimates"]["100"] == pytest.approx(expected_100)
        # IL scales as 1/Qu
        assert result["il_estimates"]["250"] == pytest.approx(expected_100 * 100.0 / 250.0)
        assert result["q_min"] > 0

    def test_user_qu_adds_entry(self):
        result = calculate_bandpass_filter(10e6, 0.5e6, 50, 3, "butterworth", "top", qu=150.0)
        assert set(result["il_estimates"]) == {"100", "250", "150"}

    def test_user_qu_duplicate_of_standard_not_repeated(self):
        result = calculate_bandpass_filter(10e6, 0.5e6, 50, 3, "butterworth", "top", qu=100.0)
        assert set(result["il_estimates"]) == {"100", "250"}

    def test_user_qu_rendering_like_standard_keeps_standard_entry(self):
        """A user Qu whose "%g" rendering collides with a standard key must not
        overwrite the standard estimate or lose the separate user estimate."""
        result = calculate_bandpass_filter(
            10e6, 0.5e6, 50, 3, "butterworth", "top", qu=249.9999999999
        )
        assert set(result["il_estimates"]) == {"100", "250", "249.9999999999"}
        expected_250 = 4.343 * sum(result["g_values"]) / (result["fbw_synth"] * 250.0)
        assert result["il_estimates"]["250"] == pytest.approx(expected_250)
        expected_user = 4.343 * sum(result["g_values"]) / (result["fbw_synth"] * 249.9999999999)
        assert result["il_estimates"]["249.9999999999"] == pytest.approx(expected_user, rel=1e-14)

    def test_invalid_qu_in_calculate_rejected(self):
        with pytest.raises(ValueError, match="must be positive and finite"):
            calculate_bandpass_filter(10e6, 0.5e6, 50, 3, "butterworth", "top", qu=0.0)

    @pytest.mark.parametrize(
        "filter_type, ripple_db, ripple_to_3db_ratio",
        [
            ("butterworth", 0.5, 1.0),
            ("bessel", 0.5, 1.0),
            # Textbook 0.5 dB, n=3 Chebyshev: the -3 dB frequency is 1.1675× the ripple edge.
            ("chebyshev", 0.5, 1.1675),
        ],
    )
    def test_calibration_starts_from_prototype_ripple_bandwidth(
        self, filter_type, ripple_db, ripple_to_3db_ratio
    ):
        """bw is the true -3 dB bandwidth; Chebyshev starts from its narrower ripple band."""
        result = calculate_bandpass_filter(
            10e6, 0.5e6, 50, 3, filter_type, "top", ripple_db=ripple_db
        )
        assert result["fbw_synth_initial"] == pytest.approx(
            result["fbw"] / ripple_to_3db_ratio, rel=1e-4
        )

    def test_chebyshev_il_uses_fbw_synth(self):
        """IL is computed against the prototype-mapped FBW, not the user's -3 dB FBW."""
        result = calculate_bandpass_filter(10e6, 0.5e6, 50, 3, "chebyshev", "top", ripple_db=0.5)
        expected = 4.343 * sum(result["g_values"]) / (result["fbw_synth"] * 100.0)
        assert result["il_estimates"]["100"] == pytest.approx(expected)

    def test_separate_component_q_values_combine_as_resonator_q(self):
        assert combine_resonator_q(ql=200, qc=400) == pytest.approx(1 / (1 / 200 + 1 / 400))
        assert combine_resonator_q(ql=200) == 200
        assert combine_resonator_q(qc=400) == 400

    def test_component_q_combination_avoids_reciprocal_overflow(self):
        combined = combine_resonator_q(ql=1e-309, qc=1e-309)
        assert combined is not None and combined > 0
        assert combined == pytest.approx(5e-310, rel=1e-12, abs=0)

    def test_component_q_combination_rejects_unrepresentable_result(self):
        with pytest.raises(ValueError, match="too small to represent"):
            combine_resonator_q(ql=5e-324, qc=5e-324)

    def test_direct_qu_is_mutually_exclusive_with_component_q(self):
        with pytest.raises(ValueError, match="mutually exclusive"):
            combine_resonator_q(qu=100, ql=200)

    def test_min_q_heuristic_is_loaded_q_times_safety_factor(self):
        assert calculate_min_q(f0=14.175e6, bw=350e3, safety_factor=2.0) == pytest.approx(81.0)
        # The documented default safety factor is 2.0.
        assert calculate_min_q(f0=14.175e6, bw=350e3) == pytest.approx(81.0)

    def test_synthesis_defaults_are_half_db_ripple_and_safety_factor_two(self):
        result = calculate_bandpass_filter(14.175e6, 350e3, 50, 3, "chebyshev", "top")
        assert result["ripple_db"] == 0.5
        # Matthaei/Young/Jones 0.5 dB, n=3 prototype.
        assert result["g_values"] == pytest.approx([1.5963, 1.0967, 1.5963], abs=1e-4)
        assert result["q_safety"] == 2.0
        assert result["q_min"] == pytest.approx(81.0, rel=1e-12)

    @pytest.mark.parametrize("arguments", [(0.0, 1e3, 2.0), (1e6, math.inf, 2.0), (1e6, 1e3, -2)])
    def test_min_q_heuristic_rejects_invalid_inputs(self, arguments):
        with pytest.raises(ValueError, match="Q heuristic inputs must be positive and finite"):
            calculate_min_q(*arguments)

    def test_result_records_truthful_q_model(self):
        result = calculate_bandpass_filter(
            10e6,
            0.5e6,
            50,
            3,
            "butterworth",
            "top",
            ql=200,
            qc=400,
        )
        assert result["q_model"]["resonator_qu"] == pytest.approx(133.3333333333)
        assert result["q_model"]["definition"] == "complete_resonator_unloaded_q"
        assert result["q_model"]["combination"] == "reciprocal_component_loss_sum"
        assert result["q_model"]["inductor_ql"] == 200
        assert result["q_model"]["capacitor_qc"] == 400
        assert result["q_min_resonator"] == result["q_min"]
        assert result["q_min_is_heuristic"] is True
        assert result["q_safety_compatibility_only"] is True


class TestBandpass3dBEdges:
    """True -3 dB edges solve (f²−f0²)/(BW·f) = ±1; they are not f0 ± BW/2."""

    @pytest.mark.parametrize(
        "filter_type, order, tolerance_db",
        [
            ("butterworth", 3, 1e-9),
            ("butterworth", 9, 1e-9),
            ("chebyshev", 3, 1e-9),
            ("chebyshev", 9, 1e-9),
            # Bessel is normalized through its tabulated prototype, not a closed form.
            ("bessel", 2, 5e-4),
            ("bessel", 9, 5e-4),
        ],
    )
    @pytest.mark.parametrize(
        "f0, bw",
        [
            (1.0e6, 400e3),  # 40% fractional BW — arithmetic approx fails here
            (14.175e6, 350e3),  # narrow, typical HF bandpass
            (1e9, 20e6),  # very narrow
        ],
    )
    def test_ideal_responses_are_minus_3db_at_true_edges(
        self, f0, bw, filter_type, order, tolerance_db
    ):
        f_low, f_high = compute_bandpass_3db_edges(f0, bw)
        target_db = 10.0 * math.log10(0.5)
        for edge in (f_low, f_high):
            assert magnitude_db(edge, f0, bw, order, filter_type, 0.5) == pytest.approx(
                target_db, abs=tolerance_db
            )

    @pytest.mark.parametrize(
        "order, ripple_db, expected_ratio",
        [(3, 0.5, 1.1675), (5, 0.5, 1.0593), (3, 1.0, 1.0949)],
    )
    def test_chebyshev_ripple_edge_lies_inside_true_edges(self, order, ripple_db, expected_ratio):
        """Textbook -3 dB / ripple-edge ratios; the response equals -ripple at that edge."""
        ratio = chebyshev_3db_deviation(order, ripple_db)
        assert ratio == pytest.approx(expected_ratio, abs=1e-4)

        f0, bw = 14.175e6, 350e3
        for sign in (-1.0, 1.0):
            ripple_edge = frequency_from_deviation(sign / ratio, f0, bw)
            assert magnitude_db(ripple_edge, f0, bw, order, "chebyshev", ripple_db) == (
                pytest.approx(-ripple_db, abs=1e-9)
            )

    @pytest.mark.parametrize(
        "f0, bw", [(1e6, 400e3), (14.175e6, 350e3), (100e6, 10e6), (1e9, 20e6)]
    )
    def test_edges_span_bw_around_geometric_center(self, f0, bw):
        f_low, f_high = compute_bandpass_3db_edges(f0, bw)
        assert f_high - f_low == pytest.approx(bw, rel=1e-12)
        assert math.sqrt(f_low * f_high) == pytest.approx(f0, rel=1e-12)

    @pytest.mark.parametrize(
        "f0, bw, message",
        [
            (0, 100e3, "f0 must be positive and finite"),
            (math.nan, 100e3, "f0 must be positive and finite"),
            (math.inf, 100e3, "f0 must be positive and finite"),
            (1e6, 0, "bw must be positive and finite"),
            (1e6, -1, "bw must be positive and finite"),
            (1e6, math.nan, "bw must be positive and finite"),
            (1e6, math.inf, "bw must be positive and finite"),
            # Representable inputs whose upper edge overflows binary64.
            (1.7e308, 1.7e308, "must produce positive finite band edges"),
        ],
    )
    def test_rejects_inputs_without_finite_edges(self, f0, bw, message):
        with pytest.raises(ValueError, match=message):
            compute_bandpass_3db_edges(f0, bw)

    def test_no_catastrophic_cancellation_for_extreme_bw(self):
        """f_low must remain accurate even when bw >> 2*f0."""
        f0 = 1.0
        bw = 1e20  # Pathological: bw orders of magnitude larger than f0
        f_low, f_high = compute_bandpass_3db_edges(f0, bw)
        # Geometric invariant must hold exactly
        assert math.sqrt(f_low * f_high) == pytest.approx(f0, rel=1e-12)
        # f_low must be strictly positive, not crushed to 0 by cancellation
        assert f_low > 0

    def test_result_dict_uses_true_edges(self):
        """calculate_bandpass_filter propagates the correct -3 dB edges in the result."""
        result = calculate_bandpass_filter(
            f0=1e6,
            bw=400e3,
            z0=50,
            n_resonators=3,
            filter_type="butterworth",
            coupling="top",
        )
        expected_low, expected_high = compute_bandpass_3db_edges(1e6, 400e3)
        assert result["f_low"] == pytest.approx(expected_low, rel=1e-12)
        assert result["f_high"] == pytest.approx(expected_high, rel=1e-12)
        # Sanity: arithmetic shortcut would be 800 kHz / 1.2 MHz — these are not that
        assert abs(result["f_low"] - 800e3) > 10e3
        assert abs(result["f_high"] - 1.2e6) > 10e3

    def test_stays_finite_near_float_limit(self):
        f_low, f_high = compute_bandpass_3db_edges(1e308, 1e307)
        assert math.isfinite(f_low)
        assert math.isfinite(f_high)
        assert math.sqrt(f_low / f_high) * f_high == pytest.approx(1e308)

    @pytest.mark.parametrize(
        ("f0", "bw", "z0"),
        [(1e307, 1e305, 10.0), (3e307, 1e305, 1.0), (1e308, 1e307, 50.0)],
    )
    def test_filter_accepts_extreme_frequency_when_final_components_are_finite(self, f0, bw, z0):
        result = calculate_bandpass_filter(f0, bw, z0, 3, "butterworth", "top")

        component_values = [
            result["L_resonant"],
            result["C_resonant"],
            result["c_end_in"],
            result["c_end_out"],
            *result["c_tank"],
            *result["c_coupling"],
        ]
        assert all(math.isfinite(value) and value > 0 for value in component_values)

    def test_filter_rejects_frequency_that_cannot_make_finite_components(self):
        with pytest.raises(ValueError, match="numeric range"):
            calculate_bandpass_filter(1e308, 1e307, 1e308, 3, "butterworth", "top")


class TestInverseBandpassDeviation:
    """frequency_from_deviation inverts delta = (f²−f0²)/(BW·f) without cancellation."""

    @pytest.mark.parametrize(
        "delta, f0, bw",
        [
            (0.5, 10e6, 1e6),
            (-3.0, 10e6, 1e6),
            (4.0, 14.2e6, 142e3),
            (-4.0, 1.0, 1e20),
            # Shift ratio beyond binary64: the positive and negative asymptotic roots.
            (1e150, 1e-10, 1e150),
            (-1e300, 1e200, 1e300),
        ],
    )
    def test_round_trip_matches_exact_rational_deviation(self, delta, f0, bw):
        frequency = frequency_from_deviation(delta, f0, bw)
        exact = (Fraction(frequency) ** 2 - Fraction(f0) ** 2) / (
            Fraction(bw) * Fraction(frequency)
        )
        assert float(exact) == pytest.approx(delta, rel=1e-12)

    @pytest.mark.parametrize(
        "delta, f0, bw, message",
        [
            (math.nan, 1.0, 1.0, "delta must be finite"),
            (1.0, 0.0, 1.0, "f0 must be positive and finite"),
            (1.0, 1.0, math.inf, "bw must be positive and finite"),
            (1e300, 1e200, 1e300, "must produce a positive finite frequency"),
        ],
    )
    def test_rejects_inputs_without_finite_frequency(self, delta, f0, bw, message):
        with pytest.raises(ValueError, match=message):
            frequency_from_deviation(delta, f0, bw)

    def test_bessel_response_rejects_orders_without_tabulated_prototype(self):
        with pytest.raises(ValueError, match="Order must be between 2 and 9"):
            magnitude_bessel(10e6, 10e6, 1e6, 10)


class TestCalibratedBandpassSynthesis:
    @pytest.mark.parametrize("filter_type", ["butterworth", "bessel"])
    def test_monotonic_responses_do_not_mislabel_edge_variation_as_ripple(self, filter_type):
        result = calculate_bandpass_filter(10e6, 0.5e6, 50, 3, filter_type, "top")
        validation = result["synthesis_validation"]

        assert validation["measured_passband_variation_db"] > 0
        assert "measured_ripple_db" not in validation

    def test_chebyshev_validation_reports_measured_ripple_near_requested(self):
        result = calculate_bandpass_filter(10e6, 0.5e6, 50, 3, "chebyshev", "top", ripple_db=0.5)
        validation = result["synthesis_validation"]

        assert validation["measured_ripple_db"] == validation["measured_passband_variation_db"]
        assert validation["measured_ripple_db"] == pytest.approx(0.5, abs=0.2)

    def test_requested_and_internal_parameters_are_distinct_and_verified(self):
        result = calculate_bandpass_filter(10e6, 1e6, 50, 3, "chebyshev", "top", ripple_db=0.5)
        validation = result["synthesis_validation"]
        assert result["f_low"] != result["f_high"]
        assert result["f_tank_hz"] != pytest.approx(result["f0"], rel=1e-4)
        assert result["fbw_synth_initial"] != pytest.approx(result["fbw_synth"], rel=1e-4)
        assert result["requested_parameters"]["f0_hz"] == 10e6
        assert result["internal_synthesis_parameters"]["tank_frequency_hz"] == result["f_tank_hz"]
        assert abs(validation["lower_edge_error_rel"]) <= 1e-3
        assert abs(validation["upper_edge_error_rel"]) <= 1e-3
        assert validation["connected_region_count"] >= 1
        assert validation["iterations"] <= 12
        assert validation["calibration_converged"] is True
        assert validation["calibration_method"] == "bounded_log_newton"
        assert validation["calibration_tolerance"] == 2e-5
        assert validation["calibration_max_iterations"] == 12

    def test_fixed_l_survives_calibration(self):
        chosen_l = 1.8e-6
        result = calculate_bandpass_filter(
            10e6,
            0.5e6,
            50,
            3,
            "butterworth",
            "top",
            resonator_inductance=chosen_l,
        )
        assert result["L_resonant"] == chosen_l
        assert result["resonator_selection"] == "fixed_inductance"
        # A fixed inductor sets the tank reactance X = ω_tank·L = √(L/C) at the tuned frequency.
        reactance = 2 * math.pi * result["f_tank_hz"] * chosen_l
        assert result["resonator_impedance"] == pytest.approx(reactance, rel=1e-12)
        assert result["resonator_impedance"] == pytest.approx(
            math.sqrt(chosen_l / result["C_resonant"]), rel=1e-12
        )
        assert (
            result["internal_synthesis_parameters"]["resonator_impedance_ohms"]
            == (result["resonator_impedance"])
        )
        assert abs(result["synthesis_validation"]["lower_edge_error_rel"]) <= 1e-3
        assert abs(result["synthesis_validation"]["upper_edge_error_rel"]) <= 1e-3

    def test_custom_resonator_impedance_survives_calibration(self):
        result = calculate_bandpass_filter(
            10e6,
            0.5e6,
            50,
            3,
            "butterworth",
            "top",
            resonator_impedance=200,
        )
        assert result["resonator_selection"] == "fixed_impedance"
        assert result["resonator_impedance"] == pytest.approx(200)
        assert math.sqrt(result["L_resonant"] / result["C_resonant"]) == pytest.approx(200)
        assert result["internal_synthesis_parameters"]["resonator_impedance_ohms"] == 200
        assert abs(result["synthesis_validation"]["lower_edge_error_rel"]) <= 1e-3
        assert abs(result["synthesis_validation"]["upper_edge_error_rel"]) <= 1e-3

    @pytest.mark.parametrize(
        "filter_type, ripple_db, expected_ripple",
        [("butterworth", 0.5, None), ("bessel", 0.5, None), ("chebyshev", 0.25, 0.25)],
    )
    def test_ripple_is_reported_only_for_chebyshev(self, filter_type, ripple_db, expected_ripple):
        result = calculate_bandpass_filter(
            10e6, 0.5e6, 50, 3, filter_type, "top", ripple_db=ripple_db
        )
        assert result["filter_type"] == filter_type
        assert result["ripple_db"] == expected_ripple


class TestBandpassFbwGuidance:
    def test_public_guidance_boundaries_match_engine_contract(self):
        assert BANDPASS_EDGE_CALIBRATION_FBW_MAX == 0.10
        assert BANDPASS_LUMPED_MODEL_CAUTION_FBW == 0.40

    @pytest.mark.parametrize(
        "fbw, validation_warning, lumped_warning, percent",
        [
            (BANDPASS_EDGE_CALIBRATION_FBW_MAX, False, False, None),
            (BANDPASS_EDGE_CALIBRATION_FBW_MAX + 1e-6, True, False, "FBW 10.0%"),
            (BANDPASS_LUMPED_MODEL_CAUTION_FBW, True, False, "FBW 40.0%"),
            (BANDPASS_LUMPED_MODEL_CAUTION_FBW + 1e-6, True, True, "FBW 40.0%"),
        ],
    )
    def test_warning_boundaries_are_strict(self, fbw, validation_warning, lumped_warning, percent):
        result = calculate_bandpass_filter(10e6, 10e6 * fbw, 50, 3, "butterworth", "top")
        warnings = result["warnings"]
        assert (
            any("studied edge-calibration range" in warning for warning in warnings)
            is validation_warning
        )
        assert any("transmission-line design" in warning for warning in warnings) is lumped_warning
        # The warnings quote the requested fractional bandwidth as a percentage.
        assert all(warning.startswith(percent) for warning in warnings if "FBW" in warning)
        # Edges are calibrated at every width; only the studied envelope carries the claim.
        assert result["synthesis_validation"]["edge_validated"] is True
        assert result["synthesis_validation"]["validated"] is not validation_warning
        assert result["response_validation_status"] == (
            "outside_validated_envelope" if validation_warning else "validated"
        )
        if not validation_warning:
            assert warnings == []


class TestBandpassPublicInputValidation:
    """Public synthesis inputs reject wrong types and out-of-range values with clear errors."""

    @staticmethod
    def _arguments() -> dict:
        return {
            "f0": 10e6,
            "bw": 0.5e6,
            "z0": 50.0,
            "n_resonators": 3,
            "filter_type": "butterworth",
            "coupling": "top",
        }

    @pytest.mark.parametrize(
        "changes, message",
        [
            ({"f0": -1e6}, "Center frequency must be positive"),
            ({"bw": -100e3}, "Bandwidth must be positive"),
            ({"bw": 10e6}, "Bandwidth must be less than center frequency"),
            ({"z0": -50.0}, "Impedance must be positive"),
            ({"n_resonators": 1}, "integer between 2 and 9"),
            ({"n_resonators": 10}, "integer between 2 and 9"),
            ({"filter_type": "elliptic"}, "Filter type must be"),
            ({"coupling": "bottom"}, "Coupling must be 'top'"),
            ({"coupling": "shunt"}, "Shunt-C coupling has been removed"),
            ({"filter_type": "chebyshev", "n_resonators": 4}, "odd resonator count"),
        ],
    )
    def test_rejects_out_of_range_values(self, changes, message):
        arguments = self._arguments()
        arguments.update(changes)
        with pytest.raises(ValueError, match=message):
            calculate_bandpass_filter(**arguments)

    @pytest.mark.parametrize("n_resonators", [True, False, 3.0, 3.5, "3"])
    def test_rejects_non_integer_resonator_count(self, n_resonators):
        arguments = self._arguments()
        arguments["n_resonators"] = n_resonators
        with pytest.raises(ValueError, match="integer between 2 and 9"):
            calculate_bandpass_filter(**arguments)

    @pytest.mark.parametrize(
        "name,error",
        [
            ("q_safety", "q_safety"),
            ("qu", "Qu"),
            ("ql", "QL"),
            ("qc", "QC"),
            ("resonator_impedance", "resonator_impedance"),
            ("resonator_inductance", "resonator_inductance"),
        ],
    )
    def test_rejects_bool_advanced_numeric_input(self, name, error):
        arguments = self._arguments()
        arguments[name] = True
        with pytest.raises(ValueError, match=error):
            calculate_bandpass_filter(**arguments)

    @pytest.mark.parametrize(
        "name,error",
        [
            ("f0", "Center frequency"),
            ("bw", "Bandwidth"),
            ("z0", "Impedance"),
        ],
    )
    def test_rejects_bool_core_numeric_input(self, name, error):
        arguments = self._arguments()
        arguments[name] = True
        with pytest.raises(ValueError, match=error):
            calculate_bandpass_filter(**arguments)

    @pytest.mark.parametrize("value", [math.nan, math.inf], ids=["nan", "inf"])
    @pytest.mark.parametrize(
        "changes, message",
        [
            ({"f0": None}, "Center frequency must be positive and finite"),
            ({"bw": None}, "Bandwidth must be positive and finite"),
            ({"z0": None}, "Impedance must be positive and finite"),
            ({"q_safety": None}, "q_safety must be positive and finite"),
            (
                {"filter_type": "chebyshev", "ripple_db": None},
                "ripple_db must be positive and finite for Chebyshev",
            ),
        ],
        ids=["f0", "bw", "z0", "q_safety", "ripple_db"],
    )
    def test_rejects_non_finite_numeric_input(self, changes, message, value):
        arguments = self._arguments()
        arguments.update({name: value if new is None else new for name, new in changes.items()})
        with pytest.raises(ValueError, match=message):
            calculate_bandpass_filter(**arguments)

    def test_rejects_bool_chebyshev_ripple(self):
        arguments = self._arguments()
        arguments.update(filter_type="chebyshev", ripple_db=True)
        with pytest.raises(ValueError, match="ripple_db must be positive and finite"):
            calculate_bandpass_filter(**arguments)

    @pytest.mark.parametrize(
        "changes, message",
        [
            ({"f0": Decimal("1e7")}, "Center frequency"),
            ({"f0": Fraction(10**7)}, "Center frequency"),
            ({"f0": 1e7 + 0j}, "Center frequency"),
            ({"f0": "10e6"}, "Center frequency"),
            ({"z0": 10**400}, "Impedance"),
            ({"bw": 10.000001e6}, "less than center frequency"),
            ({"bw": math.nextafter(10e6, 0.0)}, "too wide to realize"),
            # Far below the float resolution of the band edges: any ValueError, not a crash.
            # (The current message names the internal grid rather than the bandwidth.)
            ({"bw": 1e-6}, "."),
            ({"f0": 1.7e308, "bw": 1.7e308 * 0.05}, "positive finite frequency"),
            ({"z0": 5e-324}, "numeric range"),
            ({"qu": 5e-324}, "numeric range"),
            ({"q_safety": 1e308}, "numeric range"),
            ({"resonator_impedance": 0.1}, "input/output coupling"),
            ({"resonator_inductance": 1e-3}, "would be negative"),
        ],
        ids=[
            "decimal",
            "fraction",
            "complex",
            "string",
            "huge-int-impedance",
            "bandwidth-above-center",
            "bandwidth-just-below-center",
            "sub-resolution-bandwidth",
            "overflowing-grid",
            "subnormal-impedance",
            "subnormal-q",
            "huge-q-safety",
            "tiny-tank-impedance",
            "huge-tank-inductance",
        ],
    )
    def test_hostile_inputs_raise_clear_value_errors(self, changes, message):
        arguments = self._arguments()
        arguments.update(changes)
        with pytest.raises(ValueError, match=message):
            calculate_bandpass_filter(**arguments)

    @pytest.mark.parametrize(
        "changes",
        [
            {"f0": 1e-300, "bw": 5e-302},
            {"f0": 1e300, "bw": 5e298},
            {"z0": 1e-300},
            {"z0": 1.7e308},
            {"bw": 1e-3},
            {"filter_type": "chebyshev", "n_resonators": 9, "ripple_db": 5e-324},
            {"qu": 1e-300},
            {"ql": 1e300, "qc": 1e300},
        ],
        ids=[
            "tiny-frequency",
            "huge-frequency",
            "tiny-impedance",
            "huge-impedance",
            "fbw-1e-10",
            "subnormal-ripple",
            "tiny-q",
            "huge-component-q",
        ],
    )
    def test_extreme_valid_inputs_give_finite_calibrated_results(self, changes):
        arguments = self._arguments()
        arguments.update(changes)
        result = calculate_bandpass_filter(**arguments)

        def non_finite(value, path="result"):
            if isinstance(value, float):
                return [] if math.isfinite(value) else [path]
            if isinstance(value, dict):
                return [bad for key, item in value.items() for bad in non_finite(item, key)]
            if isinstance(value, (list, tuple)):
                return [bad for item in value for bad in non_finite(item, path)]
            return []

        assert non_finite(result) == []
        assert result["synthesis_validation"]["edge_validated"] is True
        assert all(value > 0 for value in result["c_tank"] + result["c_coupling"])


class TestBandpassCompatibilityFacades:
    """Legacy calculation and transfer import surfaces remain available."""

    def test_calculations_facade_keeps_existing_names(self):
        from filter_lib.bandpass import calculations

        expected_names = (
            "math",
            "Any",
            "BandpassResult",
            "BANDPASS_EDGE_CALIBRATION_FBW_MAX",
            "BANDPASS_LUMPED_MODEL_CAUTION_FBW",
            "STANDARD_QU_VALUES",
            "calculate_coupling_coefficients",
            "calculate_external_q",
            "_resolve_resonator_components",
            "calculate_resonator_components",
            "calculate_coupling_capacitors",
            "calculate_tank_capacitors",
            "calculate_end_coupling",
            "combine_resonator_q",
            "estimate_insertion_loss",
            "calculate_min_q",
            "compute_bandpass_3db_edges",
            "_validate_inputs",
            "_get_fbw_warnings",
            "_synthesize_top_c_raw",
            "_calibrate_top_c",
            "calculate_bandpass_filter",
        )
        assert all(hasattr(calculations, name) for name in expected_names)

    def test_transfer_facade_keeps_existing_names(self):
        from filter_lib.bandpass import transfer

        expected_names = (
            "math",
            "Any",
            "lowpass_bessel_response",
            "chebyshev_polynomial",
            "magnitude_to_db",
            "BANDPASS_EDGE_CALIBRATION_FBW_MAX",
            "THREE_DB_DOWN",
            "EDGE_ERROR_LIMIT_REL",
            "PASSBAND_SHAPE_ERROR_LIMIT_DB",
            "CHEBYSHEV_RIPPLE_ALLOWANCE_DB",
            "STOPBAND_SAMPLE_ERROR_LIMIT_DB",
            "chebyshev_3db_deviation",
            "_bandpass_deviation",
            "frequency_from_deviation",
            "_deviation_grid",
            "measure_netlist_passband",
            "validate_netlist_shape",
            "magnitude_butterworth",
            "magnitude_chebyshev",
            "magnitude_bessel",
            "magnitude_db",
            "frequency_sweep",
            "netlist_frequency_sweep",
            "generate_frequency_points",
            "_log_sweep_frequencies",
            "frequency_response",
        )
        assert all(hasattr(transfer, name) for name in expected_names)
