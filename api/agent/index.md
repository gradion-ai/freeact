## freeact.Agent

```
Agent(
    runtime: ResolvedRuntime,
    agent_id: str | None = None,
    session_id: str | None = None,
    sandbox: bool = False,
    sandbox_config: Path | None = None,
    cancel_token: CancelToken | None = None,
)
```

Code action agent that executes Python code and shell commands.

Fulfills user requests by writing code and running it in a stateful IPython kernel provided by ipybox. Variables persist across executions. MCP server tools can be called in two ways:

- JSON tool calls: MCP servers called directly via structured arguments
- Programmatic tool calls (PTC): agent writes Python code that imports and calls tool APIs, auto-generated from MCP schemas (`mcptools/`) or user-defined (`gentools/`)

All code actions and tool calls require approval. The `stream()` method yields ApprovalRequest events that must be resolved before execution proceeds.

Use as an async context manager or call `start()`/`stop()` explicitly.

Initialize the agent.

Parameters:

| Name             | Type              | Description                             | Default                                                                                                                                                                                                                                                                         |
| ---------------- | ----------------- | --------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `runtime`        | `ResolvedRuntime` | Resolved runtime produced by resolve(). | *required*                                                                                                                                                                                                                                                                      |
| `agent_id`       | \`str             | None\`                                  | Identifier for this agent instance. Defaults to "main" when not provided.                                                                                                                                                                                                       |
| `session_id`     | \`str             | None\`                                  | Optional session identifier for persistence. If None and persistence is enabled, a new session ID is generated. If provided and persistence is enabled, that session ID is used. Existing session history is resumed when present; otherwise a new session starts with that ID. |
| `sandbox`        | `bool`            | Run the kernel in sandbox mode.         | `False`                                                                                                                                                                                                                                                                         |
| `sandbox_config` | \`Path            | None\`                                  | Path to custom sandbox configuration.                                                                                                                                                                                                                                           |
| `cancel_token`   | \`CancelToken     | None\`                                  | Shared cancellation token. Used internally to propagate parent cancellation to subagents; leave unset otherwise.                                                                                                                                                                |

Raises:

| Type         | Description                                                                   |
| ------------ | ----------------------------------------------------------------------------- |
| `ValueError` | If session_id is provided while persistence is disabled in the configuration. |

### runtime

```
runtime: ResolvedRuntime
```

Resolved runtime this agent was constructed with.

### session_id

```
session_id: str | None
```

Session ID used by this agent, or `None` when persistence is disabled.

### tool_names

```
tool_names: list[str]
```

Names of all registered tools (ipybox tools and MCP server tools).

### cancel

```
cancel() -> None
```

Cancel the current agent turn.

Sets the cancellation token and interrupts any running kernel execution. The active `stream()` call will stop at the next phase boundary and yield a Cancelled event.

### start

```
start() -> None
```

Restore persisted history, start the code executor and MCP servers.

Automatically called when entering the async context manager.

### stop

```
stop() -> None
```

Stop the code executor and MCP servers.

Automatically called when exiting the async context manager.

### stream

```
stream(
    prompt: str | Sequence[UserContent],
    max_turns: int | None = None,
) -> AsyncIterator[AgentEvent]
```

Run a single agent turn, yielding events as they occur.

Loops through model responses and tool executions until the model produces a response without tool calls. All code actions and tool calls yield an ApprovalRequest that must be resolved before execution proceeds.

Parameters:

| Name        | Type  | Description             | Default                                                                                                                                                         |
| ----------- | ----- | ----------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `prompt`    | \`str | Sequence[UserContent]\` | User message as text or multimodal content sequence.                                                                                                            |
| `max_turns` | \`int | None\`                  | Maximum number of tool-execution rounds. Each round consists of a model response followed by tool execution. If None, runs until the model stops calling tools. |

Returns:

| Type                        | Description              |
| --------------------------- | ------------------------ |
| `AsyncIterator[AgentEvent]` | An async event iterator. |

## freeact.AgentEvent

```
AgentEvent(
    *,
    agent_id: str = "",
    corr_id: str = "",
    parent_corr_id: str = ""
)
```

Base class for all agent stream events.

Carries the `agent_id` of the agent that produced the event, allowing callers to distinguish events from a parent agent vs. its subagents. Tool-related events carry a `corr_id`; events produced by a subagent additionally carry the parent task's correlation id in `parent_corr_id`.

## freeact.Response

```
Response(
    content: str,
    *,
    agent_id: str = "",
    corr_id: str = "",
    parent_corr_id: str = ""
)
```

Bases: `AgentEvent`

Complete model response at a given step.

## freeact.ResponseChunk

```
ResponseChunk(
    content: str,
    *,
    agent_id: str = "",
    corr_id: str = "",
    parent_corr_id: str = ""
)
```

Bases: `AgentEvent`

Partial model response text (content streaming).

## freeact.Thoughts

```
Thoughts(
    content: str,
    *,
    agent_id: str = "",
    corr_id: str = "",
    parent_corr_id: str = ""
)
```

Bases: `AgentEvent`

Complete model thoughts at a given step.

## freeact.ThoughtsChunk

```
ThoughtsChunk(
    content: str,
    *,
    agent_id: str = "",
    corr_id: str = "",
    parent_corr_id: str = ""
)
```

Bases: `AgentEvent`

Partial model thinking text (content streaming).

## freeact.CodeExecutionOutput

```
CodeExecutionOutput(
    text: str | None,
    images: list[Path],
    truncated: bool = False,
    approval_rejected: bool = False,
    *,
    agent_id: str = "",
    corr_id: str = "",
    parent_corr_id: str = ""
)
```

Bases: `AgentEvent`

Complete code execution output.

### format

```
format() -> str
```

Format output with image markdown links.

## freeact.CodeExecutionOutputChunk

```
CodeExecutionOutputChunk(
    text: str,
    *,
    agent_id: str = "",
    corr_id: str = "",
    parent_corr_id: str = ""
)
```

Bases: `AgentEvent`

Partial code execution output (content streaming).

## freeact.ApprovalRequest

```
ApprovalRequest(
    tool_call: ToolCall,
    _future: Future[bool] = Future(),
    *,
    agent_id: str = "",
    corr_id: str = "",
    parent_corr_id: str = ""
)
```

Bases: `AgentEvent`

Pending code action or tool call awaiting approval.

Yielded by Agent.stream() before executing any code action, shell command, programmatic tool call, JSON tool call, or subagent task. The affected execution is suspended until `approve()` is called.

### approve

```
approve(decision: bool) -> None
```

Resolve this approval request.

No-op if already resolved (e.g. by cancellation or timeout).

Parameters:

| Name       | Type   | Description                                                      | Default    |
| ---------- | ------ | ---------------------------------------------------------------- | ---------- |
| `decision` | `bool` | True to execute, False to reject and end the current agent turn. | *required* |

### approved

```
approved() -> bool
```

Await until `approve()` is called and return the decision.

## freeact.ToolOutput

```
ToolOutput(
    content: ToolResult,
    *,
    agent_id: str = "",
    corr_id: str = "",
    parent_corr_id: str = ""
)
```

Bases: `AgentEvent`

JSON tool call or built-in operation output.

## freeact.Cancelled

```
Cancelled(
    *,
    agent_id: str = "",
    corr_id: str = "",
    parent_corr_id: str = "",
    phase: Phase
)
```

Bases: `AgentEvent`

Agent execution was cancelled by the user.

## freeact.Phase

Bases: `str`, `Enum`

Phase boundary at which a turn can be cancelled.

## freeact.CancelToken

```
CancelToken()
```

Cooperative cancellation signal shared across a turn's components.

## freeact.ToolCall

```
ToolCall(tool_name: str)
```

Base class for typed tool call representations.

### from_pattern

```
from_pattern(pattern: str) -> ToolCall
```

Reconstruct a ToolCall from a user-edited pattern string.

### from_raw

```
from_raw(
    tool_name: str, tool_args: dict[str, Any]
) -> ToolCall
```

Construct the appropriate ToolCall subclass from raw API data.

Parameters:

| Name        | Type             | Description                                  | Default    |
| ----------- | ---------------- | -------------------------------------------- | ---------- |
| `tool_name` | `str`            | Tool identifier from the agent event stream. | *required* |
| `tool_args` | `dict[str, Any]` | Raw tool argument payload.                   | *required* |

Returns:

| Type       | Description              |
| ---------- | ------------------------ |
| `ToolCall` | Typed ToolCall instance. |

### to_display

```
to_display() -> str
```

Return display text for the approval bar.

Empty string means "fall back to the suggested pattern". Subclasses override this to surface the verbatim action being approved (e.g. a shell command) instead of the permission pattern.

### to_pattern

```
to_pattern() -> str
```

Suggest a permission pattern string for this tool call.

## freeact.GenericCall

```
GenericCall(
    tool_name: str,
    tool_args: dict[str, Any],
    ptc: bool = False,
)
```

Bases: `ToolCall`

Fallback for tool calls without specialized handling.

## freeact.ShellAction

```
ShellAction(tool_name: str, command: str)
```

Bases: `ToolCall`

Shell command extracted from a code cell.

## freeact.CodeAction

```
CodeAction(tool_name: str, code: str)
```

Bases: `ToolCall`

Code execution action.

## freeact.FileRead

```
FileRead(
    tool_name: str,
    path: str,
    offset: int | None,
    limit: int | None,
)
```

Bases: `ToolCall`

File read action.

## freeact.FileWrite

```
FileWrite(tool_name: str, path: str, content: str)
```

Bases: `ToolCall`

File write action.

## freeact.FileEdit

```
FileEdit(
    tool_name: str, path: str, old_text: str, new_text: str
)
```

Bases: `ToolCall`

File edit action.

## freeact.suggest_pattern

```
suggest_pattern(tool_call: ToolCall) -> str
```

Suggest a permission pattern string for a tool call.

Parameters:

| Name        | Type       | Description                             | Default    |
| ----------- | ---------- | --------------------------------------- | ---------- |
| `tool_call` | `ToolCall` | The tool call to suggest a pattern for. | *required* |

Returns:

| Type  | Description                                   |
| ----- | --------------------------------------------- |
| `str` | Pattern string suitable for the approval bar. |

## freeact.suggest_display

```
suggest_display(tool_call: ToolCall) -> str
```

Suggest display text for the approval bar for a tool call.

Parameters:

| Name        | Type       | Description                                  | Default    |
| ----------- | ---------- | -------------------------------------------- | ---------- |
| `tool_call` | `ToolCall` | The tool call to render in the approval bar. | *required* |

Returns:

| Type  | Description                                                      |
| ----- | ---------------------------------------------------------------- |
| `str` | Display string for the approval bar, or an empty string when the |
| `str` | bar should fall back to the suggested permission pattern.        |

## freeact.parse_pattern

```
parse_pattern(pattern: str, template: ToolCall) -> ToolCall
```

Reconstruct a ToolCall from a user-edited pattern string and an original type.

Parameters:

| Name       | Type       | Description                                               | Default    |
| ---------- | ---------- | --------------------------------------------------------- | ---------- |
| `pattern`  | `str`      | User-edited pattern string from the approval bar.         | *required* |
| `template` | `ToolCall` | Original ToolCall that determines the reconstructed type. | *required* |

Returns:

| Type       | Description                                            |
| ---------- | ------------------------------------------------------ |
| `ToolCall` | A ToolCall with pattern fields from the edited string. |

## freeact.extract_tool_output_text

```
extract_tool_output_text(content: object) -> str
```

Extract readable text from heterogeneous tool result payloads.

Parameters:

| Name      | Type     | Description              | Default    |
| --------- | -------- | ------------------------ | ---------- |
| `content` | `object` | Raw tool result payload. | *required* |

Returns:

| Type  | Description                                     |
| ----- | ----------------------------------------------- |
| `str` | Displayable text representation of the payload. |
