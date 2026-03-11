# Widget Factory Constraints

Terminal widgets are created via `create_*_box()` factory functions in `freeact/terminal/widgets.py`. Each returns a `Collapsible` or `tuple[Collapsible, Widget]` (when the inner widget needs further updates, e.g., streaming content into a `Markdown` or `RichLog`).

All factories accept `agent_id: str = ""` and `corr_id: str = ""` for uniform title formatting via `_titled()`:

- `create_user_input_box(content, agent_id, corr_id)` -> `Collapsible`
- `create_thoughts_box(agent_id, corr_id)` -> `tuple[Collapsible, Markdown]`
- `create_response_box(agent_id, corr_id)` -> `tuple[Collapsible, Markdown]`
- `create_code_action_box(code, agent_id, corr_id)` -> `Collapsible`
- `create_tool_call_box(tool_name, tool_args, agent_id, corr_id)` -> `Collapsible`
- `create_exec_output_box(agent_id, corr_id)` -> `tuple[Collapsible, RichLog]`
- `create_tool_output_box(content, agent_id, corr_id)` -> `Collapsible`
- `create_error_box(message, agent_id, corr_id)` -> `Collapsible`
- `create_file_read_action_box(paths, head, tail, agent_id, corr_id)` -> `Collapsible`
- `create_file_write_action_box(path, content, agent_id, corr_id)` -> `Collapsible`
- `create_file_edit_action_box(path, edits, agent_id, corr_id)` -> `Collapsible`

Title formatting uses `_titled(title, agent_id, corr_id)` for consistent prefixing.

When adding a new widget type, follow this pattern: free function (not a method), returns `Collapsible` or `tuple[Collapsible, Widget]`, accepts `agent_id` and `corr_id` for title formatting.
