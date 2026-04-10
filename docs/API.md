# API Documentation

OpenBlend Public provides an **OpenAI-compatible API** — you can use it with any OpenAI client library.

## Endpoints

### POST `/v1/chat/completions`

Create a chat completion (OpenAI-compatible).

**Request:**
Same as OpenAI's [ChatCompletion](https://platform.openai.com/docs/api-reference/chat/create) request format.

```json
{
  "model": "blend/best",
  "messages": [
    {"role": "user", "content": "Write a Python function to check if a string is a palindrome"}
  ],
  "max_tokens": 1000,
  "temperature": 0.7,
  "stream": false
}
```

**Supported fields:**
- `model` (string): One of: `blend/best`, `blend/fast`, `blend/cheap`, or `provider/model` for direct routing
- `messages` (array): List of chat messages, same format as OpenAI
- `max_tokens` (int, optional): Maximum tokens to generate
- `temperature` (float, optional): Sampling temperature
- `stream` (bool, optional): Enable streaming (default: `false`)
- `extra_body` (dict, optional): Extra Blend-specific parameters

**Response:**
Same as OpenAI's response format, with extra Blend metadata in the `blend` field.

```json
{
  "id": "chatcmpl-abc123",
  "object": "chat.completion",
  "model": "blend/best",
  "choices": [{
    "index": 0,
    "message": {
      "role": "assistant",
      "content": "Here's a Python function...",
    },
    "finish_reason": "stop"
  }],
  "usage": {
    "prompt_tokens": 10,
    "completion_tokens": 50,
    "total_tokens": 60
  },
  "blend": {
    "recipe": "best_of_n",
    "paths": 3,
    "models_used": ["model1", "model2", "model3", "judge-model"],
    "judge_score": 0.87,
    "cost": 0.0023,
    "trace_id": "abc123xyz"
  }
}
```

**Response Headers:**
- `X-Blend-Strategy`: Strategy used (e.g., `route`, `best_of_n`)
- `X-Blend-Trace`: Trace ID for logging/debugging
- `X-Blend-Models`: Comma-separated list of models used

### Streaming

Set `stream: true` in the request to get streaming response. The format is the same as OpenAI's server-sent events.

Example with curl:

```bash
curl http://localhost:8000/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{
    "model": "blend/best",
    "messages": [{"role": "user", "content": "Count to 10"}],
    "stream": true
  }'
```

### GET `/v1/models`

List available models.

**Response:**
```json
{
  "object": "list",
  "data": [
    {"id": "blend/best", "object": "model", "owned_by": "openblend"},
    {"id": "blend/fast", "object": "model", "owned_by": "openblend"},
    {"id": "blend/cheap", "object": "model", "owned_by": "openblend"},
    {"id": "provider/model-name", "object": "model", "owned_by": "provider"}
  ]
}
```

### GET `/health`

Health check endpoint.

**Response:**
```json
{
  "status": "healthy",
  "engine": "OpenBlend Public",
  "elo_active": true
}
```

## Model IDs

| Model ID | Description |
|----------|-------------|
| `blend/best` | Adaptive: uses intent analysis to pick best strategy |
| `blend/fast` | Always direct route to best single model |
| `blend/cheap` | Always route to cheapest capable model |
| `provider/model` | Direct route to a specific model bypassing blending |

## Example Usage

### Python with openai package

```python
from openai import OpenAI

client = OpenAI(
    base_url="http://localhost:8000/v1",
    api_key="any"  # Not required for default local setup
)

# Non-streaming
response = client.chat.completions.create(
    model="blend/best",
    messages=[{"role": "user", "content": "What is the meaning of life?"}]
)

print(response.choices[0].message.content)

# Access Blend metadata
if hasattr(response, 'blend'):
    print(f"Strategy: {response.blend['strategy']}")
    print(f"Cost: ${response.blend['cost']:.4f}")
```

### Streaming

```python
from openai import OpenAI

client = OpenAI(base_url="http://localhost:8000/v1", api_key="any")

stream = client.chat.completions.create(
    model="blend/best",
    messages=[{"role": "user", "content": "Write a short poem"}],
    stream=True,
)

for chunk in stream:
    if chunk.choices[0].delta.content:
        print(chunk.choices[0].delta.content, end="")
```

### curl

```bash
# Non-streaming
curl http://localhost:8000/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{
    "model": "blend/fast",
    "messages": [{"role": "user", "content": "What is 2+2?"}]
  }'

# List models
curl http://localhost:8000/v1/models

# Health check
curl http://localhost:8000/health
```

## Authentication

By default, the API doesn't require authentication. To enable API key authentication:

1. Add to your `.env`:
```env
OPENBLEND_API_ACCESS_KEY=your-secret-key-here
```

2. Clients must include the header:
```
Authorization: Bearer your-secret-key-here
```
