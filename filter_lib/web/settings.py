"""Runtime settings for the local web UI."""

from __future__ import annotations

from dataclasses import dataclass

DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 8765
LOOPBACK_HOSTS = frozenset({"127.0.0.1", "localhost", "::1"})
# Bind addresses that listen on every interface; the server then cannot know which
# names clients will use to reach it.
WILDCARD_HOSTS = frozenset({"0.0.0.0", "::", ""})


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

    @property
    def allowed_hosts(self) -> frozenset[str] | None:
        """Host names a request may be addressed to, or ``None`` to accept any.

        Loopback names are always allowed; a specific bind address is allowed too. A
        wildcard bind accepts any Host because its reachable names are unknown.
        """
        if self.host in WILDCARD_HOSTS:
            return None
        return LOOPBACK_HOSTS | {self.host.lower()}
