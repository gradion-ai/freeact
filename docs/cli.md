# Command-line interface

`freeact` provides a minimalistic command-line interface (CLI) for running agents. It is currently intended for demonstration purposes only. [Install `freeact`](installation.md) and run the following command to see all available options:

```bash
python -m freeact.cli --help
```

or check [quickstart](quickstart.md) and [tutorials](tutorials/index.md) for usage examples.

## Multiline input

The `freeact` CLI supports entering messages that span multiple lines in two ways:

1. **Copy-paste**: You can directly copy and paste multiline content into the CLI
2. **Manual entry**: Press `Alt+Enter` (Linux/Windows) or `Option+Enter` (macOS) to add a new line while typing

To submit a multiline message, simply press `Enter`.

![Multiline input](img/multiline.png)

## Environment variables

The CLI reads environment variables from a `.env` file in the current directory and passes them to the [execution environment](environment.md#execution-environment). API keys required for an agent's code action model must be either defined in the `.env` file, passed as command-line arguments, or directly set as variables in the shell.

### Example 1

The [quickstart](quickstart.md) example requires `ANTHROPIC_API_KEY` and `GOOGLE_API_KEY` to be defined in a `.env` file in the current directory. The `ANTHROPIC_API_KEY` is needed for the `claude-3-5-sonnet-20241022` code action model, while the `GOOGLE_API_KEY` is required for the `freeact_skills.search.google.stream.api` skill in the execution environment. Given a `.env` file with the following content:

```env title=".env"
# Required for Claude 3.5 Sonnet
ANTHROPIC_API_KEY=your-anthropic-api-key

# Required for generative Google Search via Gemini 2
GOOGLE_API_KEY=your-google-api-key
```

the following command will launch an agent with `claude-3-5-sonnet-20241022` as code action model configured with a generative Google search skill implemented by module `freeact_skills.search.google.stream.api`:

```bash
python -m freeact.cli \
  --model-name=claude-3-5-sonnet-20241022 \
  --ipybox-tag=ghcr.io/gradion-ai/ipybox:basic \
  --skill-modules=freeact_skills.search.google.stream.api
```

The API key can alternatively be passed as command-line argument:

```bash
python -m freeact.cli \
  --model-name=claude-3-5-sonnet-20241022 \
  --api-key=your-anthropic-api-key \
  --ipybox-tag=ghcr.io/gradion-ai/ipybox:basic \
  --skill-modules=freeact_skills.search.google.stream.api
```

### Example 2

To use models from other providers, such as [accounts/fireworks/models/deepseek-v3](https://fireworks.ai/models/fireworks/deepseek-v3) hosted by [Fireworks](https://fireworks.ai/), you can either provide all required environment variables in a `.env` file:

```env title=".env"
# Required for DeepSeek V3 hosted by Fireworks
DEEPSEEK_BASE_URL=https://api.fireworks.ai/inference/v1
DEEPSEEK_API_KEY=your-deepseek-api-key

# Required for generative Google Search via Gemini 2
GOOGLE_API_KEY=your-google-api-key
```

and launch the agent with

```bash
python -m freeact.cli \
  --model-name=accounts/fireworks/models/deepseek-v3 \
  --ipybox-tag=ghcr.io/gradion-ai/ipybox:basic \
  --skill-modules=freeact_skills.search.google.stream.api
```

or pass the base URL and API key directly as command-line arguments:

```bash
python -m freeact.cli \
  --model-name=accounts/fireworks/models/deepseek-v3 \
  --base-url=https://api.fireworks.ai/inference/v1 \
  --api-key=your-deepseek-api-key \
  --ipybox-tag=ghcr.io/gradion-ai/ipybox:basic \
  --skill-modules=freeact_skills.search.google.stream.api
```
