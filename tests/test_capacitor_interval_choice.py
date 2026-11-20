"""Standard capacitors chosen by their worst case within tolerance.

The expected choices come from ``tests/capacitor_interval_oracle.py``, a plain brute force
written from the evidence page, never from production code. Rows assumed there: the
series makes 0.5–9.9 pF in 0.1 pF steps and E24 values from 10 pF to 10 nF; standard
grade ±0.1/±0.25/±0.5 pF below 10 pF and ±5% from 10 pF; tight grade ±0.05/±0.1/±0.25 pF,
±2% to 910 pF and ±5% from 1 nF.
"""

from __future__ import annotations

import json
import random
import re
from fractions import Fraction

import pytest

from filter_lib.shared import capacitor_choice
from filter_lib.shared.capacitor_choice import pair_wins, part_tolerance_pf
from filter_lib.shared.eseries import (
    DEFAULT_MATCH_POLICY,
    TOLERANCE_NOT_SOURCED,
    MatchPolicy,
    match_component,
)
from filter_lib.shared.formatting import format_capacitance
from tests.capacitor_interval_oracle import best_choice
from tests.cli_parity_helpers import cli_stdout

PF = 1e-12
F = Fraction


def _choice(target_pf: str | Fraction, series: str = "E24", **policy) -> tuple:
    """Production's ``(parts in pF, score in pF)`` for ``target_pf``."""
    target = F(target_pf) if isinstance(target_pf, str) else target_pf
    match = match_component(
        float(target) * PF, series, parallel_mode="additive", policy=MatchPolicy(**policy)
    )
    parts = tuple(F(repr(value)) * 10**12 for value in match.selected_components)
    return parts, match


# -- Acceptance criterion 2 ------------------------------------------------------------


@pytest.mark.parametrize(
    ("grade", "parts", "score"),
    [
        # 13 pF scores 1.1244 pF standard and 0.7344 pF tight; the pairs win.
        ("standard", ("4.3", "9.1"), "0.8756"),
        ("tight", ("2.4", "11"), "0.4456"),
    ],
)
def test_criterion_two_example_chooses_the_exhaustive_search_winner(grade, parts, score):
    target = F("13.4744")
    expected_parts, expected_score = best_choice(target, grade=grade)

    chosen, match = _choice(target, grade=grade)

    assert expected_parts == tuple(F(part) for part in parts)
    assert expected_score == F(score)
    assert chosen == expected_parts
    assert match.worst_case_error_f == pytest.approx(float(expected_score) * PF, rel=1e-12)
    assert match.status == "recommended" and match.tolerance_sourced is True


@pytest.mark.parametrize(
    "policy_flags",
    [
        ("--capacitor-grade", "tight"),
        (
            "--capacitor-grade",
            "tight",
            "--capacitor-tolerance",
            "3",
            "--stray-capacitance",
            "0.1pF",
        ),
    ],
    ids=["tight", "tight-override-stray"],
)
def test_one_choice_reaches_the_table_json_csv_build_and_spice(monkeypatch, capsys, policy_flags):
    """The 13.47 pF capacitor gets the same parts in every output of the CLI."""
    argv = ("lp", "bw", "pi", "146MHz", "-n", "5", *policy_flags)
    table = cli_stdout(monkeypatch, capsys, *argv)
    document = json.loads(cli_stdout(monkeypatch, capsys, *argv, "--format", "json"))
    csv_row = cli_stdout(monkeypatch, capsys, *argv, "--format", "csv").splitlines()[1]
    build = json.loads(
        cli_stdout(
            monkeypatch, capsys, *argv, "--format", "json", "--sim-build", "--analysis-points", "51"
        )
    )
    deck = cli_stdout(monkeypatch, capsys, *argv, "--format", "spice")

    selected = document["components"]["capacitors"][0]["standard_match"]["selected"]
    parts = [part["value_farads"] for part in selected["components"]]
    target = F(document["components"]["capacitors"][0]["value_farads"]) * 10**12
    override = F(policy_flags[3]) if len(policy_flags) > 2 else None
    stray = F("0.1") if len(policy_flags) > 2 else F(1, 5)
    expected, _score = best_choice(target, grade="tight", stray_pf=stray, override_pct=override)
    assert [F(repr(value)) * 10**12 for value in parts] == list(expected)
    shown = " || ".join(format_capacitance(value) for value in parts)
    assert re.search(rf"C1 calculated 13\.47 pF\n  Use: +{re.escape(shown)}", table)
    assert "tight grade" in table and "Murata GRM1885C1H…A01" in table
    if override is not None:
        assert "Tolerance: the larger of ±3% and the tight grade" in table
    assert shown in csv_row and "grade=tight" in csv_row
    assert build["nominal_build"]["substitutions"][0]["physical_parts_si"] == parts
    for suffix, value in zip("AB", parts, strict=False):
        assert re.search(rf"^C1{suffix if len(parts) > 1 else ''} 1 0 {value:.12g}$", deck, re.M)
    if len(parts) > 1:
        assert re.search(rf"^CSTRAY_C1 1 0 {float(stray) * 1e-12:.12g}$", deck, re.M)


# -- Agreement with the independent brute force ------------------------------------------

_RANDOM = random.Random(20261119)
# Targets across the sourced range, rounded to 0.01 pF so the oracle works in exact pF.
_TARGETS = sorted(
    {F(round(10 ** _RANDOM.uniform(0, 4), 2)).limit_denominator(100) for _ in range(24)}
)
_CONFIGS = [
    {"series": "E24", "grade": "standard"},
    {"series": "E24", "grade": "tight", "stray_capacitance_f": 0.0},
    {"series": "E12", "grade": "standard", "tolerance_override_pct": 3.0},
]


@pytest.mark.parametrize("config", _CONFIGS, ids=["e24-standard", "e24-tight-no-stray", "e12-3pct"])
def test_choices_equal_the_brute_force_for_many_targets(config):
    series = config["series"]
    policy = {key: value for key, value in config.items() if key != "series"}
    override = policy.get("tolerance_override_pct")
    stray = F(repr(policy.get("stray_capacitance_f", 0.2e-12))) * 10**12
    for decimal_target in _TARGETS:
        # The binary value production receives: a decimal tie need not be a tie in it.
        target = F(float(decimal_target) * PF) * 10**12
        expected_parts, expected_score = best_choice(
            target,
            series=series,
            grade=policy["grade"],
            stray_pf=stray,
            override_pct=None if override is None else F(repr(override)),
        )
        chosen, match = _choice(target, series, **policy)
        if match.status == TOLERANCE_NOT_SOURCED:
            # The nominal rule chose a part the series does not make (an E12 target's
            # nearest value is always made, so this only happens outside the range).
            assert not 1 <= target <= 10000, target
            continue
        assert chosen == expected_parts, target
        assert match.worst_case_error_f == pytest.approx(float(expected_score) * PF, rel=1e-12)
        assert max(chosen) <= 10 * min(chosen)


# -- Tie-breaks, margin, ratio, floor ---------------------------------------------------


def test_equal_single_scores_go_to_the_lower_value():
    """4.5 pF: 4.3 pF and 4.7 pF (both ±0.25 pF) score 0.45 pF; 4.3 pF wins."""
    chosen, match = _choice("4.5")

    assert chosen == (F("4.3"),)
    assert match.worst_case_error_f == pytest.approx(0.45 * PF, rel=1e-12)


def test_equal_pair_scores_go_to_the_smaller_ratio_then_the_lower_total():
    candidates = [
        (F("1.0"), F(1, 4)),
        (F("1.3"), F(1, 4)),
        (F("3.0"), F(1, 4)),
        (F("3.3"), F(1, 4)),
    ]
    # 1.0 + 3.3 and 1.3 + 3.0 both total 4.3 pF with ±0.5 pF: the 1.3 + 3.0 pair is balanced.
    best = capacitor_choice._best_pair(candidates, F("4.3"), F(1), 10.0, DEFAULT_MATCH_POLICY)

    assert best[3][0] == F("1.3") and best[4][0] == F("3.0")


def test_a_pair_needs_half_a_point_better_and_the_margin_is_inclusive():
    target = F(100)
    # Exactly 0.5 percentage points of 100 pF is 0.5 pF.
    assert pair_wins(F(2), F("1.5"), target, F(1, 2))
    assert not pair_wins(F(2), F("1.5") + F(1, 10**9), target, F(1, 2))

    # 13.4744 pF: 13 pF scores 1.1244 pF, 4.3 + 9.1 pF 0.8756 pF (1.84 points better).
    assert _choice("13.4744", min_parallel_improvement_pct_points=1.8)[1].prefers_parallel
    single = _choice("13.4744", min_parallel_improvement_pct_points=1.9)[1]
    assert single.recommended_kind == "single"
    assert single.recommendation_reason == "parallel_worst_case_improvement_below_policy_threshold"


def test_no_pair_is_wider_than_ten_to_one():
    for target in ("1.37", "10.7", "107", "1070"):
        chosen, _match = _choice(target)
        assert max(chosen) <= 10 * min(chosen), target


def test_sub_pf_targets_still_choose_no_part_without_the_switch():
    match = match_component(0.62 * PF, "E24", parallel_mode="additive")

    assert (match.status, match.selected_components) == ("expert_override_required", None)


def test_the_floor_keeps_sub_pf_parts_out_of_pairs():
    chosen, match = _choice("1.37")

    assert chosen == (F("1.3"),)
    assert match.recommendation_reason == "single_worst_case_is_best"


def test_an_ineligible_part_is_never_chosen(monkeypatch):
    """A part whose tolerance is not smaller than its value cannot be chosen."""
    real = capacitor_choice.sourced_tolerance_pf

    def one_picofarad_is_useless(value, grade):
        return F(1) if value == 1 else real(value, grade)

    monkeypatch.setattr(capacitor_choice, "sourced_tolerance_pf", one_picofarad_is_useless)

    chosen, _match = _choice("1.05")

    assert F(1) not in chosen
    assert chosen == (F("1.1"),)


# -- Tolerance override -------------------------------------------------------------


@pytest.mark.parametrize(
    ("value", "override", "expected"),
    [
        ("100", None, "5"),  # the grade: ±5%
        ("100", 3.0, "5"),  # tighter than the grade: the grade stays
        ("100", 5.0, "5"),  # at the crossover: equal
        ("100", 8.0, "8"),  # looser: the override
        ("4.3", 3.0, "0.25"),  # 3% is 0.129 pF, under the ±0.25 pF grade
        ("4.3", 10.0, "0.43"),  # 10% is 0.43 pF, over the grade
        ("5", 5.0, "0.25"),  # 5% of 5 pF is exactly the ±0.25 pF grade
        ("5", 6.0, "0.3"),
    ],
)
def test_override_is_the_larger_of_the_percentage_and_the_grade(value, override, expected):
    policy = MatchPolicy(tolerance_override_pct=override)

    assert part_tolerance_pf(F(value), policy) == pytest.approx(F(expected), rel=1e-12)


def test_override_reaches_the_chosen_parts_tolerances():
    match = match_component(
        100e-12, "E24", parallel_mode="additive", policy=MatchPolicy(tolerance_override_pct=8)
    )

    assert match.selected_components == (100e-12,)
    assert match.part_tolerances_f == pytest.approx((8e-12,), rel=1e-12)
    assert match.part_tolerance_fractions == (0.08,)


# -- Values the series does not make -----------------------------------------------------


@pytest.mark.parametrize(
    ("target", "series", "override", "fraction"),
    [
        (13.3e-12, "E96", None, 0.05),  # 13.3 pF: a three-digit value
        (22.7e-9, "E24", None, 0.05),  # above 10 nF
        (13.3e-12, "E96", 3.0, 0.03),  # the override replaces the assumed 5%
    ],
)
def test_values_the_series_does_not_make_keep_the_nominal_rule(target, series, override, fraction):
    policy = MatchPolicy(tolerance_override_pct=override)
    nominal = match_component(target, series, parallel_mode="harmonic")

    match = match_component(target, series, parallel_mode="additive", policy=policy)

    assert match.status == TOLERANCE_NOT_SOURCED
    assert match.tolerance_sourced is False
    assert match.worst_case_error_f is None
    assert set(match.part_tolerance_fractions) == {fraction}
    # The nominal rule's nearest single is the same for both kinds of matching.
    assert match.nearest_value == nominal.single_value


def test_inductor_matching_ignores_the_capacitor_policy():
    loose = MatchPolicy(grade="tight", tolerance_override_pct=20, stray_capacitance_f=1e-12)
    for target in (1.457e-6, 74.74e-9, 0.909e-6):
        default = match_component(target, "E24", parallel_mode="harmonic")
        other = match_component(target, "E24", parallel_mode="harmonic", policy=loose)
        assert (default.selected_components, default.status) == (
            other.selected_components,
            other.status,
        )
        assert default.part_tolerances_f is None
