# Getting Started Guide

This guide will walk you through getting API keys from different providers and setting up OpenBlend Public.

## Step 1: Get Your API Keys

### Premium Provider (Required)

You need at least one premium API key for the judge role. We recommend:

### Anthropic Claude

1. Go to https://console.anthropic.com/
2. Sign up or log in
3. Go to API Keys → Create Key
4. Copy your API key
5. Add to `.env`:
```env
BAOSI_API_KEY=sk-ant-your-key-here
```

### OpenAI

1. Go to https://platform.openai.com/
2. Sign up or log in
3. Go to API Keys → Create new secret key
4. Copy your API key
5. Add to `.env`:
```env
OPENAI_API_KEY=sk-your-key-here
```

Update `blend.yaml` to point to your provider if you use OpenAI instead of Anthropic.

### Free Providers (Optional but Recommended)

We've pre-configured free models from these providers. Adding them gives you more candidates and better results at no cost.

### Kilo Gateway

Kilo Gateway provides free access to many models.

1. Go to https://kilo.ai/
2. Sign up for an account
3. Go to API Keys → Create API Key
4. Copy your API key
5. Add to `.env`:
```env
KILO_API_KEY=eyJhbGciOiJIUzI1NiIs...
```

### OpenRouter

OpenRouter has a free tier with many models.

1. Go to https://openrouter.ai/
2. Sign up or log in
3. Go to API Keys → Create key
4. Copy your API key
5. Add to `.env`:
```env
OPENROUTER_API_KEY=sk-or-v1-your-key-here
```

## Step 2: Install Dependencies

```bash
pip install -e .
```

Or from PyPI:
```bash
pip install openblend-public
```

## Step 3: Configure

Copy the example environment file:

```bash
cp .env.example .env
```

Edit `.env` and add the API keys you got in Step 1.

## Step 4: Verify

Check that everything is configured correctly:

```bash
openblend status
```

You should see a table of all your configured providers and the pre-trained ELO rankings.

## Step 5: Serve

Start the API server:

```bash
openblend serve
```

This starts the server on `http://localhost:8000`.

## Step 6: Test

Test with curl in another terminal:

```bash
curl http://localhost:8000/v1/models
```

You should get a response listing the available models.

Test a completion:

```bash
curl http://localhost:8000/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{
    "model": "blend/fast",
    "messages": [{"role": "user", "content": "What is 2+2?"}]
  }'
```

You should get a response back from the model!

## Next Steps

- Read the [API Documentation](API.md) to learn how to use the OpenAI-compatible API
- See [Configuration](CONFIGURATION.md) to learn how to add your own models
- Check the [FAQ](FAQ.md) for common questions
