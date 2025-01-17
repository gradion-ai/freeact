# Development Guide

This guide provides instructions for setting up a development environment for `freeact`. Follow these steps to get started with development, testing, and contributing to the project.

Clone the repository:

```bash
git clone https://github.com/gradion-ai/freeact.git
cd freeact
```

Create a new Conda environment and activate it:

```bash
conda env create -f environment.yml
conda activate freeact
```

Install the poetry dynamic versioning plugin:

```bash
poetry self add "poetry-dynamic-versioning[plugin]"
```

Install dependencies with Poetry:

```bash
poetry install --with dev --with docs --with eval
```

Install pre-commit hooks:

```bash
invoke precommit-install
```

Create a `.env` file with [Anthropic](https://console.anthropic.com/settings/keys) and [Gemini](https://aistudio.google.com/app/apikey) API keys:

```env title=".env"
# Required for Claude 3.5 Sonnet
ANTHROPIC_API_KEY=...

# Required for generative Google Search via Gemini 2
GOOGLE_API_KEY=...

# Required to run integration tests using Qwen models via HuggingFace API
QWEN_MODEL_NAME=Qwen/Qwen2.5-Coder-32B-Instruct
QWEN_BASE_URL=https://api-inference.huggingface.co/v1/
QWEN_API_KEY=...
```

Enforce coding conventions (done automatically by pre-commit hooks):

```bash
invoke cc
```

Run unit tests:

```bash
invoke ut
```

Run integration tests:

```bash
invoke it
```

Run all tests:

```bash
invoke test
```
