# Permission System Constraints

The permission system maintains a parallel structure between ToolCall subtypes and permission rule matching. Every ToolCall subtype must have a corresponding case in four functions:

| Function | File | Purpose |
|---|---|---|
| `suggest_pattern()` | `freeact/agent/call.py` | Suggest editable pattern from ToolCall |
| `parse_pattern()` | `freeact/agent/call.py` | Reconstruct ToolCall from edited pattern |
| `_matches()` | `freeact/permissions.py` | Check if a rule matches a concrete ToolCall |
| `_tool_call_to_entry()` | `freeact/permissions.py` | Serialize ToolCall to permission dict |

When adding a new ToolCall subtype, all four functions must be updated with a new case.

Additionally, `ToolCall.from_raw()` must map the tool name to the new subtype.
