"""Strategy selector — Simplified adaptive choice based on intent and providers.

P0 Refactoring: Removed complex ELO dependencies, simplified slot selection.
"""

from __future__ import annotations
import logging
import random
from openblend_public.core.types import BlendMode, Intent, ProviderSlot, Strategy, Tier
from openblend_public.memory.store import get_rankings, best_provider_for

logger = logging.getLogger("openblend_public.core.strategy")


def select_strategy(intent: Intent, mode: BlendMode, slots: list[ProviderSlot], budget_exhausted: bool = False) -> Strategy:
    """Choose the optimal strategy based on mode, intent, and available providers.

    Simplified: ELO already trained, just use complexity-based selection.
    """
    if budget_exhausted or len(slots) < 2:
        return Strategy.ROUTE
    if mode == BlendMode.FAST:
        return Strategy.ROUTE
    if mode == BlendMode.CHEAP:
        return Strategy.BEST_OF_N if intent.complexity > 0.7 else Strategy.ROUTE

    # BlendMode.BEST — simplified adaptive
    if intent.complexity < 0.3:
        return Strategy.ROUTE
    if intent.complexity < 0.7:
        return Strategy.BEST_OF_N
    return Strategy.BEST_OF_N  # Simplified: always Best-of-N


def get_propose_slots(
    slots: list[ProviderSlot],
    n: int = 3,
    task_type: str | None = "general",
    tier_limit: Tier | None = None,
) -> list[ProviderSlot]:
    """Select N best slots for proposal generation (ELO-Aware with Fallback)."""

    # 1. Filter by tier if requested
    available = slots
    if tier_limit:
        tiers = [Tier.FREE, Tier.CHEAP, Tier.STANDARD, Tier.PREMIUM]
        limit_idx = tiers.index(tier_limit)
        allowed_tiers = set(tiers[:limit_idx + 1])
        available = [s for s in available if s.tier in allowed_tiers]

    if not available:
        available = slots

    # 2. Get ELO rankings
    try:
        rankings = {f"{r['provider']}/{r['model']}": r['elo'] for r in get_rankings(task_type or "general")}
    except (KeyError, TypeError, ValueError):
        rankings = {}

    if not rankings:
        # Genesis Phase: Use a mix of models
        return random.sample(available, min(n, len(available)))

    # 3. Weighted Selection by ELO
    def get_elo(slot):
        return rankings.get(f"{slot.provider}/{slot.model}", 1200)

    sorted_available = sorted(available, key=get_elo, reverse=True)
    return sorted_available[:n]


def get_judge_slot(slots: list[ProviderSlot]) -> ProviderSlot:
    """Select the strongest slot for judging (Champion Selection with Fallback)."""

    available = [s for s in slots if s.transport != "cli"]
    if not available:
        available = slots

    # Try to pick the current ELO champion
    try:
        champion = best_provider_for("reasoning")
        if champion:
            prov, mod = champion
            for s in available:
                if s.provider == prov and s.model == mod:
                    return s
    except (KeyError, TypeError):
        pass

    # Fallback to premium tier
    premium = [s for s in available if s.tier.value == "premium"]
    if premium:
        return premium[0]

    return max(available, key=lambda s: s.cost_output)


def get_critique_slot(slots: list[ProviderSlot]) -> ProviderSlot:
    """Select premium slot for critique — same logic as judge."""
    return get_judge_slot(slots)


def get_refine_slot(slots: list[ProviderSlot]) -> ProviderSlot:
    """Select a cheap slot for refinement."""
    return min(slots, key=lambda s: s.cost_output)
