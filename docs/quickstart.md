# Quickstart

Install `freeact` using pip:

```bash
pip install freeact
```

Create a `.env` file with [Anthropic](https://console.anthropic.com/settings/keys) and [Gemini](https://aistudio.google.com/app/apikey) API keys:

```env title=".env"
# Required for Claude 3.5 Sonnet
ANTHROPIC_API_KEY=...

# Required for generative Google Search via Gemini 2
GOOGLE_API_KEY=...
```

Launch a `freeact` agent with generative Google Search skill using the [CLI](cli.md):

```bash
python -m freeact.cli \
  --model-name=claude-3-5-sonnet-20241022 \
  --ipybox-tag=ghcr.io/gradion-ai/ipybox:basic \
  --skill-modules=freeact_skills.search.google.stream.api
```

or an equivalent Python script:

```python title="freeact/examples/quickstart.py"
--8<-- "freeact/examples/quickstart.py"
```

Once launched, you can start interacting with the agent:

<video width="100%" controls>
  <source src="https://github.com/user-attachments/assets/83cec179-54dc-456c-b647-ea98ec99600b" type="video/mp4">
  Your browser does not support the video tag.
</video>
