# Subagent Specification

## Overview

Extend the freeact agent with a **Task tool** that allows a main agent to spawn subagents. Subagents are fresh agent instances of the same type and configuration as the parent. They execute isolated multi-step tasks in a separate context window and return only the final result to the parent.

## Agent Identity

Every agent receives an auto-generated short ID (e.g., `agent-a3f2`). The main agent created by the CLI gets an ID at construction time. Each subagent gets a new ID when spawned.

All stream event types inherit from a common `AgentEvent` base class that carries the `agent_id` field:

```python
@dataclass
class AgentEvent:
    agent_id: str

@dataclass
class ResponseChunk(AgentEvent):
    content: str

@dataclass
class ApprovalRequest(AgentEvent):
    tool_name: str
    tool_args: dict[str, Any]
    ...
```

This applies to every existing event type: `ResponseChunk`, `Response`, `ThoughtsChunk`, `Thoughts`, `ToolOutput`, `CodeExecutionOutputChunk`, `CodeExecutionOutput`, `ApprovalRequest`.

## Task Tool

### Tool Definition

A new tool definition file `freeact/agent/tools/task.json` following the same pattern as `ipybox.json`:

```json
[
  {
    "name": "task",
    "parameters_json_schema": {
      "properties": {
        "prompt": {
          "description": "Task description for the subagent",
          "title": "Prompt",
          "type": "string"
        },
        "max_turns": {
          "description": "Maximum number of agentic turns before stopping. Defaults to 10.",
          "title": "Max Turns",
          "type": "integer",
          "default": 10
        }
      },
      "required": ["prompt"],
      "type": "object"
    },
    "description": "Spawn a subagent to execute a multi-step task in isolation. Only use this tool when the user explicitly requests running something as a subagent or subtask. The subagent has the same tools and capabilities but a fresh context window and kernel. Returns the subagent's final text response. For independent tasks, spawn multiple subagents in parallel."
  }
]
```

### Handling in `Agent`

The `task` tool is handled in `_execute_tool()` alongside the existing `ipybox_*` cases:

```python
case "task":
    async for item in self._execute_task(
        prompt=tool_args["prompt"],
        max_turns=tool_args.get("max_turns", 10),
    ):
        yield item
        match item:
            case ToolOutput():
                content = item.content
```

## Subagent Lifecycle

### Spawning

`Agent._execute_task()` creates a child `Agent` with:

- **Same model and model_settings** as the parent
- **Same system prompt** as the parent
- **Same MCP server configuration** (new connections, not shared instances)
- **Fresh IPython kernel** (own `CodeExecutor`, own state)
- **Own agent ID** (auto-generated)
- **No access to the Task tool** (no nesting; the subagent's tool definitions exclude `task`)

### Execution

The subagent runs `stream(prompt)` internally. Each agentic turn (model response + tool execution) counts toward `max_turns`. When the limit is reached, the subagent is stopped and its last response is returned.

### Cleanup

When the task completes (or is stopped due to turn limit), the subagent's resources are cleaned up immediately:

- IPython kernel is shut down
- MCP server connections are closed
- The `Agent` instance is discarded

This happens via the subagent's `stop()` method (or async context manager exit).

## Stream Events

### During Subagent Execution

The Python SDK (`Agent.stream()`) emits all subagent events (thinking, response chunks, approval requests, code execution output, etc.) through the parent's stream. Each event carries the subagent's `agent_id`, allowing callers to distinguish parent from child events.

### Approval Requests

Subagent `ApprovalRequest` events bubble up transparently through the parent's stream. They carry the subagent's `agent_id` and are handled identically to parent approval requests by the caller (terminal or programmatic consumer). The agent is suspended until the approval is resolved, just like parent approvals.

### CLI (Terminal) Behavior

Subagent events are handled the same as main agent events with one exception: subagent thinking (`ThoughtsChunk`, `Thoughts`) is hidden. Tool calls, approval requests, code execution output, and responses are all displayed and approved the same way as main agent events.

The terminal displays the `agent_id` with all rendered events (tool calls, code actions, approval requests, execution output, responses) so the user can always see which agent is acting.

### Task Result

No separate `TaskResult` event type. The subagent's final text response is returned as a `ToolOutput` (reusing the existing type), which becomes the `ToolReturnPart` content for the parent's message history.

## Error Handling

- If the subagent encounters an error (exception, timeout, max turns reached), the error or partial result is returned as the tool result text. No separate error status or structured error field.
- The parent agent receives the error as a normal `ToolReturnPart` content string and decides how to proceed.

## Constraints

- **No nesting**: Only the main agent can spawn subagents. Subagents do not have access to the `task` tool.
- **No shared kernel state**: Subagents cannot access parent variables or kernel state.
- **Hidden thinking only**: Subagent thinking is hidden in the CLI. All other events (tool calls, approvals, code execution, responses) are displayed normally.
- **Bounded parallelism**: Multiple subagents can run in parallel for independent tasks, capped at a configurable maximum (default: 5) to prevent resource exhaustion.
