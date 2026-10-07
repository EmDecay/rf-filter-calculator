"""Typed readers for submitted form fields.

Browsers send every field as text, and unchecked boxes are not sent at all. These
helpers turn that text into numbers with plain error messages; quantities with units
(frequencies, impedances, inductances) go through the shared parsers instead, so
their messages are the CLI's.
"""

from __future__ import annotations

from collections.abc import Mapping

FormData = Mapping[str, str]


def text(form: FormData, name: str, default: str = "") -> str:
    """Return the stripped field value, or ``default`` when absent or blank."""
    value = form.get(name)
    if value is None:
        return default
    value = str(value).strip()
    return value if value else default


def flag(form: FormData, name: str) -> bool:
    """Return whether a checkbox was submitted checked."""
    return text(form, name).lower() in {"on", "true", "1", "yes"}


def choice(form: FormData, name: str, allowed: tuple[str, ...], default: str, label: str) -> str:
    """Return a field restricted to ``allowed`` values."""
    value = text(form, name, default)
    if value not in allowed:
        raise ValueError(f"{label} must be one of: {', '.join(allowed)}")
    return value


def optional_float(form: FormData, name: str, label: str) -> float | None:
    """Return a decimal number, or ``None`` for a blank field."""
    value = text(form, name)
    if not value:
        return None
    try:
        return float(value)
    except ValueError:
        raise ValueError(f"{label} must be a number") from None


def float_or(form: FormData, name: str, label: str, default: float) -> float:
    value = optional_float(form, name, label)
    return default if value is None else value


def optional_int(form: FormData, name: str, label: str) -> int | None:
    """Return a whole number, or ``None`` for a blank field."""
    value = text(form, name)
    if not value:
        return None
    try:
        return int(value)
    except ValueError:
        raise ValueError(f"{label} must be a whole number") from None


def int_or(form: FormData, name: str, label: str, default: int) -> int:
    value = optional_int(form, name, label)
    return default if value is None else value


def required(form: FormData, name: str, label: str) -> str:
    """Return a non-blank field or reject the submission."""
    value = text(form, name)
    if not value:
        raise ValueError(f"{label} is required")
    return value
