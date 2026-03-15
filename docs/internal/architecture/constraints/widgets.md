# Widget Factory Constraints

Terminal widgets are created via `create_*_box()` factory functions in `freeact/terminal/widgets.py`. Each returns a `Collapsible`, `tuple[Collapsible, Widget]`, or `tuple[Collapsible, Vertical]` depending on whether the widget needs streaming updates or a nested trace container for tool results.

All factories accept `agent_id: str = ""` for uniform title formatting via `_titled()`:

- `create_user_input_box(content, agent_id)` -> `Collapsible`
- `create_thoughts_box(agent_id)` -> `tuple[Collapsible, Markdown]`
- `create_response_box(agent_id)` -> `tuple[Collapsible, Markdown]`
- `create_code_action_box(code, agent_id)` -> `tuple[Collapsible, Vertical]`
- `create_tool_call_box(tool_name, tool_args, agent_id, ptc)` -> `tuple[Collapsible, Vertical]`
- `create_subagent_task_box(tool_args, agent_id)` -> `tuple[Collapsible, Vertical]`
- `create_exec_output_box(agent_id)` -> `tuple[Collapsible, RichLog]`
- `create_tool_output_box(content, agent_id)` -> `Collapsible`
- `create_error_box(message, agent_id)` -> `Collapsible`
- `create_file_read_action_box(paths, head, tail, agent_id)` -> `tuple[Collapsible, Vertical]`
- `create_file_write_action_box(path, content, agent_id)` -> `tuple[Collapsible, Vertical]`
- `create_file_edit_action_box(path, edits, agent_id)` -> `tuple[Collapsible, Vertical]`

Tool-call factories (code action, tool call, file read/write/edit, subagent task) return a `Vertical` trace container with class `tool-trace-container` inside a `tool-call-content` wrapper. Tool results mount into this container, nesting them visually under the tool call widget.

Title formatting uses `_titled(title, agent_id)` for consistent prefixing.

When adding a new widget type, follow this pattern: free function (not a method), returns `Collapsible` or `tuple[Collapsible, Widget]`, accepts `agent_id` for title formatting. For tool-call widgets, include a `tool-trace-container` for nested results.
