"""Core types for OpenBlend Public — all shared data structures."""

from __future__ import annotations

from dataclasses import dataclass, field, asdict
from enum import Enum
from typing import Any


# ── Enums ───────────────────────────────────────────────────────────────────

class Tier(str, Enum):
    FREE = "free"
    CHEAP = "cheap"
    STANDARD = "standard"
    PREMIUM = "premium"


class Strategy(str, Enum):
    ROUTE = "route"
    BEST_OF_N = "best_of_n"
    CRITIQUE_REFINE = "critique_refine"
    FULL_BLEND = "full_blend"


class BlendMode(str, Enum):
    FAST = "fast"
    BEST = "best"
    CHEAP = "cheap"


class Transport(str, Enum):
    HTTP = "http"
    CLI = "cli"


# ── Provider Config ──────────────────────────────────────────────────────────

@dataclass
class ModelConfig:
    """A single model within a provider."""

    id: str
    cost_input: float = 0.0   # $/M input tokens
    cost_output: float = 0.0  # $/M output tokens
    tier: Tier = Tier.FREE

    @property
    def is_free(self) -> bool:
        return self.cost_input == 0.0 and self.cost_output == 0.0

    def estimate_cost(self, input_tokens: int, output_tokens: int) -> float:
        """Estimate cost in dollars."""
        return (
            input_tokens * self.cost_input + output_tokens * self.cost_output
        ) / 1_000_000


@dataclass
class ProviderConfig:
    """Configuration for a single LLM provider."""

    name: str
    base_url: str = ""
    api_key_env: str = ""
    api_key: str = ""          # Resolved at runtime from env
    models: list[ModelConfig] = field(default_factory=list)
    rate_limit: int = 60       # RPM
    timeout: int = 30          # seconds
    transport: Transport = Transport.HTTP
    cli_bin: str | None = None

    @property
    def has_key(self) -> bool:
        if self.transport == Transport.CLI:
            return True
        return bool(self.api_key) or not self.api_key_env

    @property
    def cheapest_model(self) -> ModelConfig | None:
        return min(self.models, key=lambda m: m.cost_output) if self.models else None

    @property
    def strongest_model(self) -> ModelConfig | None:
        return max(self.models, key=lambda m: m.cost_output) if self.models else None


@dataclass
class ProviderSlot:
    """A resolved provider + model combination ready to use."""

    provider: str
    model: str
    base_url: str
    api_key: str
    cost_input: float = 0.0
    cost_output: float = 0.0
    tier: Tier = Tier.FREE
    timeout: int = 30
    transport: Transport = Transport.HTTP
    cli_bin: str | None = None

    @property
    def is_free(self) -> bool:
        return self.cost_input == 0.0 and self.cost_output == 0.0


# ── LLM Response ───────────────────────────────────────────────────────────

@dataclass
class LLMResponse:
    """Standard response from any model call."""

    content: str
    model: str
    provider: str = ""
    tokens_used: int = 0
    input_tokens: int = 0
    output_tokens: int = 0
    cost: float = 0.0
    latency_ms: int = 0
    confidence: float = 1.0
    raw_response: dict[str, Any] = field(default_factory=dict)

    @property
    def success(self) -> bool:
        return bool(self.content) and self.raw_response.get("success", True)


@dataclass
class StreamChunk:
    """A single chunk in a streaming response."""

    content: str = ""
    done: bool = False
    model: str = ""
    provider: str = ""


# ── Intent ───────────────────────────────────────────────────────────────────

@dataclass
class Intent:
    """Classification result for a user prompt."""

    task_type: str = "general"
    complexity: float = 0.2
    confidence: float = 0.5
    suggested_strategy: Strategy = Strategy.ROUTE
    conflict_potential: float = 0.0
    blueprint_focus: list[str] = field(default_factory=list)


# ── Judge ────────────────────────────────────────────────────────────────────

@dataclass
class JudgeVerdict:
    """Result from the quality judge."""

    reasoning_chain: str = ""
    critique: str = ""
    scores: dict[str, float] = field(default_factory=dict)
    overall: float = 0.0
    passed: bool = False
    cost: float = 0.0
    tokens_used: int = 0


# ── Blend Result ────────────────────────────────────────────────────────────

@dataclass
class BlendResult:
    """Final output from the Blend pipeline."""

    success: bool = False
    content: str = ""
    mode: str = "best"
    strategy: Strategy = Strategy.ROUTE
    paths: int = 1
    models_used: list[str] = field(default_factory=list)
    judge_score: float = 0.0
    judge_passed: bool = False
    total_cost: float = 0.0
    latency_ms: int = 0
    trace_id: str = ""
    refine_rounds: int = 0

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["strategy"] = self.strategy.value
        return d
