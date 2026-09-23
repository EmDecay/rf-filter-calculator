"""E-series preferred-value matching and the builder-facing recommendation policy.

Raw search (``find_closest_single``/``find_parallel_combo``) returns the nearest
preferred values. ``match_component`` then applies the calculator policy: a single
part within 1 % wins, a parallel pair must improve the absolute error by at least
0.5 percentage points, and additive (capacitor) targets below 1 pF require an
explicit expert override. Expected values below are worked by hand from the
IEC 60063 tables.
"""

import math
import sys

import pytest

from filter_lib.shared.eseries import (
    DEFAULT_MATCH_POLICY,
    E_SERIES,
    MatchPolicy,
    find_closest_single,
    find_parallel_combo,
    match_component,
)

PF = 1e-12


class TestPreferredValueTables:
    @pytest.mark.parametrize(("series", "size"), [("E12", 12), ("E24", 24), ("E96", 96)])
    def test_series_is_one_strictly_increasing_decade(self, series, size):
        values = E_SERIES[series]

        assert len(values) == size
        assert values[0] == 1.0
        assert all(low < high for low, high in zip(values, values[1:]))
        assert values[-1] < 10.0

    def test_e12_and_e24_match_the_iec_60063_tables(self):
        """E24 is not the rounded geometric series: 2.7-4.7 and 8.2 are historical values."""
        iec_e24 = [
            1.0, 1.1, 1.2, 1.3, 1.5, 1.6, 1.8, 2.0, 2.2, 2.4, 2.7, 3.0,
            3.3, 3.6, 3.9, 4.3, 4.7, 5.1, 5.6, 6.2, 6.8, 7.5, 8.2, 9.1,
        ]  # fmt: skip

        assert E_SERIES["E24"] == iec_e24
        assert E_SERIES["E24"] != [round(10 ** (k / 24), 1) for k in range(24)]
        assert E_SERIES["E12"] == iec_e24[::2]

    def test_e96_is_the_three_digit_geometric_series(self):
        assert E_SERIES["E96"] == [round(10 ** (k / 96), 2) for k in range(96)]


class TestClosestSingle:
    @pytest.mark.parametrize("series", ["E12", "E24", "E96"])
    def test_every_preferred_value_matches_itself_in_any_decade(self, series):
        for decade in (-12, -6, 0, 3):
            for value in E_SERIES[series]:
                target = value * 10.0**decade
                matched, error = find_closest_single(target, series)
                assert matched == pytest.approx(target, rel=1e-12, abs=0)
                assert error == pytest.approx(0.0, abs=1e-9)

    @pytest.mark.parametrize(
        ("target_pf", "series", "expected_pf", "expected_error_pct"),
        [
            (108.0, "E24", 110.0, 1.851852),  # 110 is closer than 100 (-7.41 %)
            (95.0, "E24", 91.0, -4.210526),  # 91 is closer than 100 (+5.26 %)
            (123.0, "E12", 120.0, -2.439024),  # E12 has no 1.3
            (123.0, "E96", 124.0, 0.813008),  # E96 has no 1.20
            (347.0, "E12", 330.0, -4.899135),
            (347.0, "E24", 360.0, 3.746398),
            (347.0, "E96", 348.0, 0.288184),
        ],
    )
    def test_nearest_value_and_signed_error_relative_to_target(
        self, target_pf, series, expected_pf, expected_error_pct
    ):
        matched, error = find_closest_single(target_pf * PF, series)

        assert matched == pytest.approx(expected_pf * PF, rel=1e-12, abs=0)
        assert error == pytest.approx(expected_error_pct, abs=1e-6)

    @pytest.mark.parametrize(
        ("target_pf", "series", "expected_error_pct"),
        [
            (9.8, "E12", 2.040816),  # E12 tops out at 8.2 pF (-16.3 %) within the decade.
            (9.6, "E24", 4.166667),  # 9.1 pF is -5.21 %.
            (9.9, "E96", 1.010101),  # 9.76 pF is -1.41 %.
        ],
    )
    def test_next_decade_value_wins_near_upper_boundary(
        self, target_pf, series, expected_error_pct
    ):
        matched, error = find_closest_single(target_pf * PF, series)

        assert matched == pytest.approx(10 * PF, rel=1e-12, abs=0)
        assert error == pytest.approx(expected_error_pct, abs=1e-6)

    @pytest.mark.parametrize("target", [5e-324, 1e-320, 1e308])
    def test_extreme_preferred_values_match_exactly(self, target):
        assert find_closest_single(target, "E24") == (target, 0.0)

    def test_candidates_that_overflow_are_skipped(self):
        """At the float maximum the in-decade 1.8e308 is infinite, so 1.6e308 is chosen."""
        matched, error = find_closest_single(sys.float_info.max, "E24")

        assert matched == pytest.approx(1.6e308, rel=1e-12)
        assert error == pytest.approx(-10.997046, abs=1e-6)


_MATCHERS = {
    "single": lambda target, series: find_closest_single(target, series),
    "parallel": lambda target, series: find_parallel_combo(target, series, mode="additive"),
    "match": lambda target, series: match_component(target, series, parallel_mode="additive"),
}


class TestInputValidation:
    @pytest.mark.parametrize("target", [0, -1e-12, float("nan"), float("inf"), True, "1e-12", None])
    @pytest.mark.parametrize("matcher", sorted(_MATCHERS))
    def test_target_must_be_a_positive_finite_real(self, matcher, target):
        with pytest.raises(ValueError, match="positive and finite"):
            _MATCHERS[matcher](target, "E24")

    @pytest.mark.parametrize("series", ["E48", "e24", None, 24, []])
    @pytest.mark.parametrize("matcher", sorted(_MATCHERS))
    def test_series_must_be_e12_e24_or_e96(self, matcher, series):
        with pytest.raises(ValueError, match="Unknown series"):
            _MATCHERS[matcher](PF, series)

    @pytest.mark.parametrize("mode", [None, "auto", "series"])
    def test_parallel_mode_is_required(self, mode):
        """Component physics (sum vs reciprocal sum) cannot be inferred from a value."""
        with pytest.raises(ValueError, match="Mode is required"):
            find_parallel_combo(50 * PF, "E24", mode=mode)
        with pytest.raises(ValueError, match="Mode is required"):
            match_component(50 * PF, "E24", parallel_mode=mode)

    @pytest.mark.parametrize("mode", ["additive", "harmonic"])
    @pytest.mark.parametrize("ratio_limit", [0.5, True, "10", None, float("nan"), float("inf")])
    def test_ratio_limit_must_be_finite_and_at_least_one(self, mode, ratio_limit):
        with pytest.raises(ValueError, match="ratio_limit must be finite and >= 1"):
            find_parallel_combo(1e-9, "E24", mode=mode, ratio_limit=ratio_limit)

    @pytest.mark.parametrize("minimum_value", [0.0, -PF, float("nan"), True, "1e-12"])
    def test_minimum_part_value_must_be_positive_and_finite(self, minimum_value):
        with pytest.raises(ValueError, match="minimum_value must be positive and finite"):
            find_parallel_combo(PF, "E24", mode="additive", minimum_value=minimum_value)

    @pytest.mark.parametrize("policy", [0, object(), {"allow_sub_pf": True}])
    def test_match_component_requires_policy_instance(self, policy):
        with pytest.raises(ValueError, match="MatchPolicy"):
            match_component(PF, parallel_mode="additive", policy=policy)

    @pytest.mark.parametrize(
        ("field", "value"),
        [
            ("prefer_single_within_pct", True),
            ("prefer_single_within_pct", "1"),
            ("prefer_single_within_pct", -0.001),
            ("prefer_single_within_pct", float("inf")),
            ("min_parallel_improvement_pct_points", True),
            ("min_parallel_improvement_pct_points", -0.5),
            ("min_parallel_improvement_pct_points", float("nan")),
            ("minimum_capacitance_f", True),
            ("minimum_capacitance_f", 0.0),
            ("minimum_capacitance_f", float("inf")),
            ("allow_sub_pf", 1),
            ("allow_sub_pf", None),
        ],
    )
    def test_policy_rejects_invalid_fields(self, field, value):
        with pytest.raises(ValueError, match=field):
            MatchPolicy(**{field: value})

    def test_zero_single_part_window_is_allowed_and_always_considers_a_pair(self):
        # 100 pF is +0.990 %, inside the default window; 24 pF + 75 pF = 99 pF is -0.020 %.
        policy = MatchPolicy(prefer_single_within_pct=0, min_parallel_improvement_pct_points=0)
        match = match_component(99.0197 * PF, "E24", parallel_mode="additive", policy=policy)

        assert match.recommended_kind == "parallel"
        assert match.parallel_value == pytest.approx(99 * PF, rel=1e-12, abs=0)


class TestParallelCombinations:
    def test_additive_pair_sums_to_target(self):
        """99 pF = 24 pF + 75 pF (or 43 + 56) exactly."""
        (low, high), value, error = find_parallel_combo(99 * PF, "E24", mode="additive")

        assert (low, high) in [
            pytest.approx((24 * PF, 75 * PF), rel=1e-12, abs=0),
            pytest.approx((43 * PF, 56 * PF), rel=1e-12, abs=0),
        ]
        assert value == pytest.approx(low + high, rel=1e-15, abs=0)
        assert value == pytest.approx(99 * PF, rel=1e-12, abs=0)
        assert error == pytest.approx(0.0, abs=1e-9)

    def test_harmonic_pair_combines_reciprocally(self):
        """0.75 uH = 1 uH || 3 uH = 1.2 uH || 2 uH = 1.5 uH || 1.5 uH exactly."""
        (low, high), value, error = find_parallel_combo(0.75e-6, "E24", mode="harmonic")

        assert low <= high
        assert low > 0.75e-6
        assert value == pytest.approx(low * high / (low + high), rel=1e-12, abs=0)
        assert value == pytest.approx(0.75e-6, rel=1e-12, abs=0)
        assert error == pytest.approx(0.0, abs=1e-9)

    @pytest.mark.parametrize(
        ("target", "mode"),
        [
            (11.0, "additive"),  # 1 + 10 = 11: E12 has no 11, and no other pair is exact.
            (10.0 / 11.0, "harmonic"),  # 1 || 10 = 10/11; 1.2 || 3.9 misses by +1 %.
        ],
    )
    def test_ratio_limit_is_inclusive_at_exactly_ten_to_one(self, target, mode):
        """Decade-0 parts make 10.0 / 1.0 exactly 10 in binary64, so the limit itself is tested."""
        (low, high), value, error = find_parallel_combo(target, "E12", mode=mode)

        assert (low, high) == (1.0, 10.0)
        assert value == pytest.approx(target, rel=1e-15, abs=0)
        assert error == pytest.approx(0.0, abs=1e-12)

    @pytest.mark.parametrize(
        ("target", "mode", "equal_part"),
        [
            (2.4, "additive", 1.2),  # 1.1 + 1.3 is also exact but unequal.
            (0.75e-6, "harmonic", 1.5e-6),  # 1 uH || 3 uH is also exact but unequal.
        ],
    )
    def test_ratio_limit_of_one_allows_only_equal_parts(self, target, mode, equal_part):
        (low, high), value, error = find_parallel_combo(target, "E24", mode=mode, ratio_limit=1)

        assert (low, high) == pytest.approx((equal_part, equal_part), rel=1e-12, abs=0)
        assert value == pytest.approx(target, rel=1e-12, abs=0)
        assert error == pytest.approx(0.0, abs=1e-9)

    def test_harmonic_minimum_part_value_is_inclusive(self):
        """0.75 = 1.5 || 1.5; 1 || 3 and 1.2 || 2 use parts below the 1.5 floor."""
        pair, value, error = find_parallel_combo(0.75, "E24", mode="harmonic", minimum_value=1.5)

        assert pair == (1.5, 1.5)
        assert value == pytest.approx(0.75, rel=1e-15, abs=0)
        assert error == pytest.approx(0.0, abs=1e-12)

    def test_ratio_limit_excludes_wider_pairs(self):
        """99.2 pF is exactly 8.2 pF + 91 pF, a spread of 11.1 that the default limit forbids."""
        (low, high), value, error = find_parallel_combo(
            99.2 * PF, "E24", mode="additive", ratio_limit=12
        )
        assert (low, high) == pytest.approx((8.2 * PF, 91 * PF), rel=1e-12, abs=0)
        assert error == pytest.approx(0.0, abs=1e-9)

        (low, high), value, error = find_parallel_combo(99.2 * PF, "E24", mode="additive")
        assert high / low <= 10
        assert value == pytest.approx(99 * PF, rel=1e-12, abs=0)
        assert error == pytest.approx(-0.201613, abs=1e-6)

    @pytest.mark.parametrize(
        ("target", "mode", "minimum_value"),
        [(PF, "additive", 1e-9), (1e-6, "harmonic", 1e-3)],
    )
    def test_no_pair_when_every_candidate_is_below_minimum(self, target, mode, minimum_value):
        assert find_parallel_combo(target, "E24", mode=mode, minimum_value=minimum_value) is None

    @pytest.mark.parametrize(
        ("target", "mode", "minimum_value", "expected_pair"),
        [
            # 0.62 pF + 0.75 pF would be exact; the smallest legal sum is 1 + 1 pF.
            (1.37 * PF, "additive", PF, (PF, PF)),
            # 1.3 uH || 3 uH is within 0.33 %, but 1.3 uH is below the floor.
            (0.91e-6, "harmonic", 1.5e-6, (1.8e-6, 1.8e-6)),
        ],
    )
    def test_minimum_part_value_applies_to_both_parts(
        self, target, mode, minimum_value, expected_pair
    ):
        unconstrained = find_parallel_combo(target, "E24", mode=mode)
        assert min(unconstrained[0]) < minimum_value

        pair, _, _ = find_parallel_combo(target, "E24", mode=mode, minimum_value=minimum_value)
        assert pair == pytest.approx(expected_pair, rel=1e-12, abs=0)

    def test_harmonic_search_skips_companions_beyond_float_range(self):
        """Every companion needed to reach 1e308 in parallel overflows, so there is no pair."""
        assert find_parallel_combo(1e308, "E24", mode="harmonic") is None

    def test_harmonic_pair_value_survives_reciprocal_overflow(self):
        """1/v overflows for subnormal parts, which once collapsed the pair to 0.0 (-100 %)."""
        target = 1e-310
        (low, high), value, error = find_parallel_combo(target, "E24", mode="harmonic")

        scale = 1e300
        scaled_low, scaled_high = low * scale, high * scale
        expected = scaled_low * scaled_high / (scaled_low + scaled_high) / scale
        assert value > 0
        assert value == pytest.approx(expected, rel=1e-12, abs=0)
        assert error == pytest.approx((value - target) / target * 100, rel=1e-12, abs=0)
        assert abs(error) < 5

        match = match_component(target, "E24", parallel_mode="harmonic")
        assert match.raw_parallel_improvement_pct_points == pytest.approx(
            abs(match.single_error_pct) - abs(error), rel=1e-12, abs=0
        )
        assert match.raw_parallel_improvement_pct_points > -5


class TestRecommendationPolicy:
    def test_default_policy_contract(self):
        assert DEFAULT_MATCH_POLICY == MatchPolicy(
            prefer_single_within_pct=1.0,
            min_parallel_improvement_pct_points=0.5,
            minimum_capacitance_f=1e-12,
            allow_sub_pf=False,
        )

    def test_single_part_within_one_percent_wins_even_when_a_pair_is_better(self):
        # 100 pF is +0.990 %; 24 pF + 75 pF = 99 pF would be -0.020 %.
        match = match_component(99.0197 * PF, "E24", parallel_mode="additive")

        assert match.single_error_pct == pytest.approx(0.990005, abs=1e-6)
        assert match.parallel_improvement_pct_points == pytest.approx(0.970110, abs=1e-6)
        assert match.recommended_kind == "single"
        assert match.recommendation_reason == "single_within_preferred_error"
        assert match.prefers_parallel is False
        assert match.selected_components == (match.single_value,)
        assert match.parallel is None and match.parallel_value is None

    def test_single_part_just_outside_one_percent_yields_to_a_better_pair(self):
        # 100 pF is +1.010 %; 24 pF + 75 pF = 99 pF is -0.0001 %.
        match = match_component(99.0001 * PF, "E24", parallel_mode="additive")

        assert match.single_error_pct == pytest.approx(1.009999, abs=1e-6)
        assert match.recommended_kind == "parallel"
        assert match.recommendation_reason == "parallel_materially_improves_error"
        assert match.prefers_parallel is True
        assert match.selected_value == match.parallel_value
        assert match.parallel_value == pytest.approx(99 * PF, rel=1e-12, abs=0)
        assert match.selected_components == match.parallel

    @pytest.mark.parametrize(
        ("target_pf", "improvement", "kind", "reason"),
        [
            # 240 pF is +1.0952 %; 36 pF + 200 pF = 236 pF is -0.5897 %.
            (237.40, 0.505476, "parallel", "parallel_materially_improves_error"),
            # 240 pF is +1.0909 %; 236 pF is -0.5939 %.
            (237.41, 0.497030, "single", "parallel_improvement_below_policy_threshold"),
        ],
    )
    def test_pair_must_improve_absolute_error_by_half_a_percentage_point(
        self, target_pf, improvement, kind, reason
    ):
        match = match_component(target_pf * PF, "E24", parallel_mode="additive")

        assert match.parallel_improvement_pct_points == pytest.approx(improvement, abs=1e-6)
        assert match.recommended_kind == kind
        assert match.recommendation_reason == reason
        if kind == "single":
            assert match.parallel is None
            assert match.parallel_value is None
            assert match.parallel_error_pct is None
        else:
            assert match.parallel == pytest.approx((36 * PF, 200 * PF), rel=1e-12, abs=0)

    def test_policy_thresholds_are_inclusive(self):
        """A reported error or improvement exactly at a threshold satisfies it."""
        reference = match_component(138.8 * PF, "E24", parallel_mode="additive")
        single_error = abs(reference.single_error_pct)
        improvement = reference.parallel_improvement_pct_points

        def kind(**policy_fields):
            policy = MatchPolicy(**policy_fields)
            return match_component(
                138.8 * PF, "E24", parallel_mode="additive", policy=policy
            ).recommended_kind

        assert kind(prefer_single_within_pct=single_error) == "single"
        assert kind(prefer_single_within_pct=math.nextafter(single_error, 0)) == "parallel"
        assert kind(min_parallel_improvement_pct_points=improvement) == "parallel"
        assert (
            kind(min_parallel_improvement_pct_points=math.nextafter(improvement, math.inf))
            == "single"
        )

    @pytest.mark.parametrize(
        ("mode", "expected_pair_pf", "expected_error_pct"),
        [
            ("additive", (39.0, 100.0), 0.144092),  # 39 + 100 = 139 pF
            ("harmonic", (240.0, 330.0), 0.106173),  # 240 || 330 = 138.947 pF
        ],
    )
    def test_materially_better_pair_is_selected(self, mode, expected_pair_pf, expected_error_pct):
        # The single 130 pF part is -6.340 % from 138.8 pF.
        match = match_component(138.8 * PF, "E24", parallel_mode=mode)

        assert match.single_value == pytest.approx(130 * PF, rel=1e-12, abs=0)
        assert match.single_error_pct == pytest.approx(-6.340058, abs=1e-6)
        assert match.recommended_kind == "parallel"
        assert match.parallel == pytest.approx(
            tuple(v * PF for v in expected_pair_pf), rel=1e-12, abs=0
        )
        assert match.parallel_error_pct == pytest.approx(expected_error_pct, abs=1e-6)

    @pytest.mark.parametrize("scale", [1e-12, 1e-9, 1e-6])
    def test_recommendation_is_decade_invariant(self, scale):
        match = match_component(138.8 * scale, "E24", parallel_mode="additive")

        assert match.recommended_kind == "parallel"
        assert match.single_error_pct == pytest.approx(-6.340058, abs=1e-6)
        assert match.parallel == pytest.approx((39 * scale, 100 * scale), rel=1e-12, abs=0)

    def test_one_picofarad_is_automatically_selectable(self):
        match = match_component(PF, "E24", parallel_mode="additive")

        assert match.status == "recommended"
        assert match.recommended_kind == "single"
        assert match.selected_components == (PF,)
        assert match.warnings == ()

    @pytest.mark.parametrize("target", [math.nextafter(PF, 0), 0.62 * PF, 5e-324])
    def test_capacitance_below_one_picofarad_requires_expert_override(self, target):
        match = match_component(target, "E24", parallel_mode="additive")

        assert match.status == "expert_override_required"
        assert match.recommended_kind == "none"
        assert match.recommendation_reason == "target_below_automatic_capacitance_floor"
        assert match.selected_value is None
        assert match.selected_components is None
        assert match.best_value == target  # exact target, never a disallowed part
        assert match.parallel is None
        assert "below the 1 pF automatic-selection floor" in " ".join(match.warnings)

    def test_capacitance_floor_applies_only_to_additive_matching(self):
        match = match_component(0.62 * PF, "E24", parallel_mode="harmonic")

        assert match.status == "recommended"
        assert match.recommended_kind == "single"
        assert match.selected_value == pytest.approx(0.62 * PF, rel=1e-12, abs=0)

    def test_default_floor_excludes_sub_pf_parts_from_pairs(self):
        """1.37 pF = 0.62 pF + 0.75 pF, but every pair of >= 1 pF parts sums to >= 2 pF."""
        default = match_component(1.37 * PF, "E24", parallel_mode="additive")
        assert default.recommended_kind == "single"
        assert default.selected_value == pytest.approx(1.3 * PF, rel=1e-12, abs=0)
        assert default.recommendation_reason == "parallel_improvement_below_policy_threshold"

        expert = match_component(
            1.37 * PF, "E24", parallel_mode="additive", policy=MatchPolicy(allow_sub_pf=True)
        )
        assert expert.recommended_kind == "parallel"
        assert expert.parallel == pytest.approx((0.62 * PF, 0.75 * PF), rel=1e-12, abs=0)

    def test_expert_override_selects_a_sub_pf_single_part(self):
        match = match_component(
            0.62 * PF, "E24", parallel_mode="additive", policy=MatchPolicy(allow_sub_pf=True)
        )

        assert match.status == "recommended"
        assert match.recommended_kind == "single"
        assert match.selected_value == pytest.approx(0.62 * PF, rel=1e-12, abs=0)

    def test_pair_search_skips_overflowing_candidates_at_float_maximum(self):
        match = match_component(sys.float_info.max, "E24", parallel_mode="additive")

        assert match.recommended_kind == "parallel"
        assert match.parallel == pytest.approx((1.8e307, 1.6e308), rel=1e-12)
        assert math.isfinite(match.parallel_value)
        assert match.parallel_error_pct == pytest.approx(-0.984213, abs=1e-6)

    def test_policy_summary_describes_thresholds_and_floor(self):
        assert DEFAULT_MATCH_POLICY.summary() == (
            "single<=1%;parallel-improvement>=0.5pp;minimum-cap=1pF"
        )
        expert = MatchPolicy(
            prefer_single_within_pct=2.5, min_parallel_improvement_pct_points=0, allow_sub_pf=True
        )
        assert expert.summary() == "single<=2.5%;parallel-improvement>=0pp;minimum-cap=disabled"
        assert expert.as_dict() == {
            "prefer_single_within_pct": 2.5,
            "min_parallel_improvement_pct_points": 0,
            "minimum_capacitance_f": 1e-12,
            "allow_sub_pf": True,
        }
