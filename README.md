# freeact

`freeact` is a lightweight Python implementation of AI agents that use *code actions*—snippets of executable Python code—to dynamically interact with and adapt to their environment.

## Documentation

The official documentation is available [here](https://gradion-ai.github.io/freeact/).

## Development

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

Install dependencies with Poetry:

```bash
poetry install --with docs
```

Install pre-commit hooks:

```bash
invoke precommit-install
```

Run tests:

```bash
pytest -s tests
```
