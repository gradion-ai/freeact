"""Tests for freeact/agent/config/config.py."""

import json
from pathlib import Path

import pytest

from freeact.agent.config.config import (
    FILESYSTEM_CONFIG,
    PYTOOLS_BASIC_CONFIG,
    PYTOOLS_HYBRID_CONFIG,
    Config,
    _ensure_hybrid_env_defaults,
)


@pytest.fixture
def freeact_dir(tmp_path: Path) -> Path:
    """Create minimal .freeact directory structure."""
    freeact_dir = tmp_path / ".freeact"
    freeact_dir.mkdir()
    (freeact_dir / "config.json").write_text(json.dumps({}))
    return freeact_dir


class TestParseSkillFile:
    """Tests for skill file parsing via Config initialization."""

    def test_parses_valid_yaml_frontmatter(self, tmp_path: Path, freeact_dir: Path):
        """Parses name and description from YAML frontmatter."""
        skill_dir = freeact_dir / "skills" / "test-skill"
        skill_dir.mkdir(parents=True)
        (skill_dir / "SKILL.md").write_text(
            """---
name: test-skill
description: A test skill for testing
---

# Test Skill

Content here.
"""
        )

        config = Config(working_dir=tmp_path)

        assert len(config.skills_metadata) == 1
        assert config.skills_metadata[0].name == "test-skill"
        assert config.skills_metadata[0].description == "A test skill for testing"

    def test_skips_file_without_frontmatter(self, tmp_path: Path, freeact_dir: Path):
        """Skips skill files that don't start with ---."""
        skill_dir = freeact_dir / "skills" / "invalid-skill"
        skill_dir.mkdir(parents=True)
        (skill_dir / "SKILL.md").write_text(
            """# Test Skill

No frontmatter here.
"""
        )

        config = Config(working_dir=tmp_path)

        assert len(config.skills_metadata) == 0

    def test_skips_file_with_incomplete_frontmatter(self, tmp_path: Path, freeact_dir: Path):
        """Skips skill files with unclosed frontmatter."""
        skill_dir = freeact_dir / "skills" / "incomplete-skill"
        skill_dir.mkdir(parents=True)
        (skill_dir / "SKILL.md").write_text("---\nname: test-skill\ndescription: No closing delimiter")

        config = Config(working_dir=tmp_path)

        assert len(config.skills_metadata) == 0


class TestRenderSkillsSection:
    """Tests for skills section rendering in system prompt."""

    def test_renders_skills_in_system_prompt(self, tmp_path: Path, freeact_dir: Path):
        """Renders skill metadata as markdown in system prompt."""
        for name, desc in [("skill-one", "First description"), ("skill-two", "Second description")]:
            skill_dir = freeact_dir / "skills" / name
            skill_dir.mkdir(parents=True)
            (skill_dir / "SKILL.md").write_text(f"---\nname: {name}\ndescription: {desc}\n---\nContent.")

        config = Config(working_dir=tmp_path)

        assert "**skill-one**" in config.system_prompt
        assert "First description" in config.system_prompt
        assert "**skill-two**" in config.system_prompt
        assert "Second description" in config.system_prompt

    def test_shows_no_skills_message_when_empty(self, tmp_path: Path, freeact_dir: Path):
        """Shows 'No skills available.' when no skills exist."""
        config = Config(working_dir=tmp_path)

        assert "No skills available." in config.system_prompt


class TestLoadSystemPrompt:
    """Tests for system prompt loading from package resources."""

    def test_loads_and_renders_placeholders(self, tmp_path: Path, freeact_dir: Path):
        """Substitutes {working_dir} and {skills} in system prompt."""
        config = Config(working_dir=tmp_path)

        assert str(tmp_path) in config.system_prompt
        assert "No skills available." in config.system_prompt


class TestSystemPromptSelection:
    """Tests for system prompt file selection based on tool-search config."""

    def test_loads_basic_prompt_by_default(self, tmp_path: Path, freeact_dir: Path):
        """Loads basic system prompt when tool-search is not set."""
        config = Config(working_dir=tmp_path)

        assert "pytools_list_categories" in config.system_prompt

    def test_loads_basic_prompt_for_basic_tool_search(self, tmp_path: Path, freeact_dir: Path):
        """Loads basic system prompt when tool-search is 'basic'."""
        (freeact_dir / "config.json").write_text(json.dumps({"tool-search": "basic"}))

        config = Config(working_dir=tmp_path)

        assert "pytools_list_categories" in config.system_prompt

    def test_loads_hybrid_prompt_for_hybrid_tool_search(
        self, tmp_path: Path, freeact_dir: Path, monkeypatch: pytest.MonkeyPatch
    ):
        """Loads hybrid system prompt when tool-search is 'hybrid'."""
        monkeypatch.setenv("GEMINI_API_KEY", "test-key")
        (freeact_dir / "config.json").write_text(json.dumps({"tool-search": "hybrid"}))

        config = Config(working_dir=tmp_path)

        assert "pytools_search_tools" in config.system_prompt


class TestToolSearchConfig:
    """Tests for tool-search setting from config.json."""

    def test_defaults_to_basic(self, tmp_path: Path, freeact_dir: Path):
        """Defaults to 'basic' when tool-search is not in config.json."""
        config = Config(working_dir=tmp_path)

        assert config.tool_search == "basic"

    def test_reads_from_config_json(self, tmp_path: Path, freeact_dir: Path, monkeypatch: pytest.MonkeyPatch):
        """Reads tool-search value from config.json."""
        monkeypatch.setenv("GEMINI_API_KEY", "test-key")
        (freeact_dir / "config.json").write_text(json.dumps({"tool-search": "hybrid"}))

        config = Config(working_dir=tmp_path)

        assert config.tool_search == "hybrid"


class TestHybridEnvDefaults:
    """Tests for _ensure_hybrid_env_defaults."""

    def test_sets_missing_env_vars(self, monkeypatch: pytest.MonkeyPatch):
        """Sets default values for env vars that are not already set."""
        monkeypatch.delenv("PYTOOLS_DIR", raising=False)
        monkeypatch.delenv("PYTOOLS_DB_PATH", raising=False)
        monkeypatch.delenv("PYTOOLS_EMBEDDING_MODEL", raising=False)

        _ensure_hybrid_env_defaults()

        import os

        assert os.environ["PYTOOLS_DIR"] == ".freeact/generated"
        assert os.environ["PYTOOLS_DB_PATH"] == ".freeact/search.db"
        assert os.environ["PYTOOLS_EMBEDDING_MODEL"] == "google-gla:gemini-embedding-001"

    def test_preserves_existing_env_vars(self, monkeypatch: pytest.MonkeyPatch):
        """Does not overwrite env vars that are already set."""
        monkeypatch.setenv("PYTOOLS_DIR", "/custom/path")
        monkeypatch.setenv("PYTOOLS_DB_PATH", "/custom/db.sqlite")

        _ensure_hybrid_env_defaults()

        import os

        assert os.environ["PYTOOLS_DIR"] == "/custom/path"
        assert os.environ["PYTOOLS_DB_PATH"] == "/custom/db.sqlite"


class TestLoadConfigJson:
    """Tests for config.json loading."""

    def test_loads_config(self, tmp_path: Path, freeact_dir: Path):
        """Loads and parses config.json file."""
        (freeact_dir / "config.json").write_text(
            json.dumps(
                {
                    "mcp-servers": {"test": {"command": "echo", "args": []}},
                    "ptc-servers": {"ptc-test": {"command": "python"}},
                }
            )
        )

        config = Config(working_dir=tmp_path)

        assert "test" in config.mcp_servers
        assert "ptc-test" in config.ptc_servers

    def test_handles_missing_config_json(self, tmp_path: Path, freeact_dir: Path):
        """Handles missing config.json gracefully."""
        (freeact_dir / "config.json").unlink()

        config = Config(working_dir=tmp_path)

        # Internal MCP servers are still present
        assert "pytools" in config.mcp_servers
        assert "filesystem" in config.mcp_servers
        assert config.ptc_servers == {}


class TestLoadMcpServers:
    """Tests for MCP server config loading with internal/user merging."""

    def test_internal_servers_present_by_default(self, tmp_path: Path, freeact_dir: Path):
        """Internal pytools and filesystem servers are loaded by default."""
        config = Config(working_dir=tmp_path)

        assert "pytools" in config.mcp_servers
        assert "filesystem" in config.mcp_servers
        assert config.mcp_servers["pytools"] == PYTOOLS_BASIC_CONFIG
        assert config.mcp_servers["filesystem"] == FILESYSTEM_CONFIG

    def test_hybrid_pytools_when_hybrid_tool_search(
        self, tmp_path: Path, freeact_dir: Path, monkeypatch: pytest.MonkeyPatch
    ):
        """Uses hybrid pytools config when tool-search is 'hybrid'."""
        monkeypatch.setenv("GEMINI_API_KEY", "test-key")
        (freeact_dir / "config.json").write_text(json.dumps({"tool-search": "hybrid"}))

        config = Config(working_dir=tmp_path)

        assert config.mcp_servers["pytools"] == PYTOOLS_HYBRID_CONFIG

    def test_user_pytools_overrides_internal(self, tmp_path: Path, freeact_dir: Path):
        """User pytools config in config.json overrides internal default."""
        user_pytools = {"command": "custom-pytools", "args": ["--custom"]}
        (freeact_dir / "config.json").write_text(json.dumps({"mcp-servers": {"pytools": user_pytools}}))

        config = Config(working_dir=tmp_path)

        assert config.mcp_servers["pytools"] == user_pytools

    def test_user_filesystem_overrides_internal(self, tmp_path: Path, freeact_dir: Path):
        """User filesystem config in config.json overrides internal default."""
        user_filesystem = {"command": "custom-fs", "args": ["--verbose"]}
        (freeact_dir / "config.json").write_text(json.dumps({"mcp-servers": {"filesystem": user_filesystem}}))

        config = Config(working_dir=tmp_path)

        assert config.mcp_servers["filesystem"] == user_filesystem

    def test_user_adds_custom_server(self, tmp_path: Path, freeact_dir: Path):
        """User can add custom MCP servers alongside internal ones."""
        custom = {"command": "my-server"}
        (freeact_dir / "config.json").write_text(json.dumps({"mcp-servers": {"custom": custom}}))

        config = Config(working_dir=tmp_path)

        assert "pytools" in config.mcp_servers
        assert "filesystem" in config.mcp_servers
        assert config.mcp_servers["custom"] == custom

    def test_empty_mcp_servers_uses_internal_defaults(self, tmp_path: Path, freeact_dir: Path):
        """Empty mcp-servers section uses internal defaults only."""
        (freeact_dir / "config.json").write_text(json.dumps({"mcp-servers": {}}))

        config = Config(working_dir=tmp_path)

        assert config.mcp_servers["pytools"] == PYTOOLS_BASIC_CONFIG
        assert config.mcp_servers["filesystem"] == FILESYSTEM_CONFIG

    def test_raises_on_missing_env_variables(self, tmp_path: Path, freeact_dir: Path, monkeypatch: pytest.MonkeyPatch):
        """Raises ValueError when ${VAR} references missing env var."""
        (freeact_dir / "config.json").write_text(
            json.dumps(
                {"mcp-servers": {"test-server": {"command": "python", "env": {"API_KEY": "${MISSING_ENV_VAR}"}}}}
            )
        )
        monkeypatch.delenv("MISSING_ENV_VAR", raising=False)

        with pytest.raises(ValueError, match="Missing environment variables"):
            Config(working_dir=tmp_path)


class TestLoadPtcServers:
    """Tests for PTC server loading."""

    def test_loads_ptc_config(self, tmp_path: Path, freeact_dir: Path, monkeypatch: pytest.MonkeyPatch):
        """Loads PTC server configurations."""
        monkeypatch.setenv("TEST_API_KEY", "test-key-value")
        (freeact_dir / "config.json").write_text(
            json.dumps(
                {
                    "ptc-servers": {
                        "google": {"command": "python", "args": ["-m", "test"], "env": {"API_KEY": "${TEST_API_KEY}"}}
                    }
                }
            )
        )

        config = Config(working_dir=tmp_path)

        assert "google" in config.ptc_servers
        # Config is returned with original placeholders (not replaced)
        assert config.ptc_servers["google"]["env"]["API_KEY"] == "${TEST_API_KEY}"

    def test_raises_on_missing_env_variables(self, tmp_path: Path, freeact_dir: Path, monkeypatch: pytest.MonkeyPatch):
        """Raises ValueError when env variables are missing."""
        (freeact_dir / "config.json").write_text(
            json.dumps({"ptc-servers": {"test": {"command": "python", "env": {"API_KEY": "${MISSING_PTC_ENV_VAR}"}}}})
        )
        monkeypatch.delenv("MISSING_PTC_ENV_VAR", raising=False)

        with pytest.raises(ValueError, match="Missing environment variables"):
            Config(working_dir=tmp_path)

    def test_returns_empty_when_no_ptc_servers(self, tmp_path: Path, freeact_dir: Path):
        """Returns empty dict when ptc-servers section is missing."""
        config = Config(working_dir=tmp_path)

        assert config.ptc_servers == {}


class TestConfigInit:
    """Tests for full Config initialization."""

    def test_full_initialization(self, tmp_path: Path, freeact_dir: Path, monkeypatch: pytest.MonkeyPatch):
        """Full Config initialization with all components."""
        monkeypatch.setenv("TEST_API_KEY", "test-value")

        (freeact_dir / "config.json").write_text(
            json.dumps(
                {
                    "ptc-servers": {"ptc": {"command": "python", "env": {"KEY": "${TEST_API_KEY}"}}},
                }
            )
        )

        skill_dir = freeact_dir / "skills" / "test-skill"
        skill_dir.mkdir(parents=True)
        (skill_dir / "SKILL.md").write_text("---\nname: test-skill\ndescription: Test skill\n---\nContent.")

        (freeact_dir / "plans").mkdir()

        config = Config(working_dir=tmp_path)

        assert config.working_dir == tmp_path
        assert config.freeact_dir == freeact_dir
        assert config.plans_dir == freeact_dir / "plans"
        assert len(config.skills_metadata) == 1
        assert config.skills_metadata[0].name == "test-skill"
        assert str(tmp_path) in config.system_prompt
        assert "pytools" in config.mcp_servers
        assert "filesystem" in config.mcp_servers
        assert "ptc" in config.ptc_servers

    def test_uses_cwd_when_working_dir_is_none(
        self, tmp_path: Path, freeact_dir: Path, monkeypatch: pytest.MonkeyPatch
    ):
        """Uses current working directory when working_dir is None."""
        monkeypatch.chdir(tmp_path)

        config = Config()

        assert config.working_dir == tmp_path
