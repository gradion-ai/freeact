# Textual Terminal Interface - Phase 1: UI with Mock Agent

## Context

The current Rich + prompt_toolkit terminal in `freeact/terminal/legacy/` is being replaced by a Textual-based interface. Phase 1 builds the complete UI with a mock agent to validate that Textual provides all needed features and to enable manual acceptance testing before real agent integration.

## File Structure

All new files in `freeact/terminal/default/`:

```
freeact/terminal/default/
    __init__.py      # Terminal class (same interface as legacy)
    app.py           # FreeactApp(App) - main Textual application
    widgets.py       # PromptInput, ApprovalBar, collapsible box factories
    screens.py       # FilePickerScreen(ModalScreen) for @file selection
    mock.py          # MockAgent + run_demo() for standalone testing
```

Standalone runner script in `workspace/run_mock.py` (thin wrapper).

## Widget Hierarchy

```
FreeactApp(App)
  Screen
    VerticalScroll #conversation          (scrollable history, anchored)
      Collapsible .thoughts-box           (title="Thinking", Markdown inside)
      Collapsible .response-box           (title="Response", Markdown inside)
      Collapsible .code-action-box        (title="Code Action", Static with Syntax)
      Collapsible .tool-call-box          (title="Tool: <name>", Static with JSON Syntax)
      Collapsible .exec-output-box        (title="Execution Output", RichLog)
      Collapsible .tool-output-box        (title="Tool Output", Static, collapsed)
      Collapsible .diff-box               (title="Edit: <path>", Static with diff Syntax)
      ApprovalBar                         (mounted inline when needed, removed after)
    Vertical #input-dock                  (docked bottom)
      PromptInput #prompt-input           (custom TextArea subclass)
```

## Implementation Details

### 1. `widgets.py` - Custom Widgets and Factories

**`PromptInput(TextArea)`**: Multi-line input that submits on Enter, inserts newline on Alt/Option+Enter.
- Enter submits the prompt, Alt+Enter (escape+enter sequence) inserts a newline
- Posts `PromptInput.Submitted(text)` message on submit
- Clears itself after submission
- Shows warning toast on empty submit
- Can be disabled during agent processing

**`ApprovalBar(Horizontal)`**: Inline approval prompt with 4 buttons.
- Buttons: `[Y] Yes`, `[n] No`, `[s] Session`, `[a] Always`
- Key bindings: `y`=approve(1), `n`=reject(0), `s`=session(3), `a`=always(2), `Enter`=confirm focused
- Posts `ApprovalBar.Decided(decision: int)` message
- Default focus on Yes button

**Factory functions** (return configured `Collapsible` widgets):
- `create_thoughts_box()` -> `(Collapsible, Markdown)` - expanded, for MarkdownStream
- `create_response_box()` -> `(Collapsible, Markdown)` - expanded, for MarkdownStream
- `create_code_action_box(code, agent_id)` -> `Collapsible` - Python Syntax inside Static
- `create_tool_call_box(tool_name, tool_args, agent_id)` -> `Collapsible` - JSON Syntax inside Static
- `create_exec_output_box(agent_id)` -> `(Collapsible, RichLog)` - for streaming chunks
- `create_tool_output_box(content, agent_id)` -> `Collapsible` - collapsed, truncated text
- `create_diff_box(tool_args)` -> `Collapsible` - unified diff via `Syntax(text, "diff")`

### 2. `screens.py` - File Picker

**`FilePickerScreen(ModalScreen[Path | None])`**: Modal overlay with `DirectoryTree`.
- Triggered when user types `@` in `PromptInput`
- On file selection, dismisses with the `Path`; the app inserts it after the `@`
- Escape cancels and dismisses with `None`

### 3. `app.py` - Main Application

**Agent abstraction**: `FreeactApp` accepts a callable `agent_stream` parameter rather than an `Agent` directly. Type: `Callable[[str | Sequence[UserContent]], AsyncIterator[AgentEvent]]`. The mock agent's `.stream()` method matches this. For real integration later, `agent.stream` fits directly.

**Layout** (`compose`): `VerticalScroll` for conversation + bottom-docked `Vertical` with `PromptInput`.

**Main flow** (`process_turn` as `@work` method):
1. Disables input
2. Iterates `async for event in agent_stream(content):`
3. Uses `match`/`case` to dispatch events:
   - `ThoughtsChunk`: create thoughts box if needed, write to MarkdownStream
   - `Thoughts`: stop stream, collapse box
   - `ResponseChunk`/`Response`: same pattern as thoughts
   - `ApprovalRequest`: mount code/tool/diff box, check `permission_manager.is_allowed()`, if not pre-approved mount `ApprovalBar` and await decision via `asyncio.Future`
   - `CodeExecutionOutputChunk`: create exec output box if needed, `RichLog.write()`
   - `CodeExecutionOutput`: collapse box
   - `ToolOutput`: mount collapsed tool output box
4. Re-enables input

**Approval handling**:
- Mount appropriate collapsible box (code action, tool call, or diff)
- If `permission_manager.is_allowed()`: leave box collapsed, approve immediately
- Otherwise: expand box, mount `ApprovalBar` below it, await `ApprovalBar.Decided` message via `asyncio.Future`, update permissions, remove bar, call `request.approve()`

**File picker integration**: On `TextArea.Changed` in `#prompt-input`, detect `@` typed at cursor position, push `FilePickerScreen`, insert returned path.

**Auto-scrolling**: Call `conversation.anchor()` when starting a turn.

### 4. `mock.py` - Mock Agent

**`MockAgent`** with multiple scenarios yielded based on turn number:

- **Scenario 1 (default)**: Thinking -> Response -> Code Action (approval) -> Execution Output -> Final Response
- **Scenario 2**: Tool call with JSON args (approval needed)
- **Scenario 3**: Pre-approved tool (filesystem_read_file within .freeact/) -> collapsed box, no prompt
- **Scenario 4**: `filesystem_text_edit` with diff display
- **Scenario 5**: Long streaming output to test scroll behavior

Each scenario yields events with realistic delays (30ms for chunks, 50ms for completions).

For `ApprovalRequest` events, the mock yields the request and then `await event.approved()` to pause until the UI resolves it.

**`run_demo()`** function and `if __name__ == "__main__"` block for standalone running.

### 5. `__init__.py` - Terminal Wrapper

```python
class Terminal:
    def __init__(self, agent: Agent, console: Console | None = None) -> None:
        ...
    async def run(self) -> None:
        await permission_manager.load()
        async with self._agent:
            app = FreeactApp(agent_stream=self._agent.stream, permission_manager=...)
            await app.run_async()
```

Same interface as legacy `Terminal`. `console` parameter accepted but unused (Textual manages its own rendering).

### 6. Diff Rendering

For `filesystem_text_edit` tool calls only (exact tool name match), format `tool_args` as a unified diff string and render with `Syntax(diff_text, "diff", theme="monokai")`. This uses Rich's built-in diff lexer for red/green coloring. Simpler and more maintainable than the sandbox experiment's manual approach.

## Key Reusable Code

- `convert_at_references()` from `freeact/terminal/legacy/interface.py:26` - converts `@path` to `<attachment>` tags
- `parse_prompt()` from `freeact/media/prompt.py:14` - extracts image attachments
- `PermissionManager` from `freeact/permissions.py` - approval management (used as-is)
- Agent event types from `freeact/agent/events.py` - all event dataclasses

## Files Modified

- `freeact/terminal/default/__init__.py` - replace empty file with Terminal class
- `freeact/terminal/default/app.py` - new file
- `freeact/terminal/default/widgets.py` - new file
- `freeact/terminal/default/screens.py` - new file
- `freeact/terminal/default/mock.py` - new file
- `workspace/run_mock.py` - new file (thin runner script)

No changes to existing files. `freeact/terminal/__init__.py` continues to export the legacy terminal.

## Verification

1. Run `uv run python -m freeact.terminal.default.mock`
2. Test each scenario by entering prompts:
   - Verify streaming markdown renders incrementally in expanded collapsible
   - Verify collapsibles collapse when streaming completes
   - Verify approval bar appears for unapproved tools, responds to y/n/s/a keys
   - Verify `@` opens file picker modal, selected path is inserted
   - Verify code actions show syntax-highlighted Python
   - Verify tool calls show formatted JSON
   - Verify execution output streams incrementally
   - Verify auto-scroll follows content during streaming
   - Verify diff rendering for filesystem_text_edit
3. Run `uv run invoke cc` to verify type checking passes
