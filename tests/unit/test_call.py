from typing import Any

import pytest

from freeact.agent.call import (
    CodeAction,
    FileEdit,
    FileRead,
    FileWrite,
    GenericCall,
    ShellAction,
    ToolCall,
    extract_tool_output_text,
    parse_pattern,
    suggest_pattern,
)


@pytest.mark.parametrize(
    ("tool_name", "tool_args", "expected"),
    [
        (
            "ipybox_execute_ipython_cell",
            {"code": "print('x')"},
            CodeAction(tool_name="ipybox_execute_ipython_cell", code="print('x')"),
        ),
        (
            "filesystem_read_text_file",
            {"path": "/tmp/config.json", "offset": 3, "limit": 10},
            FileRead(tool_name="filesystem_read_text_file", path="/tmp/config.json", offset=3, limit=10),
        ),
        (
            "filesystem_read_text_file",
            {"path": "/tmp/README.md"},
            FileRead(tool_name="filesystem_read_text_file", path="/tmp/README.md", offset=None, limit=None),
        ),
        (
            "filesystem_write_text_file",
            {"path": "src/main.py", "content": "print(1)"},
            FileWrite(tool_name="filesystem_write_text_file", path="src/main.py", content="print(1)"),
        ),
        (
            "filesystem_edit_text_file",
            {"path": "src/config.py", "old_text": "DEBUG = True", "new_text": "DEBUG = False"},
            FileEdit(
                tool_name="filesystem_edit_text_file",
                path="src/config.py",
                old_text="DEBUG = True",
                new_text="DEBUG = False",
            ),
        ),
        (
            "database_query",
            {"sql": "SELECT 1"},
            GenericCall(tool_name="database_query", tool_args={"sql": "SELECT 1"}, ptc=False),
        ),
        ("ipybox_execute_ipython_cell", {}, CodeAction(tool_name="ipybox_execute_ipython_cell", code="")),
        (
            "filesystem_read_text_file",
            {},
            FileRead(tool_name="filesystem_read_text_file", path="unknown", offset=None, limit=None),
        ),
        (
            "filesystem_edit_text_file",
            {"path": "f.py"},
            FileEdit(tool_name="filesystem_edit_text_file", path="f.py", old_text="", new_text=""),
        ),
    ],
)
def test_from_raw(tool_name: str, tool_args: dict[str, Any], expected: ToolCall) -> None:
    assert ToolCall.from_raw(tool_name, tool_args) == expected


@pytest.mark.parametrize(
    "tool_call",
    [
        GenericCall(tool_name="x", tool_args={}, ptc=False),
        ShellAction(tool_name="bash", command="ls"),
        CodeAction(tool_name="ipybox_execute_ipython_cell", code="x=1"),
        FileRead(tool_name="filesystem_read_text_file", path="a", offset=None, limit=None),
        FileWrite(tool_name="filesystem_write_text_file", path="a", content="c"),
        FileEdit(tool_name="filesystem_edit_text_file", path="a", old_text="x", new_text="y"),
    ],
)
def test_tool_calls_are_frozen(tool_call: ToolCall) -> None:
    with pytest.raises(AttributeError):
        tool_call.tool_name = "other"  # type: ignore[misc]


@pytest.mark.parametrize(
    ("tool_call", "expected"),
    [
        (GenericCall(tool_name="github_search", tool_args={}, ptc=False), "github_search"),
        (CodeAction(tool_name="ipybox_execute_ipython_cell", code="x=1"), "ipybox_execute_ipython_cell"),
        (ShellAction(tool_name="bash", command="git add /path/to/file.py"), "git add *"),
        (ShellAction(tool_name="bash", command="ls"), "ls *"),
        (ShellAction(tool_name="shell_magic", command="echo hello\necho world"), "echo hello\\necho world"),
        (
            FileRead(tool_name="filesystem_read_text_file", path="/tmp/a.txt", offset=None, limit=None),
            "filesystem_read_text_file /tmp/a.txt",
        ),
        (
            FileWrite(tool_name="filesystem_write_text_file", path="src/main.py", content="x"),
            "filesystem_write_text_file src/main.py",
        ),
        (
            FileEdit(tool_name="filesystem_edit_text_file", path="src/main.py", old_text="a", new_text="b"),
            "filesystem_edit_text_file src/main.py",
        ),
    ],
)
def test_suggest_pattern(tool_call: ToolCall, expected: str) -> None:
    assert suggest_pattern(tool_call) == expected


@pytest.mark.parametrize(
    ("payload", "expected"),
    [
        ("plain text", "plain text"),
        ({"content": "dict-content"}, "dict-content"),
        ({"text": "dict-text"}, "dict-text"),
        ([{"text": "a"}, "b", {"content": "c"}], "a\nb\nc"),
        ({"unexpected": 1}, '{\n  "unexpected": 1\n}'),
        (42, "42"),
    ],
)
def test_extract_tool_output_text(payload: object, expected: str) -> None:
    assert extract_tool_output_text(payload) == expected


@pytest.mark.parametrize(
    ("pattern", "template", "expected"),
    [
        (
            "git *",
            ShellAction(tool_name="bash", command="git status"),
            ShellAction(tool_name="bash", command="git *"),
        ),
        (
            "echo *",
            ShellAction(tool_name="shell_magic", command="echo test"),
            ShellAction(tool_name="shell_magic", command="echo *"),
        ),
        (
            "ipybox_*",
            CodeAction(tool_name="ipybox_execute_ipython_cell", code="print(1)"),
            CodeAction(tool_name="ipybox_*", code=""),
        ),
        (
            "filesystem_* src/**",
            FileRead(tool_name="filesystem_read_text_file", path="src/main.py", offset=None, limit=None),
            FileRead(tool_name="filesystem_*", path="src/**", offset=None, limit=None),
        ),
        (
            "github_*",
            GenericCall(tool_name="github_search", tool_args={"q": "test"}, ptc=False),
            GenericCall(tool_name="github_*", tool_args={}, ptc=False),
        ),
    ],
)
def test_parse_pattern(pattern: str, template: ToolCall, expected: ToolCall) -> None:
    assert parse_pattern(pattern, template) == expected


@pytest.mark.parametrize(
    ("tool_call", "expected"),
    [
        (
            ShellAction(tool_name="bash", command="git add /path/to/file.py"),
            ShellAction(tool_name="bash", command="git add *"),
        ),
        (
            ShellAction(tool_name="shell_magic", command="echo hello\necho world"),
            ShellAction(tool_name="shell_magic", command="echo hello\necho world"),
        ),
        (
            CodeAction(tool_name="ipybox_execute_ipython_cell", code="x = 1"),
            CodeAction(tool_name="ipybox_execute_ipython_cell", code=""),
        ),
        (
            FileRead(tool_name="filesystem_read_text_file", path="/tmp/a.txt", offset=3, limit=None),
            FileRead(tool_name="filesystem_read_text_file", path="/tmp/a.txt", offset=None, limit=None),
        ),
        (
            FileWrite(tool_name="filesystem_write_text_file", path="src/main.py", content="x"),
            FileWrite(tool_name="filesystem_write_text_file", path="src/main.py", content=""),
        ),
        (
            FileEdit(tool_name="filesystem_edit_text_file", path="src/config.py", old_text="a", new_text="b"),
            FileEdit(tool_name="filesystem_edit_text_file", path="src/config.py", old_text="", new_text=""),
        ),
    ],
)
def test_parse_pattern_roundtrip(tool_call: ToolCall, expected: ToolCall) -> None:
    assert parse_pattern(suggest_pattern(tool_call), tool_call) == expected
