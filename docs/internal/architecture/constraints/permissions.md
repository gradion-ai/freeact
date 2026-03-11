# Permission System Constraints

The permission system uses methods on `ToolCall` subtypes for self-description. Each subtype implements four methods:

| Method | Purpose |
|---|---|
| `to_pattern()` | Suggest editable pattern from ToolCall |
| `from_pattern(pattern)` | Reconstruct ToolCall from edited pattern |
| `to_entry()` | Serialize ToolCall to permission dict |
| `matches_entry(entry, working_dir)` | Check if a rule matches this concrete ToolCall |

The base `ToolCall` class provides defaults (returns `tool_name` for pattern, `False` for matching). Subtypes override with type-specific logic.

Standalone functions `suggest_pattern()` and `parse_pattern()` in `freeact/agent/call.py` delegate to these methods and are kept for API stability.

`PermissionManager` in `freeact/permissions.py` calls `tool_call.to_entry()` and `tool_call.matches_entry()` directly, importing only the `ToolCall` base class.

When adding a new ToolCall subtype, three places must be updated:

| Location | Purpose |
|---|---|
| `ToolCall.from_raw()` in `freeact/agent/call.py` | Map raw tool name to subtype |
| Methods on the new subtype in `freeact/agent/call.py` | `to_pattern`, `from_pattern`, `to_entry`, `matches_entry` |
| Widget dispatch in `freeact/terminal/app.py` | Route to UI factory |
