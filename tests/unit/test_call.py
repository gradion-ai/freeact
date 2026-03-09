import pytest

from freeact.agent.call import (
    CodeAction,
    FileEdit,
    FileRead,
    FileWrite,
    GenericCall,
    ShellAction,
    TextEdit,
    ToolCall,
    extract_tool_output_text,
    parse_pattern,
    suggest_pattern,
)


class TestFromRaw:
    """Tests for ToolCall.from_raw() factory method."""

    def test_code_action(self) -> None:
        tc = ToolCall.from_raw("ipybox_execute_ipython_cell", {"code": "print('x')"})
        assert isinstance(tc, CodeAction)
        assert tc.tool_name == "ipybox_execute_ipython_cell"
        assert tc.code == "print('x')"

    def test_read_single_file(self) -> None:
        tc = ToolCall.from_raw(
            "filesystem_read_text_file",
            {"path": "/tmp/config.json", "head": 3, "tail": 1},
        )
        assert isinstance(tc, FileRead)
        assert tc.paths == ("/tmp/config.json",)
        assert tc.head == 3
        assert tc.tail == 1

    def test_read_file_alias(self) -> None:
        tc = ToolCall.from_raw("filesystem_read_file", {"path": "/tmp/README.md"})
        assert isinstance(tc, FileRead)
        assert tc.paths == ("/tmp/README.md",)
        assert tc.head is None
        assert tc.tail is None

    def test_read_multiple_files(self) -> None:
        tc = ToolCall.from_raw(
            "filesystem_read_multiple_files",
            {"paths": ["/tmp/a.py", "/tmp/b.py"]},
        )
        assert isinstance(tc, FileRead)
        assert tc.paths == ("/tmp/a.py", "/tmp/b.py")
        assert tc.head is None
        assert tc.tail is None

    def test_write_file(self) -> None:
        tc = ToolCall.from_raw(
            "filesystem_write_file",
            {"path": "src/main.py", "content": "print(1)"},
        )
        assert isinstance(tc, FileWrite)
        assert tc.path == "src/main.py"
        assert tc.content == "print(1)"

    def test_edit_file_camel_case(self) -> None:
        tc = ToolCall.from_raw(
            "filesystem_edit_file",
            {
                "path": "src/config.py",
                "edits": [
                    {"oldText": "DEBUG = True", "newText": "DEBUG = False"},
                ],
            },
        )
        assert isinstance(tc, FileEdit)
        assert tc.path == "src/config.py"
        assert tc.edits == (TextEdit(old_text="DEBUG = True", new_text="DEBUG = False"),)

    def test_edit_file_snake_case(self) -> None:
        tc = ToolCall.from_raw(
            "filesystem_edit_file",
            {
                "path": "src/config.py",
                "edits": [
                    {"old_text": "A = 1", "new_text": "A = 2"},
                ],
            },
        )
        assert isinstance(tc, FileEdit)
        assert tc.edits == (TextEdit(old_text="A = 1", new_text="A = 2"),)

    def test_edit_file_mixed_case(self) -> None:
        tc = ToolCall.from_raw(
            "filesystem_edit_file",
            {
                "path": "src/config.py",
                "edits": [
                    {"oldText": "B = 1", "new_text": "B = 2"},
                    {"old_text": "C = 1", "newText": "C = 2"},
                ],
            },
        )
        assert isinstance(tc, FileEdit)
        assert tc.edits == (
            TextEdit(old_text="B = 1", new_text="B = 2"),
            TextEdit(old_text="C = 1", new_text="C = 2"),
        )

    def test_unknown_tool_returns_generic_call(self) -> None:
        tc = ToolCall.from_raw("database_query", {"sql": "SELECT 1"})
        assert isinstance(tc, GenericCall)
        assert tc.tool_name == "database_query"
        assert tc.tool_args == {"sql": "SELECT 1"}
        assert tc.ptc is False

    def test_missing_code_key(self) -> None:
        tc = ToolCall.from_raw("ipybox_execute_ipython_cell", {})
        assert isinstance(tc, CodeAction)
        assert tc.code == ""

    def test_missing_path_key(self) -> None:
        tc = ToolCall.from_raw("filesystem_read_file", {})
        assert isinstance(tc, FileRead)
        assert tc.paths == ("unknown",)

    def test_missing_edits_key(self) -> None:
        tc = ToolCall.from_raw("filesystem_edit_file", {"path": "f.py"})
        assert isinstance(tc, FileEdit)
        assert tc.edits == ()

    def test_non_list_paths(self) -> None:
        tc = ToolCall.from_raw("filesystem_read_multiple_files", {"paths": "not-a-list"})
        assert isinstance(tc, FileRead)
        assert tc.paths == ()


class TestFrozenImmutability:
    """ToolCall subclasses are frozen dataclasses."""

    def test_generic_call_is_frozen(self) -> None:
        tc = GenericCall(tool_name="x", tool_args={}, ptc=False)
        with pytest.raises(AttributeError):
            tc.tool_name = "y"  # type: ignore[misc]

    def test_shell_action_is_frozen(self) -> None:
        tc = ShellAction(tool_name="bash", command="ls")
        with pytest.raises(AttributeError):
            tc.command = "rm"  # type: ignore[misc]

    def test_code_action_is_frozen(self) -> None:
        tc = CodeAction(tool_name="ipybox_execute_ipython_cell", code="x=1")
        with pytest.raises(AttributeError):
            tc.code = "y=2"  # type: ignore[misc]

    def test_file_read_is_frozen(self) -> None:
        tc = FileRead(tool_name="filesystem_read_file", paths=("a",), head=None, tail=None)
        with pytest.raises(AttributeError):
            tc.paths = ("b",)  # type: ignore[misc]

    def test_file_write_is_frozen(self) -> None:
        tc = FileWrite(tool_name="filesystem_write_file", path="a", content="c")
        with pytest.raises(AttributeError):
            tc.path = "b"  # type: ignore[misc]

    def test_file_edit_is_frozen(self) -> None:
        tc = FileEdit(tool_name="filesystem_edit_file", path="a", edits=())
        with pytest.raises(AttributeError):
            tc.path = "b"  # type: ignore[misc]


class TestSuggestPattern:
    """Tests for suggest_pattern()."""

    def test_generic_call(self) -> None:
        tc = GenericCall(tool_name="github_search", tool_args={}, ptc=False)
        assert suggest_pattern(tc) == "github_search"

    def test_code_action(self) -> None:
        tc = CodeAction(tool_name="ipybox_execute_ipython_cell", code="x=1")
        assert suggest_pattern(tc) == "ipybox_execute_ipython_cell"

    def test_shell_action_delegates_to_shell_module(self) -> None:
        tc = ShellAction(tool_name="bash", command="git add /path/to/file.py")
        assert suggest_pattern(tc) == "git add *"

    def test_shell_action_single_token(self) -> None:
        tc = ShellAction(tool_name="bash", command="ls")
        assert suggest_pattern(tc) == "ls *"

    def test_file_read_single_path(self) -> None:
        tc = FileRead(tool_name="filesystem_read_file", paths=("/tmp/a.txt",), head=None, tail=None)
        assert suggest_pattern(tc) == "filesystem_read_file /tmp/a.txt"

    def test_file_read_multiple_paths(self) -> None:
        tc = FileRead(
            tool_name="filesystem_read_multiple_files", paths=("/tmp/a.txt", "/tmp/b.txt"), head=None, tail=None
        )
        assert suggest_pattern(tc) == "filesystem_read_multiple_files /tmp/a.txt /tmp/b.txt"

    def test_file_write(self) -> None:
        tc = FileWrite(tool_name="filesystem_write_file", path="src/main.py", content="x")
        assert suggest_pattern(tc) == "filesystem_write_file src/main.py"

    def test_file_edit(self) -> None:
        tc = FileEdit(tool_name="filesystem_edit_file", path="src/main.py", edits=())
        assert suggest_pattern(tc) == "filesystem_edit_file src/main.py"


class TestExtractToolOutputText:
    """Tests for extract_tool_output_text(), ported from test_tool_adapter.py."""

    def test_string_payload(self) -> None:
        assert extract_tool_output_text("plain text") == "plain text"

    def test_content_dict(self) -> None:
        assert extract_tool_output_text({"content": "dict-content"}) == "dict-content"

    def test_text_dict(self) -> None:
        assert extract_tool_output_text({"text": "dict-text"}) == "dict-text"

    def test_list_payload(self) -> None:
        result = extract_tool_output_text([{"text": "a"}, "b", {"content": "c"}])
        assert result == "a\nb\nc"

    def test_unknown_dict_serializes_as_json(self) -> None:
        result = extract_tool_output_text({"unexpected": 1})
        assert result == '{\n  "unexpected": 1\n}'

    def test_non_string_non_dict_uses_str(self) -> None:
        assert extract_tool_output_text(42) == "42"


class TestParsePattern:
    """Tests for parse_pattern()."""

    def test_shell_action(self) -> None:
        template = ShellAction(tool_name="bash", command="git status")
        result = parse_pattern("git *", template)
        assert isinstance(result, ShellAction)
        assert result.tool_name == "bash"
        assert result.command == "git *"

    def test_code_action(self) -> None:
        template = CodeAction(tool_name="ipybox_execute_ipython_cell", code="print(1)")
        result = parse_pattern("ipybox_*", template)
        assert isinstance(result, CodeAction)
        assert result.tool_name == "ipybox_*"
        assert result.code == ""

    def test_code_action_roundtrip(self) -> None:
        tc = CodeAction(tool_name="ipybox_execute_ipython_cell", code="x = 1")
        result = parse_pattern(suggest_pattern(tc), tc)
        assert isinstance(result, CodeAction)
        assert result.tool_name == tc.tool_name

    def test_file_read_with_tool_name_and_paths(self) -> None:
        template = FileRead(tool_name="filesystem_read_file", paths=("src/main.py",), head=None, tail=None)
        result = parse_pattern("filesystem_* src/**", template)
        assert isinstance(result, FileRead)
        assert result.tool_name == "filesystem_*"
        assert result.paths == ("src/**",)

    def test_file_write_roundtrip(self) -> None:
        tc = FileWrite(tool_name="filesystem_write_file", path="src/main.py", content="x")
        pattern = suggest_pattern(tc)
        result = parse_pattern(pattern, tc)
        assert isinstance(result, FileWrite)
        assert result.tool_name == tc.tool_name
        assert result.path == tc.path

    def test_file_edit_roundtrip(self) -> None:
        tc = FileEdit(tool_name="filesystem_edit_file", path="src/config.py", edits=())
        pattern = suggest_pattern(tc)
        result = parse_pattern(pattern, tc)
        assert isinstance(result, FileEdit)
        assert result.tool_name == tc.tool_name
        assert result.path == tc.path

    def test_fallback_to_generic_call(self) -> None:
        template = GenericCall(tool_name="github_search", tool_args={"q": "test"}, ptc=False)
        result = parse_pattern("github_*", template)
        assert isinstance(result, GenericCall)
        assert result.tool_name == "github_*"

    def test_roundtrip_shell_action(self) -> None:
        tc = ShellAction(tool_name="bash", command="git add /path/to/file.py")
        result = parse_pattern(suggest_pattern(tc), tc)
        assert isinstance(result, ShellAction)
        assert result.tool_name == "bash"

    def test_roundtrip_file_read(self) -> None:
        tc = FileRead(tool_name="filesystem_read_file", paths=("/tmp/a.txt",), head=3, tail=None)
        result = parse_pattern(suggest_pattern(tc), tc)
        assert isinstance(result, FileRead)
        assert result.tool_name == tc.tool_name
        assert result.paths == tc.paths
