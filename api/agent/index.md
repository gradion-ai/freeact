## freeact.agent.Agent

```
Agent(
    model: str | Model,
    model_settings: ModelSettings,
    system_prompt: str,
    mcp_servers: dict[str, MCPServer] | None = None,
    kernel_env: dict[str, str] | None = None,
    sandbox: bool = False,
    sandbox_config: Path | None = None,
    images_dir: Path | None = None,
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

| Name             | Type                   | Description                                      | Default                                             |
| ---------------- | ---------------------- | ------------------------------------------------ | --------------------------------------------------- |
| `model`          | \`str                  | Model\`                                          | LLM model identifier or pydantic-ai Model instance. |
| `model_settings` | `ModelSettings`        | Temperature, max tokens, and other model params. | *required*                                          |
| `system_prompt`  | `str`                  | Instructions defining agent behavior.            | *required*                                          |
| `mcp_servers`    | \`dict[str, MCPServer] | None\`                                           | Named MCP servers for JSON-based tool calls.        |
| `kernel_env`     | \`dict[str, str]       | None\`                                           | Environment variables passed to the IPython kernel. |
| `sandbox`        | `bool`                 | Run the kernel in sandbox mode.                  | `False`                                             |
| `sandbox_config` | \`Path                 | None\`                                           | Path to custom sandbox configuration.               |
| `images_dir`     | \`Path                 | None\`                                           | Directory for saving generated images.              |

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
) -> AsyncIterator[
    ApprovalRequest
    | ToolOutput
    | CodeExecutionOutputChunk
    | CodeExecutionOutput
    | ThoughtsChunk
    | Thoughts
    | ResponseChunk
    | Response
]
```

Run a full agentic turn, yielding events as they occur.

Loops through model responses and tool executions until the model produces a response without tool calls. Both JSON-based and programmatic tool calls yield an ApprovalRequest that must be resolved before execution proceeds.

Parameters:

| Name     | Type  | Description             | Default                                              |
| -------- | ----- | ----------------------- | ---------------------------------------------------- |
| `prompt` | \`str | Sequence[UserContent]\` | User message as text or multimodal content sequence. |

Returns:

| Type                             | Description |
| -------------------------------- | ----------- |
| \`AsyncIterator\[ApprovalRequest | ToolOutput  |

## freeact.agent.ApprovalRequest

```
ApprovalRequest(
    tool_name: str,
    tool_args: dict[str, Any],
    _future: Future[bool] = Future(),
)
```

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
Response(content: str)
```

Complete model text response after streaming finishes.

## freeact.agent.ResponseChunk

```
ResponseChunk(content: str)
```

Partial text from an in-progress model response.

## freeact.agent.Thoughts

```
Thoughts(content: str)
```

Complete model thoughts after streaming finishes.

## freeact.agent.ThoughtsChunk

```
ThoughtsChunk(content: str)
```

Partial text from model's extended thinking.

## freeact.agent.CodeExecutionOutput

```
CodeExecutionOutput(text: str | None, images: list[Path])
```

Complete result from Python code execution in the ipybox kernel.

## freeact.agent.CodeExecutionOutputChunk

```
CodeExecutionOutputChunk(text: str)
```

Partial output from an in-progress code execution.

## freeact.agent.ToolOutput

```
ToolOutput(content: ToolResult)
```

Result from a JSON-based MCP tool call.
