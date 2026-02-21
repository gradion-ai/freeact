from textual.binding import Binding
from textual.widgets import Static

from freeact.terminal.tool_data import TextEditData, ToolOutputData
from freeact.terminal.widgets import (
    ApprovalBar,
    PromptInput,
    create_error_box,
    create_file_edit_action_box,
    create_file_read_action_box,
    create_tool_call_box,
    create_tool_output_box,
    create_user_input_box,
)


def test_create_file_read_action_box_single_path_metadata() -> None:
    box = create_file_read_action_box(
        paths=("/tmp/workspace/config.json",),
        head=3,
        tail=1,
        agent_id="agent-1",
        corr_id="corr-1",
    )

    assert "read-file-box" in box.classes
    assert not box.collapsed
    assert box.title == r"\[agent-1] \[corr-1] Read Action: config.json"


def test_create_file_read_action_box_multiple_paths_metadata() -> None:
    box = create_file_read_action_box(
        paths=("/tmp/workspace/a.py", "/tmp/workspace/b.py"),
        head=None,
        tail=None,
        agent_id="agent-1",
        corr_id="corr-1",
    )

    assert "read-files-box" in box.classes
    assert not box.collapsed
    assert box.title == r"\[agent-1] \[corr-1] Read Action: 2 files"


def test_create_file_edit_action_box_has_diff_class_and_is_expanded() -> None:
    box = create_file_edit_action_box(
        path="src/config.py",
        edits=(TextEditData(old_text="DEBUG = True", new_text="DEBUG = False"),),
        agent_id="agent-1",
        corr_id="corr-1",
    )

    assert "diff-box" in box.classes
    assert not box.collapsed
    assert box.title == r"\[agent-1] \[corr-1] Edit Action: src/config.py"


def test_create_error_box_has_error_class_and_is_expanded() -> None:
    box = create_error_box("RuntimeError: boom")

    assert "error-box" in box.classes
    assert not box.collapsed
    assert box.title == "Error"


def test_create_tool_output_box_generic_is_collapsed() -> None:
    box = create_tool_output_box(
        ToolOutputData(content="ok"),
        agent_id="agent-1",
        corr_id="corr-1",
    )

    assert "tool-output-box" in box.classes
    assert box.collapsed
    assert box.title == r"\[agent-1] \[corr-1] Tool Output"


def test_create_tool_call_box_uses_tool_call_prefix_by_default() -> None:
    box = create_tool_call_box(
        tool_name="filesystem_read",
        tool_args={"path": "README.md"},
        agent_id="agent-1",
        corr_id="corr-1",
    )

    assert "tool-call-box" in box.classes
    assert not box.collapsed
    assert box.title == r"\[agent-1] \[corr-1] Tool Call: filesystem_read"


def test_create_tool_call_box_uses_ptc_prefix_when_requested() -> None:
    box = create_tool_call_box(
        tool_name="mcp_list_resources",
        tool_args={},
        agent_id="agent-1",
        corr_id="corr-1",
        ptc=True,
    )

    assert "tool-call-box" in box.classes
    assert not box.collapsed
    assert box.title == r"\[agent-1] \[corr-1] PTC: mcp_list_resources"


def test_approval_bar_prompt_text_matches_current_ui() -> None:
    bar = ApprovalBar()
    assert str(bar.content) == "Approve? [Y/n/a/s]"


def test_prompt_input_css_uses_solid_border_variants() -> None:
    css = PromptInput.DEFAULT_CSS
    assert "border: solid $border-blurred;" in css
    assert "PromptInput:focus" in css
    assert "border: solid $border;" in css


def test_prompt_input_enables_soft_wrap() -> None:
    prompt = PromptInput()
    assert prompt.soft_wrap


def test_prompt_input_has_terminal_paste_fallback_bindings() -> None:
    keymap = {
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
