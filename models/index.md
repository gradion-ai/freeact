# Models

Freeact supports any model compatible with [Pydantic AI](https://ai.pydantic.dev/models/). The model is configured in [`.freeact/agent.json`](https://gradion-ai.github.io/freeact/configuration/#configuration-file) through three settings:

| Setting             | Required | Description                                                                     |
| ------------------- | -------- | ------------------------------------------------------------------------------- |
| `model`             | yes      | Model identifier in `provider:model-name` format                                |
| `model_settings`    | no       | Model behavior settings (for example thinking settings or `temperature`)        |
| `provider_settings` | no       | Provider options (for example `api_key`, `base_url`, `app_url`, or `app_title`) |

## Model Identifier

The `model` field uses Pydantic AI's `provider:model-name` format. Common providers:

| Provider            | Prefix           | Example                                  |
| ------------------- | ---------------- | ---------------------------------------- |
| Google (Gemini API) | `google-gla:`    | `google-gla:gemini-3-flash-preview`      |
| Google (Vertex AI)  | `google-vertex:` | `google-vertex:gemini-3-flash-preview`   |
| Anthropic           | `anthropic:`     | `anthropic:claude-sonnet-4-6`            |
| OpenAI              | `openai:`        | `openai:gpt-5.2`                         |
| OpenRouter          | `openrouter:`    | `openrouter:anthropic/claude-sonnet-4.6` |

See Pydantic AI's [model documentation](https://ai.pydantic.dev/models/) for the full list of supported providers and model names.

## Provider Examples

### Google (default)

The default configuration uses Google's Gemini API with dynamic thinking enabled:

```
{
  "model": "google-gla:gemini-3-flash-preview",
  "model_settings": {
    "google_thinking_config": {
      "thinking_level": "high",
      "include_thoughts": true
    }
  }
}
```

Set the `GEMINI_API_KEY` environment variable to authenticate.

### Anthropic

```
{
  "model": "anthropic:claude-sonnet-4-6",
  "model_settings": {
    "anthropic_thinking": {
      "type": "adaptive"
    }
  }
}
```

Set the `ANTHROPIC_API_KEY` environment variable to authenticate.

### OpenAI

```
{
  "model": "openai:gpt-5.2",
  "model_settings": {
    "openai_reasoning_effort": "medium"
  }
}
```

Set the `OPENAI_API_KEY` environment variable to authenticate.

### OpenRouter

For providers like OpenRouter, put provider-specific options in `provider_settings` (for example `api_key`, `app_url`, and `app_title`):

```
{
  "model": "openrouter:anthropic/claude-sonnet-4.6",
  "model_settings": {
    "anthropic_thinking": {
      "type": "adaptive"
    }
  },
  "provider_settings": {
    "api_key": "${OPENROUTER_API_KEY}",
    "app_url": "https://my-app.example.com",
    "app_title": "freeact"
  }
}
```

### OpenAI-Compatible Endpoints

Any OpenAI-compatible API can be used by setting `base_url` in `provider_settings`:

```
{
  "model": "openai:my-custom-model",
  "model_settings": {
    "temperature": 0.7
  },
  "provider_settings": {
    "base_url": "https://my-api.example.com/v1",
    "api_key": "${CUSTOM_API_KEY}"
  }
}
```

## Model Settings

`model_settings` is passed directly to Pydantic AI's model request. Available settings depend on the provider.

### Extended Thinking

Freeact streams thinking content when the model supports it. Thinking is configured through provider-specific settings in `model_settings`.

**Google (Gemini)**:

```
"model_settings": {
  "google_thinking_config": {
    "thinking_level": "high",
    "include_thoughts": true
  }
}
```

`thinking_level` accepts `"low"`, `"medium"`, or `"high"`. Set `include_thoughts` to `true` to stream thinking content.

**Anthropic** (Opus 4.6, Sonnet 4.6):

```
"model_settings": {
  "anthropic_thinking": {
    "type": "adaptive"
  },
  "anthropic_effort": "high"
}
```

Adaptive thinking lets the model decide when and how much to think. `anthropic_effort` accepts `"low"`, `"medium"`, `"high"`, or `"max"` (Opus only). The default is `"high"`.

**OpenAI**:

```
"model_settings": {
  "openai_reasoning_effort": "medium"
}
```

`openai_reasoning_effort` accepts `"low"`, `"medium"`, or `"high"`.

### Common Settings

| Setting       | Description                       |
| ------------- | --------------------------------- |
| `temperature` | Controls randomness (e.g., `0.7`) |
| `max_tokens`  | Maximum response tokens           |

See Pydantic AI's [settings documentation](https://ai.pydantic.dev/api/settings/) for the full reference.

## Provider Settings

Use `provider_settings` for provider-specific options such as `api_key`, `base_url`, `app_url`, or `app_title`.
