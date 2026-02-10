## freeact.agent.Agent

```
Agent(
    model: str | Model,
    model_settings: ModelSettings,
    system_prompt: str,
    agent_id: str = "main",
    mcp_servers: dict[str, dict[str, Any]] | None = None,
    kernel_env: dict[str, str] | None = None,
    sandbox: bool = False,
    sandbox_config: Path | None = None,
    images_dir: Path | None = None,
    execution_timeout: float | None = 300,
    approval_timeout: float | None = None,
    enable_subagents: bool = True,
    max_subagents: int = 5,
)
```

Code action agent that generates and executes Python code in ipybox.

The agent fulfills user requests by writing Python code and running it in a sandboxed IPython kernel where variables persist across executions. Tools can be called in two ways:

- **JSON tool calls**: MCP servers called directly via structured arguments
- **Programmatic tool calls (PTC)**: Agent writes Python code that imports and calls tool APIs. These can be auto-generated from MCP schemas (`mcptools/`) or user-defined (`gentools/`).

All tool executions require approval. The `stream()` method yields ApprovalRequest events that must be resolved before execution proceeds.

Use as an async context manager or call `start()`/`stop()` explicitly.

Initialize the agent.

Parameters:

| Name                | Type                          | Description                                             | Default                                                                                                                                                                                                                   |
| ------------------- | ----------------------------- | ------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `model`             | \`str                         | Model\`                                                 | LLM model identifier or pydantic-ai Model instance.                                                                                                                                                                       |
| `model_settings`    | `ModelSettings`               | Temperature, max tokens, and other model params.        | *required*                                                                                                                                                                                                                |
| `system_prompt`     | `str`                         | Instructions defining agent behavior.                   | *required*                                                                                                                                                                                                                |
| `agent_id`          | `str`                         | Identifier for this agent instance. Defaults to "main". | `'main'`                                                                                                                                                                                                                  |
| `mcp_servers`       | \`dict\[str, dict[str, Any]\] | None\`                                                  | Raw MCP server configurations. Each key is a server name, each value is a config dict with command or url and optional excluded_tools. Used during startup and passed to subagents so each gets its own server processes. |
| `kernel_env`        | \`dict[str, str]              | None\`                                                  | Environment variables passed to the IPython kernel.                                                                                                                                                                       |
| `sandbox`           | `bool`                        | Run the kernel in sandbox mode.                         | `False`                                                                                                                                                                                                                   |
| `sandbox_config`    | \`Path                        | None\`                                                  | Path to custom sandbox configuration.                                                                                                                                                                                     |
| `images_dir`        | \`Path                        | None\`                                                  | Directory for saving generated images.                                                                                                                                                                                    |
| `execution_timeout` | \`float                       | None\`                                                  | Maximum time in seconds for code execution. Approval wait time is excluded from this timeout budget. If None, no timeout is applied. Defaults to 300 seconds.                                                             |
| `approval_timeout`  | \`float                       | None\`                                                  | Timeout in seconds for approval requests during programmatic tool calls. If an approval request is not accepted or rejected within this time, the tool call fails. If None, no timeout is applied.                        |
| `enable_subagents`  | `bool`                        | Whether to enable subagent delegation.                  | `True`                                                                                                                                                                                                                    |
| `max_subagents`     | `int`                         | Maximum number of concurrent subagents. Defaults to 5.  | `5`                                                                                                                                                                                                                       |

### start

```
start() -> None
```

Start the code executor and connect to MCP servers.

Automatically called when entering the async context manager.

### stop

```
stop() -> None
```

Stop the code executor and disconnect from MCP servers.

Automatically called when exiting the async context manager.

### stream

```
stream(
    prompt: str | Sequence[UserContent],
    max_turns: int | None = None,
) -> AsyncIterator[AgentEvent]
```

Run a full agentic turn, yielding events as they occur.

Loops through model responses and tool executions until the model produces a response without tool calls. Both JSON-based and programmatic tool calls yield an ApprovalRequest that must be resolved before execution proceeds.

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
AgentEvent(*, agent_id: str = '')
```

Base class for all agent stream events.

Carries the `agent_id` of the agent that produced the event, allowing callers to distinguish events from a parent agent vs. its subagents.

## freeact.agent.ApprovalRequest

```
ApprovalRequest(
    tool_name: str,
    tool_args: dict[str, Any],
    _future: Future[bool] = Future(),
    *,
    agent_id: str = ""
)
```

Bases: `AgentEvent`

Pending tool execution awaiting user approval.

Yielded by Agent.stream() before executing any tool. The agent is suspended until `approve()` is called.

### approve

```
approve(decision: bool) -> None
```

Resolve this approval request.

Parameters:

| Name       | Type   | Description                               | Default    |
| ---------- | ------ | ----------------------------------------- | ---------- |
| `decision` | `bool` | True to allow execution, False to reject. | *required* |

### approved

```
approved() -> bool
```

Await until `approve()` is called and return the decision.

## freeact.agent.Response

```
Response(content: str, *, agent_id: str = '')
```

Bases: `AgentEvent`

Complete model text response after streaming finishes.

## freeact.agent.ResponseChunk

```
ResponseChunk(content: str, *, agent_id: str = '')
```

Bases: `AgentEvent`

Partial text from an in-progress model response.

## freeact.agent.Thoughts

```
Thoughts(content: str, *, agent_id: str = '')
```

Bases: `AgentEvent`

Complete model thoughts after streaming finishes.

## freeact.agent.ThoughtsChunk

```
ThoughtsChunk(content: str, *, agent_id: str = '')
```

Bases: `AgentEvent`

Partial text from model's extended thinking.

## freeact.agent.CodeExecutionOutput

```
CodeExecutionOutput(
    text: str | None,
    images: list[Path],
    *,
    agent_id: str = ""
)
```

Bases: `AgentEvent`

Complete result from Python code execution in the ipybox kernel.

## freeact.agent.CodeExecutionOutputChunk

```
CodeExecutionOutputChunk(text: str, *, agent_id: str = '')
```

Bases: `AgentEvent`

Partial output from an in-progress code execution.

## freeact.agent.ToolOutput

```
ToolOutput(content: ToolResult, *, agent_id: str = '')
```

Bases: `AgentEvent`

Result from a tool or built-in agent operation.
