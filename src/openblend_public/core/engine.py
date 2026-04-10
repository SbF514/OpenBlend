"""OpenBlend Public Engine — Core execution with pre-trained ELO.

Simplified: we already have trained ELO, just do the blending.
"""

from __future__ import annotations

import asyncio
import logging
import time
import uuid
from typing import Any, AsyncIterator

from openblend_public.config import get_config
from openblend_public.core.types import (
    BlendMode, BlendResult, Intent, LLMResponse,
    ProviderSlot, Strategy, StreamChunk, Tier,
)
from openblend_public.core.strategy import (
    select_strategy, get_propose_slots, get_judge_slot, get_critique_slot, get_refine_slot,
)
from openblend_public.intent.analyzer import classify
from openblend_public.providers.unified import get_provider

logger = logging.getLogger("openblend_public.core.engine")


class EngineMetrics:
    def __init__(self):
        self.total_requests = 0
        self.total_latency_ms = 0
        self.errors = 0
        self.strategy_counts: dict[str, int] = {}

    def record(self, latency_ms: int, success: bool, strategy: str = "unknown"):
        self.total_requests += 1
        self.total_latency_ms += latency_ms
        if not success:
            self.errors += 1
        self.strategy_counts[strategy] = self.strategy_counts.get(strategy, 0) + 1


metrics = EngineMetrics()


async def execute(
    prompt: str,
    *,
    mode: BlendMode | str = BlendMode.BEST,
    messages: list[dict[str, str]] | None = None,
    trace_id: str | None = None,
    **kwargs: Any,
) -> BlendResult:
    """Core execution entry point.

    Simplified for public release - uses pre-trained ELO, no dynamic recipe learning.
    """
    start_time = time.monotonic()
    trace_id = trace_id or uuid.uuid4().hex[:12]
    cfg = get_config()
    provider = get_provider()
    await provider.startup()

    if isinstance(mode, str):
        mode = BlendMode(mode)

    # 1. Intent Analysis
    intent = classify(prompt)
    slots = cfg.all_slots()

    # 2. Strategy Selection
    strategy = select_strategy(intent, mode, slots)
    logger.info(
        "Execute: mode=%s strategy=%s complexity=%.2f trace=%s",
        mode.value, strategy.value, intent.complexity, trace_id
    )

    # 3. Execute based on selected strategy
    try:
        result = await _execute_legacy(prompt, slots, strategy, cfg, intent, messages, trace_id, **kwargs)
    except Exception as e:
        logger.exception("Execute failed for trace=%s: %s", trace_id, e)
        result = BlendResult(
            success=False,
            content=f"[OpenBlend] Execution error: {e}",
            strategy=strategy,
            trace_id=trace_id,
        )

    latency_ms = int((time.monotonic() - start_time) * 1000)
    result.latency_ms = latency_ms
    result.trace_id = trace_id
    metrics.record(latency_ms, result.success, result.strategy.value)

    return result


def _select_strategy_simple(intent: Intent, mode: BlendMode, slot_count: int) -> Strategy:
    if mode == BlendMode.FAST or slot_count < 2 or mode == BlendMode.CHEAP:
        return Strategy.ROUTE
    if intent.complexity < 0.3:
        return Strategy.ROUTE
    if intent.complexity < 0.7:
        return Strategy.BEST_OF_N
    return Strategy.BEST_OF_N


async def _execute_legacy(
    prompt: str, slots: list[ProviderSlot], strategy: Strategy,
    cfg: Any, intent: Intent, messages: list | None, trace_id: str | None, **kwargs: Any,
) -> BlendResult:
    """Legacy strategy dispatch."""
    if strategy == Strategy.ROUTE:
        return await _execute_route(prompt, slots, messages=messages, trace_id=trace_id, **kwargs)
    elif strategy == Strategy.BEST_OF_N:
        return await _execute_best_of_n(
            prompt, slots, cfg.judge_pass_threshold, intent_type=intent.task_type,
            messages=messages, trace_id=trace_id, **kwargs
        )
    else:
        return await _execute_route(prompt, slots, messages=messages, trace_id=trace_id, **kwargs)


async def _execute_route(
    prompt: str, slots: list[ProviderSlot], messages: list[dict] | None = None, **kwargs: Any
) -> BlendResult:
    """Direct route - use ELO best slot."""
    from openblend_public.memory.elo import best_provider_for
    from openblend_public.providers.unified import get_provider

    provider = get_provider()

    # Try to use ELO champion for this task type
    best = best_provider_for("general")  # Default to general if no category
    slot = None
    if best:
        prov, mod = best
        for s in slots:
            if s.provider == prov and s.model == mod:
                slot = s
                break

    # Fallback to strongest by cost
    if not slot:
        slot = get_judge_slot(slots)

    response = await provider.generate(prompt, slot, messages=messages, **kwargs)

    return BlendResult(
        success=response.success,
        content=response.content,
        strategy=Strategy.ROUTE,
        paths=1,
        models_used=[response.model],
        total_cost=response.cost,
    )


async def _execute_best_of_n(
    prompt: str, slots: list[ProviderSlot], threshold: float, intent_type: str, **kwargs: Any,
) -> BlendResult:
    """Best of N - get multiple proposals, judge picks best."""
    from openblend_public.providers.unified import get_provider
    from openblend_public.nodes.propose import propose, filter_successful
    from openblend_public.nodes.select import select_best

    provider = get_provider()
    propose_slots = get_propose_slots(slots, n=3, task_type=intent_type)
    responses = await propose(prompt, propose_slots, **kwargs)
    successful = filter_successful(responses)

    if not successful:
        return await _execute_route(prompt, slots, **kwargs)

    judge_slot = get_judge_slot(slots)
    best, score = await select_best(prompt, successful, judge_slot, threshold, **kwargs)

    total_cost = sum(r.cost for r in responses) + (best.cost if best else 0)

    return BlendResult(
        success=best.success if best else False,
        content=best.content if best else "",
        strategy=Strategy.BEST_OF_N,
        paths=len(successful),
        models_used=[r.model for r in successful] + ([best.model] if best else []),
        judge_score=score,
        judge_passed=score >= threshold,
        total_cost=total_cost,
    )


async def execute_stream(prompt: str, **kwargs: Any) -> AsyncIterator[StreamChunk]:
    """Streaming response support."""
    result = await execute(prompt, **kwargs)
    yield StreamChunk(content=result.content, done=True)


def _pick_slot_for_tier(slots: list[ProviderSlot], tier_pref: str | None) -> ProviderSlot | None:
    """Pick a slot matching the preferred tier."""
    if not tier_pref:
        return None
    tier_map = {"free": Tier.FREE, "cheap": Tier.CHEAP, "standard": Tier.STANDARD, "premium": Tier.PREMIUM}
    target = tier_map.get(tier_pref)
    if not target:
        return None
    http_slots = [s for s in slots if s.transport != "cli"]
    matching = [s for s in http_slots if s.tier == target]
    return matching[0] if matching else None
