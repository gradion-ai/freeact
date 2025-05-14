# Execution environment

`freeact` uses [`ipybox`](https://gradion-ai.github.io/ipybox/) as sandboxed code execution environment, a solution based on [IPython](https://ipython.org/) and [Docker](https://www.docker.com/). There are several options for providing dependencies needed by code actions in `ipybox`:

- [Use a prebuilt Docker image](#prebuilt-docker-images).
- [Build a custom Docker image](#custom-docker-image).
- [Install dependencies at runtime](#installing-dependencies-at-runtime)

## Prebuilt Docker images

`freeact` provides prebuilt Docker images in variants `minimal`, `basic`, and `example`. They have the following dependencies pre-installed:

- `ghcr.io/gradion-ai/ipybox:minimal`: 

    ```toml title="docker/dependencies-minimal.txt"
    --8<-- "docker/dependencies-minimal.txt"
    ```

- `ghcr.io/gradion-ai/ipybox:basic`: 

    ```toml title="docker/dependencies-basic.txt"
    --8<-- "docker/dependencies-basic.txt"
    ```

- `ghcr.io/gradion-ai/ipybox:example`: 

    ```toml title="docker/dependencies-example.txt"
    --8<-- "docker/dependencies-example.txt"
    ```

!!! Note

    The [`freeact-skills`](https://gradion-ai.github.io/freeact-skills/) package provides predefined example skills for the `freeact` agent library.

!!! Note

    Prebuilt `ipybox` images run with root privileges. For non-root execution, build a [custom Docker image](#custom-docker-image) (see also `ipybox`'s [installation guide](https://gradion-ai.github.io/ipybox/installation/)).

## Custom Docker image

To build a custom `ipybox` image, create a `dependencies.txt` file with your custom dependencies. For example:

```toml title="dependencies.txt"
freeact-skills = {version = "0.0.8", extras = ["search-google"]}
numpy = "^2.2"
# ...
```

!!! Note 

    `dependencies.txt` must follow the [Poetry dependency specification format](https://python-poetry.org/docs/dependency-specification/).

Then build a custom Docker image with `ipybox`'s `build` command:

```bash
python -m ipybox build -t ghcr.io/gradion-ai/ipybox:custom -d dependencies.txt
```

To use the image, reference it in [`CodeExecutionContainer`][freeact.environment.CodeExecutionContainer] with `tag="ghcr.io/gradion-ai/ipybox:custom"` or in [`execution_environment`][freeact.environment.execution_environment] with `ipybox_tag="ghcr.io/gradion-ai/ipybox:custom"`:

```python
from freeact import execution_environment

async with execution_environment(ipybox_tag="ghcr.io/gradion-ai/ipybox:custom") as env:
    ...
```

## Installing dependencies at runtime

Dependencies can also be installed at runtime with `!pip install <package>` using a [code executor][freeact.environment.CodeExecutor]. When agents require additional Python packages for executing their code actions, they usually install them on demand, either based on prior knowledge or by reacting on code execution errors when an `import` failed. Alternatively, application code may also install packages at runtime prior to running an agent:

```python
from freeact import execution_environment

async with execution_environment(ipybox_tag="ghcr.io/gradion-ai/ipybox:basic") as env:
    async with env.code_executor() as executor:
        # Install the serpapi package prior to running an agent
        await executor.execute("!pip install serpapi")
    
    async with env.code_provider() as provider:
        # Load skill modules that depend on serpapi
        skill_sources = await provider.get_sources(
            module_names=["my_skill_module_1", "my_skill_module_2"],
        )

    async with env.code_executor() as executor:
        # Initialize and run agent
        # ...
```

!!! Tip 

    For production use, it's recommended to include frequently used dependencies in a [custom Docker image](#custom-docker-image).
