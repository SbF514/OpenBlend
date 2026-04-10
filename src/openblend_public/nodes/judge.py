"""Judge node — CoT reasoning evaluation (not bare JSON scoring).

Key V2 improvement over V1:
- Judge must chain-of-thought REASON before scoring
- Outputs structured critique, not just a number
- Parse failure → second judge fallback, not auto-pass
"""

from __future__ import annotations

import json
import logging
import re
from typing import Any

from openblend_public.core.types import JudgeVerdict, ProviderSlot
from openblend_public.providers.unified import get_provider

logger = logging.getLogger("openblend_public.nodes.judge")

JUDGE_PROMPT = """You are an expert quality judge. Evaluate the AI response below.

## Process
1. First, THINK step by step about the response quality
2. Then provide specific, actionable critique
3. Finally, score each dimension

## Question (truncated)
{question}

## Response to evaluate (truncated)
{response}

## Required output format
Think through your evaluation, then output a JSON block:

```json
{{
  "reasoning": "Your step-by-step analysis of the response quality...",
  "critique": "One specific, actionable suggestion for improvement",
  "scores": {{
    "accuracy": 0.X,
    "completeness": 0.X,
    "clarity": 0.X,
    "reasoning": 0.X
  }},
  "overall": 0.X
}}
```

Scoring rules:
- 0.8+ = genuinely excellent, few issues
- 0.6-0.8 = good but has notable gaps
- 0.4-0.6 = mediocre, significant issues
- <0.4 = poor quality
- overall = weighted: accuracy 30%, completeness 25%, clarity 20%, reasoning 25%"""


async def judge(
    question: str,
    response_content: str,
    slot: ProviderSlot,
    threshold: float = 0.75,
    trace_id: str | None = None,
    response_confidence: float = 0.5,  # Added in V2.1: The confidence of the response being judged
) -> JudgeVerdict:
    """Have a model judge the quality of a response using CoT reasoning.

    Unlike V1, this now weights the judge's score with the model's self-confidence (CISC).
    """
    prompt = JUDGE_PROMPT.format(
        question=question[:500],
        response=response_content[:2000],
    )

    provider = get_provider()
    result = await provider.generate(prompt, slot, max_tokens=500)

    verdict = JudgeVerdict(cost=result.cost, tokens_used=result.tokens_used)

    try:
        data = _extract_json(result.content)
        verdict.reasoning_chain = str(data.get("reasoning", ""))
        verdict.critique = str(data.get("critique", ""))
        scores = data.get("scores", {})
        verdict.scores = {k: float(v) for k, v in scores.items()}

        # CISC Weighted Scoring (0.1 Self-Confidence + 0.9 External Judge)
        raw_overall = float(data.get("overall", 0))
        verdict.overall = (response_confidence * 0.1) + (raw_overall * 0.9)
        verdict.passed = verdict.overall >= threshold
    except (json.JSONDecodeError, ValueError, KeyError) as e:
        logger.warning("Judge parse failed: %s — attempting fallback", e)
        # Retain response_confidence for fallback as well
        verdict = await _fallback_judge(question, response_content, slot, threshold, response_confidence)

    logger.info(
        "Judge: raw=%.2f self=%.2f weighted=%.2f passed=%s",
        raw_overall if 'raw_overall' in locals() else 0,
        response_confidence,
        verdict.overall,
        verdict.passed
    )
    return verdict


async def _fallback_judge(
    question: str,
    response_content: str,
    slot: ProviderSlot,
    threshold: float,
    response_confidence: float = 0.5,
) -> JudgeVerdict:
    """Simpler fallback judge when CoT parse fails."""
    prompt = (
        f"Rate this response 0.0-1.0. Output ONLY a number.\n\n"
        f"Question: {question[:300]}\n\nResponse: {response_content[:1000]}"
    )
    provider = get_provider()
    result = await provider.generate(prompt, slot, max_tokens=10)

    verdict = JudgeVerdict(cost=result.cost, tokens_used=result.tokens_used)
    try:
        match = re.search(r"[\d.]+", result.content)
        score = float(match.group()) if match else 0.5  # type: ignore
        raw_score = min(1.0, max(0.0, score))
        # Even in fallback, apply CISC weighting (0.1 self + 0.9 external)
        verdict.overall = (response_confidence * 0.1) + (raw_score * 0.9)
        verdict.passed = verdict.overall >= threshold
        verdict.critique = f"Fallback (Raw: {raw_score:.2f}, Weighted by Self: {response_confidence:.2f})"
    except (AttributeError, ValueError):
        logger.error("Fallback judge also failed — defaulting to threshold")
        verdict.overall = threshold
        verdict.passed = True
        verdict.critique = "Both judges failed to parse"

    return verdict


def _extract_json(text: str) -> dict[str, Any]:
    """Extract JSON from LLM output (handles markdown fences, prose wrapping)."""
    text = text.strip()

    # Strip markdown code fences
    if "```" in text:
        text = re.sub(r"```(?:json)?\s*\n?", "", text)
        text = re.sub(r"\n?```\s*$", "", text)
        text = text.strip()

    # Direct parse
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    # Find deepest {...} block
    match = re.search(r"\{.*\}", text, re.DOTALL)
    if match:
        try:
            return json.loads(match.group())
        except json.JSONDecodeError:
            pass

    raise json.JSONDecodeError("No valid JSON found", text, 0)
