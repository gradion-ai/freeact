# Textual Terminal Interface - Implementation Status 1

## Completed

### Files created

- `freeact/terminal/default/widgets.py` - PromptInput, ApprovalBar, collapsible box factories
- `freeact/terminal/default/screens.py` - FilePickerScreen
- `freeact/terminal/default/app.py` - FreeactApp main application
- `freeact/terminal/default/mock.py` - MockAgent with 5 scenarios
- `freeact/terminal/default/__init__.py` - Terminal wrapper class
- `workspace/run_mock.py` - Thin runner script

### All code checks pass

`uv run invoke cc` passes (ruff, ruff-format, mypy). All 185 unit tests pass.

### Working features

- Widget hierarchy: VerticalScroll conversation + bottom-docked input
- `> ` gutter rendered inside the PromptInput (custom `gutter_width` + `render_line` override)
- Enter submits prompt, Ctrl+J / Alt+Enter inserts newline
- Streaming thoughts via MarkdownStream (collapses when done)
- Streaming responses via MarkdownStream (stays expanded)
- Code action boxes with syntax-highlighted Python
- Tool call boxes with formatted JSON
- Diff boxes for `filesystem_text_edit` with unified diff rendering
- Execution output streaming via RichLog (collapses when done)
- Tool output boxes (collapsed by default)
- Approval flow: `Approve? [Y/n/a/s]:` text prompt with y/n/a/s key bindings
- Permission manager integration (pre-approved tools auto-approve)
- `@` file picker modal via DirectoryTree
- Auto-scroll via `anchor()` + `scroll_end()` after each mount
- Box titles show `[agent_id]` prefix (e.g. `[mock-agent] Thinking`)
- Collapsed boxes: reduced height (no border-top, minimal padding, centered title)
- `ctrl+c` quits the app
- Mock agent with 5 scenarios cycling on each turn

## Resolved Issues

### Multiline input (Ctrl+J / Alt+Enter)

- **Root cause (Alt+Enter)**: Textual's xterm parser dropped `\x1b\r` entirely
  in basic keyboard mode (not in `ANSI_SEQUENCES_KEYS`, length > 1).
- **Root cause (Ctrl+J)**: `PromptInput._on_key` replaced `TextArea._on_key`
  (Python MRO) but only handled `enter`/`ctrl+m`. The `ctrl+j` key fell through
  to the binding system, but the binding approach didn't work reliably.
- **Fix**: Register `"\x1b\r"` in `ANSI_SEQUENCES_KEYS` as `(Keys.ControlJ,)` at
  module level in `widgets.py`. Handle `ctrl+j`/`newline` explicitly in `_on_key`
  before the enter check. Both Alt+Enter and Ctrl+J now insert newlines.

### Box titles not showing [agent_id] prefix

- **Root cause**: Collapsible's `title` parameter is rendered as Rich markup.
  `[mock-agent]` was interpreted as a Rich tag (style/link) and consumed.
- **Fix**: Escape the opening bracket in `_titled()`: `f"\\[{agent_id}] {label}"`.

## Architecture Notes

- `FreeactApp` accepts a `Callable` `agent_stream` parameter (not an `Agent`
  directly), making it testable with the mock.
- Event dispatch uses `match`/`case` on agent event dataclasses, filtering by
  `self._main_agent_id` for thoughts/response events.
- Approval uses `asyncio.Future` to bridge the `ApprovalBar.Decided` message
  back into the `_process_turn` worker coroutine.
- `_mount_and_scroll()` helper ensures `scroll_end(animate=False)` is called
  after every widget mount.
