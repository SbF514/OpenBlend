"""OpenBlend Public API Server — OpenAI-compatible.

Simplified version: only pre-trained inference, no autonomous evolution.
"""

from __future__ import annotations

import json
import logging
import os
import uuid
from typing import Any

from fastapi import FastAPI, HTTPException, Depends, Security
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security.api_key import APIKeyHeader
from fastapi.responses import StreamingResponse, JSONResponse

from openblend_public.api.schemas import (
    ChatCompletionRequest, ChatCompletionResponse, ChatChoice,
    ChatMessageResponse, UsageInfo, BlendMeta,
)
from openblend_public.config import get_config
from openblend_public.core.engine import execute, execute_stream

logger = logging.getLogger("openblend_public.api")

# --- Security ---
API_KEY_NAME = "Authorization"
api_key_header = APIKeyHeader(name=API_KEY_NAME, auto_error=False)


async def get_api_key(api_key: str = Security(api_key_header)) -> Any:
    master_key = os.getenv("OPENBLEND_API_ACCESS_KEY")
    if not master_key:
        return None  # No auth required by default
    if api_key and (api_key == f"Bearer {master_key}" or api_key == master_key):
        return api_key
    raise HTTPException(status_code=403, detail="Could not validate credentials")


app = FastAPI(title="🍸 OpenBlend Public - Pre-trained Blended LLM", version="0.1.0")

# --- CORS Configuration ---
# Allow all origins for development; in production this can be restricted
cfg = get_config()
app.add_middleware(
    CORSMiddleware,
    allow_origins=cfg.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
async def startup() -> None:
    from openblend_public.providers.unified import get_provider
    provider = get_provider()
    await provider.startup()
    logger.info("OpenBlend Public API started — ELO Routing Active")


@app.on_event("shutdown")
async def shutdown() -> None:
    from openblend_public.providers.unified import get_provider
    provider = get_provider()
    await provider.shutdown()


@app.post("/v1/chat/completions")
async def chat_completions(req: ChatCompletionRequest, authenticated: Any = Depends(get_api_key)) -> Any:
    """Chat Completion endpoint (OpenAI-compatible)."""
    model = req.model.lower()
    messages = [{"role": m.role, "content": m.content} for m in req.messages]
    prompt = messages[-1]["content"] if messages else ""

    # Mode determination
    mode = "best"
    if "fast" in model:
        mode = "fast"
    elif "cheap" in model:
        mode = "cheap"

    if req.stream:
        return StreamingResponse(
            _stream_response(prompt, mode, messages, req),
            media_type="text/event-stream",
        )

    # Execute Blend pipeline
    result = await execute(prompt, mode=mode, messages=messages, **vars(req))

    # Count tokens approximately (4 chars ~= 1 token)
    prompt_tokens = len(prompt) // 4
    completion_tokens = len(result.content) // 4 if result.content else 0
    total_tokens = prompt_tokens + completion_tokens

    response = ChatCompletionResponse(
        id=f"chatcmpl-{result.trace_id}",
        model=f"blend/{mode}",
        choices=[ChatChoice(
            message=ChatMessageResponse(content=result.content),
            finish_reason="stop",
        )],
        usage=UsageInfo(
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_tokens=total_tokens,
        ),
        blend=BlendMeta(
            recipe=result.strategy.value,
            paths=result.paths,
            models_used=result.models_used,
            judge_score=result.judge_score,
            cost=result.total_cost,
            trace_id=result.trace_id,
        ),
    )

    # Standard OpenAI response with custom headers
    return JSONResponse(
        content=response.dict(),
        headers={
            "X-Blend-Strategy": result.strategy.value,
            "X-Blend-Trace": result.trace_id,
            "X-Blend-Models": ",".join(result.models_used) if result.models_used else "",
        }
    )


async def _stream_response(prompt: str, mode: str, messages: list[dict[str, str]], req: ChatCompletionRequest):
    completion_id = f"chatcmpl-stream-{uuid.uuid4().hex[:8]}"
    async for chunk in execute_stream(prompt, mode=mode, messages=messages, **vars(req)):
        if chunk.done:
            yield f"data: {json.dumps({'id': completion_id, 'object': 'chat.completion.chunk', 'choices': [{'index': 0, 'delta': {}, 'finish_reason': 'stop'}]})}\n\n"
            yield "data: [DONE]\n\n"
            return
        if chunk.content:
            data = {"id": completion_id, "object": "chat.completion.chunk", "choices": [{"index": 0, "delta": {"content": chunk.content}}]}
            yield f"data: {json.dumps(data)}\n\n"


@app.get("/health")
async def health() -> dict:
    return {"status": "healthy", "engine": "OpenBlend Public", "elo_active": True}


@app.get("/v1/models")
async def list_models() -> dict:
    cfg = get_config()
    models = [
        {"id": "blend/best", "object": "model", "owned_by": "openblend"},
        {"id": "blend/fast", "object": "model", "owned_by": "openblend"},
        {"id": "blend/cheap", "object": "model", "owned_by": "openblend"},
    ]
    for slot in cfg.all_slots():
        models.append({"id": f"{slot.provider}/{slot.model}", "object": "model", "owned_by": slot.provider})
    return {"object": "list", "data": models}


def serve() -> None:
    import uvicorn
    cfg = get_config()
    uvicorn.run(app, host=cfg.host, port=cfg.port)


if __name__ == "__main__":
    serve()
