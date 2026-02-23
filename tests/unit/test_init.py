"""Tests for config.save() scaffolding behavior."""

import json
from pathlib import Path

import pytest

from freeact.agent.config import Config


@pytest.fixture(autouse=True)
def _set_gemini_api_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GEMINI_API_KEY", "test")


class TestConfigSave:
    """Tests for config.save() behavior."""

    @pytest.mark.asyncio
    async def test_creates_freeact_directory(self, tmp_path: Path):
        config = Config(working_dir=tmp_path)

        await config.save()

        freeact_dir = tmp_path / ".freeact"
        assert freeact_dir.exists()
        assert freeact_dir.is_dir()

    @pytest.mark.asyncio
    async def test_creates_plans_and_sessions_directories(self, tmp_path: Path):
        config = Config(working_dir=tmp_path)

        await config.save()

        assert (tmp_path / ".freeact" / "plans").exists()
        assert (tmp_path / ".freeact" / "sessions").exists()

    @pytest.mark.asyncio
    async def test_writes_snake_case_config_json(self, tmp_path: Path):
        config = Config(working_dir=tmp_path)

        await config.save()

        payload = json.loads((tmp_path / ".freeact" / "agent.json").read_text())
        assert "tool_search" in payload
        assert "model_settings" in payload
        assert payload["model_settings"]["google_thinking_config"]["thinking_level"] == "high"
        assert "kernel_env" in payload
        assert "tool_result_inline_max_bytes" in payload
        assert "tool_result_preview_lines" in payload
        assert "enable_persistence" in payload
        assert "ptc_servers" in payload
        assert "google" in payload["ptc_servers"]
        assert "tool-search" not in payload
        assert "model-settings" not in payload

    @pytest.mark.asyncio
    async def test_creates_skill_templates(self, tmp_path: Path):
        config = Config(working_dir=tmp_path)

        await config.save()

        skills_dir = tmp_path / ".freeact" / "skills"
        assert skills_dir.exists()
        assert any(path.name == "SKILL.md" for path in skills_dir.rglob("SKILL.md"))

    @pytest.mark.asyncio
    async def test_idempotent_multiple_saves(self, tmp_path: Path):
        config = Config(working_dir=tmp_path)

        await config.save()
        await config.save()
        await config.save()

        freeact_dir = tmp_path / ".freeact"
        assert (freeact_dir / "agent.json").exists()
        assert (freeact_dir / "generated").exists()
        assert (freeact_dir / "sessions").exists()
