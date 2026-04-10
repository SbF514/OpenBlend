"""Provider pool — connection management, rate limiting, health tracking."""

from __future__ import annotations

import asyncio
import logging
import time

import httpx

logger = logging.getLogger("openblend_public.providers.pool")


class TokenBucket:
    """Simple token bucket rate limiter."""

    def __init__(self, rate: int = 60, capacity: int | None = None) -> None:
        self.rate = rate  # tokens per minute
        self.capacity = capacity or rate
        self.tokens = float(self.capacity)
        self._last = time.monotonic()
        self._lock = asyncio.Lock()

    async def acquire(self) -> None:
        """Wait until a token is available."""
        async with self._lock:
            now = time.monotonic()
            elapsed = now - self._last
            self._last = now
            self.tokens = min(self.capacity, self.tokens + elapsed * self.rate / 60.0)

            if self.tokens < 1.0:
                wait = (1.0 - self.tokens) * 60.0 / self.rate
                logger.debug("Rate limit: waiting %.2fs", wait)
                await asyncio.sleep(wait)
                self.tokens = 0.0
            else:
                self.tokens -= 1.0


class HealthStatus:
    """Track provider health with automatic cool-down and recovery."""

    def __init__(self, cooldown_seconds: int = 300) -> None:
        self.healthy: bool = True
        self.consecutive_failures: int = 0
        self.last_failure: float = 0.0
        self.total_calls: int = 0
        self.total_failures: int = 0
        self.cooldown_seconds = cooldown_seconds
        self._circuit_state = "closed"  # closed, open, half-open
        self._half_open_attempts: int = 0

    def mark_success(self) -> None:
        self.healthy = True
        self.consecutive_failures = 0
        self.total_calls += 1
        if self._circuit_state == "half-open":
            self._circuit_state = "closed"
            self._half_open_attempts = 0
            logger.info("Provider circuit CLOSED - recovery confirmed")

    def mark_failure(self, is_transient: bool = True) -> None:
        """Mark failure with transient vs permanent distinction.

        Args:
            is_transient: True for network errors, rate limits. False for auth errors.
        """
        self.consecutive_failures += 1
        self.total_failures += 1
        self.total_calls += 1
        self.last_failure = time.time()

        # Permanent failures (auth, invalid model) trip immediately
        if not is_transient:
            self.healthy = False
            self._circuit_state = "open"
            logger.warning("Provider PERMANENT failure. Circuit OPEN.")
            return

        # Transient failures need more tolerance
        if self._circuit_state == "closed" and self.consecutive_failures >= 3:
            self.healthy = False
            self._circuit_state = "open"
            logger.warning(
                "Provider breaker TRIPPED after %d failures. Cooling down for %ds.",
                self.consecutive_failures, self.cooldown_seconds
            )
        elif self._circuit_state == "half-open":
            self._half_open_attempts += 1
            if self._half_open_attempts >= 2:
                self.healthy = False
                self._circuit_state = "open"
                logger.warning("Provider recovery failed. Circuit OPEN again.")

    def check_health(self) -> bool:
        """Check health with time-based recovery and circuit breaker."""
        if self._circuit_state == "closed":
            return True

        # Check if cool-down period is over
        if time.time() - self.last_failure > self.cooldown_seconds:
            if self._circuit_state == "open":
                self._circuit_state = "half-open"
                self._half_open_attempts = 0
                logger.info("Provider cool-down over. Circuit HALF-OPEN - testing recovery.")
            return True

        return False

    @property
    def failure_rate(self) -> float:
        return self.total_failures / max(1, self.total_calls)


class ProviderPool:
    """Manages HTTP connections, rate limits, and intelligent health tracking."""

    def __init__(self) -> None:
        self._client: httpx.AsyncClient | None = None
        self._limiters: dict[str, TokenBucket] = {}
        self._health: dict[str, HealthStatus] = {}

    async def startup(self) -> None:
        """Create shared HTTP client."""
        if self._client is None:
            self._client = httpx.AsyncClient(
                limits=httpx.Limits(
                    max_connections=100,
                    max_keepalive_connections=20,
                    keepalive_expiry=30.0,
                ),
                follow_redirects=True,
            )

    async def shutdown(self) -> None:
        """Close the HTTP client."""
        if self._client:
            await self._client.aclose()
            self._client = None

    async def get_client(self) -> httpx.AsyncClient:
        """Get or create the shared HTTP client."""
        if self._client is None:
            await self.startup()
        assert self._client is not None
        return self._client

    async def acquire(self, provider: str, rate_limit: int = 60) -> None:
        """Acquire a rate limit token for a provider."""
        if provider not in self._limiters:
            self._limiters[provider] = TokenBucket(rate=rate_limit)
        await self._limiters[provider].acquire()

    def mark_unhealthy(self, provider: str, is_transient: bool = True) -> None:
        """Record a failure for a provider."""
        if provider not in self._health:
            self._health[provider] = HealthStatus()
        self._health[provider].mark_failure(is_transient=is_transient)

    def mark_healthy(self, provider: str) -> None:
        """Record a success for a provider."""
        if provider not in self._health:
            self._health[provider] = HealthStatus()
        self._health[provider].mark_success()

    def is_healthy(self, provider: str) -> bool:
        """Check if a provider is healthy (smart time-based check)."""
        if provider not in self._health:
            return True
        return self._health[provider].check_health()

    def get_health(self, provider: str) -> HealthStatus:
        if provider not in self._health:
            self._health[provider] = HealthStatus()
        return self._health[provider]
