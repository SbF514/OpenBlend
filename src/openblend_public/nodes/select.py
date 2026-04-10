"""Select node — Best-of-N selection with consistency checking."""

from __future__ import annotations

import logging

from openblend_public.core.types import LLMResponse, ProviderSlot
from openblend_public.nodes.judge import judge

logger = logging.getLogger("openblend_public.nodes.select")


async def select_best(
    question: str,
    candidates: list[LLMResponse],
    judge_slot: ProviderSlot,
    threshold: float = 0.75,
    trace_id: str | None = None,
) -> tuple[LLMResponse | None, float]:
    """Score N candidates with the judge and return the best one (CISC weighted)."""
    if len(candidates) == 1:
        # Pass confidence to judge (V2.1)
        if not candidates[0].success:
            return None, 0.0
        verdict = await judge(question, candidates[0].content, judge_slot, threshold, response_confidence=candidates[0].confidence)
        return candidates[0], verdict.overall

    best_response = None
    best_score = 0.0

    for candidate in candidates:
        if not candidate.success:
            continue
        # V2.1: Pass the model's self-confidence to the external judge
        verdict = await judge(question, candidate.content, judge_slot, threshold, response_confidence=candidate.confidence)
        if verdict.overall > best_score:
            best_score = verdict.overall
            best_response = candidate

    logger.info(
        "Select: best=%.2f from %d candidates (Weighted by Self-Confidence)",
        best_score, len(candidates),
    )
    return best_response, best_score


async def select_by_consistency(
    candidates: list[LLMResponse],
) -> LLMResponse:
    """Select based on weighted agreement (CISC 2.0).

    Score = Sum of overlaps with other candidates, weighted by each candidate's confidence.
    """
    successful = [c for c in candidates if c.success]
    if not successful:
        return candidates[0] if candidates else LLMResponse(content="", model="none", success=False)
    if len(successful) == 1:
        return successful[0]

    # Weighted overlap scoring: overlap * self_confidence
    scores = []
    for i, c in enumerate(successful):
        words_i = set(c.content.lower().split())
        total_weighted_overlap = 0.0
        for j, other in enumerate(successful):
            if i == j:
                continue
            words_j = set(other.content.lower().split())
            overlap = len(words_i & words_j)
            # Consensus is stronger when more confident models agree
            total_weighted_overlap += (overlap * other.confidence)

        # Self-correction: also weight the primary candidate's confidence
        score = total_weighted_overlap * c.confidence
        scores.append(score)

    best_idx = scores.index(max(scores))
    logger.info("CISC Weighted Consensus: chose candidate %d (score=%.2f, self_conf=%.2f)",
                best_idx, scores[best_idx], successful[best_idx].confidence)
    return successful[best_idx]
