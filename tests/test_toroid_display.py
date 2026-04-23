"""Tests for toroid display formatters (Phase 5)."""

import json

from filter_lib.shared.toroid_display import (
    CSV_TOROID_HEADER,
    build_json_recommendations,
    csv_columns_for_best,
    format_recommendation_block,
    format_recommendation_block_compact,
)
from filter_lib.shared.toroid_selection import recommend_cores


def _recs():
    return recommend_cores(1.457e-6, 10e6)


def test_full_block_expected_line_count():
    """Full block: 2 header + 6 lines x 3 recs = 20 lines."""
    recs = _recs()
    lines = format_recommendation_block("L1", 1.457e-6, 10e6, recs)
    assert len(lines) == 2 + 6 * len(recs)


def test_full_block_contains_core_names():
    recs = _recs()
    lines = format_recommendation_block("L1", 1.457e-6, 10e6, recs)
    assert any(recs[0].core.name in ln for ln in lines)


def test_full_block_empty_recs_message():
    lines = format_recommendation_block("L1", 1e-6, 500e6, [])
    assert len(lines) == 3  # label + rule + message
    assert "No iron-powder" in lines[-1]


def test_full_block_contains_q_label():
    recs = _recs()
    lines = format_recommendation_block("L1", 1.457e-6, 10e6, recs)
    text = "\n".join(lines)
    assert "Q (DC est, upper bound)" in text


def test_compact_block_line_count():
    """Compact block: 1 header + 1 line per rec."""
    recs = _recs()
    lines = format_recommendation_block_compact("L1", 1.457e-6, 10e6, recs)
    assert len(lines) == 1 + len(recs)


def test_compact_block_has_q_shorthand():
    recs = _recs()
    lines = format_recommendation_block_compact("L1", 1.457e-6, 10e6, recs)
    assert any("Q≈" in ln for ln in lines)


def test_compact_block_empty_recs_two_lines():
    """Compact empty: label + no-candidate message."""
    lines = format_recommendation_block_compact("L1", 1e-6, 500e6, [])
    assert len(lines) == 2


def test_build_json_recommendations_serializable():
    """Output round-trips through json.dumps/loads."""
    recs = _recs()
    data = build_json_recommendations(recs)
    round_trip = json.loads(json.dumps(data))
    assert round_trip == data


def test_build_json_recommendations_shape():
    recs = _recs()
    data = build_json_recommendations(recs)
    assert data
    entry = data[0]
    assert {"rank", "core", "winding", "wire", "q_dc_upper_bound", "design_freq_hz"}.issubset(
        entry.keys()
    )
    assert "name" in entry["core"]
    assert "turns" in entry["winding"]
    assert "awg" in entry["wire"]


def test_csv_columns_count_matches_header():
    """CSV row length == header length (10)."""
    recs = _recs()
    cols = csv_columns_for_best(recs)
    assert len(cols) == len(CSV_TOROID_HEADER) == 10


def test_csv_columns_empty_returns_blanks():
    """With no recs, all 10 CSV columns are empty strings."""
    cols = csv_columns_for_best([])
    assert cols == [""] * 10


def test_csv_header_constant_length():
    """CSV_TOROID_HEADER is exactly 10 columns."""
    assert len(CSV_TOROID_HEADER) == 10
