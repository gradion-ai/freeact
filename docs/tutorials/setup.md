# Setup

Follow the [installation instructions](../installation.md) with the following modifications:

1. Use a custom `dependencies.txt` file.

    ```bash title="dependencies.txt"
    --8<-- "freeact/examples/dependencies.txt"
    ```

2. Build a custom `ipybox` Docker image.

    ```bash
    python -m ipybox build -t gradion-ai/ipybox-example -d dependencies.txt
    ```

3. Create a `.env` file with API keys:

    The predefined [freeact-skills](https://gradion-ai.github.io/freeact-skills/) used in the tutorials require an `ANTHROPIC_API_KEY` and a `GOOGLE_API_KEY`. You can get them from [Anthropic](https://docs.anthropic.com/en/docs/api/api-keys) and [Google AI Studio](https://aistudio.google.com/app/apikey). Add them to a `.env` file in the current working directory:

    ```env title=".env"
    ANTHROPIC_API_KEY=...
    GOOGLE_API_KEY=...
    ```
