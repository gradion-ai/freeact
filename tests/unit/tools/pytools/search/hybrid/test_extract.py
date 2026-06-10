from pathlib import Path

import pytest

from freeact.tools.pytools import GENTOOLS_DIR, MCPTOOLS_DIR
from freeact.tools.pytools.search.hybrid.extract import (
    extract_docstring,
    make_tool_id,
    parse_tool_id,
    scan_tools,
    tool_id_from_path,
    tool_info_from_path,
)

INVALID_TOOL_PATHS = [
    f"{MCPTOOLS_DIR}/_private/tool.py",
    f"{MCPTOOLS_DIR}/cat/_internal.py",
    f"{MCPTOOLS_DIR}/cat/sub/tool.py",
    f"{GENTOOLS_DIR}/cat/tool/other.py",
    "unknown/cat/tool.py",
]


@pytest.fixture
def fixtures_dir() -> Path:
    return Path(__file__).parent / "fixtures"


def write_tool(filepath: Path) -> Path:
    filepath.parent.mkdir(parents=True, exist_ok=True)
    filepath.write_text('def run(): """Doc."""\n    pass\n')
    return filepath


class TestExtractDocstring:
    def test_extract_run_docstring(self, fixtures_dir: Path) -> None:
        docstring = extract_docstring(fixtures_dir / MCPTOOLS_DIR / "github" / "create_issue.py")

        assert docstring is not None
        assert "Create a new issue in a GitHub repository" in docstring
        assert "Args:" in docstring
        assert "Returns:" in docstring

    def test_prefer_run_parsed_and_multiline(self, fixtures_dir: Path) -> None:
        docstring = extract_docstring(fixtures_dir / GENTOOLS_DIR / "data" / "csv_parser" / "api.py")

        assert docstring is not None
        assert "Parse CSV files into structured data" in docstring
        assert "Raises:" in docstring
        assert "using the first row as column headers" in docstring
        assert "basic version" not in docstring  # run() docstring, not run_parsed()

    def test_missing_run_function(self, tmp_path: Path) -> None:
        filepath = tmp_path / "no_run.py"
        filepath.write_text('def other(): """Not a run function."""\n    pass\n')

        assert extract_docstring(filepath) is None

    def test_missing_docstring(self, fixtures_dir: Path) -> None:
        assert extract_docstring(fixtures_dir / MCPTOOLS_DIR / "github" / "no_docstring.py") is None

    def test_nonexistent_file(self, tmp_path: Path) -> None:
        assert extract_docstring(tmp_path / "nonexistent.py") is None

    def test_syntax_error(self, tmp_path: Path) -> None:
        filepath = tmp_path / "syntax_error.py"
        filepath.write_text("def invalid syntax here")

        assert extract_docstring(filepath) is None


class TestScanTools:
    def test_scan_finds_valid_tools_and_skips_others(self, fixtures_dir: Path) -> None:
        tools = scan_tools(fixtures_dir)
        ids = [t.id for t in tools]

        assert f"{MCPTOOLS_DIR}:github:create_issue" in ids
        assert f"{MCPTOOLS_DIR}:github:list_repos" in ids
        assert f"{GENTOOLS_DIR}:data:csv_parser" in ids
        assert not any("_internal" in id for id in ids)  # _prefixed files skipped
        assert not any("no_docstring" in id for id in ids)  # tools without docstrings skipped

    def test_skip_prefixed_directories(self, tmp_path: Path) -> None:
        write_tool(tmp_path / MCPTOOLS_DIR / "_private" / "tool.py")

        assert scan_tools(tmp_path) == []

    def test_tool_info_fields(self, fixtures_dir: Path) -> None:
        tools = scan_tools(fixtures_dir)
        tool = next(t for t in tools if t.id == f"{MCPTOOLS_DIR}:github:create_issue")

        assert tool.name == "create_issue"
        assert tool.category == "github"
        assert tool.source == MCPTOOLS_DIR
        assert tool.filepath.name == "create_issue.py"
        assert "Create a new issue" in tool.description

    def test_empty_directory(self, tmp_path: Path) -> None:
        assert scan_tools(tmp_path) == []

    def test_missing_api_py(self, tmp_path: Path) -> None:
        write_tool(tmp_path / GENTOOLS_DIR / "cat" / "tool" / "other.py")

        assert scan_tools(tmp_path) == []


class TestToolIdFunctions:
    def test_make_tool_id(self) -> None:
        assert make_tool_id(MCPTOOLS_DIR, "github", "create_issue") == f"{MCPTOOLS_DIR}:github:create_issue"

    def test_parse_tool_id(self) -> None:
        source, category, name = parse_tool_id(f"{MCPTOOLS_DIR}:github:create_issue")

        assert source == MCPTOOLS_DIR
        assert category == "github"
        assert name == "create_issue"

    @pytest.mark.parametrize("tool_id", ["invalid", "too:many:colons:here"])
    def test_parse_tool_id_invalid(self, tool_id: str) -> None:
        with pytest.raises(ValueError, match="Invalid tool ID format"):
            parse_tool_id(tool_id)


class TestToolIdFromPath:
    def test_mcptools_valid_path(self, fixtures_dir: Path) -> None:
        filepath = fixtures_dir / MCPTOOLS_DIR / "github" / "create_issue.py"

        assert tool_id_from_path(filepath, fixtures_dir) == f"{MCPTOOLS_DIR}:github:create_issue"

    def test_gentools_valid_path(self, fixtures_dir: Path) -> None:
        filepath = fixtures_dir / GENTOOLS_DIR / "data" / "csv_parser" / "api.py"

        assert tool_id_from_path(filepath, fixtures_dir) == f"{GENTOOLS_DIR}:data:csv_parser"

    def test_path_outside_base_dir(self, fixtures_dir: Path, tmp_path: Path) -> None:
        assert tool_id_from_path(tmp_path / MCPTOOLS_DIR / "cat" / "tool.py", fixtures_dir) is None

    @pytest.mark.parametrize("relative", INVALID_TOOL_PATHS)
    def test_invalid_path_returns_none(self, tmp_path: Path, relative: str) -> None:
        assert tool_id_from_path(tmp_path / relative, tmp_path) is None


class TestToolInfoFromPath:
    def test_mcptools_valid_path(self, fixtures_dir: Path) -> None:
        filepath = fixtures_dir / MCPTOOLS_DIR / "github" / "create_issue.py"
        tool_info = tool_info_from_path(filepath, fixtures_dir)

        assert tool_info is not None
        assert tool_info.id == f"{MCPTOOLS_DIR}:github:create_issue"
        assert tool_info.name == "create_issue"
        assert tool_info.category == "github"
        assert tool_info.source == MCPTOOLS_DIR
        assert tool_info.filepath == filepath
        assert "Create a new issue" in tool_info.description

    def test_gentools_valid_path(self, fixtures_dir: Path) -> None:
        filepath = fixtures_dir / GENTOOLS_DIR / "data" / "csv_parser" / "api.py"
        tool_info = tool_info_from_path(filepath, fixtures_dir)

        assert tool_info is not None
        assert tool_info.id == f"{GENTOOLS_DIR}:data:csv_parser"
        assert tool_info.name == "csv_parser"
        assert tool_info.category == "data"
        assert tool_info.source == GENTOOLS_DIR
        assert tool_info.filepath == filepath

    def test_path_outside_base_dir(self, fixtures_dir: Path, tmp_path: Path) -> None:
        filepath = write_tool(tmp_path / MCPTOOLS_DIR / "cat" / "tool.py")

        assert tool_info_from_path(filepath, fixtures_dir) is None

    @pytest.mark.parametrize("relative", INVALID_TOOL_PATHS)
    def test_invalid_path_returns_none(self, tmp_path: Path, relative: str) -> None:
        filepath = write_tool(tmp_path / relative)

        assert tool_info_from_path(filepath, tmp_path) is None

    def test_no_docstring_returns_none(self, fixtures_dir: Path) -> None:
        filepath = fixtures_dir / MCPTOOLS_DIR / "github" / "no_docstring.py"

        assert tool_info_from_path(filepath, fixtures_dir) is None
