"""Unit tests for the docstring extraction module."""

from __future__ import annotations

from pathlib import Path

import pytest

from freeact.agent.tools.pytools.search.hybrid.extract import (
    extract_docstring,
    make_tool_id,
    parse_tool_id,
    scan_tools,
)


@pytest.fixture
def fixtures_dir() -> Path:
    """Path to test fixtures directory."""
    return Path(__file__).parent / "fixtures"


class TestExtractDocstring:
    """Tests for extract_docstring function."""

    def test_extract_run_docstring(self, fixtures_dir: Path) -> None:
        """Test extracting full docstring from run() function."""
        filepath = fixtures_dir / "mcptools" / "github" / "create_issue.py"
        docstring = extract_docstring(filepath)

        assert docstring is not None
        assert "Create a new issue in a GitHub repository" in docstring
        assert "Args:" in docstring
        assert "Returns:" in docstring

    def test_prefer_run_parsed(self, fixtures_dir: Path) -> None:
        """Test that run_parsed() is preferred over run() when both exist."""
        filepath = fixtures_dir / "gentools" / "data" / "csv_parser" / "api.py"
        docstring = extract_docstring(filepath)

        assert docstring is not None
        # Should get run_parsed docstring, not run
        assert "Parse CSV files into structured data" in docstring
        assert "Raises:" in docstring
        # run() docstring says "basic version"
        assert "basic version" not in docstring

    def test_multiline_docstring(self, fixtures_dir: Path) -> None:
        """Test extracting multiline docstrings."""
        filepath = fixtures_dir / "gentools" / "data" / "csv_parser" / "api.py"
        docstring = extract_docstring(filepath)

        assert docstring is not None
        # Check that multi-paragraph content is included
        assert "using the first row as column headers" in docstring

    def test_missing_run_function(self, tmp_path: Path) -> None:
        """Test returns None when no run() function exists."""
        filepath = tmp_path / "no_run.py"
        filepath.write_text('def other(): """Not a run function."""\n    pass\n')

        docstring = extract_docstring(filepath)

        assert docstring is None

    def test_missing_docstring(self, fixtures_dir: Path) -> None:
        """Test returns None when run() has no docstring."""
        filepath = fixtures_dir / "mcptools" / "github" / "no_docstring.py"
        docstring = extract_docstring(filepath)

        assert docstring is None

    def test_nonexistent_file(self, tmp_path: Path) -> None:
        """Test returns None for nonexistent file."""
        filepath = tmp_path / "nonexistent.py"
        docstring = extract_docstring(filepath)

        assert docstring is None

    def test_syntax_error(self, tmp_path: Path) -> None:
        """Test returns None for file with syntax error."""
        filepath = tmp_path / "syntax_error.py"
        filepath.write_text("def invalid syntax here")

        docstring = extract_docstring(filepath)

        assert docstring is None


class TestScanTools:
    """Tests for scan_tools function."""

    def test_scan_mcptools(self, fixtures_dir: Path) -> None:
        """Test scanning mcptools structure correctly."""
        tools = scan_tools(fixtures_dir)

        mcptools = [t for t in tools if t.source == "mcptools"]
        ids = [t.id for t in mcptools]

        assert "mcptools:github:create_issue" in ids
        assert "mcptools:github:list_repos" in ids

    def test_scan_gentools(self, fixtures_dir: Path) -> None:
        """Test scanning gentools structure correctly."""
        tools = scan_tools(fixtures_dir)

        gentools = [t for t in tools if t.source == "gentools"]
        ids = [t.id for t in gentools]

        assert "gentools:data:csv_parser" in ids

    def test_skip_prefixed_files(self, fixtures_dir: Path) -> None:
        """Test that _prefixed files are skipped."""
        tools = scan_tools(fixtures_dir)
        ids = [t.id for t in tools]

        # _internal.py should not be in results
        assert not any("_internal" in id for id in ids)

    def test_skip_prefixed_directories(self, tmp_path: Path) -> None:
        """Test that _prefixed directories are skipped."""
        # Create _private category
        private_dir = tmp_path / "mcptools" / "_private"
        private_dir.mkdir(parents=True)
        (private_dir / "tool.py").write_text('def run(): """Doc."""\n    pass\n')

        tools = scan_tools(tmp_path)

        assert len(tools) == 0

    def test_skip_tools_without_docstrings(self, fixtures_dir: Path) -> None:
        """Test that tools without docstrings are skipped."""
        tools = scan_tools(fixtures_dir)
        ids = [t.id for t in tools]

        # no_docstring.py has no docstring on run()
        assert not any("no_docstring" in id for id in ids)

    def test_tool_info_fields(self, fixtures_dir: Path) -> None:
        """Test that ToolInfo has correct fields."""
        tools = scan_tools(fixtures_dir)
        tool = next(t for t in tools if t.id == "mcptools:github:create_issue")

        assert tool.name == "create_issue"
        assert tool.category == "github"
        assert tool.source == "mcptools"
        assert tool.filepath.name == "create_issue.py"
        assert "Create a new issue" in tool.description

    def test_empty_directory(self, tmp_path: Path) -> None:
        """Test scanning empty/missing directories."""
        tools = scan_tools(tmp_path)

        assert tools == []

    def test_missing_api_py(self, tmp_path: Path) -> None:
        """Test gentools without api.py are skipped."""
        tool_dir = tmp_path / "gentools" / "cat" / "tool"
        tool_dir.mkdir(parents=True)
        (tool_dir / "other.py").write_text('def run(): """Doc."""\n    pass\n')

        tools = scan_tools(tmp_path)

        assert len(tools) == 0


class TestToolIdFunctions:
    """Tests for tool ID creation and parsing."""

    def test_make_tool_id(self) -> None:
        """Test creating tool ID from components."""
        id = make_tool_id("mcptools", "github", "create_issue")

        assert id == "mcptools:github:create_issue"

    def test_parse_tool_id(self) -> None:
        """Test parsing tool ID into components."""
        source, category, name = parse_tool_id("mcptools:github:create_issue")

        assert source == "mcptools"
        assert category == "github"
        assert name == "create_issue"

    def test_parse_tool_id_invalid(self) -> None:
        """Test parsing invalid tool ID raises ValueError."""
        with pytest.raises(ValueError, match="Invalid tool ID format"):
            parse_tool_id("invalid")

        with pytest.raises(ValueError, match="Invalid tool ID format"):
            parse_tool_id("too:many:colons:here")
