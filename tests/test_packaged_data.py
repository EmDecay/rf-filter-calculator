"""The shared loader and field guards behind every packaged data file."""

import pytest

from filter_lib.shared import packaged_data
from filter_lib.shared.packaged_data import (
    GUARANTEE_TYPES,
    QUALIFYING_GUARANTEES,
    load_packaged_json,
    require_finite_number,
    require_guarantee_type,
    require_https_url,
    require_printable_line,
)


def _load(monkeypatch, tmp_path, document: str, version: int = 3) -> dict:
    (tmp_path / "data.json").write_text(document, encoding="utf-8")
    monkeypatch.setattr(packaged_data, "files", lambda _package: tmp_path)
    return load_packaged_json("pkg", "data.json", schema_version=version, label="test data")


def test_loader_returns_an_object_with_the_expected_schema(monkeypatch, tmp_path):
    assert _load(monkeypatch, tmp_path, '{"schema_version": 3, "x": 1.5}') == {
        "schema_version": 3,
        "x": 1.5,
    }


@pytest.mark.parametrize("document", ['{"schema_version": 2}', "[3]", '{"x": 1}'])
def test_loader_refuses_another_schema_or_shape(monkeypatch, tmp_path, document):
    with pytest.raises(RuntimeError, match="Unsupported test data schema; expected version 3"):
        _load(monkeypatch, tmp_path, document)


@pytest.mark.parametrize("literal", ["1e999", "-1e999", "NaN", "Infinity", "-Infinity"])
def test_loader_refuses_non_finite_numbers(monkeypatch, tmp_path, literal):
    with pytest.raises(ValueError, match="Non-finite JSON .* in test data"):
        _load(monkeypatch, tmp_path, f'{{"schema_version": 3, "x": {literal}}}')


def test_https_url_guard():
    assert require_https_url("https://example.com/a.pdf", "Source") == "https://example.com/a.pdf"
    for url in ("http://example.com", "ftp://x", None, 3, "https://a\nb"):
        with pytest.raises(RuntimeError, match="Source"):
            require_https_url(url, "Source")


@pytest.mark.parametrize("text", ["", "   ", "two\nlines", "tab\tinside", None, 5])
def test_printable_line_guard_refuses(text):
    with pytest.raises(RuntimeError, match="Title must be a non-empty single line"):
        require_printable_line(text, "Title")


def test_printable_line_guard_accepts_unicode_text():
    assert require_printable_line("GRM1885C1H…A01 ±0.25 pF", "Title")


def test_guarantee_type_guard():
    assert set(QUALIFYING_GUARANTEES) == {"minimum", "maximum"}
    for value in GUARANTEE_TYPES:
        assert require_guarantee_type(value, "Row") == value
    for value in ("typ", "Maximum", None, 1):
        with pytest.raises(RuntimeError, match="unknown guarantee type"):
            require_guarantee_type(value, "Row")


def test_finite_number_guard():
    assert require_finite_number(0.25, "Tolerance") == 0.25
    for value in (float("nan"), float("inf"), True, "1", None):
        with pytest.raises(RuntimeError, match="Tolerance must be a finite number"):
            require_finite_number(value, "Tolerance")
