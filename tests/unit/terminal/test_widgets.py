from collections.abc import Callable
from functools import partial
from typing import Any

import pytest
from rich.syntax import Syntax
from textual.binding import Binding
from textual.containers import Container
from textual.content import Content
from textual.widgets import Collapsible, Static

from freeact.terminal.widgets import (
    ApprovalBar,
    PromptInput,
    _syntax_to_content,
    create_code_action_box,
    create_error_box,
    create_file_edit_action_box,
    create_file_read_action_box,
    create_subagent_task_box,
    create_tool_call_box,
    create_tool_output_box,
    create_user_input_box,
)

BoxFactory = Callable[[], tuple[Collapsible, Container]]


@pytest.mark.parametrize(
    ("factory", "expected_classes", "expected_title"),
    [
        (
            partial(
                create_file_read_action_box, path="/tmp/workspace/config.json", offset=3, limit=10, agent_id="agent-1"
            ),
            ["read-file-box"],
            r"\[agent-1] Read Action: config.json",
        ),
        (
            partial(
                create_file_edit_action_box,
                path="src/config.py",
                old_text="DEBUG = True",
                new_text="DEBUG = False",
                agent_id="agent-1",
            ),
            ["diff-box"],
            r"\[agent-1] Edit Action: src/config.py",
        ),
        (
            partial(
                create_tool_call_box, tool_name="filesystem_read", tool_args={"path": "README.md"}, agent_id="agent-1"
            ),
            ["tool-call-box"],
            r"\[agent-1] Tool Call: filesystem_read",
        ),
        (
            partial(create_tool_call_box, tool_name="mcp_list_resources", tool_args={}, agent_id="agent-1", ptc=True),
            ["tool-call-box"],
            r"\[agent-1] PTC: mcp_list_resources",
        ),
        (
            partial(
                create_subagent_task_box, tool_args={"prompt": "delegate work", "max_turns": 3}, agent_id="agent-1"
            ),
            ["tool-call-box", "subagent-task-box"],
            r"\[agent-1] Tool Call: subagent_task",
        ),
        (
            partial(create_code_action_box, code="print('hello')", agent_id="agent-1"),
            ["code-action-box"],
            r"\[agent-1] Code Action",
        ),
    ],
    ids=["file_read", "file_edit", "tool_call_default", "tool_call_ptc", "subagent_task", "code_action"],
)
def test_create_action_box_metadata(factory: BoxFactory, expected_classes: list[str], expected_title: str) -> None:
    box, trace_container = factory()

    for expected_class in expected_classes:
        assert expected_class in box.classes
    assert not box.collapsed
    assert box.title == expected_title
    assert "tool-trace-container" in trace_container.classes


def test_create_error_box_has_error_class_and_is_expanded() -> None:
    box = create_error_box("RuntimeError: boom")

    assert "error-box" in box.classes
    assert not box.collapsed
    assert box.title == "Error"


def test_create_tool_output_box_generic_is_collapsed() -> None:
    box = create_tool_output_box("ok", agent_id="agent-1")

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
