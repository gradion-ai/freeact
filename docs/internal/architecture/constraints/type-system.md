# Type System Constraints

## Value types use frozen dataclasses

Domain value types are `@dataclass(frozen=True)`. Subtypes inherit from a common base and add fields.

- `ToolCall` base with subtypes `GenericCall`, `ShellAction`, `CodeAction`, `FileRead`, `FileWrite`, `FileEdit` (`freeact/toolcalls.py`).
- `_CanonicalToolResult` as an internal frozen dataclass (`freeact/agent/session.py`).
- `Workspace` (`freeact/config/load.py`) and `ResolvedRuntime` (`freeact/config/resolve.py`) as frozen dataclasses with derived-value properties.
- `ClipboardBackend` (`freeact/terminal/clipboard.py`), `ToolCallBoxState` (`freeact/terminal/dispatcher.py`), `SlashCommandContext` (`freeact/terminal/app.py`).

## Event types use frozen kw_only dataclasses

Stream events inherit from `AgentEvent` (`@dataclass(frozen=True, kw_only=True)`) which carries `agent_id`, `corr_id`, and `parent_corr_id` (all defaulted to `""`).
Subtypes use `@dataclass(frozen=True)` (inheriting `kw_only` from the base) and add their own fields.
The base needs `kw_only=True` so that subtypes can add positional fields without defaults after the base's defaulted fields.

- Chunk/complete pairs: `ResponseChunk`/`Response`, `ThoughtsChunk`/`Thoughts`, `CodeExecutionOutputChunk`/`CodeExecutionOutput`.
- Standalone events: `ToolOutput`, `ApprovalRequest`, `Cancelled`.
- `Cancelled` uses `@dataclass(frozen=True, kw_only=True)` (adds `phase: Phase` with no default). `Phase` is a `str` enum in the same module.
- File: `freeact/events.py`.

`ApprovalRequest._future` is `field(default_factory=Future)`; `approve()` calls `set_result()` which mutates the `Future`'s internal state but never reassigns the field, so freezing is compatible. Events are never mutated after construction; `SubagentRunner` uses `dataclasses.replace` to derive events with `parent_corr_id` set.

## Configuration and rule types use Pydantic BaseModel

- `freeact/config/schema.py`: `FreeactConfig`, `AgentSection`, `TerminalSection`, `ToolPresets` -- all `ConfigDict(extra="forbid", frozen=True)`, pure data.
- `freeact/config/skills.py`: `SkillMetadata` (frozen).
- `freeact/permissions.py`: rule classes (`_Rule` base, `GenericCallRule`, `ShellActionRule`, `CodeActionRule`, `FileReadRule`, `FileWriteRule`, `FileEditRule`) are `ConfigDict(frozen=True, extra="forbid")` and form the `PermissionRule` discriminated union.

Exception: `PermissionsConfig` in `freeact/permissions.py` uses `ConfigDict(extra="forbid")` only (not frozen). This is intentional because its `ask`/`allow` lists are mutated in place by `PermissionManager`.

No config model uses `model_post_init`, and `object.__setattr__` does not appear anywhere in the codebase. All resolution against the environment happens in `freeact/config/resolve.py` (see [configuration.md](configuration.md)); schema models stay pure data. Keep it that way.

## match/case for type dispatch, isinstance for guards

Use `match`/`case` for dispatching on domain type hierarchies (ToolCall subtypes, AgentEvent subtypes, streaming events, tool result content types). This is used pervasively:

- `ToolCall.from_raw()` dispatches on `tool_name` to construct the right subtype (`freeact/toolcalls.py`).
- `Agent._stream_turn()` dispatches on `PartStartEvent`/`PartDeltaEvent` variants (`freeact/agent/agent.py`).
- `ToolExecutor._execute()` dispatches on `tool_name`; `_execute_code()` dispatches on ipybox stream items (`freeact/agent/executor.py`).
- Rule `matches()` methods and `rule_from_call()` dispatch on ToolCall subtypes (`freeact/permissions.py`).
- `EventDispatcher.dispatch()` dispatches on AgentEvent subtypes (`freeact/terminal/dispatcher.py`).
- `ToolResultMaterializer._canonicalize()` and `extract_tool_output_text()` dispatch on content structure.
- `MCPServerManager._create_servers()` dispatches on config shape (`{"command": _}` vs `{"url": _}`).

`isinstance()` is acceptable for runtime type guards that are not domain dispatch:

- Checking whether an `asyncio.gather` result or a queue item is an `Exception` (`freeact/agent/agent.py`, `mcp.py`, `subagents.py`).
- JSON/YAML data validation (`SessionStore._validate_envelope`, `freeact/config/skills.py`).
- `BinaryContent` check in `ToolExecutor._execute` and Rich style checks in `freeact/terminal/widgets.py`.

## Modern type hint syntax

- `str | None` not `Optional[str]`; `Type1 | Type2` not `Union[...]`.
- `TypeAlias` for type aliases (`AgentStreamFn`, `BoxBuild`, `ExecLogKey`, clipboard aliases).
- `Literal[...]` for restricted string values (rule `type` discriminators, `ToolPresets.discovery`).
- `Mapping[str, str]` for read-only mappings in signatures (`config/resolve.py`), `dict[str, str]` for concrete values.
- All function parameters and return types have type hints.

No exceptions currently exist in the codebase.

## Immutability defaults

- All dataclass value and event types: `@dataclass(frozen=True)`.
- All Pydantic models: `ConfigDict(frozen=True)` except `PermissionsConfig` (see above).
- Deliberately mutable `@dataclass` exceptions in the TUI: `CollapsePolicy` (single owner of collapse state) and the turn-scoped stream-state holders `_MarkdownStreamState`/`_ExecOutputState` (`freeact/terminal/dispatcher.py`).
