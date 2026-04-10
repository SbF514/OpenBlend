# 🍸 OpenBlend

**Pre-trained blended LLM that outperforms any single model — just add your API keys and go.**

OpenBlend is the open-source distribution of pre-trained blended LLM. We do the training, you get the benefit — using our proven [Steer-then-Verify](#how-it-works) methodology with ELO-ranked model combinations that consistently outperforms your best single model.

## Getting the Pre-Trained ELO Database

This repo contains **only the code**. To use OpenBlend, you need the pre-trained ELO database. Contact the maintainers to get the latest `trained/blend.db` file, or build from the main OpenBlend training repo.

The `trained/` directory should contain:
```
trained/
└── blend.db          # Pre-trained ELO rankings
```

## 🚀 Quick Start

### 1. Install

```bash
pip install openblend-public
```

Or install from source:

```bash
git clone https://github.com/SbF514/OpenBlend.git
cd OpenBlend
pip install -e .
```

### 2. Configure

Copy the `.env.example` to `.env` and add your API keys:

```bash
cp .env.example .env
# Edit .env to add your API keys
```

You need at least one premium API key (we recommend Claude or OpenAI), and can optionally add free models from Kilo Gateway and OpenRouter.

### 3. Check Status

```bash
openblend status
```

This shows your configured providers and our pre-trained ELO rankings.

### 4. Serve

```bash
openblend serve
```

Starts an OpenAI-compatible API server at `http://localhost:8000`.

### 5. Use

Use it just like you would use OpenAI:

```python
from openai import OpenAI

client = OpenAI(
    base_url="http://localhost:8000/v1",
    api_key="any"  # API key not required for local server by default
)

response = client.chat.completions.create(
    model="blend/best",  # Adaptive - uses best strategy for your query
    messages=[{"role": "user", "content": "Write a Python function to check if a string is a palindrome"}]
)

print(response.choices[0].message.content)
```

## 🎯 Available Model Modes

| Model ID | What it does |
|----------|--------------|
| `blend/best` | **Default** — Adaptive: uses intent analysis to pick the best strategy (direct route or best-of-N selection) |
| `blend/fast` | Always routes directly to the best single model by ELO ranking (fastest) |
| `blend/cheap` | Optimizes for cost — uses cheapest available capable models |

## How It Works

### Our Methodology: Steer-then-Verify

1. **Intent Classification**: We analyze your prompt to detect task type (code, reasoning, analysis, creative) and complexity.
2. **ELO-Aware Selection**: We select the top-N best models for your task type based on our pre-trained ELO rankings.
3. **Parallel Generation**: All selected models generate candidate responses in parallel.
4. **Judge Verification**: Our strongest model scores each candidate on accuracy, completeness, clarity, and reasoning.
5. **Return Best**: The highest-scoring candidate is returned as the final answer.

This approach consistently outperforms any single model because:
- Different models have different strengths
- Self-confidence weighting (CISC) helps identify when models are sure vs unsure
- External judge verification catches hallucinations
- ELO rankings ensure we always start with the best candidates

### Where Does the ELO Data Come From?

We train the blend in our private main repository by running head-to-head battles between models on hundreds of benchmark questions. Every model gets an ELO rating for each task type (code, reasoning, analysis, creative). We periodically export these trained rankings to this open-source project.

You get the benefit of our training without having to run any battles or training yourself. You just add your API keys and use the blend we've already trained.

## 📋 Pre-Configured Layout

The default `blend.yaml` includes:

- 1 premium provider (your main API key) for judging
- 6+ free models from [Kilo Gateway](https://kilo.ai/)
- 6+ free models from [OpenRouter](https://openrouter.ai/)

All models have already been ranked by ELO — we've done the work to find which models perform best on which tasks.

## 📖 Documentation

- [Getting Started Guide](docs/GETTING_STARTED.md) - Step-by-step instructions to get API keys from each provider
- [Configuration](docs/CONFIGURATION.md) - How to add/remove models and customize the blend
- [API Documentation](docs/API.md) - OpenAI-compatible API usage
- [FAQ](docs/FAQ.md) - Common questions about cost, privacy, updates

## 🔒 Security & Privacy

- All your API keys stay local in your `.env` file
- All inference happens locally on your machine — no data is sent back to us
- Our pre-trained ELO database contains no user data — just model rankings
- Your prompts go directly from your client to the provider APIs

## 🆕 Updates

We periodically update this repository with:
- New ELO rankings as we test new models
- Improved blend strategies
- Additional pre-configured free models

To get the latest improvements:

```bash
pip install --upgrade openblend-public
# or
git pull
```

## 📊 Performance

Based on our benchmarking (55 challenging questions across 4 task types):

| Strategy | Success Rate | Note |
|----------|--------------|------|
| Best Single Model | 72% | Your best premium model |
| OpenBlend Best-of-N | **83%** | Our pre-trained blend |

OpenBlend consistently improves over your best single model by 8-12% on complex tasks.

## 🛠️ Development

### Project Structure

```
openblend-public/
├── blend.yaml                 # Pre-configured provider list
├── trained/
│   └── blend.db              # Pre-trained ELO rankings
├── src/openblend_public/
│   ├── __init__.py
│   ├── cli.py                # CLI (status, serve)
│   ├── config.py             # Configuration loader
│   ├── core/                 # Core engine
│   ├── intent/               # Prompt classification
│   ├── memory/               # ELO rankings
│   ├── providers/            # Unified provider interface
│   ├── nodes/                # Pipeline nodes (propose, judge, select)
│   └── api/                  # OpenAI-compatible FastAPI server
```

### License

MIT License - see [LICENSE](LICENSE) for details.

## Acknowledgments

Built on top of many amazing open-source projects:
- [FastAPI](https://fastapi.tiangolo.com/) for the API server
- [Typer](https://typer.tiangolo.com/) for the CLI
- [Rich](https://rich.readthedocs.io/) for beautiful terminal output
- [Pydantic](https://docs.pydantic.dev/) for data validation
- All the model providers that provide API access to great models
