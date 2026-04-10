"""Pydantic schemas — OpenAI-compatible request/response models."""

from __future__ import annotations

from typing import Any
from pydantic import BaseModel, Field


# --- Request ---

class ChatMessage(BaseModel):
    role: str = "user"
    content: str = ""


class ChatCompletionRequest(BaseModel):
    """OpenAI-compatible chat completion request."""

    model: str = "blend/best"
    messages: list[ChatMessage] = Field(default_factory=list)
    max_tokens: int | None = None
    temperature: float | None = None
    stream: bool = False
    # Blend-specific extensions
    extra_body: dict[str, Any] | None = None


# --- Response ---

class ChatMessageResponse(BaseModel):
    role: str = "assistant"
    content: str = ""


class ChatChoice(BaseModel):
    index: int = 0
    message: ChatMessageResponse
    finish_reason: str = "stop"


class UsageInfo(BaseModel):
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0


class BlendMeta(BaseModel):
    """Blend-specific metadata in the response."""

    recipe: str = ""
    strategy: str = ""
    paths: int = 0
    models_used: list[str] = Field(default_factory=list)
    judge_score: float = 0.0
    cost: float = 0.0
    trace_id: str = ""


class ChatCompletionResponse(BaseModel):
    """OpenAI-compatible chat completion response."""

    id: str = ""
    object: str = "chat.completion"
    model: str = ""
    choices: list[ChatChoice] = Field(default_factory=list)
    usage: UsageInfo = Field(default_factory=UsageInfo)
    blend: BlendMeta | None = None


# --- Health ---

class HealthResponse(BaseModel):
    status: str = "ok"
    version: str = ""
    providers: list[str] = Field(default_factory=list)
