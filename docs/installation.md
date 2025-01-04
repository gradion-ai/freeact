# Installation

## Python package

```bash
pip install freeact
```

## Execution environment

`freeact` agents execute code actions in [`ipybox`](https://gradion-ai.github.io/ipybox/), a secure code execution environment.

### Custom Docker image

To build a custom `ipybox` Docker image with [`freeact-skills`](https://gradion-ai.github.io/freeact-skills/) pre-installed, create a `dependencies.txt` file:

```toml title="dependencies.txt"
freeact-skills = {version = "0.0.6", extras = ["all"]}
# Add additional dependencies here if needed
```

!!! Note 

    `dependencies.txt` must follow the [Poetry dependency specification format](https://python-poetry.org/docs/dependency-specification/).

Then build the `ipybox` Docker image referencing the dependencies file:

```bash
python -m ipybox build -t gradion-ai/ipybox:custom -d dependencies.txt
```

To use the image, reference it in [`CodeExecutionContainer`][freeact.executor.CodeExecutionContainer] when creating an `ipybox` Docker container. Use the `env` argument to set any API keys required by the pre-installed skills. 


### Tutorial Docker image

For running the [tutorials](index.md#tutorials), we provide a custom `ghcr.io/gradion-ai/ipybox:example` image with the following dependencies pre-installed:

```toml title="dependencies.txt"
--8<-- "freeact/examples/dependencies-example.txt"
```

!!! Note

    The tutorials run containers locally. Make sure you have [Docker](https://docs.docker.com/get-docker/) installed on your system.
