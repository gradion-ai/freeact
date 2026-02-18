"""Tests for freeact/agent/config/config.py."""

import json
import os
from pathlib import Path

import pytest
from pydantic_ai.models import Model

from freeact.agent.config.config import (
    Config,
    _ConfigPaths,
)


@pytest.fixture
def freeact_dir(tmp_path: Path) -> Path:
    """Create minimal .freeact directory structure."""
    freeact_dir = _ConfigPaths(tmp_path).freeact_dir
    freeact_dir.mkdir()
    (freeact_dir / "agent.json").write_text(json.dumps({"model": "test"}))
    return freeact_dir


class TestParseSkillFile:
    """Tests for skill file parsing via Config initialization."""

    def test_parses_valid_yaml_frontmatter(self, tmp_path: Path, freeact_dir: Path):
        """Parses name and description from YAML frontmatter."""
        skill_dir = _ConfigPaths(tmp_path).skills_dir / "test-skill"
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
        skill_dir = _ConfigPaths(tmp_path).skills_dir / "invalid-skill"
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
        skill_dir = _ConfigPaths(tmp_path).skills_dir / "incomplete-skill"
        skill_dir.mkdir(parents=True)
        (skill_dir / "SKILL.md").write_text("---\nname: test-skill\ndescription: No closing delimiter")

        config = Config(working_dir=tmp_path)

        assert len(config.skills_metadata) == 0


class TestRenderSkillsSection:
    """Tests for skills section rendering in system prompt."""

    def test_renders_skills_in_system_prompt(self, tmp_path: Path, freeact_dir: Path):
        """Renders skill metadata as markdown in system prompt."""
        for name, desc in [("skill-one", "First description"), ("skill-two", "Second description")]:
            skill_dir = _ConfigPaths(tmp_path).skills_dir / name
            skill_dir.mkdir(parents=True)
            (skill_dir / "SKILL.md").write_text(f"---\nname: {name}\ndescription: {desc}\n---\nContent.")

        config = Config(working_dir=tmp_path)

        assert "**skill-one**" in config.system_prompt
        assert "First description" in config.system_prompt
        assert "**skill-two**" in config.system_prompt
        assert "Second description" in config.system_prompt

    def test_omits_skills_section_when_empty(self, tmp_path: Path, freeact_dir: Path):
        """Omits skills section entirely when no skills exist."""
        config = Config(working_dir=tmp_path)

        assert "## Skills" not in config.system_prompt

    def test_loads_skills_from_agents_dir(self, tmp_path: Path, freeact_dir: Path):
        """Loads skills from .agents/skills/ directory."""
        skill_dir = _ConfigPaths(tmp_path).project_skills_dir / "agent-skill"
        skill_dir.mkdir(parents=True)
        (skill_dir / "SKILL.md").write_text("---\nname: agent-skill\ndescription: From agents dir\n---\nContent.")

        config = Config(working_dir=tmp_path)

        assert len(config.skills_metadata) == 1
        assert config.skills_metadata[0].name == "agent-skill"

    def test_freeact_skills_rendered_before_agents_skills(self, tmp_path: Path, freeact_dir: Path):
        """Skills from .freeact/ appear before skills from .agents/ in metadata and prompt."""
        paths = _ConfigPaths(tmp_path)

        freeact_skill = paths.skills_dir / "freeact-skill"
        freeact_skill.mkdir(parents=True)
        (freeact_skill / "SKILL.md").write_text("---\nname: freeact-skill\ndescription: From freeact\n---\nContent.")

        agents_skill = paths.project_skills_dir / "agents-skill"
        agents_skill.mkdir(parents=True)
        (agents_skill / "SKILL.md").write_text("---\nname: agents-skill\ndescription: From agents\n---\nContent.")

        config = Config(working_dir=tmp_path)

        assert len(config.skills_metadata) == 2
        assert config.skills_metadata[0].name == "freeact-skill"
        assert config.skills_metadata[1].name == "agents-skill"
        freeact_pos = config.system_prompt.index("**freeact-skill**")
        agents_pos = config.system_prompt.index("**agents-skill**")
        assert freeact_pos < agents_pos


class TestProjectInstructions:
    """Tests for project instructions rendering from AGENTS.md."""

    def test_renders_agents_md_in_system_prompt(self, tmp_path: Path, freeact_dir: Path):
        """Renders project instructions content inside project-instructions tags."""
        _ConfigPaths(tmp_path).project_instructions_file.write_text("Use pytest for testing.\nPrefer dataclasses.")

        config = Config(working_dir=tmp_path)

        assert "## Project Instructions" in config.system_prompt
        assert "<project-instructions>" in config.system_prompt
        assert "Use pytest for testing." in config.system_prompt
        assert "Prefer dataclasses." in config.system_prompt

    def test_omits_section_when_no_agents_md(self, tmp_path: Path, freeact_dir: Path):
        """Omits project instructions section when file does not exist."""
        config = Config(working_dir=tmp_path)

        assert "## Project Instructions" not in config.system_prompt
        assert "<project-instructions>" not in config.system_prompt

    def test_omits_section_when_agents_md_empty(self, tmp_path: Path, freeact_dir: Path):
        """Omits project instructions section when file is empty."""
        _ConfigPaths(tmp_path).project_instructions_file.write_text("")

        config = Config(working_dir=tmp_path)

        assert "## Project Instructions" not in config.system_prompt

    def test_omits_section_when_agents_md_whitespace_only(self, tmp_path: Path, freeact_dir: Path):
        """Omits project instructions section when file contains only whitespace."""
        _ConfigPaths(tmp_path).project_instructions_file.write_text("  \n\n  ")

        config = Config(working_dir=tmp_path)

        assert "## Project Instructions" not in config.system_prompt


class TestLoadSystemPrompt:
    """Tests for system prompt loading from package resources."""

    def test_loads_and_renders_placeholders(self, tmp_path: Path, freeact_dir: Path):
        """Substitutes {working_dir} in system prompt."""
        config = Config(working_dir=tmp_path)

        assert str(tmp_path) in config.system_prompt


class TestSystemPromptSelection:
    """Tests for system prompt file selection based on tool-search config."""

    def test_loads_basic_prompt_by_default(self, tmp_path: Path, freeact_dir: Path):
        """Loads basic system prompt when tool-search is not set."""
        config = Config(working_dir=tmp_path)

        assert "pytools_list_categories" in config.system_prompt

    def test_loads_basic_prompt_for_basic_tool_search(self, tmp_path: Path, freeact_dir: Path):
        """Loads basic system prompt when tool-search is 'basic'."""
        (freeact_dir / "agent.json").write_text(json.dumps({"model": "test", "tool-search": "basic"}))

        config = Config(working_dir=tmp_path)

        assert "pytools_list_categories" in config.system_prompt

    def test_loads_hybrid_prompt_for_hybrid_tool_search(
        self, tmp_path: Path, freeact_dir: Path, monkeypatch: pytest.MonkeyPatch
    ):
        """Loads hybrid system prompt when tool-search is 'hybrid'."""
        monkeypatch.setenv("GEMINI_API_KEY", "test-key")
        (freeact_dir / "agent.json").write_text(json.dumps({"model": "test", "tool-search": "hybrid"}))

        config = Config(working_dir=tmp_path)

        assert "pytools_search_tools" in config.system_prompt


class TestToolSearchConfig:
    """Tests for tool-search setting from agent.json."""

    def test_defaults_to_basic(self, tmp_path: Path, freeact_dir: Path):
        """Defaults to 'basic' when tool-search is not in agent.json."""
        config = Config(working_dir=tmp_path)

        assert config.tool_search == "basic"

    def test_reads_from_config_json(self, tmp_path: Path, freeact_dir: Path, monkeypatch: pytest.MonkeyPatch):
        """Reads tool-search value from agent.json."""
        monkeypatch.setenv("GEMINI_API_KEY", "test-key")
        (freeact_dir / "agent.json").write_text(json.dumps({"model": "test", "tool-search": "hybrid"}))

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
        (freeact_dir / "agent.json").write_text('{"model": "test", "tool-search": "hybrid"}')

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
    """Tests for agent.json loading."""

    def test_loads_config(self, tmp_path: Path, freeact_dir: Path):
        """Loads and parses agent.json file."""
        (freeact_dir / "agent.json").write_text(
            json.dumps(
                {
                    "model": "test",
                    "mcp-servers": {"test": {"command": "echo", "args": []}},
                    "ptc-servers": {"ptc-test": {"command": "python"}},
                }
            )
        )

        config = Config(working_dir=tmp_path)

        assert "test" in config.mcp_servers
        assert "ptc-test" in config.ptc_servers

    def test_handles_missing_config_json(self, tmp_path: Path, freeact_dir: Path):
        """Raises `ValueError` when agent.json is missing (model required)."""
        (freeact_dir / "agent.json").unlink()

        with pytest.raises(ValueError, match="'model' is required"):
            Config(working_dir=tmp_path)


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
        (freeact_dir / "agent.json").write_text(json.dumps({"model": "test", "tool-search": "hybrid"}))

        config = Config(working_dir=tmp_path)

        # Resolved, so env values should be present instead of placeholders
        assert "pytools" in config.mcp_servers
        assert "${GEMINI_API_KEY}" not in str(config.mcp_servers["pytools"])

    def test_user_pytools_overrides_internal(self, tmp_path: Path, freeact_dir: Path):
        """User pytools config in agent.json overrides internal default."""
        user_pytools = {"command": "custom-pytools", "args": ["--custom"]}
        (freeact_dir / "agent.json").write_text(json.dumps({"model": "test", "mcp-servers": {"pytools": user_pytools}}))

        config = Config(working_dir=tmp_path)

        assert config.mcp_servers["pytools"] == user_pytools

    def test_user_filesystem_overrides_internal(self, tmp_path: Path, freeact_dir: Path):
        """User filesystem config in agent.json overrides internal default."""
        user_filesystem = {"command": "custom-fs", "args": ["--verbose"]}
        (freeact_dir / "agent.json").write_text(
            json.dumps({"model": "test", "mcp-servers": {"filesystem": user_filesystem}})
        )

        config = Config(working_dir=tmp_path)

        assert config.mcp_servers["filesystem"] == user_filesystem

    def test_user_adds_custom_server(self, tmp_path: Path, freeact_dir: Path):
        """User can add custom MCP servers alongside internal ones."""
        custom = {"command": "my-server"}
        (freeact_dir / "agent.json").write_text(json.dumps({"model": "test", "mcp-servers": {"custom": custom}}))

        config = Config(working_dir=tmp_path)

        assert "pytools" in config.mcp_servers
        assert "filesystem" in config.mcp_servers
        assert config.mcp_servers["custom"] == custom

    def test_empty_mcp_servers_uses_internal_defaults(self, tmp_path: Path, freeact_dir: Path):
        """Empty mcp-servers section uses internal defaults only."""
        (freeact_dir / "agent.json").write_text(json.dumps({"model": "test", "mcp-servers": {}}))

        config = Config(working_dir=tmp_path)

        assert "pytools" in config.mcp_servers
        assert "filesystem" in config.mcp_servers

    def test_raises_on_missing_env_variables(self, tmp_path: Path, freeact_dir: Path, monkeypatch: pytest.MonkeyPatch):
        """Raises ValueError when ${VAR} references missing env var."""
        (freeact_dir / "agent.json").write_text(
            json.dumps(
                {
                    "model": "test",
                    "mcp-servers": {"test-server": {"command": "python", "env": {"API_KEY": "${MISSING_ENV_VAR}"}}},
                }
            )
        )
        monkeypatch.delenv("MISSING_ENV_VAR", raising=False)

        with pytest.raises(ValueError, match="Missing environment variables"):
            Config(working_dir=tmp_path)

    def test_mcp_servers_are_resolved(self, tmp_path: Path, freeact_dir: Path, monkeypatch: pytest.MonkeyPatch):
        """MCP server ${VAR} placeholders are resolved in stored config."""
        monkeypatch.setenv("MY_API_KEY", "resolved-key")
        (freeact_dir / "agent.json").write_text(
            json.dumps(
                {"model": "test", "mcp-servers": {"test": {"command": "python", "env": {"API_KEY": "${MY_API_KEY}"}}}}
            )
        )

        config = Config(working_dir=tmp_path)

        assert config.mcp_servers["test"]["env"]["API_KEY"] == "resolved-key"


class TestLoadPtcServers:
    """Tests for PTC server loading."""

    def test_loads_ptc_config(self, tmp_path: Path, freeact_dir: Path, monkeypatch: pytest.MonkeyPatch):
        """Loads PTC server configurations."""
        monkeypatch.setenv("TEST_API_KEY", "test-key-value")
        (freeact_dir / "agent.json").write_text(
            json.dumps(
                {
                    "model": "test",
                    "ptc-servers": {
                        "google": {"command": "python", "args": ["-m", "test"], "env": {"API_KEY": "${TEST_API_KEY}"}}
                    },
                }
            )
        )

        config = Config(working_dir=tmp_path)

        assert "google" in config.ptc_servers
        # Config is returned with original placeholders (not replaced)
        assert config.ptc_servers["google"]["env"]["API_KEY"] == "${TEST_API_KEY}"

    def test_raises_on_missing_env_variables(self, tmp_path: Path, freeact_dir: Path, monkeypatch: pytest.MonkeyPatch):
        """Raises ValueError when env variables are missing."""
        (freeact_dir / "agent.json").write_text(
            json.dumps(
                {
                    "model": "test",
                    "ptc-servers": {"test": {"command": "python", "env": {"API_KEY": "${MISSING_PTC_ENV_VAR}"}}},
                }
            )
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
        """User values in agent.json override auto-defaults."""
        monkeypatch.setenv("HOME", "/home/testuser")
        (freeact_dir / "agent.json").write_text(
            json.dumps({"model": "test", "kernel-env": {"PYTHONPATH": "/custom/path", "HOME": "/custom/home"}})
        )

        config = Config(working_dir=tmp_path)

        assert config.kernel_env["PYTHONPATH"] == "/custom/path"
        assert config.kernel_env["HOME"] == "/custom/home"

    def test_resolves_placeholders(self, tmp_path: Path, freeact_dir: Path, monkeypatch: pytest.MonkeyPatch):
        """${VAR} placeholders are resolved in kernel_env."""
        monkeypatch.setenv("MY_CUSTOM_VAR", "resolved-value")
        (freeact_dir / "agent.json").write_text(
            json.dumps({"model": "test", "kernel-env": {"CUSTOM": "${MY_CUSTOM_VAR}"}})
        )

        config = Config(working_dir=tmp_path)

        assert config.kernel_env["CUSTOM"] == "resolved-value"

    def test_raises_on_missing_env_variables(self, tmp_path: Path, freeact_dir: Path, monkeypatch: pytest.MonkeyPatch):
        """Raises ValueError when ${VAR} references missing env var."""
        (freeact_dir / "agent.json").write_text(
            json.dumps({"model": "test", "kernel-env": {"KEY": "${MISSING_KERNEL_ENV_VAR}"}})
        )
        monkeypatch.delenv("MISSING_KERNEL_ENV_VAR", raising=False)

        with pytest.raises(ValueError, match="Missing environment variables for kernel-env"):
            Config(working_dir=tmp_path)

    def test_empty_kernel_env_uses_defaults(self, tmp_path: Path, freeact_dir: Path):
        """Empty kernel-env in agent.json still gets auto-defaults."""
        (freeact_dir / "agent.json").write_text(json.dumps({"model": "test", "kernel-env": {}}))

        config = Config(working_dir=tmp_path)

        assert "PYTHONPATH" in config.kernel_env


class TestForSubagent:
    """Tests for Config.for_subagent() method."""

    def test_disables_subagents(self, tmp_path: Path, freeact_dir: Path):
        """Subagent config has enable_subagents=False."""
        config = Config(working_dir=tmp_path)
        sub = config.for_subagent()

        assert sub.enable_subagents is False

    def test_kernel_env_is_independent(self, tmp_path: Path, freeact_dir: Path):
        """Subagent kernel_env is a separate dict."""
        config = Config(working_dir=tmp_path)
        sub = config.for_subagent()

        assert sub.kernel_env is not config.kernel_env
        assert sub.kernel_env == config.kernel_env

    def test_mcp_servers_have_sync_watch_disabled(self, tmp_path: Path, freeact_dir: Path):
        """Subagent mcp_servers have pytools sync/watch disabled."""
        config = Config(working_dir=tmp_path)
        sub = config.for_subagent()

        if "pytools" in sub.mcp_servers and "env" in sub.mcp_servers["pytools"]:
            assert sub.mcp_servers["pytools"]["env"]["PYTOOLS_SYNC"] == "false"
            assert sub.mcp_servers["pytools"]["env"]["PYTOOLS_WATCH"] == "false"

    def test_parent_not_mutated(self, tmp_path: Path, freeact_dir: Path):
        """Parent config is not modified by for_subagent()."""
        config = Config(working_dir=tmp_path)
        original_enable_subagents = config.enable_subagents

        config.for_subagent()

        assert config.enable_subagents == original_enable_subagents

    def test_shares_model_and_system_prompt(self, tmp_path: Path, freeact_dir: Path):
        """Subagent shares model and system_prompt with parent."""
        config = Config(working_dir=tmp_path)
        sub = config.for_subagent()

        assert sub.model is config.model
        assert sub.system_prompt is config.system_prompt


class TestNewConfigFields:
    """Tests for new agent.json fields with defaults."""

    def test_default_images_dir(self, tmp_path: Path, freeact_dir: Path):
        """Default images-dir is None."""
        config = Config(working_dir=tmp_path)
        assert config.images_dir is None

    def test_custom_images_dir(self, tmp_path: Path, freeact_dir: Path):
        """Custom images-dir from agent.json."""
        (freeact_dir / "agent.json").write_text(json.dumps({"model": "test", "images-dir": "/tmp/images"}))
        config = Config(working_dir=tmp_path)
        assert config.images_dir == Path("/tmp/images")

    def test_default_execution_timeout(self, tmp_path: Path, freeact_dir: Path):
        """Default execution-timeout is 300."""
        config = Config(working_dir=tmp_path)
        assert config.execution_timeout == 300

    def test_custom_execution_timeout(self, tmp_path: Path, freeact_dir: Path):
        """Custom execution-timeout from agent.json."""
        (freeact_dir / "agent.json").write_text(json.dumps({"model": "test", "execution-timeout": 60}))
        config = Config(working_dir=tmp_path)
        assert config.execution_timeout == 60

    def test_null_execution_timeout(self, tmp_path: Path, freeact_dir: Path):
        """Null execution-timeout from agent.json."""
        (freeact_dir / "agent.json").write_text(json.dumps({"model": "test", "execution-timeout": None}))
        config = Config(working_dir=tmp_path)
        assert config.execution_timeout is None

    def test_default_approval_timeout(self, tmp_path: Path, freeact_dir: Path):
        """Default approval-timeout is None."""
        config = Config(working_dir=tmp_path)
        assert config.approval_timeout is None

    def test_custom_approval_timeout(self, tmp_path: Path, freeact_dir: Path):
        """Custom approval-timeout from agent.json."""
        (freeact_dir / "agent.json").write_text(json.dumps({"model": "test", "approval-timeout": 30}))
        config = Config(working_dir=tmp_path)
        assert config.approval_timeout == 30

    def test_default_enable_subagents(self, tmp_path: Path, freeact_dir: Path):
        """Default enable-subagents is True."""
        config = Config(working_dir=tmp_path)
        assert config.enable_subagents is True

    def test_custom_enable_subagents(self, tmp_path: Path, freeact_dir: Path):
        """Custom enable-subagents from agent.json."""
        (freeact_dir / "agent.json").write_text(json.dumps({"model": "test", "enable-subagents": False}))
        config = Config(working_dir=tmp_path)
        assert config.enable_subagents is False

    def test_default_max_subagents(self, tmp_path: Path, freeact_dir: Path):
        """Default max-subagents is 5."""
        config = Config(working_dir=tmp_path)
        assert config.max_subagents == 5

    def test_custom_max_subagents(self, tmp_path: Path, freeact_dir: Path):
        """Custom max-subagents from agent.json."""
        (freeact_dir / "agent.json").write_text(json.dumps({"model": "test", "max-subagents": 10}))
        config = Config(working_dir=tmp_path)
        assert config.max_subagents == 10


class TestConfigInit:
    """Tests for full Config initialization."""

    def test_full_initialization(self, tmp_path: Path, freeact_dir: Path, monkeypatch: pytest.MonkeyPatch):
        """Full Config initialization with all components."""
        monkeypatch.setenv("TEST_API_KEY", "test-value")

        (freeact_dir / "agent.json").write_text(
            json.dumps(
                {
                    "model": "test",
                    "ptc-servers": {"ptc": {"command": "python", "env": {"KEY": "${TEST_API_KEY}"}}},
                }
            )
        )

        paths = _ConfigPaths(tmp_path)
        skill_dir = paths.skills_dir / "test-skill"
        skill_dir.mkdir(parents=True)
        (skill_dir / "SKILL.md").write_text("---\nname: test-skill\ndescription: Test skill\n---\nContent.")

        paths.plans_dir.mkdir()

        config = Config(working_dir=tmp_path)

        assert config.working_dir == tmp_path
        assert config.freeact_dir == freeact_dir
        assert config.plans_dir == paths.plans_dir
        assert config.generated_dir == paths.generated_dir
        assert config._config_paths.generated_rel_dir == config.generated_dir.relative_to(config.working_dir)
        assert config.sessions_dir == paths.sessions_dir
        assert config.search_db_file == paths.search_db_file
        assert len(config.skills_metadata) == 1
        assert config.skills_metadata[0].name == "test-skill"
        assert str(tmp_path) in config.system_prompt
        assert "pytools" in config.mcp_servers
        assert "filesystem" in config.mcp_servers
        assert "ptc" in config.ptc_servers

    def test_sessions_dir_property(self, tmp_path: Path, freeact_dir: Path):
        """Sessions directory path is under .freeact/sessions."""
        config = Config(working_dir=tmp_path)

        assert config.sessions_dir == _ConfigPaths(tmp_path).sessions_dir

    def test_uses_cwd_when_working_dir_is_none(
        self, tmp_path: Path, freeact_dir: Path, monkeypatch: pytest.MonkeyPatch
    ):
        """Uses current working directory when working_dir is None."""
        monkeypatch.chdir(tmp_path)

        config = Config()

        assert config.working_dir == tmp_path


class TestLoadModelConfig:
    """Tests for model configuration loading from agent.json."""

    def test_reads_model_from_config_json(self, tmp_path: Path, freeact_dir: Path):
        """Model string loaded from agent.json."""
        (freeact_dir / "agent.json").write_text(json.dumps({"model": "test"}))

        config = Config(working_dir=tmp_path)

        assert config.model == "test"

    def test_raises_when_model_missing(self, tmp_path: Path, freeact_dir: Path):
        """`ValueError` when `model` key absent."""
        (freeact_dir / "agent.json").write_text(json.dumps({}))

        with pytest.raises(ValueError, match="'model' is required in agent.json"):
            Config(working_dir=tmp_path)

    def test_model_settings_from_config_json(self, tmp_path: Path, freeact_dir: Path):
        """Reads settings dict from agent.json."""
        settings = {"temperature": 0.7, "max_tokens": 1024}
        (freeact_dir / "agent.json").write_text(json.dumps({"model": "test", "model-settings": settings}))

        config = Config(working_dir=tmp_path)

        assert config.model_settings == settings

    def test_null_model_settings_uses_empty(self, tmp_path: Path, freeact_dir: Path):
        """`model-settings: null` results in empty dict."""
        (freeact_dir / "agent.json").write_text(json.dumps({"model": "test", "model-settings": None}))

        config = Config(working_dir=tmp_path)

        assert config.model_settings == {}

    def test_missing_model_settings_uses_empty(self, tmp_path: Path, freeact_dir: Path):
        """Omitting `model-settings` results in empty dict."""
        (freeact_dir / "agent.json").write_text(json.dumps({"model": "test"}))

        config = Config(working_dir=tmp_path)

        assert config.model_settings == {}

    def test_model_provider_builds_model_instance(
        self, tmp_path: Path, freeact_dir: Path, monkeypatch: pytest.MonkeyPatch
    ):
        """Provider config constructs a `Model` instance (not a string)."""
        monkeypatch.setenv("TEST_API_KEY", "test-key-value")
        (freeact_dir / "agent.json").write_text(
            json.dumps(
                {
                    "model": "openai:gpt-4o",
                    "model-provider": {"api_key": "${TEST_API_KEY}"},
                }
            )
        )

        config = Config(working_dir=tmp_path)

        assert isinstance(config.model, Model)

    def test_model_provider_resolves_env_vars(self, tmp_path: Path, freeact_dir: Path, monkeypatch: pytest.MonkeyPatch):
        """`${VAR}` in provider config resolved from environment."""
        monkeypatch.setenv("MY_KEY", "resolved-key")
        (freeact_dir / "agent.json").write_text(
            json.dumps(
                {
                    "model": "openai:gpt-4o",
                    "model-provider": {"api_key": "${MY_KEY}"},
                }
            )
        )

        config = Config(working_dir=tmp_path)

        assert isinstance(config.model, Model)

    def test_model_provider_missing_env_var_raises(
        self, tmp_path: Path, freeact_dir: Path, monkeypatch: pytest.MonkeyPatch
    ):
        """Missing env var in provider config raises `ValueError`."""
        monkeypatch.delenv("NONEXISTENT_KEY", raising=False)
        (freeact_dir / "agent.json").write_text(
            json.dumps(
                {
                    "model": "openai:gpt-4o",
                    "model-provider": {"api_key": "${NONEXISTENT_KEY}"},
                }
            )
        )

        with pytest.raises(ValueError, match="Missing environment variables for model-provider"):
            Config(working_dir=tmp_path)

    def test_null_model_provider_uses_default(self, tmp_path: Path, freeact_dir: Path):
        """`model-provider: null` returns model as string."""
        (freeact_dir / "agent.json").write_text(json.dumps({"model": "test", "model-provider": None}))

        config = Config(working_dir=tmp_path)

        assert config.model == "test"
        assert isinstance(config.model, str)


class TestModelConfigExamples:
    """Tests with realistic model configurations."""

    def test_google_config(self, tmp_path: Path, freeact_dir: Path):
        """Google model with thinking config settings."""
        (freeact_dir / "agent.json").write_text(
            json.dumps(
                {
                    "model": "google-gla:gemini-3-flash-preview",
                    "model-settings": {
                        "google_thinking_config": {
                            "thinking_level": "high",
                            "include_thoughts": True,
                        }
                    },
                }
            )
        )

        config = Config(working_dir=tmp_path)

        assert config.model == "google-gla:gemini-3-flash-preview"
        assert config.model_settings["google_thinking_config"]["thinking_level"] == "high"

    def test_anthropic_config(self, tmp_path: Path, freeact_dir: Path):
        """Anthropic model with extended thinking settings."""
        (freeact_dir / "agent.json").write_text(
            json.dumps(
                {
                    "model": "anthropic:claude-sonnet-4-5-20250929",
                    "model-settings": {
                        "max_tokens": 16384,
                        "anthropic_thinking": {"type": "enabled", "budget_tokens": 10000},
                    },
                }
            )
        )

        config = Config(working_dir=tmp_path)

        assert config.model == "anthropic:claude-sonnet-4-5-20250929"
        assert config.model_settings["max_tokens"] == 16384
        assert config.model_settings["anthropic_thinking"]["type"] == "enabled"
        assert config.model_settings["anthropic_thinking"]["budget_tokens"] == 10000

    def test_openrouter_config(self, tmp_path: Path, freeact_dir: Path, monkeypatch: pytest.MonkeyPatch):
        """OpenRouter model with provider kwargs."""
        monkeypatch.setenv("OPENROUTER_API_KEY", "test-or-key")
        (freeact_dir / "agent.json").write_text(
            json.dumps(
                {
                    "model": "openrouter:anthropic/claude-sonnet-4-5",
                    "model-settings": {"max_tokens": 8192},
                    "model-provider": {
                        "api_key": "${OPENROUTER_API_KEY}",
                        "app_url": "https://my-app.example.com",
                        "app_title": "freeact",
                    },
                }
            )
        )

        config = Config(working_dir=tmp_path)

        assert isinstance(config.model, Model)
        assert config.model_settings == {"max_tokens": 8192}

    def test_openai_compatible_config(self, tmp_path: Path, freeact_dir: Path, monkeypatch: pytest.MonkeyPatch):
        """OpenAI model with custom base_url and api_key."""
        monkeypatch.setenv("CUSTOM_API_KEY", "test-custom-key")
        (freeact_dir / "agent.json").write_text(
            json.dumps(
                {
                    "model": "openai:my-custom-model",
                    "model-settings": {"temperature": 0.7},
                    "model-provider": {
                        "base_url": "https://my-api.example.com/v1",
                        "api_key": "${CUSTOM_API_KEY}",
                    },
                }
            )
        )

        config = Config(working_dir=tmp_path)

        assert isinstance(config.model, Model)
        assert config.model_settings == {"temperature": 0.7}
