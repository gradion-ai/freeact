# Type System Constraints

## Value types use frozen dataclasses

Domain value types are `@dataclass(frozen=True)`. Subtypes inherit from a common base and add fields.

- `ToolCall` base with subtypes `GenericCall`, `ShellAction`, `CodeAction`, `FileRead`, `FileWrite`, `FileEdit` (`freeact/agent/call.py`).
- `TextEdit` as a standalone frozen dataclass used within `FileEdit`.
- `_CanonicalToolResult` as an internal frozen dataclass (`freeact/agent/store.py`).

## Event types use kw_only dataclasses

Stream events inherit from `AgentEvent` (`@dataclass(kw_only=True)`) which carries `agent_id` and `corr_id`.
Subtypes are plain `@dataclass` (not frozen, not kw_only themselves) and add their own fields.
The base needs `kw_only=True` so that subtypes can add positional fields without defaults after the base's defaulted fields.

- Chunk/complete pairs: `ResponseChunk`/`Response`, `ThoughtsChunk`/`Thoughts`, `CodeExecutionOutputChunk`/`CodeExecutionOutput`.
- Standalone events: `ToolOutput`, `ApprovalRequest`, `Cancelled`.
- File: `freeact/agent/events.py`.

## Configuration types use Pydantic BaseModel

Configuration models use `pydantic.BaseModel` with `ConfigDict(frozen=True, extra="forbid", validate_assignment=True)`.

- `freeact/agent/config/config.py`: `Config` (agent config, also has `arbitrary_types_allowed=True`).
- `freeact/terminal/config.py`: `Config` (terminal config).
- `freeact/agent/config/skills.py`: `SkillMetadata` (frozen, no extra config).

Exception: `PermissionsConfig` in `freeact/permissions.py` uses `ConfigDict(extra="forbid")` only (not frozen, not validate_assignment). This is intentional because its `ask`/`allow` lists are mutated in place by `PermissionManager`.

## match/case for type dispatch, isinstance for guards

Use `match`/`case` for dispatching on domain type hierarchies (ToolCall subtypes, AgentEvent subtypes, streaming events, tool result content types). This is used pervasively:

- `ToolCall.from_raw()` dispatches on `tool_name` to construct the right subtype.
- `suggest_pattern()`, `parse_pattern()`, `_tool_call_to_entry()` dispatch on ToolCall subtypes.
- `_matches()` in permissions dispatches on ToolCall subtypes.
- `Agent.stream()` dispatches on `PartStartEvent`/`PartDeltaEvent` variants.
- `ToolResultMaterializer._canonicalize()` dispatches on content type.
- `extract_tool_output_text()` dispatches on content structure.
- Private helpers `_to_str()`, `_to_int_or_none()`, `_to_paths()`, `_to_edits()` dispatch on value types.

`isinstance()` is acceptable for:

- Runtime type guards that are not domain dispatch (e.g., checking if an `asyncio.gather` result is an `Exception`).
- JSON/data validation (e.g., checking if parsed JSON is a `dict` in `SessionStore._validate_envelope`).
- AST node type checking in `freeact/shell.py` (deep nesting makes match/case impractical there).

Known exception: `freeact/agent/config/runtime.py:16` uses `isinstance(model, Model)` instead of match/case. Borderline acceptable (simple guard, not multi-branch dispatch), but could be converted for consistency.

## Modern type hint syntax

- `str | None` not `Optional[str]`.
- `Type1 | Type2` not `Union[Type1, Type2]`.
- `TypeAlias` for type aliases.
- All function parameters and return types have type hints.
- Use `Literal[...]` for restricted string values.
- Use `Mapping[str, str]` for read-only mappings in signatures, `dict[str, str]` for concrete values.

No exceptions currently exist in the codebase.

## Immutability defaults

- All dataclass value types: `@dataclass(frozen=True)`.
- All Pydantic config models: `ConfigDict(frozen=True)`.
- `AgentEvent` base is not frozen (it uses `kw_only=True` instead), but its subtypes are effectively treated as immutable.

Frozen Pydantic models use `object.__setattr__(self, attr, value)` only inside `model_post_init()` to set `PrivateAttr` values during initialization. This pattern appears in:

- `Config.model_post_init()` for `_resolved_model_instance`, `_resolved_mcp_servers`, `_resolved_kernel_env`.
- `Config.for_subagent()` for `_subagent_mode`.
- `TerminalConfig.model_post_init()` for `working_dir` resolution.

Do not use `object.__setattr__` anywhere else.
