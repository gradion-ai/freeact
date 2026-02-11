"""Tests for Config.init() scaffolding."""

import json
from pathlib import Path

import pytest

from freeact.agent.config import Config
from freeact.agent.config.config import _ConfigPaths


class TestConfigInit:
    """Tests for Config.init() classmethod."""

    @pytest.mark.asyncio
    async def test_creates_freeact_directory(self, tmp_path: Path):
        """Creates .freeact/ directory if it doesn't exist."""
        await Config.init(tmp_path)

        freeact_dir = _ConfigPaths(tmp_path).freeact_dir
        assert freeact_dir.exists()
        assert freeact_dir.is_dir()

    @pytest.mark.asyncio
    async def test_creates_plans_directory(self, tmp_path: Path):
        """Creates .freeact/plans/ directory."""
        await Config.init(tmp_path)

        plans_dir = _ConfigPaths(tmp_path).plans_dir
        assert plans_dir.exists()
        assert plans_dir.is_dir()

    @pytest.mark.asyncio
    async def test_creates_sessions_directory(self, tmp_path: Path):
        """Creates .freeact/sessions/ directory."""
        await Config.init(tmp_path)

        sessions_dir = _ConfigPaths(tmp_path).sessions_dir
        assert sessions_dir.exists()
        assert sessions_dir.is_dir()

    @pytest.mark.asyncio
    async def test_copies_config_json_template(self, tmp_path: Path):
        """Copies config.json with all expected keys."""
        await Config.init(tmp_path)

        config_json = _ConfigPaths(tmp_path).freeact_dir / "config.json"
        assert config_json.exists()

        config = json.loads(config_json.read_text())
        assert "tool-search" in config
        assert config["tool-search"] == "basic"
        assert "agent-id" in config
        assert config["agent-id"] == "main"
        assert "images-dir" in config
        assert config["images-dir"] is None
        assert "execution-timeout" in config
        assert config["execution-timeout"] == 300
        assert "approval-timeout" in config
        assert config["approval-timeout"] is None
        assert "enable-subagents" in config
        assert config["enable-subagents"] is True
        assert "max-subagents" in config
        assert config["max-subagents"] == 5
        assert "kernel-env" in config
        assert config["kernel-env"] == {}
        assert "mcp-servers" in config
        assert config["mcp-servers"] == {}
        assert "ptc-servers" in config

    @pytest.mark.asyncio
    async def test_does_not_copy_system_prompts(self, tmp_path: Path):
        """System prompts are not copied to .freeact/ (they are package resources)."""
        await Config.init(tmp_path)

        prompts_dir = _ConfigPaths(tmp_path).freeact_dir / "prompts"
        assert not prompts_dir.exists()

    @pytest.mark.asyncio
    async def test_copies_skill_templates(self, tmp_path: Path):
        """Copies skill directories from templates."""
        await Config.init(tmp_path)

        skills_dir = _ConfigPaths(tmp_path).skills_dir
        assert skills_dir.exists()

        # Check that at least one skill is copied
        skill_dirs = list(skills_dir.iterdir())
        assert len(skill_dirs) > 0

        # Verify each skill has a SKILL.md file
        for skill_dir in skill_dirs:
            if skill_dir.is_dir():
                skill_file = skill_dir / "SKILL.md"
                assert skill_file.exists(), f"Missing SKILL.md in {skill_dir}"

    @pytest.mark.asyncio
    async def test_preserves_existing_files(self, tmp_path: Path):
        """Does not overwrite existing user files."""
        freeact_dir = _ConfigPaths(tmp_path).freeact_dir
        freeact_dir.mkdir(parents=True)

        # Create existing file with custom content
        existing_content = '{"tool-search": "hybrid"}'
        config_json = freeact_dir / "config.json"
        config_json.write_text(existing_content)

        await Config.init(tmp_path)

        # Verify content was not overwritten
        assert config_json.read_text() == existing_content

    @pytest.mark.asyncio
    async def test_uses_cwd_when_working_dir_is_none(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
        """Uses current working directory when working_dir is None."""
        monkeypatch.chdir(tmp_path)

        await Config.init(None)

        freeact_dir = _ConfigPaths(tmp_path).freeact_dir
        assert freeact_dir.exists()

    @pytest.mark.asyncio
    async def test_renders_skill_placeholders(self, tmp_path: Path):
        """Renders placeholders in skill templates during copy."""
        await Config.init(tmp_path)

        skills_dir = _ConfigPaths(tmp_path).skills_dir
        for skill_file in skills_dir.rglob("SKILL.md"):
            content = skill_file.read_text()
            assert "{generated_rel_dir}" not in content
            assert "{plans_rel_dir}" not in content

    @pytest.mark.asyncio
    async def test_idempotent_multiple_calls(self, tmp_path: Path):
        """Multiple calls do not fail or duplicate content."""
        await Config.init(tmp_path)
        await Config.init(tmp_path)
        await Config.init(tmp_path)

        paths = _ConfigPaths(tmp_path)
        freeact_dir = paths.freeact_dir
        assert freeact_dir.exists()

        # Verify structure is intact after multiple calls
        assert (freeact_dir / "config.json").exists()
        assert paths.plans_dir.exists()
        assert paths.sessions_dir.exists()
