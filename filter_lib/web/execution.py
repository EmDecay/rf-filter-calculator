"""Bounded, cancellable execution of design work off the event loop.

Every calculation runs on a small dedicated thread pool. A request waits at most
``calculation_timeout_s``; on expiry its cancellation flag is set and the request
fails with ``CalculationTimeout``. ``design()`` polls that flag before synthesis,
before each circuit evaluation of a band-pass calibration and its response check,
before each part it resolves, and before each build case, so running work stops at
its next check (a ladder synthesis is one closed-form step) and its result is
discarded. Shutdown cancels queued work, flags running work, and joins the pool
threads so none outlive the app.
"""

from __future__ import annotations

import asyncio
import threading
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from typing import TypeVar

from .settings import WebSettings

T = TypeVar("T")
CancellationCheck = Callable[[], bool]


def _consume_outcome(waiter: asyncio.Future) -> None:
    if not waiter.cancelled():
        waiter.exception()


class CalculationTimeout(Exception):
    """Raised when a calculation exceeds the configured timeout."""


def timeout_message(timeout_s: float) -> str:
    """What a timed-out request says: what can make each kind of calculation shorter.

    A band-pass calibration takes longer with more resonators, the build simulation with
    more tolerance cases or frequency points; a ladder synthesis is instant.
    """
    return (
        f"Calculation stopped after {timeout_s:g} s. Try fewer resonators, or with the "
        "build simulation, fewer extra random tolerance cases or frequency points."
    )


class CalculationRunner:
    """Run ``work(should_cancel)`` callables on a bounded pool with a timeout."""

    def __init__(self, settings: WebSettings) -> None:
        self.timeout_s = settings.calculation_timeout_s
        self._executor = ThreadPoolExecutor(
            max_workers=settings.max_workers, thread_name_prefix="filter-calc-web"
        )
        self._flags: set[threading.Event] = set()
        self._lock = threading.Lock()

    async def run(self, work: Callable[[CancellationCheck], T]) -> T:
        """Run ``work`` in the pool and return its result or raise its exception."""
        flag = threading.Event()
        with self._lock:
            self._flags.add(flag)
        try:
            future = self._executor.submit(work, flag.is_set)
            waiter = asyncio.wrap_future(future)
            try:
                return await asyncio.wait_for(asyncio.shield(waiter), self.timeout_s)
            except (TimeoutError, asyncio.CancelledError) as stop:
                # Timed out, or the request itself was abandoned: either way stop the
                # work. Queued work never starts; running work ends at its next check,
                # and its outcome is consumed here so nothing is logged.
                flag.set()
                future.cancel()
                waiter.add_done_callback(_consume_outcome)
                if isinstance(stop, asyncio.CancelledError):
                    raise
                raise CalculationTimeout(timeout_message(self.timeout_s)) from None
        finally:
            with self._lock:
                self._flags.discard(flag)

    def shutdown(self) -> None:
        """Stop accepting work, flag running work, and join every pool thread."""
        with self._lock:
            for flag in self._flags:
                flag.set()
        self._executor.shutdown(wait=True, cancel_futures=True)
