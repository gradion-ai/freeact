"""Tests for Config.init() scaffolding."""

import json
from pathlib import Path

import pytest

from freeact.agent.config import Config


class TestConfigInit:
    """Tests for Config.init() classmethod."""

    @pytest.mark.anyio
    async def test_creates_freeact_directory(self, tmp_path: Path):
        """Creates .freeact/ directory if it doesn't exist."""
        await Config.init(tmp_path)

        freeact_dir = tmp_path / ".freeact"
        assert freeact_dir.exists()
        assert freeact_dir.is_dir()

    @pytest.mark.anyio
    async def test_creates_plans_directory(self, tmp_path: Path):
        """Creates .freeact/plans/ directory."""
        await Config.init(tmp_path)

        plans_dir = tmp_path / ".freeact" / "plans"
        assert plans_dir.exists()
        assert plans_dir.is_dir()

    @pytest.mark.anyio
    async def test_copies_config_json_template(self, tmp_path: Path):
        """Copies config.json with all expected keys."""
        await Config.init(tmp_path)

        config_json = tmp_path / ".freeact" / "config.json"
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

    @pytest.mark.anyio
    async def test_does_not_copy_system_prompts(self, tmp_path: Path):
        """System prompts are not copied to .freeact/ (they are package resources)."""
        await Config.init(tmp_path)

        prompts_dir = tmp_path / ".freeact" / "prompts"
        assert not prompts_dir.exists()

    @pytest.mark.anyio
    async def test_copies_skill_templates(self, tmp_path: Path):
        """Copies skill directories from templates."""
        await Config.init(tmp_path)

        skills_dir = tmp_path / ".freeact" / "skills"
        assert skills_dir.exists()

        # Check that at least one skill is copied
        skill_dirs = list(skills_dir.iterdir())
        assert len(skill_dirs) > 0

        # Verify each skill has a SKILL.md file
        for skill_dir in skill_dirs:
            if skill_dir.is_dir():
                skill_file = skill_dir / "SKILL.md"
                assert skill_file.exists(), f"Missing SKILL.md in {skill_dir}"

    @pytest.mark.anyio
    async def test_preserves_existing_files(self, tmp_path: Path):
        """Does not overwrite existing user files."""
        freeact_dir = tmp_path / ".freeact"
        freeact_dir.mkdir(parents=True)

        # Create existing file with custom content
        existing_content = '{"tool-search": "hybrid"}'
        config_json = freeact_dir / "config.json"
        config_json.write_text(existing_content)

        await Config.init(tmp_path)

        # Verify content was not overwritten
        assert config_json.read_text() == existing_content

    @pytest.mark.anyio
    async def test_uses_cwd_when_working_dir_is_none(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
        """Uses current working directory when working_dir is None."""
        monkeypatch.chdir(tmp_path)

        await Config.init(None)

        freeact_dir = tmp_path / ".freeact"
        assert freeact_dir.exists()

    @pytest.mark.anyio
    async def test_renders_skill_placeholders(self, tmp_path: Path):
        """Renders placeholders in skill templates during copy."""
        await Config.init(tmp_path)

        skills_dir = tmp_path / ".freeact" / "skills"
        for skill_file in skills_dir.rglob("SKILL.md"):
            content = skill_file.read_text()
            assert "{generated_rel_dir}" not in content
            assert "{plans_rel_dir}" not in content

    @pytest.mark.anyio
    async def test_idempotent_multiple_calls(self, tmp_path: Path):
        """Multiple calls do not fail or duplicate content."""
        await Config.init(tmp_path)
        await Config.init(tmp_path)
        await Config.init(tmp_path)

        freeact_dir = tmp_path / ".freeact"
        assert freeact_dir.exists()

        # Verify structure is intact after multiple calls
        assert (freeact_dir / "config.json").exists()
        assert (freeact_dir / "plans").exists()
