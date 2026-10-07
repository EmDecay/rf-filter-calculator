"""Runtime settings for the local web UI."""

from __future__ import annotations

from dataclasses import dataclass

DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 8765
LOOPBACK_HOSTS = frozenset({"127.0.0.1", "localhost", "::1"})


@dataclass(frozen=True)
class WebSettings:
    """Server address and calculation limits.

    ``calculation_timeout_s`` bounds how long a request waits for its design; on
    expiry the request's cancellation flag is set, which stops a realized-build
    analysis at its next check. ``max_workers`` caps concurrent calculations; extra
    requests queue.
    """

    host: str = DEFAULT_HOST
    port: int = DEFAULT_PORT
    calculation_timeout_s: float = 60.0
    max_workers: int = 2

    def __post_init__(self) -> None:
        if not 0 < self.calculation_timeout_s <= 3600:
            raise ValueError("Calculation timeout must be between 0 and 3600 seconds")
        if not 1 <= self.max_workers <= 32:
            raise ValueError("Worker count must be 1-32")
        if not 1 <= self.port <= 65535:
            raise ValueError("Port must be 1-65535")

    @property
    def is_loopback(self) -> bool:
        return self.host in LOOPBACK_HOSTS
