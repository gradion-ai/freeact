"""Tests for freeact/agent/config/init.py."""

import json
from pathlib import Path

import pytest

from freeact.agent.config.init import init_config


class TestInitConfig:
    """Tests for init_config function."""

    def test_creates_freeact_directory(self, tmp_path: Path):
        """Creates .freeact/ directory if it doesn't exist."""
        init_config(tmp_path)

        freeact_dir = tmp_path / ".freeact"
        assert freeact_dir.exists()
        assert freeact_dir.is_dir()

    def test_creates_plans_directory(self, tmp_path: Path):
        """Creates .freeact/plans/ directory."""
        init_config(tmp_path)

        plans_dir = tmp_path / ".freeact" / "plans"
        assert plans_dir.exists()
        assert plans_dir.is_dir()

    def test_copies_config_json_template(self, tmp_path: Path):
        """Copies config.json with tool-search, mcp-servers and ptc-servers keys."""
        init_config(tmp_path)

        config_json = tmp_path / ".freeact" / "config.json"
        assert config_json.exists()

        config = json.loads(config_json.read_text())
        assert "tool-search" in config
        assert config["tool-search"] == "basic"
        assert "mcp-servers" in config
        assert config["mcp-servers"] == {}
        assert "ptc-servers" in config

    def test_does_not_copy_system_prompts(self, tmp_path: Path):
        """System prompts are not copied to .freeact/ (they are package resources)."""
        init_config(tmp_path)

        prompts_dir = tmp_path / ".freeact" / "prompts"
        assert not prompts_dir.exists()

    def test_copies_skill_templates(self, tmp_path: Path):
        """Copies skill directories from templates."""
        init_config(tmp_path)

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

    def test_preserves_existing_files(self, tmp_path: Path):
        """Does not overwrite existing user files."""
        freeact_dir = tmp_path / ".freeact"
        freeact_dir.mkdir(parents=True)

        # Create existing file with custom content
        existing_content = '{"tool-search": "hybrid"}'
        config_json = freeact_dir / "config.json"
        config_json.write_text(existing_content)

        init_config(tmp_path)

        # Verify content was not overwritten
        assert config_json.read_text() == existing_content

    def test_uses_cwd_when_working_dir_is_none(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
        """Uses current working directory when working_dir is None."""
        monkeypatch.chdir(tmp_path)

        init_config(None)

        freeact_dir = tmp_path / ".freeact"
        assert freeact_dir.exists()

    def test_renders_skill_placeholders(self, tmp_path: Path):
        """Renders placeholders in skill templates during copy."""
        init_config(tmp_path)

        skills_dir = tmp_path / ".freeact" / "skills"
        for skill_file in skills_dir.rglob("SKILL.md"):
            content = skill_file.read_text()
            assert "{generated_rel_dir}" not in content
            assert "{plans_rel_dir}" not in content

    def test_idempotent_multiple_calls(self, tmp_path: Path):
        """Multiple calls do not fail or duplicate content."""
        init_config(tmp_path)
        init_config(tmp_path)
        init_config(tmp_path)

        freeact_dir = tmp_path / ".freeact"
        assert freeact_dir.exists()

        # Verify structure is intact after multiple calls
        assert (freeact_dir / "config.json").exists()
        assert (freeact_dir / "plans").exists()
