# Covers behavior-inventory.md section: 15 (basic discovery, source-derived contract)
from pathlib import Path

import pytest

from freeact.tools.pytools import basic


@pytest.fixture
def pytools_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    (tmp_path / "mcptools" / "github").mkdir(parents=True)
    (tmp_path / "mcptools" / "github" / "create_issue.py").write_text("def run(): ...")
    (tmp_path / "mcptools" / "github" / "_internal.py").write_text("")
    (tmp_path / "mcptools" / "weather").mkdir(parents=True)
    (tmp_path / "mcptools" / "weather" / "get_forecast.py").write_text("def run(): ...")
    (tmp_path / "gentools" / "data" / "csv_parser").mkdir(parents=True)
    (tmp_path / "gentools" / "data" / "csv_parser" / "api.py").write_text("def run(): ...")
    (tmp_path / "gentools" / "data" / "no_api").mkdir(parents=True)
    monkeypatch.setattr(basic, "_PYTOOLS_DIR", tmp_path)
    return tmp_path


class TestListCategories:
    def test_lists_categories_from_both_sources(self, pytools_dir: Path) -> None:
        categories = basic.list_categories()
        assert sorted(categories.mcptools) == ["github", "weather"]
        assert categories.gentools == ["data"]


class TestListTools:
    def test_returns_full_source_file_paths(self, pytools_dir: Path) -> None:
        """Tool listings return full source file paths so the model can read the APIs."""
        result = basic.list_tools("github")

        assert result["github"].mcptools == [str(pytools_dir / "mcptools" / "github" / "create_issue.py")]
        assert result["github"].gentools == []

    def test_underscore_prefixed_files_skipped(self, pytools_dir: Path) -> None:
        result = basic.list_tools("github")
        assert all("_internal" not in path for path in result["github"].mcptools)

    def test_gentools_require_api_py(self, pytools_dir: Path) -> None:
        result = basic.list_tools("data")
        assert result["data"].gentools == [str(pytools_dir / "gentools" / "data" / "csv_parser" / "api.py")]

    def test_accepts_list_of_categories(self, pytools_dir: Path) -> None:
        result = basic.list_tools(["github", "weather"])
        assert set(result) == {"github", "weather"}
        assert result["weather"].mcptools == [str(pytools_dir / "mcptools" / "weather" / "get_forecast.py")]

    def test_unknown_category_yields_empty_tools(self, pytools_dir: Path) -> None:
        result = basic.list_tools("nonexistent")
        assert result["nonexistent"].mcptools == []
        assert result["nonexistent"].gentools == []
