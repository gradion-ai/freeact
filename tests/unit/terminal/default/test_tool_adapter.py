from freeact.terminal.default.tool_adapter import ToolAdapter
from freeact.terminal.default.tool_data import (
    CodeActionData,
    FileEditData,
    FileReadData,
    GenericToolCallData,
    GenericToolOutputData,
    ReadOutputData,
    TextEditData,
)


def test_map_action_ipybox_code_action() -> None:
    adapter = ToolAdapter()

    mapped = adapter.map_action("ipybox_execute_ipython_cell", {"code": "print('x')"})

    match mapped:
        case CodeActionData(code=code):
            assert code == "print('x')"
        case _:
            raise AssertionError(f"unexpected mapped approval data: {mapped}")


def test_map_action_filesystem_read_text_file() -> None:
    adapter = ToolAdapter()

    mapped = adapter.map_action(
        "filesystem_read_text_file",
        {"path": "/tmp/workspace/config.json", "head": 3, "tail": 1},
    )

    match mapped:
        case FileReadData(paths=paths, head=head, tail=tail):
            assert paths == ("/tmp/workspace/config.json",)
            assert head == 3
            assert tail == 1
        case _:
            raise AssertionError(f"unexpected mapped approval data: {mapped}")


def test_map_action_filesystem_read_file_alias() -> None:
    adapter = ToolAdapter()

    mapped = adapter.map_action("filesystem_read_file", {"path": "/tmp/workspace/README.md"})

    match mapped:
        case FileReadData(paths=paths, head=head, tail=tail):
            assert paths == ("/tmp/workspace/README.md",)
            assert head is None
            assert tail is None
        case _:
            raise AssertionError(f"unexpected mapped approval data: {mapped}")


def test_map_action_filesystem_read_multiple_files() -> None:
    adapter = ToolAdapter()

    mapped = adapter.map_action(
        "filesystem_read_multiple_files",
        {"paths": ["/tmp/workspace/a.py", "/tmp/workspace/b.py"]},
    )

    match mapped:
        case FileReadData(paths=paths, head=head, tail=tail):
            assert paths == ("/tmp/workspace/a.py", "/tmp/workspace/b.py")
            assert head is None
            assert tail is None
        case _:
            raise AssertionError(f"unexpected mapped approval data: {mapped}")


def test_map_action_filesystem_edit_normalizes_camel_and_snake_case() -> None:
    adapter = ToolAdapter()

    mapped = adapter.map_action(
        "filesystem_edit_file",
        {
            "path": "src/config.py",
            "edits": [
                {"oldText": "DEBUG = True", "newText": "DEBUG = False"},
                {"old_text": "A = 1", "new_text": "A = 2"},
                {"oldText": "B = 1", "new_text": "B = 2"},
                {"old_text": "C = 1", "newText": "C = 2"},
            ],
        },
    )

    match mapped:
        case FileEditData(path=path, edits=edits):
            assert path == "src/config.py"
            assert edits == (
                TextEditData(old_text="DEBUG = True", new_text="DEBUG = False"),
                TextEditData(old_text="A = 1", new_text="A = 2"),
                TextEditData(old_text="B = 1", new_text="B = 2"),
                TextEditData(old_text="C = 1", new_text="C = 2"),
            )
        case _:
            raise AssertionError(f"unexpected mapped approval data: {mapped}")


def test_map_action_unknown_tool_returns_generic() -> None:
    adapter = ToolAdapter()

    mapped = adapter.map_action("database_query", {"sql": "SELECT 1"})

    match mapped:
        case GenericToolCallData(tool_name=tool_name, tool_args=tool_args):
            assert tool_name == "database_query"
            assert tool_args == {"sql": "SELECT 1"}
        case _:
            raise AssertionError(f"unexpected mapped approval data: {mapped}")


def test_map_output_read_single_file() -> None:
    adapter = ToolAdapter()
    approval = FileReadData(paths=("/tmp/workspace/config.json",), head=None, tail=None)

    mapped = adapter.map_output(approval, '{"name": "myapp"}')

    match mapped:
        case ReadOutputData(title=title, filenames=filenames, content=content):
            assert title == "Read Output: config.json"
            assert filenames == ("/tmp/workspace/config.json",)
            assert content == '{"name": "myapp"}'
        case _:
            raise AssertionError(f"unexpected mapped output data: {mapped}")


def test_map_output_read_multiple_files() -> None:
    adapter = ToolAdapter()
    approval = FileReadData(
        paths=("/tmp/workspace/config.json", "/tmp/workspace/main.py", "/tmp/workspace/README.md"),
        head=None,
        tail=None,
    )

    mapped = adapter.map_output(approval, "raw merged output")

    match mapped:
        case ReadOutputData(title=title, filenames=filenames, content=content):
            assert title == "Read Output: 3 files"
            assert filenames == ()
            assert content == "raw merged output"
        case _:
            raise AssertionError(f"unexpected mapped output data: {mapped}")


def test_map_output_non_read_returns_generic() -> None:
    adapter = ToolAdapter()

    mapped = adapter.map_output(CodeActionData(code="print(1)"), "done")

    match mapped:
        case GenericToolOutputData(content=content):
            assert content == "done"
        case _:
            raise AssertionError(f"unexpected mapped output data: {mapped}")


def test_map_output_extracts_text_from_string_payload() -> None:
    adapter = ToolAdapter()

    mapped = adapter.map_output(None, "plain text")

    match mapped:
        case GenericToolOutputData(content=content):
            assert content == "plain text"
        case _:
            raise AssertionError(f"unexpected mapped output data: {mapped}")


def test_map_output_extracts_text_from_content_dict() -> None:
    adapter = ToolAdapter()

    mapped = adapter.map_output(None, {"content": "dict-content"})

    match mapped:
        case GenericToolOutputData(content=content):
            assert content == "dict-content"
        case _:
            raise AssertionError(f"unexpected mapped output data: {mapped}")


def test_map_output_extracts_text_from_text_dict() -> None:
    adapter = ToolAdapter()

    mapped = adapter.map_output(None, {"text": "dict-text"})

    match mapped:
        case GenericToolOutputData(content=content):
            assert content == "dict-text"
        case _:
            raise AssertionError(f"unexpected mapped output data: {mapped}")


def test_map_output_extracts_text_from_list_payload() -> None:
    adapter = ToolAdapter()

    mapped = adapter.map_output(None, [{"text": "a"}, "b", {"content": "c"}])

    match mapped:
        case GenericToolOutputData(content=content):
            assert content == "a\nb\nc"
        case _:
            raise AssertionError(f"unexpected mapped output data: {mapped}")


def test_map_output_serializes_unknown_dict_payload() -> None:
    adapter = ToolAdapter()

    mapped = adapter.map_output(None, {"unexpected": 1})

    match mapped:
        case GenericToolOutputData(content=content):
            assert content == '{\n  "unexpected": 1\n}'
        case _:
            raise AssertionError(f"unexpected mapped output data: {mapped}")
