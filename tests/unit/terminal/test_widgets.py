# Covers behavior-inventory.md sections: 20 (terminal UI: widget metadata, approval bar, prompt input)
from typing import Any

import pytest
from rich.syntax import Syntax
from textual.binding import Binding
from textual.content import Content
from textual.widgets import Static

from freeact.terminal.approvals import build_tool_call_box
from freeact.terminal.widgets import (
    ApprovalBar,
    PromptInput,
    _syntax_to_content,
    create_box,
    create_error_box,
    create_user_input_box,
    syntax_content,
)
from freeact.toolcalls import CodeAction, FileEdit, FileRead, FileWrite, GenericCall, ShellAction, ToolCall


@pytest.mark.parametrize(
    ("tool_call", "expected_classes", "expected_title", "expected_subagent"),
    [
        (
            FileRead(tool_name="filesystem_read_text_file", path="/tmp/workspace/config.json", offset=3, limit=10),
            ["read-file-box"],
            r"\[agent-1] Read Action: config.json",
            False,
        ),
        (
            FileEdit(
                tool_name="filesystem_edit_text_file",
                path="src/config.py",
                old_text="DEBUG = True",
                new_text="DEBUG = False",
            ),
            ["diff-box"],
            r"\[agent-1] Edit Action: src/config.py",
            False,
        ),
        (
            FileWrite(tool_name="filesystem_write_text_file", path="out.py", content="x = 1"),
            ["write-file-box"],
            r"\[agent-1] Write Action: out.py",
            False,
        ),
        (
            GenericCall(tool_name="filesystem_read", tool_args={"path": "README.md"}, ptc=False),
            ["tool-call-box"],
            r"\[agent-1] Tool Call: filesystem_read",
            False,
        ),
        (
            GenericCall(tool_name="mcp_list_resources", tool_args={}, ptc=True),
            ["tool-call-box"],
            r"\[agent-1] PTC: mcp_list_resources",
            False,
        ),
        (
            GenericCall(tool_name="subagent_task", tool_args={"prompt": "delegate work", "max_turns": 3}, ptc=False),
            ["tool-call-box", "subagent-task-box"],
            r"\[agent-1] Tool Call: subagent_task",
            True,
        ),
        (
            CodeAction(tool_name="ipybox_execute_ipython_cell", code="print('hello')"),
            ["code-action-box"],
            r"\[agent-1] Code Action",
            False,
        ),
        (
            ShellAction(tool_name="bash", command="git status"),
            ["tool-call-box"],
            r"\[agent-1] Shell Command",
            False,
        ),
        (
            ShellAction(tool_name="shell_magic", command="echo a\necho b"),
            ["tool-call-box"],
            r"\[agent-1] Shell Script",
            False,
        ),
    ],
    ids=[
        "file_read",
        "file_edit",
        "file_write",
        "tool_call_default",
        "tool_call_ptc",
        "subagent_task",
        "code_action",
        "shell_command",
        "shell_script",
    ],
)
def test_build_tool_call_box_metadata(
    tool_call: ToolCall, expected_classes: list[str], expected_title: str, expected_subagent: bool
) -> None:
    box, trace_container, is_subagent_task = build_tool_call_box(tool_call, "agent-1")

    for expected_class in expected_classes:
        assert expected_class in box.classes
    assert not box.collapsed
    assert box.title == expected_title
    assert "tool-trace-container" in trace_container.classes
    assert is_subagent_task is expected_subagent


def test_create_error_box_has_error_class_and_is_expanded() -> None:
    box = create_error_box("RuntimeError: boom")

    assert "error-box" in box.classes
    assert not box.collapsed
    assert box.title == "Error"


def test_create_box_tool_output_is_collapsed() -> None:
    box = create_box(
        syntax_content("ok", "text"),
        title="Tool Output",
        agent_id="agent-1",
        collapsed=True,
        classes="tool-output-box",
    )

    assert "tool-output-box" in box.classes
    assert box.collapsed
    assert box.title == r"\[agent-1] Tool Output"


def test_approval_bar_default_state() -> None:
    bar = ApprovalBar()
    assert "Y/n/a/s" in str(bar.content)
    assert bar.pattern == ""


def test_approval_bar_displays_pattern() -> None:
    bar = ApprovalBar(pattern="github_*")
    content = str(bar.content)
    assert "github_*" in content
    assert content.startswith("Approve? [Y/n/a/s] ")


def test_approval_bar_decided_carries_pattern() -> None:
    decided = ApprovalBar.Decided(decision=2, pattern="my_pattern")
    assert decided.decision == 2
    assert decided.pattern == "my_pattern"


def test_approval_bar_display_text_overrides_pattern() -> None:
    bar = ApprovalBar(pattern="git *", display_text="git status")
    content = str(bar.content)
    assert "git status" in content
    assert "git *" not in content
    assert content.startswith("Approve? [Y/n/a/s] ")


def test_approval_bar_display_text_property_round_trip() -> None:
    bar = ApprovalBar(display_text="echo hi")
    assert bar.display_text == "echo hi"
    assert bar.pattern == ""


def test_approval_bar_does_not_shadow_widget_display_reactive() -> None:
    """Regression: ApprovalBar must not shadow Textual's `Widget.display`
    reactive (which is a bool controlling visibility). Shadowing it with a
    string property hides the bar in the running app even though the unit
    tests for content/query still pass.
    """
    bar = ApprovalBar(pattern="cmd")
    assert bar.display is True
    bar_with_text = ApprovalBar(pattern="cmd", display_text="echo hi")
    assert bar_with_text.display is True


def test_prompt_input_css_uses_solid_border_variants() -> None:
    css = PromptInput.DEFAULT_CSS
    assert "border: solid $border-blurred;" in css
    assert "PromptInput:focus" in css
    assert "border: solid $border;" in css


def test_prompt_input_enables_soft_wrap() -> None:
    prompt = PromptInput()
    assert prompt.soft_wrap


def test_prompt_input_has_terminal_paste_fallback_bindings() -> None:
    keymap: dict[str, Any] = {
        binding.key: binding.action if isinstance(binding, Binding) else binding[1] for binding in PromptInput.BINDINGS
    }
    assert keymap["super+v"] == "paste"
    assert keymap["ctrl+shift+v"] == "paste"
    assert keymap["shift+insert"] == "paste"


def test_create_user_input_box_wraps_content() -> None:
    box = create_user_input_box("long line")
    static = box._contents_list[0]
    assert isinstance(static, Static)
    assert static.content == "long line"
    assert str(static.styles.text_wrap) == "wrap"


def test_syntax_to_content_preserves_text_and_returns_content() -> None:
    syntax = Syntax("print(42)", "python", theme="monokai")
    content = _syntax_to_content(syntax)

    assert isinstance(content, Content)
    assert content.plain == "print(42)\n"
