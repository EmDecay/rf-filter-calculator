"""Wizard design-field rules shared by live Input styling and the Next handlers."""

import pytest

from filter_lib.wizard.design_field_validation import RippleValidator, parse_ripple_db

_ACCEPTED = [("5e-324", 5e-324), ("0.005", 0.005), ("0.01", 0.01), (" 0.5 ", 0.5), ("3.0", 3.0)]
_REJECTED = [
    ("0", "must be positive"),
    ("-0.1", "must be positive"),
    ("3.0000001", "must be <= 3.0 dB"),
    ("nan", "must be finite"),
    ("inf", "must be finite"),
    ("abc", "could not convert string to float: 'abc'"),
    ("", "could not convert string to float: ''"),
]


@pytest.mark.parametrize(("text", "expected"), _ACCEPTED)
def test_parse_ripple_db_accepts_the_full_design_range(text, expected):
    assert parse_ripple_db(text) == expected


@pytest.mark.parametrize(("text", "message"), _REJECTED)
def test_parse_ripple_db_rejects_with_the_next_button_message(text, message):
    with pytest.raises(ValueError) as error:
        parse_ripple_db(text)

    assert str(error.value) == message


@pytest.mark.parametrize("text", [text for text, _expected in _ACCEPTED])
def test_ripple_validator_accepts_what_the_parser_accepts(text):
    assert RippleValidator().validate(text).is_valid


@pytest.mark.parametrize(("text", "message"), _REJECTED)
def test_ripple_validator_rejects_with_the_parser_message(text, message):
    result = RippleValidator().validate(text)

    assert not result.is_valid
    assert result.failure_descriptions == [message]


@pytest.mark.parametrize("value", [True, 0.5, None])
def test_parse_ripple_db_requires_text(value):
    with pytest.raises(ValueError, match="^must be supplied as text$"):
        parse_ripple_db(value)
