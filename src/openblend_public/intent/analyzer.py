"""Intent Analyzer — multi-level classification for routing decisions."""

from __future__ import annotations
import logging
import re
from openblend_public.core.types import Intent, Strategy

logger = logging.getLogger("openblend_public.intent.analyzer")

_CODE_SIGNALS = {"code","function","class","def ","import ","error","bug","debug","implement","refactor","api","endpoint","database","sql","algorithm","代码","函数","实现","重构","接口","调试","报错"}
_ANALYSIS_SIGNALS = {"analyze","compare","evaluate","assess","review","critique","pros and cons","trade-off","implications","strategy","architecture","design","plan","分析","比较","评估","架构","设计"}
_REASONING_SIGNALS = {"prove","proof","theorem","calculate","derive","equation","math","probability","logic","reasoning","why does","how does","step by step","证明","计算","推导","数学","逻辑","推理"}
_CREATIVE_SIGNALS = {"write","story","poem","essay","creative","imagine","brainstorm","fiction","写","故事","诗","文章","创意","想象"}


def classify(prompt: str) -> Intent:
    prompt_lower = prompt.lower()
    words = set(prompt_lower.split())
    scores: dict[str, int] = {
        t: _signal_score(prompt_lower, words, s)
        for t, s in [
            ("code", _CODE_SIGNALS),
            ("analysis", _ANALYSIS_SIGNALS),
            ("reasoning", _REASONING_SIGNALS),
            ("creative", _CREATIVE_SIGNALS),
        ]
    }
    task_type = max(scores, key=scores.get) if max(scores.values()) > 0 else "general"
    type_confidence = (
        max(scores.values()) / max(1, sum(scores.values()))
        if max(scores.values()) > 0
        else 0.3
    )
    complexity = _estimate_complexity(prompt, prompt_lower, len(prompt))
    if complexity < 0.3:
        strategy = Strategy.ROUTE
    elif complexity < 0.6:
        strategy = Strategy.BEST_OF_N
    elif complexity < 0.8:
        strategy = Strategy.CRITIQUE_REFINE
    else:
        strategy = Strategy.FULL_BLEND

    conflict = _estimate_conflict(prompt_lower, task_type, complexity)
    focus = _identify_focus(prompt_lower, task_type)

    intent = Intent(
        task_type=task_type,
        complexity=complexity,
        confidence=type_confidence,
        suggested_strategy=strategy,
        conflict_potential=conflict,
        blueprint_focus=focus,
    )
    logger.info(
        "Intent: type=%s complexity=%.2f strategy=%s conflict=%.2f",
        task_type, complexity, strategy.value, conflict
    )
    return intent


def _estimate_conflict(prompt_lower: str, task_type: str, complexity: float) -> float:
    """Estimate how likely models are to disagree (0.0 - 1.0)."""
    score = 0.0
    # Subjective tasks have higher conflict potential
    if task_type in ("creative", "analysis"):
        score += 0.4
    elif task_type == "reasoning":
        score += 0.2

    # Complexity increases conflict (more steps = more places to diverge)
    score += complexity * 0.4

    # Explicit opinion/subjectivity signals
    subjective_signals = {"opinion", "better", "best", "should", "worst", "favorite", "perspective", "观点", "最好", "应该"}
    if any(s in prompt_lower for s in subjective_signals):
        score += 0.2

    return min(1.0, score)


def _identify_focus(prompt_lower: str, task_type: str) -> list[str]:
    """Suggest focus areas for the Master Blueprint."""
    focus = []
    if any(s in prompt_lower for s in ["format", "json", "markdown", "csv", "table", "格式"]):
        focus.append("formatting")

    if task_type == "code":
        focus.extend(["implementation", "edge cases"])
        if any(s in prompt_lower for s in ["performance", "fast", "slow", "optimize"]):
            focus.append("performance")
        if any(s in prompt_lower for s in ["clean", "readable", "style", "lint"]):
            focus.append("readability")
    elif task_type == "creative":
        focus.extend(["style", "tone", "flow"])
    elif task_type == "analysis":
        focus.extend(["depth", "objectivity", "structure"])
    elif task_type == "reasoning":
        focus.extend(["logic", "accuracy", "completeness"])
    else:
        if "formatting" not in focus:
            focus.append("clarity")

    return focus


def _signal_score(prompt_lower, words, signals):
    score = 0
    for s in signals:
        if " " in s:
            if s in prompt_lower:
                score += 2
        elif s in words:
            score += 1
    return score


def _estimate_complexity(prompt, prompt_lower, prompt_len):
    score = 0.0
    if prompt_len < 50:
        score += 0.05
    elif prompt_len < 200:
        score += 0.2
    elif prompt_len < 500:
        score += 0.4
    else:
        score += 0.6
    score += min(0.15, prompt.count("?") * 0.05)
    score += min(0.15, len(re.findall(r"(?:^|\n)\s*(?:\d+[.)]|[-*])\s", prompt)) * 0.05)
    constraint_words = {"must","should","exactly","only","at least","必须","至少","恰好"}
    score += min(0.1, sum(1 for w in constraint_words if w in prompt_lower) * 0.03)
    return min(1.0, score)
