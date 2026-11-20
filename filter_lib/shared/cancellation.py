"""Cooperative cancellation shared by synthesis, part resolution, and the build simulation.

A thread worker cannot be interrupted from outside, so long work polls a zero-argument
check between bounded units and stops by raising ``DesignCancelled``. ``None`` means the
caller never cancels.
"""

from __future__ import annotations

from collections.abc import Callable

CancellationCheck = Callable[[], bool]


class DesignCancelled(Exception):
    """Raised when the caller's cancellation check stops a design.

    Deliberately not a ``ValueError``: cancellation is not an input error, so a caller
    that reports rejected input never presents it as one, and solver code that retries
    on ``ValueError`` never swallows it.
    """


def require_cancellation_check(should_cancel: object) -> None:
    """Refuse a cancellation check that is neither callable nor ``None``."""
    if should_cancel is not None and not callable(should_cancel):
        raise ValueError("should_cancel must be a zero-argument callable or None")


def raise_if_cancelled(should_cancel: CancellationCheck | None) -> None:
    """Raise ``DesignCancelled`` when the optional check reports cancellation."""
    if should_cancel is not None and should_cancel():
        raise DesignCancelled("Design was cancelled")
