# Architecture Documentation

## Constraints

Topic-scoped rules and invariants. Load only the file relevant to your current task.

- [type-system.md](constraints/type-system.md) -- frozen dataclasses (events, tool calls), Pydantic models (config, permission rules), match/case vs isinstance, type hints, immutability
- [configuration.md](constraints/configuration.md) -- parse-then-resolve split (schema/load/resolve), init-writes-once config.toml, Workspace paths, `${VAR}` semantics
- [modules.md](constraints/modules.md) -- dependency DAG (agent never imports terminal/permissions), `__init__.py` re-exports, absolute imports
- [async.md](constraints/async.md) -- ApprovalGate semantics, aiostream merge + GeneratorExit protection, generator close chain, supervisors, sync-I/O wrapping
- [permissions.md](constraints/permissions.md) -- typed rule classes, evaluation order, path security invariants, TOML storage, default rules rationale
- [widgets.md](constraints/widgets.md) -- TrackedCollapsible, CollapsePolicy precedence, box factories, text selection
- [persistence.md](constraints/persistence.md) -- Session as single source of truth, JSONL invariants, rollback vs cancellation, overflow materialization
- [error-handling.md](constraints/error-handling.md) -- exception conventions, error-text tool results, logging

## Runtime documentation

- [runtime.md](runtime.md) -- agent runtime architecture (turn loop, executor, approvals, MCP, subagents, sessions)
- [terminal.md](terminal.md) -- terminal UI architecture (app, dispatcher, view, approvals)
- [cancellation.md](cancellation.md) -- cancellation semantics
