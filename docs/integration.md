# Model integration

`freeact` provides both a low-level and high-level API for integrating new models.

- The [low-level API](api/model.md) defines the `CodeActModel` interface and related abstractions
- The [high-level API](api/generic.md) provides a `GenericModel` class based on the [OpenAI Python SDK](https://github.com/openai/openai-python)

### Low-level API

The low-level API is not further described here. For implementation examples, see the [`freeact.model.claude`](https://github.com/gradion-ai/freeact/tree/main/freeact/model/claude) or [`freeact.model.gemini`](https://github.com/gradion-ai/freeact/tree/main/freeact/model/gemini) packages.

### High-level API

The high-level API supports usage of models from any provider that is compatible with the [OpenAI Python SDK](https://github.com/openai/openai-python). To use a model, you need to provide prompt templates that guide it to generate code actions. You can either reuse existing templates or create your own.

The following subsections demonstrate this using Qwen 2.5 Coder 32B Instruct as an example, showing how to use it both via the [Hugging Face Inference API](https://huggingface.co/docs/api-inference/index) and locally with [ollama](https://ollama.com/).

#### Prompt templates

Start with model-specific prompt templates that guide Qwen 2.5 Coder Instruct models to generate code actions. For example:

```python title="freeact/model/qwen/prompt.py"
--8<-- "freeact/model/qwen/prompt.py"
```

!!! Tip

    While tested with Qwen 2.5 Coder Instruct, these prompt templates can also serve as a good starting point for other models (as we did for DeepSeek V3, for example).

#### Model definition

Although we could instantiate `GenericModel` directly with these prompt templates, `freeact` provides a `QwenCoder` subclass for convenience:

```python title="freeact/model/qwen/model.py"
--8<-- "freeact/model/qwen/model.py"
```

#### Model usage

Here's a Python example that uses `QwenCoder` as code action model in a `freeact` agent. The model is accessed via the Hugging Face Inference API:

```python title="freeact/examples/qwen.py"
--8<-- "freeact/examples/qwen.py"
```

1. Your Hugging Face [user access token](https://huggingface.co/docs/hub/en/security-tokens)

2. Interact with the agent via a CLI

Run it with:

```bash
HF_TOKEN=... python -m freeact.examples.qwen
```

Alternatively, use the `freeact` [CLI](cli.md) directly:

```bash
python -m freeact.cli \
  --model-name=Qwen/Qwen2.5-Coder-32B-Instruct \
  --base-url=https://api-inference.huggingface.co/v1/ \
  --api-key=$HF_TOKEN \
  --ipybox-tag=ghcr.io/gradion-ai/ipybox:basic \
  --skill-modules=freeact_skills.search.google.stream.api
```

For using the same model deployed locally with [ollama](https://ollama.com/), modify `--model-name`, `--base-url` and `--api-key` to match your local deployment:

```bash
python -m freeact.cli \
  --model-name=qwen2.5-coder:32b-instruct-fp16 \
  --base-url=http://localhost:11434/v1 \
  --api-key=ollama \
  --ipybox-tag=ghcr.io/gradion-ai/ipybox:basic \
  --skill-modules=freeact_skills.search.google.stream.api
```
