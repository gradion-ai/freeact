# Installation

## Python package

```bash
pip install freeact
```

## Execution environment

`freeact` uses [`ipybox`](https://gradion-ai.github.io/ipybox/) as its code execution environment, providing a secure Docker-based IPython runtime. You can either use [pre-built Docker images](https://github.com/gradion-ai/ipybox/pkgs/container/ipybox) or create a [custom Docker image](#custom-docker-image) with your specific requirements.

!!! Note

    Pre-built images run with root privileges. For non-root execution, build a [custom Docker image](#custom-docker-image) (and find further details in the `ipybox` [installation guide](https://gradion-ai.github.io/ipybox/installation/)).

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

For running the [tutorials](tutorials/index.md), we provide a custom `ghcr.io/gradion-ai/ipybox:example` image with the following dependencies pre-installed:

```toml title="dependencies.txt"
--8<-- "freeact/examples/dependencies-example.txt"
```

!!! Note

    The tutorials run containers locally. Make sure you have [Docker](https://docs.docker.com/get-docker/) installed on your system.

### Installing dependencies at runtime

In addition to letting an agent install required dependencies at runtime, you can install extra dependencies at runtime before launching an agent, which is useful for testing custom skills across agent sessions without rebuilding Docker images:

```python
from freeact import execution_environment

async with execution_environment(ipybox_tag="ghcr.io/gradion-ai/ipybox:basic") as env:
    # Install the serpapi package in the current environment
    await env.executor.execute("!pip install serpapi")

    # Import skill modules that depend on serpapi
    skill_sources = await env.executor.get_module_sources(
        module_names=["my_skill_module_1", "my_skill_module_2"],
    )

    # Initialize agent with the new skills
    # ...
```

For production use, it's recommended to include frequently used dependencies in a custom Docker image instead.
