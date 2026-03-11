# Architecture Documentation

## Constraints

Topic-scoped rules and invariants. Load only the file relevant to your current task.

- [type-system.md](constraints/type-system.md) -- frozen dataclasses, Pydantic models, match/case vs isinstance, type hints, immutability
- [configuration.md](constraints/configuration.md) -- config symmetry between agent and terminal (init/load/save pattern)
- [modules.md](constraints/modules.md) -- `__init__.py` re-exports, absolute imports, dependency direction
- [async.md](constraints/async.md) -- async generators, ResourceSupervisor, arun(), approval futures, concurrency control
- [permissions.md](constraints/permissions.md) -- ToolCall subtype / permission function symmetry
- [widgets.md](constraints/widgets.md) -- `create_*_box()` factory pattern in terminal
- [persistence.md](constraints/persistence.md) -- JSONL session storage invariants
- [error-handling.md](constraints/error-handling.md) -- exception conventions, logging

## Consolidation

- [consolidation.md](consolidation.md) -- actionable cleanup and refactoring backlog

## Runtime documentation

- [runtime.md](runtime.md) -- agent runtime architecture (orchestration, tools, sessions, approvals)
- [terminal.md](terminal.md) -- terminal UI architecture
- [cancellation.md](cancellation.md) -- cancellation semantics
