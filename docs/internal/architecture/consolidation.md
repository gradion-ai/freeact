# Consolidation Opportunities

Structural improvements that would reduce duplication or make the architecture more self-enforcing. They may require major changes. See [constraints/](constraints/) for the current patterns these build on.

## Config persistence base class

Agent config (`freeact/agent/config/config.py`) and terminal config (`freeact/terminal/config.py`) duplicate the same persistence pattern: `init()` / `load()` / `save()` / `_save_sync()` classmethods with identical control flow, `working_dir` as an excluded field with `Path.cwd` default, `freeact_dir` property, and `model_dump(mode="json", exclude={"working_dir"})` serialization. The only differences are the JSON filename and domain-specific `model_post_init` logic.

Extract a `PersistentConfig` base that owns the persistence lifecycle. Subclasses provide the filename and their own post-init. This eliminates ~40 lines of duplication and ensures any future config domain (e.g., permissions config if it gains persistence) follows the same pattern automatically.

## ToolCall subtype self-description

Adding a new `ToolCall` subtype currently requires updating six separate match/case blocks across two files:

1. `ToolCall.from_raw()` in `freeact/agent/call.py` -- construct subtype from raw API data
2. `suggest_pattern()` in `freeact/agent/call.py` -- generate permission pattern string
3. `parse_pattern()` in `freeact/agent/call.py` -- reconstruct from edited pattern
4. `_matches()` in `freeact/permissions.py` -- check rule against concrete call
5. `_tool_call_to_entry()` in `freeact/permissions.py` -- serialize to permission dict
6. Widget dispatch in `freeact/terminal/app.py` -- route to UI factory

Items 2-5 are serialization/matching concerns that could live on the ToolCall subtypes themselves as methods: `to_pattern()`, `from_pattern()`, `to_entry()`, `matches_entry()`. This would reduce the "update N places" burden from 6 to 3 (from_raw, the new methods on the subclass, and widget dispatch). Widget dispatch (item 6) is a UI concern and should remain separate.

## Widget factory signature consistency

The `create_*_box()` functions in `freeact/terminal/widgets.py` have inconsistent signatures:

- `create_thoughts_box(agent_id)` and `create_response_box(agent_id)` lack `corr_id`.
- `create_user_input_box(content)` and `create_error_box(message)` lack both `agent_id` and `corr_id`.
- All other factories accept both `agent_id` and `corr_id`.

The split is semantically motivated (thoughts/responses span a turn rather than correlating to a single tool call; user input and errors are not agent-scoped). But the inconsistency creates ambiguity about what a new factory should accept. Standardizing all factories to accept `agent_id=""` and `corr_id=""` (ignoring them when not applicable) would make the pattern uniform and self-documenting.

## Frozen event dataclasses

Value types (`ToolCall` subtypes) use `@dataclass(frozen=True)`. Event types (`AgentEvent` subtypes) do not, despite being treated as immutable in practice. No event field is ever reassigned after construction. The only mutation-like operation is `dataclasses.replace()`, which creates new instances and works on frozen dataclasses. `ApprovalRequest.approve()` calls `self._future.set_result()` which mutates the `Future`'s internal state but does not reassign the `_future` field, so freezing is compatible.

Making `AgentEvent` and all subtypes `@dataclass(frozen=True, kw_only=True)` would unify the immutability convention with `ToolCall` and enforce the invariant that events are never mutated. Subtypes would use `@dataclass(frozen=True)` (inheriting `kw_only` from the base). `Cancelled` already uses `@dataclass(kw_only=True)` and would become `@dataclass(frozen=True, kw_only=True)`.

## Async file I/O convention

Two conventions coexist for async file I/O:

- Config classes and SessionStore: sync I/O wrapped with `ipybox.utils.arun()`.
- PermissionManager: native `aiofiles`.

The `arun()` pattern is dominant (used in 5+ files). Migrating `PermissionManager` to the same `arun()` + sync core pattern would make the convention uniform and remove the `aiofiles` dependency from the main codebase.

## Relative imports in agent/config/

`freeact/agent/config/` uses relative imports for same-package references (`from .prompts import ...`, `from .runtime import ...`, `from .skills import ...`). All other packages already use absolute imports. These should be converted to absolute imports for consistency.

## Module docstrings in __init__.py

Per project guidelines, module-level docstrings should not be present. Two `__init__.py` files have them:

- `freeact/agent/__init__.py`: `"""Agent package - core agent, configuration, and factory."""`
- `freeact/preproc/__init__.py`: `"""Prompt preprocessing: attachment extraction and image handling."""`
