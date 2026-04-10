"""Propose node — parallel candidate generation from cheap models."""

from __future__ import annotations

import logging
import re
from typing import Any

from openblend_public.core.types import LLMResponse, ProviderSlot
from openblend_public.providers.unified import get_provider

logger = logging.getLogger("openblend_public.nodes.propose")

CISC_PROMPT_WRAPPER = """You are a highly accurate reasoning model.
After providing your response to the user's question, you MUST evaluate your own correctness probability.

Return your response in this EXACT format:
[CONFIDENCE]: 0.X (your estimated probability of being correct, between 0.0 and 1.0)
[CONTENT]: (your actual answer to the question)

USER QUESTION:
{prompt}"""


async def propose(
    prompt: str,
    slots: list[ProviderSlot],
    trace_id: str | None = None,
    **kwargs: Any,
) -> list[LLMResponse]:
    """Generate candidate responses with self-estimated confidence (CISC)."""
    provider = get_provider()
    wrapped_prompt = CISC_PROMPT_WRAPPER.format(prompt=prompt)
    results = await provider.generate_many(wrapped_prompt, slots, **kwargs)

    for r in results:
        if r.success:
            # Extract confidence and clean content
            conf_match = re.search(r"\[CONFIDENCE\]:\s*([\d.]+)", r.content)
            content_match = re.search(r"\[CONTENT\]:\s*(.*)", r.content, re.DOTALL)

            if conf_match:
                try:
                    r.confidence = float(conf_match.group(1))  # type: ignore[attr-defined]
                except ValueError:
                    r.confidence = 0.5  # type: ignore[attr-defined]

            if content_match:
                r.content = content_match.group(1).strip()
            else:
                # If fallback parsing failed, keep as is but default confidence
                r.content = r.content.replace("[CONFIDENCE]:", "").strip()
                r.confidence = 0.5  # type: ignore[attr-defined]

    successful = [r for r in results if r.success]
    logger.info(
        "Propose: %d/%d successful from %s",
        len(successful), len(results),
        [f"{s.provider}/{s.model}" for s in slots],
    )
    return results


def filter_successful(responses: list[LLMResponse]) -> list[LLMResponse]:
    """Filter to only successful responses."""
    return [r for r in responses if r.success]
