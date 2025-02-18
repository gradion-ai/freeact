# Model integration

`freeact` provides both a low-level and high-level API for integrating new models.

- The [low-level API](api/model.md) defines the `CodeActModel` interface and related abstractions
- The [high-level API](api/litellm.md) provides a `LiteLLM` class based on the [LiteLLM Python SDK](https://docs.litellm.ai/docs/#litellm-python-sdk)

### Low-level API

The low-level API is not further described here. For implementation examples, see the [`freeact.model.litellm.model`](https://github.com/gradion-ai/freeact/tree/main/freeact/model/litellm/model.py) or [`freeact.model.gemini.live`](https://github.com/gradion-ai/freeact/tree/main/freeact/model/gemini/live.py) modules.

### High-level API

The high-level API supports usage of models from any provider that is compatible with the [LiteLLM Python SDK](https://docs.litellm.ai/docs/#litellm-python-sdk). To use a model, you need to provide prompt templates that guide it to generate code actions. You can either reuse existing templates or create your own.

The following subsections demonstrate this using Qwen 2.5 Coder 32B Instruct as an example, showing how to use it both via the [Fireworks](https://docs.fireworks.ai/) API and locally with [ollama](https://ollama.com/).

#### Prompt templates

Start with model-specific prompt templates that guide Qwen 2.5 Coder Instruct models to generate code actions. For example:

`````python title="freeact/model/qwen/prompt.py"
--8<-- "freeact/model/qwen/prompt.py"
`````

!!! Tip

    While tested with Qwen 2.5 Coder Instruct, these prompt templates can also serve as starting point for other models.

#### Model definition

Although we could instantiate `LiteLLM` directly with these prompt templates, `freeact` provides a `QwenCoder` subclass for convenience:

```python title="freeact/model/qwen/model.py"
--8<-- "freeact/model/qwen/model.py"
```

#### Model usage

Here's a Python example that uses `QwenCoder` as code action model in a `freeact` agent. The model is accessed via the Fireworks API:

```python title="examples/qwen.py"
--8<-- "examples/qwen.py"
```

1. Your Hugging Face [user access token](https://huggingface.co/docs/hub/en/security-tokens)

2. Interact with the agent via a CLI

Run it with:

```bash
FIREWORKS_API_KEY=... python -m freeact.examples.qwen
```

Alternatively, use the `freeact` [CLI](cli.md) directly:

```bash
python -m freeact.cli \
  --model-name=fireworks_ai/accounts/fireworks/models/qwen2p5-coder-32b-instruct \
  --ipybox-tag=ghcr.io/gradion-ai/ipybox:basic \
  --skill-modules=freeact_skills.search.google.stream.api \
  --api-key=$FIREWORKS_API_KEY
```

For using the same model deployed locally with [ollama](https://ollama.com/), modify `--model-name`, remove `--api-key` and set `--base-url` to match your local deployment:

```bash
python -m freeact.cli \
  --model-name=ollama/qwen2.5-coder:32b-instruct-fp16 \
  --ipybox-tag=ghcr.io/gradion-ai/ipybox:basic \
  --skill-modules=freeact_skills.search.google.stream.api \
  --base-url=http://localhost:11434
```
