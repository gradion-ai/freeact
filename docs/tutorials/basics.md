# Basic usage

A `freeact` agent system consists of:

- A code execution Docker container, managed by the [`CodeExecutionContainer`][freeact.executor.CodeExecutionContainer] context manager. This tutorial uses the [prebuilt](../environment.md#prebuilt-docker-images) `ghcr.io/gradion-ai/ipybox:example` image.
- A code provider, managed by the [`CodeProvider`][freeact.executor.CodeProvider] context manager. It loads the source code of skills and other modules available in the code execution container.
- A code executor, managed by the [`CodeExecutor`][freeact.executor.CodeExecutor] context manager. It manages an IPython kernel's lifecycle within the container and handles code execution.
- A code action model that generates *code actions* to be executed by the executor. Models must implement the interfaces defined in the [`freeact.model`](../api/model.md) package. This tutorial uses [`Claude`][freeact.model.claude.model.Claude], configured with `anthropic/claude-3-7-sonnet-20250219` as model name (1).
    { .annotate }

    1. Valid model names are those accepted by [LiteLLM](https://www.litellm.ai/).

- A [`CodeActAgent`][freeact.agent.CodeActAgent] configured with both the model and executor. It orchestrates their interaction until a final response is ready.

```python title="examples/basics.py"
--8<-- "examples/basics.py"
```

1. Tag of the `ipybox` Docker image.

2. Environment variables passed to the container. The `GOOGLE_API_KEY` is needed by the `freeact_skills.search.google.stream.api` skill module for generative Google search via the Gemini API.

3. A key for the private subdirectories in the workspace e.g. private skills are stored in `workspace/skills/private/example`.  

4. A container-specific workspace for storing private and shared custom skills, and images (see [skill development](skills.md) tutorial)

5. A dynamically allocated host port for the container's code provider.

6. Loads the source code of the `freeact_skills.search.google.stream.api` skill module.

7. A dynamically allocated host port for the container's code executor.

8. 
```python title="examples/utils.py::stream_conversation"
--8<-- "examples/utils.py:stream_conversation"
--8<-- "examples/utils.py:stream_turn"
```

A `CodeActAgent` can engage in multi-turn conversations with a user. Each turn is initiated using the agent's [`run`][freeact.agent.CodeActAgent.run] method. We use the `stream_conversation` (1) helper function to `run` the agent and stream the output from both the agent's model and code executor to `stdout`.
{ .annotate }

1.  
```python title="examples/utils.py::stream_conversation"
--8<-- "examples/utils.py:stream_conversation"
--8<-- "examples/utils.py:stream_turn"
```

This tutorial uses the `freeact_skills.search.google.stream.api` skill module from the [`freeact-skills`](https://gradion-ai.github.io/freeact-skills/) project to process queries that require internet searches. This module provides generative Google search capabilities via the Gemini API.

The skill module's source code is obtained from the `provider` and passed to the model through the agent's `run` method (inside `stream_conversation`).

!!! Note

    Other model implementations may require skill module sources to be passed to their constructor instead.

## Setup

Install `freeact` with:

```bash
pip install freeact
```

The tutorials require an `ANTHROPIC_API_KEY` for the Claude API and a `GOOGLE_API_KEY` for the Gemini 2 API. You can get them from [Anthropic Console](https://console.anthropic.com/settings/keys) and [Google AI Studio](https://aistudio.google.com/app/apikey). Add them to a `.env` file in the current working directory:

```env title=".env"
ANTHROPIC_API_KEY=...
GOOGLE_API_KEY=...
```

The tutorials use the prebuilt [`ghcr.io/gradion-ai/ipybox:example`](../environment.md#prebuilt-docker-images) Docker image for sandboxed code execution.

## Running

Download the Python example

```shell
mkdir examples
curl -o examples/basics.py https://raw.githubusercontent.com/gradion-ai/freeact/refs/heads/main/examples/basics.py
curl -o examples/utils.py https://raw.githubusercontent.com/gradion-ai/freeact/refs/heads/main/examples/utils.py
```

and run it with:

```shell
python examples/basics.py
```

For formatted and colored console output, as shown in the [example conversation](#example-conversation), you can use the `freeact` [CLI](../cli.md):

```shell
--8<-- "examples/commands.txt:cli-basics-claude"
```

To use Gemini instead of Claude, run:

```shell
--8<-- "examples/commands.txt:cli-basics-gemini"
```

See also [Supported models](../models.md) for other CLI examples.

### Example conversation

[![output](output/basics.svg)](output/basics.html){target="_blank"}

Produced images:

[![image_0](../workspace/images/example/7a90da9b.png){ width="50%" }](../workspace/images/example/7a90da9b.png){target="_blank"}
