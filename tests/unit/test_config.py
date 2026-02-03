"""Tests for freeact/agent/config/config.py."""

import json
from pathlib import Path

import pytest

from freeact.agent.config.config import Config


@pytest.fixture
def freeact_dir(tmp_path: Path) -> Path:
    """Create minimal .freeact directory structure."""
    freeact_dir = tmp_path / ".freeact"
    freeact_dir.mkdir()
    prompts_dir = freeact_dir / "prompts"
    prompts_dir.mkdir()
    # Create both prompt files for compatibility
    (prompts_dir / "system-basic.md").write_text("{working_dir} {skills}")
    (prompts_dir / "system-hybrid.md").write_text("{working_dir} {skills}")
    (freeact_dir / "servers.json").write_text(json.dumps({}))
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
        # Update system prompt template to include skills placeholder
        (freeact_dir / "prompts" / "system.md").write_text("Skills:\n{skills}")

        # Create two skills
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
        (freeact_dir / "prompts" / "system.md").write_text("{skills}")

        config = Config(working_dir=tmp_path)

        assert "No skills available." in config.system_prompt


class TestLoadSystemPrompt:
    """Tests for system prompt loading."""

    def test_loads_and_renders_placeholders(self, tmp_path: Path, freeact_dir: Path):
        """Substitutes {working_dir} and {skills} in system.md."""
        (freeact_dir / "prompts" / "system.md").write_text("Working dir: {working_dir}\nSkills: {skills}")

        config = Config(working_dir=tmp_path)

        assert str(tmp_path) in config.system_prompt
        assert "No skills available." in config.system_prompt


class TestSystemPromptSelection:
    """Tests for system prompt file selection based on pytools mode."""

    def test_loads_basic_prompt_for_basic_pytools(self, tmp_path: Path, freeact_dir: Path):
        """Loads system-basic.md when pytools uses basic search module."""
        (freeact_dir / "prompts" / "system-basic.md").write_text("basic: {working_dir} {skills}")
        (freeact_dir / "prompts" / "system-hybrid.md").write_text("hybrid: {working_dir} {skills}")
        (freeact_dir / "servers.json").write_text(
            json.dumps(
                {
                    "mcp-servers": {
                        "pytools": {"command": "python", "args": ["-m", "freeact.agent.tools.pytools.search.basic"]}
                    }
                }
            )
        )

        config = Config(working_dir=tmp_path)

        assert config.system_prompt.startswith("basic:")

    def test_loads_hybrid_prompt_for_hybrid_pytools(self, tmp_path: Path, freeact_dir: Path):
        """Loads system-hybrid.md when pytools uses hybrid search module."""
        (freeact_dir / "prompts" / "system-basic.md").write_text("basic: {working_dir} {skills}")
        (freeact_dir / "prompts" / "system-hybrid.md").write_text("hybrid: {working_dir} {skills}")
        (freeact_dir / "servers.json").write_text(
            json.dumps(
                {
                    "mcp-servers": {
                        "pytools": {"command": "python", "args": ["-m", "freeact.agent.tools.pytools.search.hybrid"]}
                    }
                }
            )
        )

        config = Config(working_dir=tmp_path)

        assert config.system_prompt.startswith("hybrid:")

    def test_loads_basic_prompt_when_no_pytools_server(self, tmp_path: Path, freeact_dir: Path):
        """Loads system-basic.md when pytools server is not configured."""
        (freeact_dir / "prompts" / "system-basic.md").write_text("basic: {working_dir} {skills}")
        (freeact_dir / "prompts" / "system-hybrid.md").write_text("hybrid: {working_dir} {skills}")
        (freeact_dir / "servers.json").write_text(
            json.dumps({"mcp-servers": {"filesystem": {"command": "npx", "args": []}}})
        )

        config = Config(working_dir=tmp_path)

        assert config.system_prompt.startswith("basic:")


class TestLoadServersJson:
    """Tests for servers.json loading."""

    def test_loads_servers_config(self, tmp_path: Path, freeact_dir: Path):
        """Loads and parses servers.json file."""
        (freeact_dir / "servers.json").write_text(
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

    def test_handles_missing_servers_json(self, tmp_path: Path, freeact_dir: Path):
        """Handles missing servers.json gracefully."""
        (freeact_dir / "servers.json").unlink()

        config = Config(working_dir=tmp_path)

        assert config.mcp_servers == {}
        assert config.ptc_servers == {}


class TestLoadMcpServers:
    """Tests for MCP server loading."""

    def test_creates_stdio_server_from_command(self, tmp_path: Path, freeact_dir: Path):
        """Creates MCPServerStdio from command-based config."""
        from pydantic_ai.mcp import MCPServerStdio

        (freeact_dir / "servers.json").write_text(
            json.dumps({"mcp-servers": {"test-server": {"command": "python", "args": ["-m", "test"]}}})
        )

        config = Config(working_dir=tmp_path)

        assert "test-server" in config.mcp_servers
        assert isinstance(config.mcp_servers["test-server"], MCPServerStdio)

    def test_creates_http_server_from_url(self, tmp_path: Path, freeact_dir: Path):
        """Creates MCPServerStreamableHTTP from url-based config."""
        from pydantic_ai.mcp import MCPServerStreamableHTTP

        (freeact_dir / "servers.json").write_text(
            json.dumps({"mcp-servers": {"http-server": {"url": "http://localhost:8080"}}})
        )

        config = Config(working_dir=tmp_path)

        assert "http-server" in config.mcp_servers
        assert isinstance(config.mcp_servers["http-server"], MCPServerStreamableHTTP)

    def test_raises_on_missing_env_variables(self, tmp_path: Path, freeact_dir: Path, monkeypatch: pytest.MonkeyPatch):
        """Raises ValueError when ${VAR} references missing env var."""
        (freeact_dir / "servers.json").write_text(
            json.dumps(
                {"mcp-servers": {"test-server": {"command": "python", "env": {"API_KEY": "${MISSING_ENV_VAR}"}}}}
            )
        )
        monkeypatch.delenv("MISSING_ENV_VAR", raising=False)

        with pytest.raises(ValueError, match="Missing environment variables"):
            Config(working_dir=tmp_path)

    def test_raises_on_invalid_config(self, tmp_path: Path, freeact_dir: Path):
        """Raises ValueError for config without command or url."""
        (freeact_dir / "servers.json").write_text(
            json.dumps({"mcp-servers": {"invalid-server": {"invalid_key": "value"}}})
        )

        with pytest.raises(ValueError, match="must have 'command' or 'url'"):
            Config(working_dir=tmp_path)

    def test_returns_empty_when_no_mcp_servers(self, tmp_path: Path, freeact_dir: Path):
        """Returns empty dict when mcp-servers section is missing."""
        (freeact_dir / "servers.json").write_text(json.dumps({"ptc-servers": {}}))

        config = Config(working_dir=tmp_path)

        assert config.mcp_servers == {}


class TestLoadPtcServers:
    """Tests for PTC server loading."""

    def test_loads_ptc_config(self, tmp_path: Path, freeact_dir: Path, monkeypatch: pytest.MonkeyPatch):
        """Loads PTC server configurations."""
        monkeypatch.setenv("TEST_API_KEY", "test-key-value")
        (freeact_dir / "servers.json").write_text(
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
        (freeact_dir / "servers.json").write_text(
            json.dumps({"ptc-servers": {"test": {"command": "python", "env": {"API_KEY": "${MISSING_PTC_ENV_VAR}"}}}})
        )
        monkeypatch.delenv("MISSING_PTC_ENV_VAR", raising=False)

        with pytest.raises(ValueError, match="Missing environment variables"):
            Config(working_dir=tmp_path)

    def test_returns_empty_when_no_ptc_servers(self, tmp_path: Path, freeact_dir: Path):
        """Returns empty dict when ptc-servers section is missing."""
        (freeact_dir / "servers.json").write_text(json.dumps({"mcp-servers": {}}))

        config = Config(working_dir=tmp_path)

        assert config.ptc_servers == {}


class TestConfigInit:
    """Tests for full Config initialization."""

    def test_full_initialization(self, tmp_path: Path, freeact_dir: Path, monkeypatch: pytest.MonkeyPatch):
        """Full Config initialization with all components."""
        monkeypatch.setenv("TEST_API_KEY", "test-value")

        (freeact_dir / "prompts" / "system.md").write_text("Dir: {working_dir}\nSkills: {skills}")
        (freeact_dir / "servers.json").write_text(
            json.dumps(
                {
                    "mcp-servers": {"test": {"command": "echo", "args": ["hello"]}},
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
        assert "test" in config.mcp_servers
        assert "ptc" in config.ptc_servers

    def test_uses_cwd_when_working_dir_is_none(
        self, tmp_path: Path, freeact_dir: Path, monkeypatch: pytest.MonkeyPatch
    ):
        """Uses current working directory when working_dir is None."""
        monkeypatch.chdir(tmp_path)

        config = Config()

        assert config.working_dir == tmp_path
