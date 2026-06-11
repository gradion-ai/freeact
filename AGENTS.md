# Repository Guidelines

## Architecture in Four Sentences
Freeact is an agent SDK plus a terminal UI joined only by an event stream: `Agent.stream()` yields typed `AgentEvent`s (including `ApprovalRequest`s the consumer must resolve), and the terminal renders them. The agent is policy-free; permission rules and approval decisions belong to the embedder (`cli.py` wires agent, permissions, and TUI together). Configuration flows one way: `.freeact/config.toml` -> `config.load()` -> `config.resolve()` -> `ResolvedRuntime` -> `Agent`. Code actions run in an ipybox kernel; bundled tools run as MCP subprocess servers under `freeact/tools/`.

## Project Structure & Module Organization
- Documentation: `docs/`
- Project description: `docs/index.md`
- Source modules:
  - `freeact/events.py`, `freeact/toolcalls.py`: SDK event and tool call types
  - `freeact/config/`: TOML config (schema, load/init, resolve, prompts, skills)
  - `freeact/agent/`: agent runtime (turn loop, approvals, executor, MCP, session, subagents)
  - `freeact/tools/`: bundled MCP tool servers (filesystem, fetch, search, discovery)
  - `freeact/terminal/`: terminal UI (app, dispatcher, view, approvals, widgets, screens, clipboard)
  - `freeact/permissions.py`: permission rules and manager
  - `freeact/cli.py`: CLI entry point
- Tests:
  - `tests/unit/`: unit tests
  - `tests/integration/`: integration tests

## Directory-specific Guidelines
- `docs/AGENTS.md`: documentation authoring
- `tests/AGENTS.md`: testing conventions and utilities

## Invariants
- `docs/internal/invariants.md`: non-obvious rules and why-invariants; read before changing core behavior
- Flag when a change may require updating an invariant

## Coding Guidelines
- All function parameters and return types must have type hints
- Modern union syntax: `str | None` instead of `Optional[str]`
- Prefer `match`/`case` over `isinstance()` for type dispatch
- Package `__init__.py` files are re-exports only; do not define functions or classes in them
- Absolute imports everywhere (no relative imports)

## Docstring Guidelines
- Use mkdocs-formatter and mkdocs-docstrings skills for docstrings
- Use Markdown formatting, not reST
- Do not add module-level docstrings

## Development Commands

```bash
uv sync                          # Install dependencies
uv add [--dev] [-U] <package>    # Add a dependency (--dev for dev-only, -U to upgrade)
uv run <command>                 # Run <command> in project's venv (uv run python ..., etc)
uv run invoke cc                 # Code checks (auto-fixes formatting, mypy needs manual fix)
uv run invoke ut                 # Unit tests only
uv run invoke it --parallel      # Integration tests only
uv run invoke test --parallel    # All tests (add --cov for coverage)
uv run invoke build-docs / serve-docs  # Build / serve docs
uv run pytest -xsv tests/integration/test_agent.py::test_name  # Single test
```

- `invoke cc` only checks files under version control. Run `git add` on new files first.

## Commit & Pull Request Guidelines
- Do not include test plan in PR messages
