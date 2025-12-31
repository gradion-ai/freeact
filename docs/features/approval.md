# Unified Approval Mechanism

Freeact gates all tool executions through a unified approval mechanism. Every action can be inspected before it proceeds, regardless of how it originates.

## Approval Flow

When the agent attempts to execute a tool, you see the action details and are prompted for approval:

```
Approve? [Y/n/a/s]:
```

## Response Options

| Option | Description |
|--------|-------------|
| **Y** (default) | Approve this execution once |
| **n** | Reject this execution |
| **a** | Always approve this tool (persisted across sessions) |
| **s** | Approve this tool for the current session only |

Pressing Enter without input is equivalent to **Y**.

## Approval Scope

The approval mechanism covers all execution paths:

- **Code actions** - Python code executed via `ipybox_execute_ipython_cell`
- **Programmatic tool calls (PTC)** - Tool calls made within code that imports from `mcptools/`
- **JSON tool calls** - Direct MCP server calls with structured arguments

## Permission Tiers

### Always Allowed (Persistent)

Tools granted "always" permission are stored in `.freeact/permissions.json`:

```json
{
  "allowed_tools": [
    "google_search",
    "filesystem_read_file"
  ]
}
```

These permissions persist across sessions. To revoke, edit the file directly.

### Session Allowed (Temporary)

Tools granted "session" permission are kept in memory and cleared when the agent stops. Useful for tools you want to allow during a specific task without permanent approval.

### Auto-Approved Operations

Filesystem operations targeting paths within `.freeact/` are automatically approved without prompting. This allows the agent to manage its own configuration, skills, and plans without interruption.

The following filesystem tools are eligible for auto-approval:

- `filesystem_read_file`
- `filesystem_read_text_file`
- `filesystem_write_file`
- `filesystem_edit_file`
- `filesystem_create_directory`
- `filesystem_list_directory`
- `filesystem_directory_tree`
- `filesystem_search_files`
- `filesystem_read_multiple_files`

## Python API

When using the Python API, [`Agent.stream()`][freeact.agent.Agent.stream] yields [`ApprovalRequest`][freeact.agent.ApprovalRequest] events that must be resolved before execution proceeds:

```python
async for event in agent.stream(prompt):
    match event:
        case ApprovalRequest() as request:
            # Inspect request.tool_name and request.tool_args
            # Then approve or reject
            request.approve(True)  # or False to reject
```

The agent is suspended until `approve()` is called on each request.

## Permission Manager

For programmatic permission handling, use `PermissionManager`:

```python
from freeact.permissions import PermissionManager

manager = PermissionManager()
await manager.load()  # Load from permissions.json

# Check if a tool is pre-approved
if manager.is_allowed("tool_name", tool_args):
    request.approve(True)

# Grant permissions
await manager.allow_always("tool_name")  # Persists to disk
manager.allow_session("tool_name")       # Session only
```

## Security Considerations

- Review tool arguments before approving, especially for code execution
- Use "session" approval for one-off tasks rather than permanent permissions
- The permissions file can be version-controlled to share trusted tools across environments
- Auto-approval for `.freeact/` paths enables agent self-management but limits exposure
