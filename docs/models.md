# Supported models

For the following models, `freeact` provides model-specific prompt templates.

| Model                       | Release    | [Evaluation](evaluation.md) | Prompt |
|-----------------------------|------------|-----------|--------------|
| Claude 3.5 Sonnet           | 2024-10-22 | ✓         | optimized    |
| Claude 3.5 Haiku            | 2024-10-22 | ✓         | optimized    |
| Gemini 2.0 Flash            | 2024-12-11 | ✓         | experimental |
| Gemini 2.0 Flash Thinking   | 2025-01-21 | ✗         | experimental |
| Qwen 2.5 Coder 32B Instruct |            | ✓         | experimental |
| DeepSeek V3                 |            | ✓         | experimental |

!!! Info

    `freeact` additionally supports the [integration](integration.md) of new models from any provider that is compatible with the [OpenAI Python SDK](https://github.com/openai/openai-python), including open models deployed locally with [ollama](https://ollama.com/) or [TGI](https://huggingface.co/docs/text-generation-inference/index), for example.

## Command line

This section demonstrates how you can launch `freeact` agents with these models from the [command line](cli.md). All agents use the [predefined](https://gradion-ai.github.io/freeact-skills/) `freeact_skills.search.google.stream.api` skill module for generative Google search. The required [Gemini](https://aistudio.google.com/app/apikey) API key for that skill must be defined in a `.env` file in the current working directory:

```env title=".env"
# Required for `freeact_skills.search.google.stream.api`
GOOGLE_API_KEY=...
```

API keys and base URLs for code action models are provided as `--api-key` and `--base-url` arguments, respectively. Code actions are executed in a Docker container created from the [prebuilt](environment.md#prebuilt-docker-images) `ghcr.io/gradion-ai/ipybox:basic` image, passed as `--ipybox-tag` argument.

!!! Info

    The [CLI documentation](cli.md) covers more details how environment variables can be passed to `freeact` agent systems.

### Claude 3.5 Sonnet

```bash
python -m freeact.cli \
  --model-name=claude-3-5-sonnet-20241022 \
  --ipybox-tag=ghcr.io/gradion-ai/ipybox:basic \
  --skill-modules=freeact_skills.search.google.stream.api \
  --api-key=$ANTHROPIC_API_KEY
```

### Claude 3.5 Haiku

```bash
python -m freeact.cli \
  --model-name=claude-3-5-haiku-20241022 \
  --ipybox-tag=ghcr.io/gradion-ai/ipybox:basic \
  --skill-modules=freeact_skills.search.google.stream.api \
  --api-key=$ANTHROPIC_API_KEY
```

### Gemini 2.0 Flash

```bash
python -m freeact.cli \
  --model-name=gemini-2.0-flash-exp \
  --ipybox-tag=ghcr.io/gradion-ai/ipybox:basic \
  --skill-modules=freeact_skills.search.google.stream.api \
  --api-key=$GOOGLE_API_KEY
```

### Gemini 2.0 Flash Thinking

```bash
python -m freeact.cli \
  --model-name=gemini-2.0-flash-thinking-exp-01-21 \
  --ipybox-tag=ghcr.io/gradion-ai/ipybox:basic \
  --skill-modules=freeact_skills.search.google.stream.api \
  --api-key=$GOOGLE_API_KEY
```

### Qwen 2.5 Coder 32B Instruct

```bash
python -m freeact.cli \
  --model-name=Qwen/Qwen2.5-Coder-32B-Instruct \
  --ipybox-tag=ghcr.io/gradion-ai/ipybox:basic \
  --skill-modules=freeact_skills.search.google.stream.api \
  --base-url=https://api-inference.huggingface.co/v1/ \
  --api-key=$HF_TOKEN
```

### DeepSeek V3

```bash
python -m freeact.cli \
  --model-name=accounts/fireworks/models/deepseek-v3 \
  --ipybox-tag=ghcr.io/gradion-ai/ipybox:basic \
  --skill-modules=freeact_skills.search.google.stream.api \
  --base-url=https://api.fireworks.ai/inference/v1 \
  --api-key=$FIREWORKS_API_KEY
```
