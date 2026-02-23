## freeact.agent.Agent

```
Agent(
    config: Config,
    agent_id: str | None = None,
    session_id: str | None = None,
    sandbox: bool = False,
    sandbox_config: Path | None = None,
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

| Name             | Type     | Description                                                                                                    | Default                                                                                                                                                                                                                                                                         |
| ---------------- | -------- | -------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `config`         | `Config` | Agent configuration containing model, system prompt, MCP servers, kernel env, timeouts, and subagent settings. | *required*                                                                                                                                                                                                                                                                      |
| `agent_id`       | \`str    | None\`                                                                                                         | Identifier for this agent instance. Defaults to "main" when not provided.                                                                                                                                                                                                       |
| `session_id`     | \`str    | None\`                                                                                                         | Optional session identifier for persistence. If None and persistence is enabled, a new session ID is generated. If provided and persistence is enabled, that session ID is used. Existing session history is resumed when present; otherwise a new session starts with that ID. |
| `sandbox`        | `bool`   | Run the kernel in sandbox mode.                                                                                | `False`                                                                                                                                                                                                                                                                         |
| `sandbox_config` | \`Path   | None\`                                                                                                         | Path to custom sandbox configuration.                                                                                                                                                                                                                                           |

Raises:

| Type         | Description                                                         |
| ------------ | ------------------------------------------------------------------- |
| `ValueError` | If session_id is provided while config.enable_persistence is False. |

### session_id

```
session_id: str | None
```

Session ID used by this agent, or `None` when persistence is disabled.

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

## freeact.agent.AgentEvent

```
AgentEvent(*, agent_id: str = '', corr_id: str = '')
```

Base class for all agent stream events.

Carries the `agent_id` of the agent that produced the event, allowing callers to distinguish events from a parent agent vs. its subagents.

## freeact.agent.ApprovalRequest

```
ApprovalRequest(
    tool_name: str,
    tool_args: dict[str, Any],
    ptc: bool = False,
    _future: Future[bool] = Future(),
    *,
    agent_id: str = "",
    corr_id: str = ""
)
```

Bases: `AgentEvent`

Pending code action or tool call awaiting user approval.

Yielded by Agent.stream() before executing any code action, programmatic tool call, or JSON tool call. The stream is suspended until `approve()` is called.

### approve

```
approve(decision: bool) -> None
```

Resolve this approval request.

Parameters:

| Name       | Type   | Description                                                      | Default    |
| ---------- | ------ | ---------------------------------------------------------------- | ---------- |
| `decision` | `bool` | True to execute, False to reject and end the current agent turn. | *required* |

### approved

```
approved() -> bool
```

Await until `approve()` is called and return the decision.

## freeact.agent.Response

```
Response(
    content: str, *, agent_id: str = "", corr_id: str = ""
)
```

Bases: `AgentEvent`

Complete model response at a given step.

## freeact.agent.ResponseChunk

```
ResponseChunk(
    content: str, *, agent_id: str = "", corr_id: str = ""
)
```

Bases: `AgentEvent`

Partial model response text (content streaming).

## freeact.agent.Thoughts

```
Thoughts(
    content: str, *, agent_id: str = "", corr_id: str = ""
)
```

Bases: `AgentEvent`

Complete model thoughts at a given step.

## freeact.agent.ThoughtsChunk

```
ThoughtsChunk(
    content: str, *, agent_id: str = "", corr_id: str = ""
)
```

Bases: `AgentEvent`

Partial model thinking text (content streaming).

## freeact.agent.CodeExecutionOutput

```
CodeExecutionOutput(
    text: str | None,
    images: list[Path],
    truncated: bool = False,
    *,
    agent_id: str = "",
    corr_id: str = ""
)
```

Bases: `AgentEvent`

Complete code execution output.

## freeact.agent.CodeExecutionOutputChunk

```
CodeExecutionOutputChunk(
    text: str, *, agent_id: str = "", corr_id: str = ""
)
```

Bases: `AgentEvent`

Partial code execution output (content streaming).

## freeact.agent.ToolOutput

```
ToolOutput(
    content: ToolResult,
    *,
    agent_id: str = "",
    corr_id: str = ""
)
```

Bases: `AgentEvent`

Tool or built-in operation output.
