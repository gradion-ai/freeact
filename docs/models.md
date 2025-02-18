# Supported models

For the following models, `freeact` provides model-specific prompt templates.

| Model                       | Release    | [Evaluation](evaluation.md) | Prompt |
|-----------------------------|------------|-----------|--------------|
| Claude 3.5 Sonnet           | 2024-10-22 | ✓         | optimized    |
| Claude 3.5 Haiku            | 2024-10-22 | ✓         | optimized    |
| Gemini 2.0 Flash            | 2024-02-05 | ✓[^1]     | experimental |
| Gemini 2.0 Flash Thinking   | 2024-02-05 | ✗         | experimental |
| Qwen 2.5 Coder 32B Instruct |            | ✓         | experimental |
| DeepSeek V3                 |            | ✓         | experimental |
| DeepSeek R1[^2]             |            | ✓         | experimental |

[^1]: We evaluated Gemini 2.0 Flash Experimental (`gemini-2.0-flash-exp`), released on 2024-12-11.
[^2]: DeepSeek R1 wasn't trained on agentic tool use but demonstrates strong performance with code actions, even surpassing Claude 3.5 Sonnet on the GAIA subset in our [evaluation](evaluation.md). See [this article](https://krasserm.github.io/2025/02/05/deepseek-r1-agent/) for further details. 

!!! info

    `freeact` supports the [integration](integration.md) of any model that is compatible with the [LiteLLM](https://www.litellm.ai/) Python SDK.

## Command line

This section demonstrates how you can launch `freeact` agents with these models from the [command line](cli.md). All agents use the [predefined](https://gradion-ai.github.io/freeact-skills/) `freeact_skills.search.google.stream.api` skill module for generative Google search. The required [Gemini](https://aistudio.google.com/app/apikey) API key for that skill must be defined in a `.env` file in the current working directory:

```env title=".env"
# Required for `freeact_skills.search.google.stream.api`
GOOGLE_API_KEY=...
```

API keys for code action models are provided as `--api-key` argument, respectively. Code actions are executed in a Docker container created from the [prebuilt](environment.md#prebuilt-docker-images) `ghcr.io/gradion-ai/ipybox:basic` image, passed as `--ipybox-tag` argument.

!!! Info

    The [CLI documentation](cli.md) covers more details how environment variables can be passed to `freeact` agent systems.

### Claude 3.5 Sonnet

```bash
python -m freeact.cli \
  --model-name=anthropic/claude-3-5-sonnet-20241022 \
  --ipybox-tag=ghcr.io/gradion-ai/ipybox:basic \
  --skill-modules=freeact_skills.search.google.stream.api \
  --api-key=$ANTHROPIC_API_KEY
```

### Claude 3.5 Haiku

```bash
python -m freeact.cli \
  --model-name=anthropic/claude-3-5-haiku-20241022 \
  --ipybox-tag=ghcr.io/gradion-ai/ipybox:basic \
  --skill-modules=freeact_skills.search.google.stream.api \
  --api-key=$ANTHROPIC_API_KEY
```

### Gemini 2.0 Flash

```bash
python -m freeact.cli \
  --model-name=gemini/gemini-2.0-flash \
  --ipybox-tag=ghcr.io/gradion-ai/ipybox:basic \
  --skill-modules=freeact_skills.search.google.stream.api \
  --api-key=$GOOGLE_API_KEY
```

### Gemini 2.0 Flash Thinking

```bash
python -m freeact.cli \
  --model-name=gemini/gemini-2.0-flash-thinking-exp-01-21 \
  --ipybox-tag=ghcr.io/gradion-ai/ipybox:basic \
  --skill-modules=freeact_skills.search.google.stream.api \
  --api-key=$GOOGLE_API_KEY
```

### Qwen 2.5 Coder 32B Instruct

```bash
python -m freeact.cli \
  --model-name=fireworks_ai/accounts/fireworks/models/qwen2p5-coder-32b-instruct \
  --ipybox-tag=ghcr.io/gradion-ai/ipybox:basic \
  --skill-modules=freeact_skills.search.google.stream.api \
  --api-key=$FIREWORKS_API_KEY
```

### DeepSeek R1

```bash
python -m freeact.cli \
  --model-name=fireworks_ai/accounts/fireworks/models/deepseek-r1 \
  --ipybox-tag=ghcr.io/gradion-ai/ipybox:basic \
  --skill-modules=freeact_skills.search.google.stream.api \
  --api-key=$FIREWORKS_API_KEY
```

### DeepSeek V3

```bash
python -m freeact.cli \
  --model-name=fireworks_ai/accounts/fireworks/models/deepseek-v3 \
  --ipybox-tag=ghcr.io/gradion-ai/ipybox:basic \
  --skill-modules=freeact_skills.search.google.stream.api \
  --api-key=$FIREWORKS_API_KEY
```
