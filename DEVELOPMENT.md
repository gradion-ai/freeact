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

Create a `.env` file with [Anthropic](https://console.anthropic.com/settings/keys), [Gemini](https://aistudio.google.com/app/apikey) and [Fireworks](https://fireworks.ai/account/api-keys) API keys:

```env title=".env"
# Required integration tests with Claude 3.5 Haiku
ANTHROPIC_API_KEY=...

# Required integration tests with Gemini 2. Flash
GOOGLE_API_KEY=...

# Required integration tests with Qwen 2.5 Coder
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
