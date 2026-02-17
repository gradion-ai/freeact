# Repository Guidelines

## Project Structure & Module Organization
- Documentation: `docs/`
- Project description: `docs/index.md`
- Internal documentation: `docs/internal/`
- Architecture: `docs/internal/architecture.md`
- Source modules:
  - `freeact/agent/`: core agent, config, session store
  - `freeact/tools/`: tool definitions, Python tool generation, tool search
  - `freeact/media/`: prompt parsing (`@file` references), image loading
  - `freeact/terminal/`: CLI interface, display, completion, recording
  - `freeact/permissions.py`: permission management
  - `freeact/cli.py`: CLI entry point
- Tests:
  - `tests/unit/`: unit tests
  - `tests/integration/`: integration tests

## Directory-specific Guidelines
- `docs/AGENTS.md`: documentation authoring
- `tests/AGENTS.md`: testing conventions and utilities

## Development Commands

```bash
uv sync                          # Install dependencies
uv add [--dev] [-U] <package>    # Add a dependency (--dev for dev-only, -U to upgrade)
uv run invoke cc                 # Code checks (auto-fixes formatting, mypy needs manual fix)
uv run invoke ut                 # Unit tests only
uv run invoke it --parallel      # Integration tests only
uv run invoke test --parallel    # All tests (add --cov for coverage)
uv run invoke build-docs / serve-docs  # Build / serve docs
uv run pytest -xsv tests/integration/test_agent.py::test_name  # Single test
```

- `invoke cc` only checks files under version control. Run `git add` on new files first.

## Docstring Guidelines
- Use mkdocs-formatter and mkdocs-docstrings skills for docstrings
- Use Markdown formatting, not reST
- Do not add module-level docstrings

## Coding Style & Naming Conventions
- All function parameters and return types must have type hints
- Modern union syntax: `str | None` instead of `Optional[str]`
- Prefer `match`/`case` over `isinstance()` for type dispatch

## Commit & Pull Request Guidelines
- Do not include test plan in PR messages
