# Development Guide

This guide provides instructions for setting up a development environment for `freeact`. Follow these steps to get started with development, testing, and contributing to the project.

Clone the repository:

```bash
git clone https://github.com/gradion-ai/freeact.git
cd freeact
```

Install dependencies and create virtual environment:

```bash
uv sync
```

Activate the virtual environment:

```bash
source .venv/bin/activate
```

Install pre-commit hooks:

```bash
invoke precommit-install
```

Create a `.env` file with [Anthropic](https://console.anthropic.com/settings/keys), [Gemini](https://aistudio.google.com/app/apikey) and [Fireworks](https://fireworks.ai/account/api-keys) API keys:

```env title=".env"
# Required for integration tests with Claude
ANTHROPIC_API_KEY=...

# Required integration tests with Gemini
GEMINI_API_KEY=...

# Required integration tests with Qwen
FIREWORKS_API_KEY=...
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
