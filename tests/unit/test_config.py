"""Tests for freeact/agent/config/config.py."""

import json
import os
from pathlib import Path

import pytest

from freeact.agent.config.config import (
    Config,
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


class TestPytoolsEnvDefaults:
    """Tests for pytools env var defaults set by Config."""

    def test_sets_absolute_paths_for_pytools_dir(
        self, tmp_path: Path, freeact_dir: Path, monkeypatch: pytest.MonkeyPatch
    ):
        """Sets PYTOOLS_DIR as absolute path derived from working_dir."""
        monkeypatch.delenv("PYTOOLS_DIR", raising=False)
        monkeypatch.delenv("PYTOOLS_DB_PATH", raising=False)

        config = Config(working_dir=tmp_path)

        assert os.environ["PYTOOLS_DIR"] == str(config.generated_dir)
        assert os.environ["PYTOOLS_DB_PATH"] == str(config.search_db_file)

    def test_sets_pytools_dir_in_basic_mode(self, tmp_path: Path, freeact_dir: Path, monkeypatch: pytest.MonkeyPatch):
        """PYTOOLS_DIR is set even in basic mode."""
        monkeypatch.delenv("PYTOOLS_DIR", raising=False)

        Config(working_dir=tmp_path)

        assert "PYTOOLS_DIR" in os.environ

    def test_sets_hybrid_specific_defaults(self, tmp_path: Path, freeact_dir: Path, monkeypatch: pytest.MonkeyPatch):
        """Sets hybrid-specific defaults when tool-search is hybrid."""
        monkeypatch.setenv("GEMINI_API_KEY", "test-key")
        monkeypatch.delenv("PYTOOLS_EMBEDDING_MODEL", raising=False)
        (freeact_dir / "config.json").write_text('{"tool-search": "hybrid"}')

        Config(working_dir=tmp_path)

        assert os.environ["PYTOOLS_EMBEDDING_MODEL"] == "google-gla:gemini-embedding-001"

    def test_preserves_existing_env_vars(self, tmp_path: Path, freeact_dir: Path, monkeypatch: pytest.MonkeyPatch):
        """Does not overwrite env vars that are already set."""
        monkeypatch.setenv("PYTOOLS_DIR", "/custom/path")
        monkeypatch.setenv("PYTOOLS_DB_PATH", "/custom/db.sqlite")

        Config(working_dir=tmp_path)

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
        # Resolved values, not raw placeholders
        assert "${PYTOOLS_DIR}" not in str(config.mcp_servers["pytools"])

    def test_hybrid_pytools_when_hybrid_tool_search(
        self, tmp_path: Path, freeact_dir: Path, monkeypatch: pytest.MonkeyPatch
    ):
        """Uses hybrid pytools config when tool-search is 'hybrid'."""
        monkeypatch.setenv("GEMINI_API_KEY", "test-key")
        (freeact_dir / "config.json").write_text(json.dumps({"tool-search": "hybrid"}))

        config = Config(working_dir=tmp_path)

        # Resolved, so env values should be present instead of placeholders
        assert "pytools" in config.mcp_servers
        assert "${GEMINI_API_KEY}" not in str(config.mcp_servers["pytools"])

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

        assert "pytools" in config.mcp_servers
        assert "filesystem" in config.mcp_servers

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

    def test_mcp_servers_are_resolved(self, tmp_path: Path, freeact_dir: Path, monkeypatch: pytest.MonkeyPatch):
        """MCP server ${VAR} placeholders are resolved in stored config."""
        monkeypatch.setenv("MY_API_KEY", "resolved-key")
        (freeact_dir / "config.json").write_text(
            json.dumps({"mcp-servers": {"test": {"command": "python", "env": {"API_KEY": "${MY_API_KEY}"}}}})
        )

        config = Config(working_dir=tmp_path)

        assert config.mcp_servers["test"]["env"]["API_KEY"] == "resolved-key"


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


class TestLoadKernelEnv:
    """Tests for kernel environment variable loading."""

    def test_pythonpath_auto_default(self, tmp_path: Path, freeact_dir: Path):
        """PYTHONPATH is auto-set to generated_dir."""
        config = Config(working_dir=tmp_path)

        assert config.kernel_env["PYTHONPATH"] == str(config.generated_dir)

    def test_home_auto_default(self, tmp_path: Path, freeact_dir: Path, monkeypatch: pytest.MonkeyPatch):
        """HOME is auto-set from os.environ."""
        monkeypatch.setenv("HOME", "/home/testuser")

        config = Config(working_dir=tmp_path)

        assert config.kernel_env["HOME"] == "/home/testuser"

    def test_home_not_added_when_missing(self, tmp_path: Path, freeact_dir: Path, monkeypatch: pytest.MonkeyPatch):
        """HOME is not added when missing from os.environ."""
        monkeypatch.delenv("HOME", raising=False)

        config = Config(working_dir=tmp_path)

        assert "HOME" not in config.kernel_env

    def test_user_overrides_auto_defaults(self, tmp_path: Path, freeact_dir: Path, monkeypatch: pytest.MonkeyPatch):
        """User values in config.json override auto-defaults."""
        monkeypatch.setenv("HOME", "/home/testuser")
        (freeact_dir / "config.json").write_text(
            json.dumps({"kernel-env": {"PYTHONPATH": "/custom/path", "HOME": "/custom/home"}})
        )

        config = Config(working_dir=tmp_path)

        assert config.kernel_env["PYTHONPATH"] == "/custom/path"
        assert config.kernel_env["HOME"] == "/custom/home"

    def test_resolves_placeholders(self, tmp_path: Path, freeact_dir: Path, monkeypatch: pytest.MonkeyPatch):
        """${VAR} placeholders are resolved in kernel_env."""
        monkeypatch.setenv("MY_CUSTOM_VAR", "resolved-value")
        (freeact_dir / "config.json").write_text(json.dumps({"kernel-env": {"CUSTOM": "${MY_CUSTOM_VAR}"}}))

        config = Config(working_dir=tmp_path)

        assert config.kernel_env["CUSTOM"] == "resolved-value"

    def test_raises_on_missing_env_variables(self, tmp_path: Path, freeact_dir: Path, monkeypatch: pytest.MonkeyPatch):
        """Raises ValueError when ${VAR} references missing env var."""
        (freeact_dir / "config.json").write_text(json.dumps({"kernel-env": {"KEY": "${MISSING_KERNEL_ENV_VAR}"}}))
        monkeypatch.delenv("MISSING_KERNEL_ENV_VAR", raising=False)

        with pytest.raises(ValueError, match="Missing environment variables for kernel-env"):
            Config(working_dir=tmp_path)

    def test_empty_kernel_env_uses_defaults(self, tmp_path: Path, freeact_dir: Path):
        """Empty kernel-env in config.json still gets auto-defaults."""
        (freeact_dir / "config.json").write_text(json.dumps({"kernel-env": {}}))

        config = Config(working_dir=tmp_path)

        assert "PYTHONPATH" in config.kernel_env


class TestForSubagent:
    """Tests for Config.for_subagent() method."""

    def test_sets_agent_id(self, tmp_path: Path, freeact_dir: Path):
        """Subagent config has the specified agent_id."""
        config = Config(working_dir=tmp_path)
        sub = config.for_subagent("sub-1234")

        assert sub.agent_id == "sub-1234"

    def test_disables_subagents(self, tmp_path: Path, freeact_dir: Path):
        """Subagent config has enable_subagents=False."""
        config = Config(working_dir=tmp_path)
        sub = config.for_subagent("sub-1234")

        assert sub.enable_subagents is False

    def test_kernel_env_is_independent(self, tmp_path: Path, freeact_dir: Path):
        """Subagent kernel_env is a separate dict."""
        config = Config(working_dir=tmp_path)
        sub = config.for_subagent("sub-1234")

        assert sub.kernel_env is not config.kernel_env
        assert sub.kernel_env == config.kernel_env

    def test_mcp_servers_have_sync_watch_disabled(self, tmp_path: Path, freeact_dir: Path):
        """Subagent mcp_servers have pytools sync/watch disabled."""
        config = Config(working_dir=tmp_path)
        sub = config.for_subagent("sub-1234")

        if "pytools" in sub.mcp_servers and "env" in sub.mcp_servers["pytools"]:
            assert sub.mcp_servers["pytools"]["env"]["PYTOOLS_SYNC"] == "false"
            assert sub.mcp_servers["pytools"]["env"]["PYTOOLS_WATCH"] == "false"

    def test_parent_not_mutated(self, tmp_path: Path, freeact_dir: Path):
        """Parent config is not modified by for_subagent()."""
        config = Config(working_dir=tmp_path)
        original_agent_id = config.agent_id
        original_enable_subagents = config.enable_subagents

        config.for_subagent("sub-1234")

        assert config.agent_id == original_agent_id
        assert config.enable_subagents == original_enable_subagents

    def test_shares_model_and_system_prompt(self, tmp_path: Path, freeact_dir: Path):
        """Subagent shares model and system_prompt with parent."""
        config = Config(working_dir=tmp_path)
        sub = config.for_subagent("sub-1234")

        assert sub.model is config.model
        assert sub.system_prompt is config.system_prompt


class TestNewConfigFields:
    """Tests for new config.json fields with defaults."""

    def test_default_agent_id(self, tmp_path: Path, freeact_dir: Path):
        """Default agent-id is 'main'."""
        config = Config(working_dir=tmp_path)
        assert config.agent_id == "main"

    def test_custom_agent_id(self, tmp_path: Path, freeact_dir: Path):
        """Custom agent-id from config.json."""
        (freeact_dir / "config.json").write_text(json.dumps({"agent-id": "custom"}))
        config = Config(working_dir=tmp_path)
        assert config.agent_id == "custom"

    def test_default_images_dir(self, tmp_path: Path, freeact_dir: Path):
        """Default images-dir is None."""
        config = Config(working_dir=tmp_path)
        assert config.images_dir is None

    def test_custom_images_dir(self, tmp_path: Path, freeact_dir: Path):
        """Custom images-dir from config.json."""
        (freeact_dir / "config.json").write_text(json.dumps({"images-dir": "/tmp/images"}))
        config = Config(working_dir=tmp_path)
        assert config.images_dir == Path("/tmp/images")

    def test_default_execution_timeout(self, tmp_path: Path, freeact_dir: Path):
        """Default execution-timeout is 300."""
        config = Config(working_dir=tmp_path)
        assert config.execution_timeout == 300

    def test_custom_execution_timeout(self, tmp_path: Path, freeact_dir: Path):
        """Custom execution-timeout from config.json."""
        (freeact_dir / "config.json").write_text(json.dumps({"execution-timeout": 60}))
        config = Config(working_dir=tmp_path)
        assert config.execution_timeout == 60

    def test_null_execution_timeout(self, tmp_path: Path, freeact_dir: Path):
        """Null execution-timeout from config.json."""
        (freeact_dir / "config.json").write_text(json.dumps({"execution-timeout": None}))
        config = Config(working_dir=tmp_path)
        assert config.execution_timeout is None

    def test_default_approval_timeout(self, tmp_path: Path, freeact_dir: Path):
        """Default approval-timeout is None."""
        config = Config(working_dir=tmp_path)
        assert config.approval_timeout is None

    def test_custom_approval_timeout(self, tmp_path: Path, freeact_dir: Path):
        """Custom approval-timeout from config.json."""
        (freeact_dir / "config.json").write_text(json.dumps({"approval-timeout": 30}))
        config = Config(working_dir=tmp_path)
        assert config.approval_timeout == 30

    def test_default_enable_subagents(self, tmp_path: Path, freeact_dir: Path):
        """Default enable-subagents is True."""
        config = Config(working_dir=tmp_path)
        assert config.enable_subagents is True

    def test_custom_enable_subagents(self, tmp_path: Path, freeact_dir: Path):
        """Custom enable-subagents from config.json."""
        (freeact_dir / "config.json").write_text(json.dumps({"enable-subagents": False}))
        config = Config(working_dir=tmp_path)
        assert config.enable_subagents is False

    def test_default_max_subagents(self, tmp_path: Path, freeact_dir: Path):
        """Default max-subagents is 5."""
        config = Config(working_dir=tmp_path)
        assert config.max_subagents == 5

    def test_custom_max_subagents(self, tmp_path: Path, freeact_dir: Path):
        """Custom max-subagents from config.json."""
        (freeact_dir / "config.json").write_text(json.dumps({"max-subagents": 10}))
        config = Config(working_dir=tmp_path)
        assert config.max_subagents == 10


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
        assert config.generated_dir == freeact_dir / "generated"
        assert config.search_db_file == freeact_dir / "search.db"
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
