"""Strict JSON serialization with path-aware finite-number validation."""

from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from typing import Any

from .numeric import is_finite_real


def _child_path(path: str, key: str) -> str:
    """Return a readable JSON-tree path for a mapping key."""
    if key.isidentifier():
        return f"{path}.{key}"
    return f"{path}[{key!r}]"


def validate_finite_tree(value: Any, *, path: str = "$") -> None:
    """Validate that a JSON-like tree contains only finite numeric values.

    Args:
        value: JSON-like value composed of mappings, sequences, scalars, and
            ``None``.
        path: Root path used in validation errors.

    Raises:
        TypeError: If a mapping key or value is not JSON-compatible.
        ValueError: If a float is NaN or infinite.
    """
    if value is None or isinstance(value, (str, bool)):
        return
    if isinstance(value, (int, float)):
        if not is_finite_real(value):
            raise ValueError(f"{path} must be finite, got {value!r}")
        return
    if isinstance(value, Mapping):
        for key, child in value.items():
            if not isinstance(key, str):
                raise TypeError(f"{path} has non-string JSON object key {key!r}")
            validate_finite_tree(child, path=_child_path(path, key))
        return
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        for index, child in enumerate(value):
            validate_finite_tree(child, path=f"{path}[{index}]")
        return
    raise TypeError(f"{path} contains non-JSON value of type {type(value).__name__}")


def dumps_strict(value: Any, *, indent: int | None = None) -> str:
    """Serialize JSON after rejecting non-finite and non-JSON tree values."""
    validate_finite_tree(value)
    return json.dumps(value, indent=indent, allow_nan=False)


# Descriptive alias for callers that prefer the module name in the function.
strict_json_dumps = dumps_strict
