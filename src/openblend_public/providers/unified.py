"""UnifiedProvider — Support for OpenAI-compatible APIs.

Supports HTTP-based OpenAI-format APIs only (simplified for public release).
"""

from __future__ import annotations

import asyncio
import json
import logging
import time
from collections import deque
from dataclasses import dataclass, field
from typing import Any, AsyncIterator

from openblend_public.core.types import LLMResponse, ProviderSlot, StreamChunk, Transport

logger = logging.getLogger("openblend_public.providers.unified")

# --- API Hygiene Constants (Configurable) ---
MIN_PROMPT_TOKENS = 10
MIN_INTERVAL_SEC = 2.0
MAX_CALLS_PER_HOUR = 100

# --- Rate Limiting Window ---
RATE_LIMIT_WINDOW = 3600  # 1 hour in seconds


class APIHygieneViolation(Exception):
    """Raised when API call fails hygiene check."""
    pass


@dataclass
class LatencyHistory:
    """Track provider latency for smart routing."""
    samples: deque = field(default_factory=lambda: deque(maxlen=50))
    errors: int = 0
    last_error_time: float = 0.0

    def add(self, latency_ms: int):
        self.samples.append(latency_ms)

    @property
    def avg_latency(self) -> float:
        return sum(self.samples) / len(self.samples) if self.samples else 1000.0

    @property
    def p95_latency(self) -> float:
        if not self.samples:
            return 1000.0
        sorted_samples = sorted(self.samples)
        idx = int(len(sorted_samples) * 0.95)
        return sorted_samples[min(idx, len(sorted_samples) - 1)]

    def record_error(self):
        self.errors += 1
        self.last_error_time = time.time()

    @property
    def is_healthy(self) -> bool:
        # Degrade if too many recent errors
        if self.errors > 5 and time.time() - self.last_error_time < 300:
            return False
        return True


class CallAudit:
    """Enhanced audit with sliding window rate limiting."""

    def __init__(self):
        self._call_history: deque = deque(maxlen=10000)  # In-memory sliding window
        self._provider_windows: dict[str, deque] = {}

    def _get_provider_window(self, provider: str) -> deque:
        if provider not in self._provider_windows:
            self._provider_windows[provider] = deque(maxlen=1000)
        return self._provider_windows[provider]

    def check_rate_limit(self, provider: str, max_calls: int = MAX_CALLS_PER_HOUR) -> bool:
        """Check if provider is within rate limit using sliding window."""
        window = self._get_provider_window(provider)
        now = time.time()
        # Remove old entries outside window
        cutoff = now - RATE_LIMIT_WINDOW
        while window and window[0] < cutoff:
            window.popleft()
        return len(window) < max_calls

    def record_call(
        self,
        provider: str,
        model: str,
        prompt_tokens: int,
        completion_tokens: int,
        cost_usd: float,
        caller_module: str,
    ) -> None:
        """Record a completed API call."""
        from datetime import datetime
        now = time.time()

        # Update sliding window
        window = self._get_provider_window(provider)
        window.append(now)
        self._call_history.append(now)

        # Warn if approaching limits
        if len(window) > MAX_CALLS_PER_HOUR * 0.8:
            logger.warning(
                "Rate Limit: %s at %d%% of hourly quota",
                provider, len(window) / MAX_CALLS_PER_HOUR * 100
            )


# Global audit singleton
_audit: CallAudit | None = None


def get_call_audit() -> CallAudit:
    global _audit
    if _audit is None:
        _audit = CallAudit()
    return _audit


class UnifiedProvider:
    def __init__(self) -> None:
        self._last_call_time: dict[str, float] = {}
        self._audit = get_call_audit()
        # Latency tracking for smart routing
        self._latency_history: dict[str, LatencyHistory] = {}
        self._token_budget: dict[str, int] = {}

    async def startup(self) -> None:
        pass

    async def shutdown(self) -> None:
        pass

    def _get_latency_history(self, provider: str) -> LatencyHistory:
        if provider not in self._latency_history:
            self._latency_history[provider] = LatencyHistory()
        return self._latency_history[provider]

    def select_best_slot(self, slots: list[ProviderSlot], strategy: str = "latency") -> ProviderSlot:
        """Smart slot selection based on strategy."""
        if not slots:
            raise ValueError("No slots available")
        if len(slots) == 1:
            return slots[0]

        if strategy == "latency":
            # Select based on lowest p95 latency
            scored = []
            for slot in slots:
                hist = self._get_latency_history(slot.provider)
                score = hist.p95_latency if hist.is_healthy else 10000.0
                scored.append((score, slot))
            scored.sort(key=lambda x: x[0])
            return scored[0][1]

        elif strategy == "cost":
            return min(slots, key=lambda s: s.cost_output)

        elif strategy == "balanced":
            # Balance latency and cost
            def balance_score(slot):
                hist = self._get_latency_history(slot.provider)
                latency_score = hist.avg_latency / 1000.0  # Normalize
                cost_score = slot.cost_output * 100  # Scale up
                return latency_score + cost_score
            return min(slots, key=balance_score)

        return slots[0]

    def set_token_budget(self, provider: str, budget: int) -> None:
        """Set token budget for a provider."""
        self._token_budget[provider] = budget

    def _check_budget(self, provider: str, estimated_tokens: int) -> bool:
        """Check if call is within token budget."""
        remaining = self._token_budget.get(provider)
        if remaining is None:
            return True
        return estimated_tokens <= remaining

    def _estimate_tokens(self, text: str) -> int:
        """Rough token count estimate (1 token ≈ 4 chars)."""
        return len(text) // 4 + 1

    def _enforce_hygiene(
        self,
        prompt: str,
        provider: str,
        force: bool = False,
    ) -> None:
        """Enforce API hygiene rules: min tokens, min interval.

        Raises:
            APIHygieneViolation: if call doesn't meet requirements.
        """
        # Check minimum prompt tokens
        tokens = self._estimate_tokens(prompt)
        if not force and tokens < MIN_PROMPT_TOKENS:
            raise APIHygieneViolation(
                f"API call rejected: Prompt only has ~{tokens} tokens, "
                f"minimum required is {MIN_PROMPT_TOKENS}. "
                "Please merge multiple small requests or use local model."
            )

        # Check minimum interval
        now = time.time()
        last = self._last_call_time.get(provider, 0.0)
        elapsed = now - last
        if elapsed < MIN_INTERVAL_SEC:
            # Sleep to enforce interval
            logger.debug(
                "API Hygiene: Sleeping %.2fs to enforce rate limit",
                MIN_INTERVAL_SEC - elapsed
            )
            time.sleep(MIN_INTERVAL_SEC - elapsed)

        # Update last call time
        self._last_call_time[provider] = now

    # --- Core Generate with Retry ---
    async def generate(
        self, prompt: str, slot: ProviderSlot, *, messages: list[dict[str, str]] | None = None,
        max_tokens: int = 4096, temperature: float | None = None, force_hygiene: bool = False,
        max_retries: int = 3, **kwargs: Any,
    ) -> LLMResponse:
        """Generate with automatic retry and exponential backoff."""
        start = time.time()

        for attempt in range(max_retries + 1):
            try:
                return await self._generate_once(
                    prompt, slot, messages=messages, max_tokens=max_tokens,
                    temperature=temperature, force_hygiene=force_hygiene, start=start,
                    **kwargs
                )
            except APIHygieneViolation:
                raise  # Don't retry hygiene violations
            except Exception as e:
                error_str = str(e).lower()
                # Classify errors
                is_transient = any(x in error_str for x in [
                    "timeout", "connection", "network", "dns", "unreachable",
                    "server error", "502", "503", "504", "temporarily"
                ])
                is_rate_limit = "429" in error_str or "rate limit" in error_str

                if attempt < max_retries and (is_transient or is_rate_limit):
                    delay = min(2 ** attempt, 30)  # Exponential backoff, max 30s
                    if is_rate_limit:
                        delay = max(delay, 10)  # Rate limits need longer wait
                    logger.warning(
                        "%s attempt %d/%d failed: %s. Retrying in %.1fs...",
                        slot.model, attempt + 1, max_retries + 1, e, delay
                    )
                    await asyncio.sleep(delay)
                    continue

                # Permanent failure or exhausted retries
                logger.error("%s failed permanently: %s", slot.model, e)
                return LLMResponse(
                    content="", model=slot.model, provider=slot.provider,
                    latency_ms=0, raw_response={"success": False, "error": str(e)}
                )

        return LLMResponse(content="", model=slot.model, provider=slot.provider, latency_ms=0, raw_response={"success": False, "error": "Max retries invalid"})

    async def _generate_once(
        self, prompt: str, slot: ProviderSlot, *, messages: list[dict[str, str]] | None = None,
        max_tokens: int = 4096, temperature: float | None = None, force_hygiene: bool = False,
        start: float = 0, **kwargs: Any,
    ) -> LLMResponse:
        """Single generation attempt."""
        if slot.transport == Transport.CLI:
            return await self._run_cli_response(prompt, slot, start or time.time())

        import httpx

        payload = {
            "model": slot.model,
            "messages": messages or [{"role": "user", "content": prompt}],
            "max_tokens": max_tokens,
        }
        if temperature is not None:
            payload["temperature"] = temperature

        # ENFORCE API HYGIENE before sending request
        self._enforce_hygiene(prompt, slot.provider, force=force_hygiene)

        async with httpx.AsyncClient() as client:
            resp = await client.post(
                self._chat_url(slot),
                json=payload,
                headers=self._headers(slot),
                timeout=float(slot.timeout),
            )
            resp.raise_for_status()
            data = resp.json()
            content = data["choices"][0]["message"]["content"]

            usage = data.get("usage", {})
            in_t = usage.get("prompt_tokens", self._estimate_tokens(prompt))
            out_t = usage.get("completion_tokens", self._estimate_tokens(content))

            cost = self._calc_cost(slot, in_t, out_t)

            # Record the call in audit log
            task = asyncio.current_task()
            caller = task.get_name() if task else "unknown"
            self._audit.record_call(
                provider=slot.provider,
                model=slot.model,
                prompt_tokens=in_t,
                completion_tokens=out_t,
                cost_usd=cost,
                caller_module=caller,
            )

            # Mark provider healthy on success
            self._get_latency_history(slot.provider).add(int((time.time() - start) * 1000))

            return LLMResponse(
                content=content, model=f"{slot.provider}/{slot.model}",
                provider=slot.provider, tokens_used=in_t + out_t,
                input_tokens=in_t, output_tokens=out_t,
                cost=cost,
                latency_ms=int((time.time() - start) * 1000),
                raw_response={"success": True},
            )

    # --- Batch Generate ---
    async def generate_many(
        self, prompt: str, slots: list[ProviderSlot], **kwargs: Any,
    ) -> list[LLMResponse]:
        """Generate from multiple slots in parallel."""
        tasks = [self.generate(prompt, slot, **kwargs) for slot in slots]
        return await asyncio.gather(*tasks)

    # --- Streaming ---
    async def stream(
        self, prompt: str, slot: ProviderSlot, *, messages: list[dict[str, str]] | None = None,
        max_tokens: int = 4096, temperature: float | None = None,
    ) -> AsyncIterator[StreamChunk]:
        """Streaming response support."""
        res = await self.generate(prompt, slot, messages=messages, max_tokens=max_tokens, temperature=temperature)
        yield StreamChunk(content=res.content, model=slot.model, provider=slot.provider)
        yield StreamChunk(done=True, model=slot.model, provider=slot.provider)

    async def _run_cli_response(self, prompt, slot, start):
        import asyncio
        cmd = [slot.cli_bin or slot.provider, "-p", prompt]
        proc = await asyncio.create_subprocess_exec(*cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
        stdout, stderr = await proc.communicate()
        content = stdout.decode().strip()
        return LLMResponse(
            content=content, model=slot.model, provider=slot.provider,
            tokens_used=len(content)//4, input_tokens=len(prompt)//4, output_tokens=len(content)//4,
            latency_ms=int((time.time()-start)*1000), raw_response={"success": proc.returncode==0}
        )

    @staticmethod
    def _chat_url(slot):
        base = slot.base_url.rstrip("/")
        return base if base.endswith("/chat/completions") else f"{base}/chat/completions"

    @staticmethod
    def _headers(slot):
        h = {"Content-Type": "application/json"}
        if slot.api_key:
            h["Authorization"] = f"Bearer {slot.api_key}"
        return h

    @staticmethod
    def _calc_cost(slot, in_t, out_t):
        return (in_t * slot.cost_input + out_t * slot.cost_output) / 1_000_000


_provider = None


def get_provider():
    global _provider
    if _provider is None:
        _provider = UnifiedProvider()
    return _provider
