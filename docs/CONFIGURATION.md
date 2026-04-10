# Configuration

This guide explains how to customize your OpenBlend Public configuration.

## Overview

Configuration lives in two files:

1. `blend.yaml` - Provider and model definitions, server settings
2. `.env` - API keys (never commit this to git!)

## Configuring Providers

### Provider Structure

Here's an example provider entry in `blend.yaml`:

```yaml
providers:
  - name: main-claude
    base_url: https://api.anthropic.com/v1
    api_key_env: BAOSI_API_KEY
    timeout: 180
    models:
      - id: "claude-3-5-sonnet-latest"
        cost_input: 3.0
        cost_output: 15.0
        tier: premium
```

**Fields:**
- `name`: Unique identifier for the provider
- `base_url`: OpenAI-compatible API endpoint URL
- `api_key_env`: Environment variable name that contains your API key
- `timeout`: Request timeout in seconds
- `models`: List of models available from this provider

**Model Fields:**
- `id`: Model ID as expected by the provider API
- `cost_input`: Cost per million input tokens (USD)
- `cost_output`: Cost per million output tokens (USD)
- `tier`: One of `free`, `cheap`, `standard`, `premium`

### Adding a New Provider

1. Add the provider entry to `providers:` in `blend.yaml`
2. Add the API key to your `.env` file with the name matching `api_key_env`
3. Run `openblend status` to verify it's detected

### Removing a Provider

Simply delete or comment out the provider entry from `blend.yaml`.

## Server Configuration

```yaml
server:
  host: "0.0.0.0"
  port: 8000
  debug: false
  cors_origins: ["*"]
```

**Fields:**
- `host`: Bind address (`0.0.0.0` to listen on all interfaces)
- `port`: Port to listen on
- `debug`: Enable debug mode for FastAPI
- `cors_origins`: CORS allowed origins

## Blend Configuration

```yaml
blend:
  default_mode: best
  judge_pass_threshold: 0.75
```

**Fields:**
- `default_mode`: Default blend mode (`best`, `fast`, or `cheap`)
- `judge_pass_threshold`: Minimum overall score for a candidate to pass (0.0 - 1.0)

## Tier Selection

OpenBlend uses tiers to manage cost vs capability:

| Tier | Description | When Used |
|------|-------------|-----------|
| `free` | No cost | Proposals |
| `cheap` | Low cost | Proposals, refinement |
| `standard` | Medium cost | Proposals |
| `premium` | Highest cost | Judge, selection |

The strategy automatically selects appropriate tiers based on the task.

## Example: Adding DeepSeek

```yaml
# Add to blend.yaml -> providers:
  - name: deepseek
    base_url: https://api.deepseek.com/v1
    api_key_env: DEEPSEEK_API_KEY
    timeout: 120
    models:
      - id: "deepseek-chat"
        cost_input: 0.14
        cost_output: 0.28
        tier: standard
```

Then add to `.env`:
```
DEEPSEEK_API_KEY=your-key-here
```

Run `openblend status` to confirm it's loaded.

## Environment Variables

Besides API keys, these environment variables affect behavior:

- `OPENBLEND_CONFIG_PATH` - Path to `blend.yaml` (defaults to project root)
- `OPENBLEND_TRAINED_DB_PATH` - Path to pre-trained ELO database (defaults to `trained/blend.db`)
- `OPENBLEND_API_ACCESS_KEY` - Optional API key for accessing the server
