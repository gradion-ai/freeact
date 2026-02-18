# Models

Freeact supports any model compatible with [Pydantic AI](https://ai.pydantic.dev/models/){target="_blank"}. The model is configured in [`.freeact/config.json`](configuration.md#configuration-file) through three settings:

| Setting | Required | Description |
|---------|----------|-------------|
| `model` | yes | Model identifier in `provider:model-name` format |
| `model-settings` | no | Provider-specific settings passed to the model (e.g., thinking config, temperature) |
| `model-provider` | no | Provider constructor kwargs for custom endpoints or credentials |

## Model Identifier

The `model` field uses Pydantic AI's `provider:model-name` format. Common providers:

| Provider | Prefix | Example |
|----------|--------|---------|
| Google (Gemini API) | `google-gla:` | `google-gla:gemini-3-flash-preview` |
| Google (Vertex AI) | `google-vertex:` | `google-vertex:gemini-3-flash-preview` |
| Anthropic | `anthropic:` | `anthropic:claude-sonnet-4-6` |
| OpenAI | `openai:` | `openai:gpt-5.2` |
| OpenRouter | `openrouter:` | `openrouter:anthropic/claude-sonnet-4.6` |

See Pydantic AI's [model documentation](https://ai.pydantic.dev/models/){target="_blank"} for the full list of supported providers and model names.

## Provider Examples

### Google (default)

The default configuration uses Google's Gemini API with dynamic thinking enabled:

```json
{
  "model": "google-gla:gemini-3-flash-preview",
  "model-settings": {
    "google_thinking_config": {
      "thinking_level": "high",
      "include_thoughts": true
    }
  }
}
```

Set the `GEMINI_API_KEY` environment variable to authenticate.

### Anthropic

```json
{
  "model": "anthropic:claude-sonnet-4-6",
  "model-settings": {
    "anthropic_thinking": {
      "type": "adaptive"
    }
  }
}
```

Set the `ANTHROPIC_API_KEY` environment variable to authenticate.

### OpenAI

```json
{
  "model": "openai:gpt-5.2",
  "model-settings": {
    "openai_reasoning_effort": "medium"
  }
}
```

Set the `OPENAI_API_KEY` environment variable to authenticate.

### OpenRouter

Providers like OpenRouter require `model-provider` to pass constructor kwargs (API key, app metadata) to the provider:

```json
{
  "model": "openrouter:anthropic/claude-sonnet-4.6",
  "model-settings": {
    "anthropic_thinking": {
      "type": "adaptive"
    }
  },
  "model-provider": {
    "api_key": "${OPENROUTER_API_KEY}",
    "app_url": "https://my-app.example.com",
    "app_title": "freeact"
  }
}
```

### OpenAI-Compatible Endpoints

Any OpenAI-compatible API can be used by setting `base_url` in `model-provider`:

```json
{
  "model": "openai:my-custom-model",
  "model-settings": {
    "temperature": 0.7
  },
  "model-provider": {
    "base_url": "https://my-api.example.com/v1",
    "api_key": "${CUSTOM_API_KEY}"
  }
}
```

## Model Settings

`model-settings` is passed directly to Pydantic AI's model request. Available settings depend on the provider.

### Extended Thinking

Freeact streams thinking content when the model supports it. Thinking is configured through provider-specific settings in `model-settings`.

**Google (Gemini)**:

```json
"model-settings": {
  "google_thinking_config": {
    "thinking_level": "high",
    "include_thoughts": true
  }
}
```

`thinking_level` accepts `"low"`, `"medium"`, or `"high"`. Set `include_thoughts` to `true` to stream thinking content.

**Anthropic** (Opus 4.6, Sonnet 4.6):

```json
"model-settings": {
  "anthropic_thinking": {
    "type": "adaptive"
  },
  "anthropic_effort": "high"
}
```

Adaptive thinking lets the model decide when and how much to think. `anthropic_effort` accepts `"low"`, `"medium"`, `"high"`, or `"max"` (Opus only). The default is `"high"`.

**OpenAI**:

```json
"model-settings": {
  "openai_reasoning_effort": "medium"
}
```

`openai_reasoning_effort` accepts `"low"`, `"medium"`, or `"high"`.

### Common Settings

| Setting | Description |
|---------|-------------|
| `temperature` | Controls randomness (e.g., `0.7`) |
| `max_tokens` | Maximum response tokens |

See Pydantic AI's [settings documentation](https://ai.pydantic.dev/api/settings/){target="_blank"} for the full reference.

## Model Provider

`model-provider` configures custom API credentials, endpoints, or other provider-specific options.

Provider config supports `${VAR}` placeholders resolved against the host environment. Missing variables cause a startup error.

When `model-provider` is omitted, Pydantic AI resolves the provider from the model name prefix and uses its default authentication (typically an environment variable like `GEMINI_API_KEY` or `ANTHROPIC_API_KEY`).
