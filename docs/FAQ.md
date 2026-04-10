# Frequently Asked Questions

## General

### Q: Do I need to train anything?

**A:** No! The whole point of OpenBlend Public is that **we've already done the training**. The `trained/blend.db` file contains our pre-trained ELO rankings. You just add your API keys and start using the blend we've already trained. We periodically release updates with new rankings as we test more models.

### Q: How much does this cost?

**A:** You pay the providers directly for their API usage. OpenBlend Public is free and open-source.

Typical costs per request:
- **Route mode (fast)**: 1 API call - same cost as using the model directly
- **Best-of-N mode**: N proposal calls + 1 judge call. If you use 3 free proposals + 1 premium judge, you only pay for the judge call.

Since most proposals can come from free models (Kilo Gateway, OpenRouter free tier), the incremental cost is often just the judge call.

### Q: Does my data leave my machine?

**A:** Your data never goes to us. All API calls go directly from your machine to the provider APIs. We don't see your prompts, your API keys, or your responses. Everything stays local to your environment.

### Q: How often do you update the pre-trained data?

**A:** We aim to release updates every 1-3 months as we test new models and get better benchmark data. Watch this repository or `pip install --upgrade openblend-public` to get the latest trained rankings.

### Q: Can I add my own models?

**A:** Yes! See [Configuration](CONFIGURATION.md) guide to adding your own providers and models. The pre-trained ELO rankings will still work for existing models, and if you add new models they'll get a default ELO rating.

## Technique

### Q: How is this different from other mixture-of-LLMs projects?

**A:** Key differences:
1. **Pre-trained**: We've already done the benchmarking and ELO ranking — you just use it. No local training required.
2. **CISC weighting**: Combines model self-confidence with external judge verification.
3. **Task-type specific ELO**: Different models rank differently for different tasks (code vs creative vs reasoning).
4. **Steer-then-Verify**: Multi-step process that systematically catches hallucinations.

### Q: Does this really outperform my best single model?

**A:** Based on our benchmarking (55 challenging questions across 4 task types), yes: we consistently see 8-12% better success rate with Best-of-N compared to the best single model. The improvement is biggest on complex tasks where multiple perspectives help.

### Q: What is CISC?

**A:** CISC stands for **Confidence-Weighted Iterative Self-Consistency**. The idea is:
- Each candidate model estimates its own confidence in its answer
- The final score combines the model's self-confidence with the external judge's score (10% self + 90% external)
- Models that are confident tend to be correct more often
- This improves overall accuracy without much extra cost

## Troubleshooting

### Q: `openblend: command not found` after install

**A:** Make sure your Python `bin` directory is in your PATH. If installing with `pip install -e .`, try:

```bash
which openblend
# Should show ~/.local/bin/openblend or similar
# If not, add ~/.local/bin to your PATH
```

### Q: All candidates fail, what's wrong?

**A:** Check that:
1. Your API keys are correctly set in `.env`
2. The provider base URL is correct in `blend.yaml`
3. The model IDs match what the provider expects
4. You have credit/quota with the provider

Check the logs for specific error messages.

### Q: The judge always gives low scores

**A:** Make sure your judge model is a strong premium model. The judge's job is to evaluate quality — weaker judges give inconsistent scores. We recommend Claude Opus 4.6 or GPT-4o for the judge role.

## Contributing

### Q: Can I contribute?

**A:** Yes! We welcome issues and pull requests:
- Bug reports
- Documentation improvements
- Adding new provider examples
- Performance improvements

Please open an issue to discuss what you'd like to change.

### Q: Where is the main development happening?

**A:** The main training/arena development happens in our private repository. This open-source repository is for distributing the pre-trained result to end-users who just want to run inference.
