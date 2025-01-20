# Supported models

In addition to the models we evaluated, `freeact` also supports any model from any provider that is compatible with the [OpenAI Python SDK](https://github.com/openai/openai-python), including open models deployed locally on [ollama](https://ollama.com/) or [TGI](https://huggingface.co/docs/text-generation-inference/index), for example. See [Model integration](#model-integration) for details.

## Evaluated models

The following models have been [evaluated](evaluation.md) with `freeact`:

- Claude 3.5 Sonnet (20241022)
- Claude 3.5 Haiku (20241022)
- Gemini 2.0 Flash (experimental)
- Qwen 2.5 Coder 32B Instruct
- DeepSeek V3

For these models, `freeact` provides model-specific prompt templates.

!!! Tip

    For best performance, we recommend using Claude 3.5 Sonnet. Support for Gemini 2.0 Flash, Qwen 2.5 Coder and DeepSeek V3 is still experimental. The Qwen 2.5 Coder integration is described in [Model integration](#model-integration). The DeepSeek V3 integration follows the same pattern using a custom model class.

## Model integration

`freeact` provides both a low-level and high-level API for integrating new models.

- The [low-level API](api/model.md) defines the `CodeActModel` interface and related abstractions
- The [high-level API](api/generic.md) provides a `GenericModel` implementation of `CodeActModel` using the [OpenAI Python SDK](https://github.com/openai/openai-python)

### Low-level API

The low-level API is not further described here. For implementation examples see packages [claude](https://github.com/gradion-ai/freeact/tree/main/freeact/model/claude) or [gemini](https://github.com/gradion-ai/freeact/tree/main/freeact/model/gemini).

### High-level API

The high-level API support usage of any model from any provider that is compatible with the [OpenAI Python SDK](https://github.com/openai/openai-python), including models deployed locally on [ollama](https://ollama.com/) or [TGI](https://huggingface.co/docs/text-generation-inference/index), for example. This is shown in the following for Qwen 2.5 Coder 32B Instruct.

#### Prompt templates

Start with model-specific prompt templates that guide Qwen 2.5 Coder Instruct models to generate code actions:

```python title="freeact/model/qwen/prompt.py"
--8<-- "freeact/model/qwen/prompt.py"
```

!!! Note

    These prompt templates are still experimental.

!!! Tip

    While tested with Qwen 2.5 Coder Instruct, these prompt templates can also serve as a good starting point for other models (as we did for DeepSeek V3, for example).

#### Model definition

Although we could instantiate `GenericModel` directly with these prompt templates, `freeact` provides a `QwenCoder` subclass for convenience.

```python title="freeact/model/qwen/model.py"
--8<-- "freeact/model/qwen/model.py"
```

#### Model usage

Here's a Python example that uses `QwenCoder` in an interactive CLI:

```python title="freeact/examples/qwen.py"
--8<-- "freeact/examples/qwen.py"
```

1. Your Hugging Face [user access token](https://huggingface.co/docs/hub/en/security-tokens)

Run it with:

```bash
HF_TOKEN=<your-huggingface-token> python -m freeact.examples.qwen
```

Or use the `freeact` CLI directly:

```bash
python -m freeact.cli \
  --model-name=Qwen/Qwen2.5-Coder-32B-Instruct \
  --base-url=https://api-inference.huggingface.co/v1/ \
  --api-key=<your-huggingface-token> \
  --ipybox-tag=ghcr.io/gradion-ai/ipybox:basic \
  --skill-modules=freeact_skills.search.google.stream.api
```

For using the same model deployed locally on [ollama](https://ollama.com/), for example, change `--model-name`, `--base-url` and `--api-key` to match your local deployment:

```bash
python -m freeact.cli \
  --model-name=qwen2.5-coder:32b-instruct-fp16 \
  --base-url=http://localhost:11434/v1 \
  --api-key=ollama \
  --ipybox-tag=ghcr.io/gradion-ai/ipybox:basic \
  --skill-modules=freeact_skills.search.google.stream.api
```
