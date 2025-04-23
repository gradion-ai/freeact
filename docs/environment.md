# Execution environment

`freeact` uses [`ipybox`](https://gradion-ai.github.io/ipybox/) as its code execution environment, providing a secure Docker-based IPython runtime. You can either create a [custom Docker image](#custom-docker-image) with your specific requirements or use [prebuilt Docker images](#prebuilt-docker-images).

## Custom Docker image

To build a custom `ipybox` Docker image with [`freeact-skills`](https://gradion-ai.github.io/freeact-skills/) pre-installed, create a `dependencies.txt` file:

```toml title="dependencies.txt"
freeact-skills = {version = "*", extras = ["all"]}
# Add additional dependencies here if needed
```

!!! Note 

    `dependencies.txt` must follow the [Poetry dependency specification format](https://python-poetry.org/docs/dependency-specification/).

Then build the `ipybox` Docker image referencing the dependencies file:

```bash
python -m ipybox build -t gradion-ai/ipybox:custom -d dependencies.txt
```

To use the image, reference it in [`CodeExecutionContainer`][freeact.executor.CodeExecutionContainer] when creating an `ipybox` Docker container. Use the `env` argument to set any API keys required by the pre-installed skills. 

## Prebuilt Docker images

We provide [prebuilt Docker images](https://github.com/gradion-ai/ipybox/pkgs/container/ipybox) with variants `minimal`, `basic`, and `example`. These variants have the following dependencies installed:

- `ghcr.io/gradion-ai/ipybox:minimal`: 

    ```toml title="docker/dependencies-minimal.txt"
    --8<-- "docker/dependencies-minimal.txt"
    ```

- `ghcr.io/gradion-ai/ipybox:basic`: 

    ```toml title="docker/dependencies-basic.txt"
    --8<-- "docker/dependencies-basic.txt"
    ```

- `ghcr.io/gradion-ai/ipybox:example`, used for the [tutorials](tutorials/index.md): 

    ```toml title="docker/dependencies-example.txt"
    --8<-- "docker/dependencies-example.txt"
    ```

!!! Note

    Prebuilt images run with root privileges. For non-root execution, build a [custom Docker image](#custom-docker-image) (and find further details in the `ipybox` [installation guide](https://gradion-ai.github.io/ipybox/installation/)).

## Installing dependencies at runtime

In addition to letting an agent install required dependencies at runtime, you can install extra dependencies at runtime before launching an agent, which is useful for testing custom skills across agent sessions without rebuilding Docker images:

```python
from freeact import execution_environment

async with execution_environment(ipybox_tag="ghcr.io/gradion-ai/ipybox:basic") as env:
    async with env.code_executor() as executor:
        # Install the serpapi package in the current environment
        await executor.execute("!pip install serpapi")
    
    async with env.code_provider() as provider:
        # Import skill modules that depend on serpapi
        skill_sources = await provider.get_sources(
            module_names=["my_skill_module_1", "my_skill_module_2"],
        )

    async with env.code_executor() as executor:
        # Initialize agent with the new skills
        # ...
```

For production use, it's recommended to include frequently used dependencies in a custom Docker image instead.
