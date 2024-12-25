# Installation

## Python package

```bash
pip install freeact
```

## Execution environment

`freeact` agents execute code actions in [ipybox](https://gradion-ai.github.io/ipybox/), a secure code execution environment. To build an `ipybox` Docker image with [freeact-skills](https://github.com/gradion-ai/freeact-skills) pre-installed:

1. Create a `dependencies.txt` file:

    ```toml title="dependencies.txt"
    freeact-skills = {version = "0.0.6", extras = ["all"]}
    # Add additional dependencies here if needed
    ```
    
    !!! Note 

        `dependencies.txt` must follow the [Poetry dependency specification format](https://python-poetry.org/docs/dependency-specification/).

2. Build the `ipybox` Docker image:

    ```bash
    python -m ipybox build -t gradion-ai/ipybox-default -d dependencies.txt
    ```

    To use the image, reference it in [`CodeExecutionContainer`][freeact.executor.CodeExecutionContainer] when creating an `ipybox` Docker container. Use the `env` argument to set any API keys required by the pre-installed skills. 
