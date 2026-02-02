"""Tests for freeact/agent/config/init.py."""

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

    def test_copies_system_prompt_templates(self, tmp_path: Path):
        """Copies prompts/system-basic.md and system-hybrid.md with placeholders."""
        init_config(tmp_path)

        prompts_dir = tmp_path / ".freeact" / "prompts"

        # Both prompt files should exist
        basic_prompt = prompts_dir / "system-basic.md"
        hybrid_prompt = prompts_dir / "system-hybrid.md"
        assert basic_prompt.exists()
        assert hybrid_prompt.exists()

        # Both should have template placeholders
        for prompt_file in [basic_prompt, hybrid_prompt]:
            content = prompt_file.read_text()
            assert "{working_dir}" in content
            assert "{skills}" in content

    def test_copies_servers_json_template(self, tmp_path: Path):
        """Copies servers.json with mcp-servers and ptc-servers keys."""
        init_config(tmp_path)

        servers_json = tmp_path / ".freeact" / "servers.json"
        assert servers_json.exists()

        import json

        config = json.loads(servers_json.read_text())
        assert "mcp-servers" in config
        assert "ptc-servers" in config

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
        prompts_dir = freeact_dir / "prompts"
        prompts_dir.mkdir(parents=True)

        # Create existing file with custom content
        existing_content = "Custom user content"
        system_prompt = prompts_dir / "system-basic.md"
        system_prompt.write_text(existing_content)

        init_config(tmp_path)

        # Verify content was not overwritten
        assert system_prompt.read_text() == existing_content

    def test_uses_cwd_when_working_dir_is_none(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
        """Uses current working directory when working_dir is None."""
        monkeypatch.chdir(tmp_path)

        init_config(None)

        freeact_dir = tmp_path / ".freeact"
        assert freeact_dir.exists()

    def test_idempotent_multiple_calls(self, tmp_path: Path):
        """Multiple calls do not fail or duplicate content."""
        init_config(tmp_path)
        init_config(tmp_path)
        init_config(tmp_path)

        freeact_dir = tmp_path / ".freeact"
        assert freeact_dir.exists()

        # Verify structure is intact after multiple calls
        assert (freeact_dir / "prompts" / "system-basic.md").exists()
        assert (freeact_dir / "prompts" / "system-hybrid.md").exists()
        assert (freeact_dir / "servers.json").exists()
        assert (freeact_dir / "plans").exists()
