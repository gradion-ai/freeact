from freeact.terminal.default.tool_data import GenericToolOutputData, ReadOutputData, TextEditData
from freeact.terminal.default.widgets import (
    create_error_box,
    create_file_edit_action_box,
    create_file_read_action_box,
    create_tool_output_box,
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
    assert box.title == r"\[agent-1] \[corr-1] Read: config.json"


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
    assert box.title == r"\[agent-1] \[corr-1] Read: 2 files"


def test_create_file_edit_action_box_has_diff_class_and_is_expanded() -> None:
    box = create_file_edit_action_box(
        path="src/config.py",
        edits=(TextEditData(old_text="DEBUG = True", new_text="DEBUG = False"),),
        agent_id="agent-1",
        corr_id="corr-1",
    )

    assert "diff-box" in box.classes
    assert not box.collapsed
    assert box.title == r"\[agent-1] \[corr-1] Edit: src/config.py"


def test_create_error_box_has_error_class_and_is_expanded() -> None:
    box = create_error_box("RuntimeError: boom")

    assert "error-box" in box.classes
    assert not box.collapsed
    assert box.title == "Error"


def test_create_tool_output_box_generic_is_collapsed() -> None:
    box = create_tool_output_box(
        GenericToolOutputData(content="ok"),
        agent_id="agent-1",
        corr_id="corr-1",
    )

    assert "tool-output-box" in box.classes
    assert box.collapsed
    assert box.title == r"\[agent-1] \[corr-1] Tool Output"


def test_create_tool_output_box_read_output_is_collapsed_and_titled() -> None:
    box = create_tool_output_box(
        ReadOutputData(
            title="Read Output: config.json",
            filenames=("/tmp/workspace/config.json",),
            content='{"name":"app"}',
        ),
        agent_id="agent-1",
        corr_id="corr-1",
    )

    assert "tool-output-box" in box.classes
    assert box.collapsed
    assert box.title == r"\[agent-1] \[corr-1] Read Output: config.json"
