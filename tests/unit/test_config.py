import json
import os
from pathlib import Path

import pytest
from pydantic import ValidationError
from pydantic_ai.models import Model

from freeact.agent.config.config import Config


@pytest.fixture(autouse=True)
def _set_gemini_api_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GEMINI_API_KEY", "test")


def test_config_constructor_is_in_memory_defaults(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(tmp_path)

    config = Config()

    assert config.freeact_dir == tmp_path / ".freeact"
    assert config.model == "google-gla:gemini-3-flash-preview"
    assert config.model_settings["google_thinking_config"]["thinking_level"] == "high"
    assert config.tool_result_inline_max_bytes == 32768
    assert config.tool_result_preview_lines == 10
    assert config.enable_persistence is True
    assert "google" in config.ptc_servers
    assert not config.freeact_dir.exists()


def test_constructor_accepts_custom_scalar_overrides(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GEMINI_API_KEY", "test")

    config = Config(
        working_dir=tmp_path,
        model="openai:gpt-4o-mini",
        model_settings={"temperature": 0.2},
        tool_search="hybrid",
        images_dir=Path("images"),
        execution_timeout=123,
        approval_timeout=45,
        tool_result_inline_max_bytes=64000,
        tool_result_preview_lines=7,
        enable_subagents=False,
        max_subagents=2,
        enable_persistence=False,
    )

    assert config.model == "openai:gpt-4o-mini"
    assert config.model_settings == {"temperature": 0.2}
    assert config.tool_search == "hybrid"
    assert config.images_dir == Path("images")
    assert config.execution_timeout == 123
    assert config.approval_timeout == 45
    assert config.tool_result_inline_max_bytes == 64000
    assert config.tool_result_preview_lines == 7
    assert config.enable_subagents is False
    assert config.max_subagents == 2
    assert config.enable_persistence is False


def test_constructor_accepts_custom_server_overrides(tmp_path: Path) -> None:
    custom_mcp = {"custom": {"command": "python", "args": ["-m", "demo"]}}
    custom_ptc = {"local": {"command": "python", "args": ["-m", "demo"]}}

    config = Config(
        working_dir=tmp_path,
        mcp_servers=custom_mcp,
        ptc_servers=custom_ptc,
    )

    assert config.mcp_servers == custom_mcp
    assert config.ptc_servers == custom_ptc
    assert "custom" in config.resolved_mcp_servers
    assert "pytools" in config.resolved_mcp_servers


def test_ptc_servers_env_vars_are_validated_but_not_replaced(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("PTC_API_KEY", "resolved-key")
    ptc_servers = {
        "demo": {
            "command": "python",
            "args": ["-m", "demo"],
            "env": {"API_KEY": "${PTC_API_KEY}"},
        }
    }

    config = Config(working_dir=tmp_path, ptc_servers=ptc_servers)

    assert config.ptc_servers["demo"]["env"]["API_KEY"] == "${PTC_API_KEY}"


def test_ptc_servers_missing_env_raises(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.delenv("MISSING_PTC_KEY", raising=False)
    ptc_servers = {
        "demo": {
            "command": "python",
            "args": ["-m", "demo"],
            "env": {"API_KEY": "${MISSING_PTC_KEY}"},
        }
    }

    with pytest.raises(ValueError, match="ptc_servers"):
        Config(working_dir=tmp_path, ptc_servers=ptc_servers)


@pytest.mark.asyncio
async def test_load_returns_defaults_when_config_missing(tmp_path: Path) -> None:
    config = await Config.load(working_dir=tmp_path)

    assert config.freeact_dir == tmp_path / ".freeact"
    assert config.model == "google-gla:gemini-3-flash-preview"
    assert not config.freeact_dir.exists()


@pytest.mark.asyncio
async def test_init_saves_defaults_when_freeact_missing(tmp_path: Path) -> None:
    config = await Config.init(working_dir=tmp_path)

    assert config.freeact_dir == tmp_path / ".freeact"
    assert (config.freeact_dir / "agent.json").exists()


@pytest.mark.asyncio
async def test_init_loads_config_when_freeact_exists(tmp_path: Path) -> None:
    freeact_dir = tmp_path / ".freeact"
    freeact_dir.mkdir(parents=True)
    (freeact_dir / "agent.json").write_text(json.dumps({"model": "test-model", "ptc_servers": {}}))

    config = await Config.init(working_dir=tmp_path)

    assert config.model == "test-model"


@pytest.mark.asyncio
async def test_save_creates_agent_json_and_runtime_directories(tmp_path: Path) -> None:
    config = Config(working_dir=tmp_path)

    await config.save()

    freeact_dir = tmp_path / ".freeact"
    assert (freeact_dir / "agent.json").exists()
    payload = json.loads((freeact_dir / "agent.json").read_text())
    assert "tool_search" in payload
    assert "model_settings" in payload
    assert "mcp_servers" in payload
    assert "ptc_servers" in payload
    assert "enable_persistence" in payload
    assert (freeact_dir / "generated").exists()
    assert (freeact_dir / "plans").exists()
    assert (freeact_dir / "sessions").exists()


@pytest.mark.asyncio
async def test_load_save_roundtrip(tmp_path: Path) -> None:
    config = Config(
        working_dir=tmp_path,
        model="test-model",
        tool_search="basic",
        execution_timeout=42,
        tool_result_inline_max_bytes=2048,
        tool_result_preview_lines=3,
        max_subagents=7,
        ptc_servers={"demo": {"command": "python", "args": ["-m", "demo"]}},
    )
    await config.save()

    loaded = await Config.load(working_dir=tmp_path)

    assert loaded.model == "test-model"
    assert loaded.execution_timeout == 42
    assert loaded.tool_result_inline_max_bytes == 2048
    assert loaded.tool_result_preview_lines == 3
    assert loaded.max_subagents == 7
    assert "demo" in loaded.ptc_servers


@pytest.mark.asyncio
async def test_load_save_roundtrip_preserves_constructor_overrides(tmp_path: Path) -> None:
    config = Config(
        working_dir=tmp_path,
        model="openai:gpt-4o-mini",
        model_settings={"temperature": 0.3},
        execution_timeout=77,
        approval_timeout=9,
        tool_result_inline_max_bytes=12345,
        tool_result_preview_lines=9,
        enable_subagents=False,
        max_subagents=3,
        enable_persistence=False,
        kernel_env={"FOO": "bar"},
        mcp_servers={"custom": {"command": "python", "args": ["-m", "demo"]}},
        ptc_servers={"local": {"command": "python", "args": ["-m", "demo"]}},
    )
    await config.save()

    loaded = await Config.load(working_dir=tmp_path)

    assert loaded.model == "openai:gpt-4o-mini"
    assert loaded.model_settings == {"temperature": 0.3}
    assert loaded.execution_timeout == 77
    assert loaded.approval_timeout == 9
    assert loaded.tool_result_inline_max_bytes == 12345
    assert loaded.tool_result_preview_lines == 9
    assert loaded.enable_subagents is False
    assert loaded.max_subagents == 3
    assert loaded.enable_persistence is False
    assert loaded.kernel_env == {"FOO": "bar"}
    assert loaded.mcp_servers == {"custom": {"command": "python", "args": ["-m", "demo"]}}
    assert loaded.ptc_servers == {"local": {"command": "python", "args": ["-m", "demo"]}}


@pytest.mark.asyncio
async def test_load_rejects_kebab_case_keys(tmp_path: Path) -> None:
    freeact_dir = tmp_path / ".freeact"
    freeact_dir.mkdir(parents=True)
    (freeact_dir / "agent.json").write_text(
        json.dumps(
            {
                "model": "test",
                "tool-search": "basic",
            }
        )
    )

    with pytest.raises(ValidationError):
        await Config.load(working_dir=tmp_path)


@pytest.mark.asyncio
async def test_unsaved_config_has_no_bundled_skills(tmp_path: Path) -> None:
    config = Config(working_dir=tmp_path)

    assert config.skills_metadata == []
    assert not config.skills_dir.exists()


@pytest.mark.asyncio
async def test_save_materializes_bundled_skills(tmp_path: Path) -> None:
    config = Config(working_dir=tmp_path)

    await config.save()

    skills = config.skills_metadata
    assert len(skills) > 0
    assert config.skills_dir.exists()


@pytest.mark.asyncio
async def test_save_skips_existing_bundled_skill_directory(tmp_path: Path) -> None:
    config = Config(working_dir=tmp_path)
    await config.save()

    skill_dir = config.skills_dir / "task-planning"
    skill_file = skill_dir / "SKILL.md"
    custom_content = "custom-content"
    skill_file.write_text(custom_content)

    await config.save()

    assert skill_file.read_text() == custom_content


@pytest.mark.asyncio
async def test_save_is_non_destructive_for_runtime_files(tmp_path: Path) -> None:
    config = Config(working_dir=tmp_path)
    freeact_dir = config.freeact_dir
    freeact_dir.mkdir(parents=True)

    search_db = freeact_dir / "search.db"
    permissions = freeact_dir / "permissions.json"
    search_db.write_bytes(b"sqlite")
    permissions.write_text('{"allowed_tools": ["x"]}')

    await config.save()

    assert search_db.read_bytes() == b"sqlite"
    assert permissions.read_text() == '{"allowed_tools": ["x"]}'


def test_project_skills_are_loaded(tmp_path: Path) -> None:
    config = Config(working_dir=tmp_path)
    skill_dir = config.project_skills_dir / "my-skill"
    skill_dir.mkdir(parents=True)
    (skill_dir / "SKILL.md").write_text("---\nname: my-skill\ndescription: Test skill\n---\n")

    names = [skill.name for skill in config.skills_metadata]
    assert "my-skill" in names


def test_system_prompt_renders_project_instructions(tmp_path: Path) -> None:
    config = Config(working_dir=tmp_path)
    config.project_instructions_file.write_text("Use pytest")

    prompt = config.system_prompt

    assert "Use pytest" in prompt


def test_system_prompt_mentions_overflow_file_guidance(tmp_path: Path) -> None:
    config = Config(working_dir=tmp_path)

    prompt = config.system_prompt

    assert "saved to a file" in prompt
    assert "Prefer shell commands that read specific sections." in prompt


def test_pytools_defaults_are_resolved_without_mutating_process_env(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.delenv("PYTOOLS_DIR", raising=False)
    monkeypatch.delenv("PYTOOLS_DB_PATH", raising=False)

    config = Config(working_dir=tmp_path)
    pytools_env = config.resolved_mcp_servers["pytools"]["env"]

    assert pytools_env["PYTOOLS_DIR"] == str(config.generated_rel_dir)
    assert "PYTOOLS_DIR" not in os.environ
    assert "PYTOOLS_DB_PATH" not in os.environ


def test_hybrid_defaults_are_resolved_without_mutating_process_env(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("GEMINI_API_KEY", "test")
    monkeypatch.delenv("PYTOOLS_EMBEDDING_MODEL", raising=False)

    config = Config(working_dir=tmp_path, tool_search="hybrid")
    pytools_env = config.resolved_mcp_servers["pytools"]["env"]

    assert pytools_env["PYTOOLS_EMBEDDING_MODEL"] == "google-gla:gemini-embedding-001"
    assert "PYTOOLS_EMBEDDING_MODEL" not in os.environ


def test_resolved_mcp_servers_include_internal_defaults(tmp_path: Path) -> None:
    config = Config(working_dir=tmp_path)

    servers = config.resolved_mcp_servers

    assert "pytools" in servers
    assert "filesystem" in servers


def test_provider_settings_builds_runtime_model(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("MY_API_KEY", "secret")

    config = Config(
        working_dir=tmp_path,
        model="openai:gpt-4o",
        provider_settings={"api_key": "${MY_API_KEY}"},
    )

    assert isinstance(config.model_instance, Model)


def test_provider_settings_missing_env_raises(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.delenv("MISSING_KEY", raising=False)

    with pytest.raises(ValueError, match="provider_settings"):
        Config(
            working_dir=tmp_path,
            model="openai:gpt-4o",
            provider_settings={"api_key": "${MISSING_KEY}"},
        )


def test_kernel_env_runtime_defaults_and_overrides(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("HOME", "/home/test")
    monkeypatch.setenv("CUSTOM_VAR", "value")

    config = Config(
        working_dir=tmp_path,
        kernel_env={"CUSTOM": "${CUSTOM_VAR}"},
    )

    runtime_env = config.resolved_kernel_env
    assert runtime_env["PYTHONPATH"] == str(config.generated_dir)
    assert runtime_env["HOME"] == "/home/test"
    assert runtime_env["CUSTOM"] == "value"


def test_for_subagent_disables_subagents_and_sync_watch(tmp_path: Path) -> None:
    config = Config(working_dir=tmp_path, tool_search="basic")
    subagent = config.for_subagent()

    assert subagent.enable_subagents is False

    pytools_env = subagent.resolved_mcp_servers.get("pytools", {}).get("env", {})
    if pytools_env:
        assert pytools_env["PYTOOLS_SYNC"] == "false"
        assert pytools_env["PYTOOLS_WATCH"] == "false"


def test_freeact_dir_is_derived_from_working_dir(tmp_path: Path) -> None:
    config = Config(working_dir=tmp_path)

    assert config.freeact_dir == tmp_path / ".freeact"
    assert config.generated_dir == tmp_path / ".freeact" / "generated"


def test_config_is_immutable(tmp_path: Path) -> None:
    config = Config(working_dir=tmp_path)

    with pytest.raises(ValidationError):
        setattr(config, "execution_timeout", 1)


def test_tool_result_limits_must_be_positive(tmp_path: Path) -> None:
    with pytest.raises(ValidationError):
        Config(working_dir=tmp_path, tool_result_inline_max_bytes=0)

    with pytest.raises(ValidationError):
        Config(working_dir=tmp_path, tool_result_preview_lines=0)
