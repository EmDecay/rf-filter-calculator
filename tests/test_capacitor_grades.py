"""The packaged capacitor grade table matches its evidence and refuses malformed data."""

from __future__ import annotations

import json
from fractions import Fraction
from importlib.resources import files

import pytest

from filter_lib.shared import capacitor_grades, packaged_data
from filter_lib.shared.capacitor_grades import (
    GRADE_NAMES,
    GRADES,
    SERIES,
    is_made,
    made_values_pf,
    require_grade,
    sourced_tolerance_pf,
    tolerance_rule_text,
)
from tests.capacitor_interval_oracle import tolerance as oracle_tolerance

F = Fraction


def test_series_is_the_one_the_evidence_page_records():
    assert SERIES.title == "Murata GRM1885C1H…A01"
    assert "C0G" in SERIES.description and "0603" in SERIES.description
    assert GRADE_NAMES == ("standard", "tight")


@pytest.mark.parametrize(
    ("value", "standard", "tight"),
    [
        # Rated-value lines read from the reference sheets (docs/component-data-sources.md).
        ("0.5", "0.1", "0.05"),
        ("0.9", "0.1", "0.05"),
        ("1", "0.25", "0.1"),
        ("4.3", "0.25", "0.1"),
        ("5", "0.25", "0.1"),
        ("5.1", "0.5", "0.25"),
        ("9.9", "0.5", "0.25"),
        ("10", "0.5", "0.2"),
        ("910", "45.5", "18.2"),
        ("1000", "50", "50"),
        ("10000", "500", "500"),
    ],
)
def test_tolerances_match_the_sourced_rows(value, standard, tight):
    assert sourced_tolerance_pf(F(value), "standard") == F(standard)
    assert sourced_tolerance_pf(F(value), "tight") == F(tight)


def test_every_made_value_has_one_tolerance_equal_to_the_independent_statement():
    values = made_values_pf()

    assert len(values) == 168  # 95 values from 0.5 to 9.9 pF, 73 E24 values from 10 pF
    assert values == tuple(sorted(values))
    for value in values:
        for grade in GRADE_NAMES:
            assert sourced_tolerance_pf(value, grade) == oracle_tolerance(value, grade), value


@pytest.mark.parametrize(
    ("value", "made"),
    [
        ("0.4", False),
        ("0.5", True),
        ("0.56", False),  # an E24 sub-pF value; the series steps by 0.1 pF
        ("1.02", False),  # a three-digit E96 value
        ("9.9", True),
        ("10", True),
        ("10.2", False),
        ("14", False),  # a two-digit value that is not E24
        ("9100", True),
        ("10000", True),
        ("11000", False),
        ("22000", False),
    ],
)
def test_coverage_is_the_values_with_a_current_sheet(value, made):
    assert is_made(F(value)) is made
    assert (sourced_tolerance_pf(F(value), "standard") is None) is not made


def test_no_part_has_a_tolerance_as_large_as_its_value():
    for value in made_values_pf():
        for grade in GRADE_NAMES:
            assert sourced_tolerance_pf(value, grade) < value


def test_tolerance_rule_text_names_each_range():
    assert tolerance_rule_text("standard") == (
        "±0.1 pF (0.5–0.9 pF), ±0.25 pF (1–5 pF), ±0.5 pF (5.1–9.9 pF), ±5% (10–10000 pF)"
    )
    assert tolerance_rule_text("tight") == (
        "±0.05 pF (0.5–0.9 pF), ±0.1 pF (1–5 pF), ±0.25 pF (5.1–9.9 pF), ±2% (10–910 pF), "
        "±5% (1000–10000 pF)"
    )


def test_every_row_is_a_guaranteed_limit_with_a_read_sheet():
    data = json.loads(files("filter_lib.shared").joinpath("capacitor_grade_data.json").read_text())
    for grade in GRADES.values():
        for row in grade.rows:
            assert row.guarantee == "maximum"
            assert row.tolerance_sheet in data["sheets"]
            assert row.range_parts
    for sheet in data["sheets"].values():
        assert sheet["url"].startswith("https://pim.murata.com/")
        assert len(sheet["sha256"]) == 64


def test_unknown_grade_is_refused_with_the_choices():
    with pytest.raises(ValueError, match="^Capacitor grade must be standard or tight$"):
        require_grade("loose")


def _reload_with(monkeypatch, tmp_path, change) -> None:
    """Load the packaged table after ``change(data)`` edits a copy of it."""
    source = files("filter_lib.shared").joinpath("capacitor_grade_data.json").read_text()
    data = json.loads(source)
    change(data)
    (tmp_path / "capacitor_grade_data.json").write_text(json.dumps(data), encoding="utf-8")
    monkeypatch.setattr(packaged_data, "files", lambda _package: tmp_path)
    capacitor_grades._load()


def _row(data, grade="standard", index=0):
    return data["grades"][grade]["rows"][index]


@pytest.mark.parametrize(
    ("change", "message"),
    [
        (lambda d: _row(d).update(guarantee="typical"), "not a guaranteed limit"),
        (lambda d: _row(d).update(guarantee="typ"), "unknown guarantee type"),
        (lambda d: _row(d).update(tolerance_pct=5), "exactly one of tolerance_pf"),
        (lambda d: _row(d).update(tolerance_pf=0), "non-positive tolerance"),
        (lambda d: _row(d).update(from_pf=2, to_pf=1), "invalid value range"),
        (lambda d: _row(d).update(tolerance_sheet="GRM1885C1H999JA01"), "sheet that was not read"),
        (lambda d: _row(d).update(range_parts=[]), "part numbers that show its range"),
        (lambda d: d["sheets"]["GRM1885C1H100JA01"].update(url="http://x"), "HTTPS"),
        (lambda d: d["sheets"]["GRM1885C1H100JA01"].update(sha256="abc"), "SHA-256"),
        (lambda d: d["grades"].pop("tight"), "Capacitor grades must be standard, tight"),
        (lambda d: d["series"].update(name="two\nlines"), "single line of printable text"),
        (lambda d: d.update(schema_version=2), "expected version 1"),
    ],
)
def test_loader_refuses_malformed_data(monkeypatch, tmp_path, change, message):
    with pytest.raises(RuntimeError, match=message):
        _reload_with(monkeypatch, tmp_path, change)


def test_the_tight_grade_scope_is_read_from_the_table():
    """Tight is tighter for every listed value below 1000 pF and the same J ±5% from there."""
    from filter_lib.design.capacitor_policy_inputs import GRADE_HELP
    from filter_lib.shared.capacitor_grades import (
        CAPACITOR_GRADE_HELP,
        TIGHT_GRADE_SCOPE,
        made_values_pf,
        sourced_tolerance_pf,
    )

    assert TIGHT_GRADE_SCOPE == "one step tighter below 1000 pF; from 1000 pF both grades are ±5%"
    for value in made_values_pf():
        tight = sourced_tolerance_pf(value, "tight")
        standard = sourced_tolerance_pf(value, "standard")
        assert (tight < standard) if value < 1000 else (tight == standard), value
    assert TIGHT_GRADE_SCOPE in CAPACITOR_GRADE_HELP and TIGHT_GRADE_SCOPE in GRADE_HELP
