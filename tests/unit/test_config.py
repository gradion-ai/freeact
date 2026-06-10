# Covers behavior-inventory.md sections: 17 (configuration capabilities), 19 (system prompt & skills)
from pathlib import Path

import pytest
from pydantic import ValidationError

from freeact.config import DEFAULT_CONFIG_TOML, FreeactConfig, init, load, resolve, workspace

BUNDLED_SKILLS = {"task-planning", "output-parsers", "saving-codeacts"}


def _write_config(working_dir: Path, content: str) -> None:
    freeact_dir = working_dir / ".freeact"
    freeact_dir.mkdir(parents=True, exist_ok=True)
    (freeact_dir / "config.toml").write_text(content)


class TestSchemaDefaults:
    def test_agent_defaults(self) -> None:
        config = FreeactConfig()

        assert config.agent.model == "google-gla:gemini-3.5-flash"
        assert config.agent.model_settings["google_thinking_config"]["thinking_level"] == "medium"
        assert config.agent.execution_timeout == 300
        assert config.agent.approval_timeout == 0
        assert config.agent.tool_result_inline_max_bytes == 32768
        assert config.agent.tool_result_preview_chars == 2048
        assert config.agent.enable_persistence is True
        assert config.agent.enable_subagents is True
        assert config.agent.max_subagents == 5
        assert config.agent.kernel_env == {}
        assert config.agent.mcp_servers == {}
        assert config.agent.ptc_servers == {}

    def test_tool_presets_default_off(self) -> None:
        config = FreeactConfig()

        assert config.agent.tools.search is False
        assert config.agent.tools.fetch is False
        assert config.agent.tools.discovery is None

    def test_tool_result_limits_must_be_positive(self) -> None:
        with pytest.raises(ValidationError):
            FreeactConfig.model_validate({"agent": {"tool_result_inline_max_bytes": 0}})

        with pytest.raises(ValidationError):
            FreeactConfig.model_validate({"agent": {"tool_result_preview_chars": 0}})

    def test_config_is_immutable(self) -> None:
        config = FreeactConfig()

        with pytest.raises(ValidationError):
            setattr(config.agent, "execution_timeout", 1)


class TestLoad:
    def test_load_returns_defaults_when_config_missing(self, tmp_path: Path) -> None:
        config = load(working_dir=tmp_path)

        assert config == FreeactConfig()
        assert not (tmp_path / ".freeact").exists()

    def test_load_parses_toml_overrides(self, tmp_path: Path) -> None:
        _write_config(
            tmp_path,
            """
            [agent]
            model = "openai:gpt-4o-mini"
            execution_timeout = 77.0
            approval_timeout = 9.0
            tool_result_inline_max_bytes = 12345
            tool_result_preview_chars = 900
            enable_subagents = false
            max_subagents = 3
            enable_persistence = false

            [agent.model_settings]
            temperature = 0.3

            [agent.kernel_env]
            FOO = "bar"

            [agent.tools]
            search = true
            fetch = true
            discovery = "basic"

            [agent.mcp_servers.custom]
            command = "python"
            args = ["-m", "demo"]

            [agent.ptc_servers.local]
            command = "python"
            args = ["-m", "demo"]

            [terminal]
            collapse_thoughts_on_complete = false
            """,
        )

        config = load(working_dir=tmp_path)

        assert config.agent.model == "openai:gpt-4o-mini"
        assert config.agent.model_settings == {"temperature": 0.3}
        assert config.agent.execution_timeout == 77
        assert config.agent.approval_timeout == 9
        assert config.agent.tool_result_inline_max_bytes == 12345
        assert config.agent.tool_result_preview_chars == 900
        assert config.agent.enable_subagents is False
        assert config.agent.max_subagents == 3
        assert config.agent.enable_persistence is False
        assert config.agent.kernel_env == {"FOO": "bar"}
        assert config.agent.tools.search is True
        assert config.agent.tools.fetch is True
        assert config.agent.tools.discovery == "basic"
        assert config.agent.mcp_servers == {"custom": {"command": "python", "args": ["-m", "demo"]}}
        assert config.agent.ptc_servers == {"local": {"command": "python", "args": ["-m", "demo"]}}
        assert config.terminal.collapse_thoughts_on_complete is False

    def test_load_rejects_unknown_keys(self, tmp_path: Path) -> None:
        _write_config(tmp_path, '[agent]\nbogus = "value"\n')

        with pytest.raises(ValidationError):
            load(working_dir=tmp_path)


class TestInit:
    def test_init_writes_default_config_and_creates_dirs(self, tmp_path: Path) -> None:
        config = init(working_dir=tmp_path)

        freeact_dir = tmp_path / ".freeact"
        assert (freeact_dir / "config.toml").read_text() == DEFAULT_CONFIG_TOML
        assert (freeact_dir / "generated").is_dir()
        assert (freeact_dir / "plans").is_dir()
        assert (freeact_dir / "sessions").is_dir()
        assert config == FreeactConfig()

    def test_init_does_not_overwrite_existing_config(self, tmp_path: Path) -> None:
        custom = '[agent]\nmodel = "custom:model"\n'
        _write_config(tmp_path, custom)

        config = init(working_dir=tmp_path)

        assert (tmp_path / ".freeact" / "config.toml").read_text() == custom
        assert config.agent.model == "custom:model"

    def test_init_is_idempotent(self, tmp_path: Path) -> None:
        init(working_dir=tmp_path)
        init(working_dir=tmp_path)

        freeact_dir = tmp_path / ".freeact"
        assert (freeact_dir / "config.toml").exists()
        assert (freeact_dir / "generated").is_dir()
        assert (freeact_dir / "sessions").is_dir()

    def test_init_materializes_bundled_skills(self, tmp_path: Path) -> None:
        init(working_dir=tmp_path)

        skills_dir = tmp_path / ".freeact" / "skills"
        skill_names = {path.name for path in skills_dir.iterdir() if path.is_dir()}
        assert skill_names == BUNDLED_SKILLS
        for name in BUNDLED_SKILLS:
            assert (skills_dir / name / "SKILL.md").exists()

    def test_init_skips_existing_skill_directories(self, tmp_path: Path) -> None:
        init(working_dir=tmp_path)
        skill_file = tmp_path / ".freeact" / "skills" / "task-planning" / "SKILL.md"
        custom_content = "custom-content"
        skill_file.write_text(custom_content)

        init(working_dir=tmp_path)

        assert skill_file.read_text() == custom_content


class TestResolve:
    def test_minimal_defaults(self, tmp_path: Path) -> None:
        runtime = resolve(FreeactConfig(), working_dir=tmp_path, env={})

        assert set(runtime.mcp_servers.keys()) == {"filesystem"}
        assert runtime.ptc_servers == {}
        assert runtime.model == "google-gla:gemini-3.5-flash"
        assert runtime.enable_subagents is True
        assert runtime.subagent_mode is False

    def test_search_and_fetch_presets_expand_to_ptc_servers(self, tmp_path: Path) -> None:
        config = FreeactConfig.model_validate({"agent": {"tools": {"search": True, "fetch": True}}})

        runtime = resolve(config, working_dir=tmp_path, env={"GEMINI_API_KEY": "test"})

        assert set(runtime.ptc_servers.keys()) == {"google", "fetch"}
        # Validated against the environment but returned unsubstituted.
        assert runtime.ptc_servers["google"]["env"]["GEMINI_API_KEY"] == "${GEMINI_API_KEY}"

    def test_search_preset_missing_env_raises(self, tmp_path: Path) -> None:
        config = FreeactConfig.model_validate({"agent": {"tools": {"search": True}}})

        with pytest.raises(ValueError, match="GEMINI_API_KEY"):
            resolve(config, working_dir=tmp_path, env={})

    def test_user_ptc_servers_are_validated_but_not_replaced(self, tmp_path: Path) -> None:
        config = FreeactConfig.model_validate(
            {
                "agent": {
                    "ptc_servers": {
                        "demo": {
                            "command": "python",
                            "args": ["-m", "demo"],
                            "env": {"API_KEY": "${PTC_API_KEY}"},
                        }
                    }
                }
            }
        )

        runtime = resolve(config, working_dir=tmp_path, env={"PTC_API_KEY": "resolved-key"})

        assert runtime.ptc_servers["demo"]["env"]["API_KEY"] == "${PTC_API_KEY}"

    def test_ptc_servers_missing_env_raises(self, tmp_path: Path) -> None:
        config = FreeactConfig.model_validate(
            {
                "agent": {
                    "ptc_servers": {
                        "demo": {
                            "command": "python",
                            "args": ["-m", "demo"],
                            "env": {"API_KEY": "${MISSING_PTC_KEY}"},
                        }
                    }
                }
            }
        )

        with pytest.raises(ValueError, match="MISSING_PTC_KEY"):
            resolve(config, working_dir=tmp_path, env={})

    def test_discovery_basic_adds_pytools_mcp_server(self, tmp_path: Path) -> None:
        config = FreeactConfig.model_validate({"agent": {"tools": {"discovery": "basic"}}})

        runtime = resolve(config, working_dir=tmp_path, env={})

        assert set(runtime.mcp_servers.keys()) == {"filesystem", "pytools"}
        assert runtime.mcp_servers["pytools"]["args"] == ["-m", "freeact.tools.pytools.search.basic"]
        ws = workspace(tmp_path)
        assert runtime.mcp_servers["pytools"]["env"]["PYTOOLS_DIR"] == str(ws.generated_rel_dir)

    def test_discovery_hybrid_adds_pytools_mcp_server_with_defaults(self, tmp_path: Path) -> None:
        config = FreeactConfig.model_validate({"agent": {"tools": {"discovery": "hybrid"}}})

        runtime = resolve(config, working_dir=tmp_path, env={"GEMINI_API_KEY": "test"})

        assert runtime.mcp_servers["pytools"]["args"] == ["-m", "freeact.tools.pytools.search.hybrid"]
        pytools_env = runtime.mcp_servers["pytools"]["env"]
        assert pytools_env["GEMINI_API_KEY"] == "test"
        assert pytools_env["PYTOOLS_EMBEDDING_MODEL"] == "google-gla:gemini-embedding-001"
        assert pytools_env["PYTOOLS_SYNC"] == "true"
        assert pytools_env["PYTOOLS_WATCH"] == "true"

    def test_mcp_servers_missing_env_raises(self, tmp_path: Path) -> None:
        config = FreeactConfig.model_validate(
            {
                "agent": {
                    "mcp_servers": {
                        "custom": {
                            "command": "python",
                            "args": ["-m", "demo"],
                            "env": {"TOKEN": "${MISSING_MCP_TOKEN}"},
                        }
                    }
                }
            }
        )

        with pytest.raises(ValueError, match="MISSING_MCP_TOKEN"):
            resolve(config, working_dir=tmp_path, env={})

    def test_kernel_env_defaults_and_substitution(self, tmp_path: Path) -> None:
        config = FreeactConfig.model_validate({"agent": {"kernel_env": {"CUSTOM": "${CUSTOM_VAR}"}}})

        runtime = resolve(config, working_dir=tmp_path, env={"HOME": "/home/test", "CUSTOM_VAR": "value"})

        ws = workspace(tmp_path)
        assert runtime.kernel_env["PYTHONPATH"] == str(ws.generated_dir)
        assert runtime.kernel_env["HOME"] == "/home/test"
        assert runtime.kernel_env["CUSTOM"] == "value"

    def test_kernel_env_home_can_be_overridden(self, tmp_path: Path) -> None:
        config = FreeactConfig.model_validate({"agent": {"kernel_env": {"HOME": "/custom/home"}}})

        runtime = resolve(config, working_dir=tmp_path, env={"HOME": "/home/test"})

        assert runtime.kernel_env["HOME"] == "/custom/home"

    def test_kernel_env_missing_env_raises(self, tmp_path: Path) -> None:
        config = FreeactConfig.model_validate({"agent": {"kernel_env": {"FOO": "${MISSING_KERNEL_VAR}"}}})

        with pytest.raises(ValueError, match="MISSING_KERNEL_VAR"):
            resolve(config, working_dir=tmp_path, env={})

    def test_zero_timeouts_disable_runtime_timeouts(self, tmp_path: Path) -> None:
        config = FreeactConfig.model_validate({"agent": {"execution_timeout": 0, "approval_timeout": 0}})

        runtime = resolve(config, working_dir=tmp_path, env={})

        assert runtime.execution_timeout is None
        assert runtime.approval_timeout is None

    def test_nonzero_timeouts_pass_through(self, tmp_path: Path) -> None:
        config = FreeactConfig.model_validate({"agent": {"execution_timeout": 123, "approval_timeout": 45}})

        runtime = resolve(config, working_dir=tmp_path, env={})

        assert runtime.execution_timeout == 123
        assert runtime.approval_timeout == 45

    def test_for_subagent_disables_subagents_and_sync_watch(self, tmp_path: Path) -> None:
        config = FreeactConfig.model_validate({"agent": {"tools": {"discovery": "hybrid"}}})
        runtime = resolve(config, working_dir=tmp_path, env={"GEMINI_API_KEY": "test"})

        subagent = runtime.for_subagent()

        assert subagent.enable_subagents is False
        assert subagent.subagent_mode is True
        pytools_env = subagent.mcp_servers["pytools"]["env"]
        assert pytools_env["PYTOOLS_SYNC"] == "false"
        assert pytools_env["PYTOOLS_WATCH"] == "false"
        # Parent runtime stays untouched.
        assert runtime.mcp_servers["pytools"]["env"]["PYTOOLS_SYNC"] == "true"
        assert runtime.mcp_servers["pytools"]["env"]["PYTOOLS_WATCH"] == "true"


class TestSystemPrompt:
    def test_system_prompt_contains_working_dir(self, tmp_path: Path) -> None:
        runtime = resolve(FreeactConfig(), working_dir=tmp_path, env={})

        assert str(runtime.working_dir) in runtime.system_prompt

    def test_system_prompt_renders_project_instructions(self, tmp_path: Path) -> None:
        (tmp_path / "AGENTS.md").write_text("Use pytest")
        runtime = resolve(FreeactConfig(), working_dir=tmp_path, env={})

        prompt = runtime.system_prompt

        assert "Use pytest" in prompt
        assert "<project-instructions>" in prompt

    def test_system_prompt_omits_project_instructions_when_absent(self, tmp_path: Path) -> None:
        runtime = resolve(FreeactConfig(), working_dir=tmp_path, env={})

        assert "<project-instructions>" not in runtime.system_prompt

    def test_system_prompt_lists_skills(self, tmp_path: Path) -> None:
        init(working_dir=tmp_path)
        runtime = resolve(load(working_dir=tmp_path), working_dir=tmp_path, env={})

        prompt = runtime.system_prompt

        for name in BUNDLED_SKILLS:
            assert name in prompt

    def test_system_prompt_mentions_overflow_file_guidance(self, tmp_path: Path) -> None:
        runtime = resolve(FreeactConfig(), working_dir=tmp_path, env={})

        prompt = runtime.system_prompt

        assert "saved to a file" in prompt
        assert "Prefer shell commands that read specific sections." in prompt

    def test_project_skills_are_loaded(self, tmp_path: Path) -> None:
        skill_dir = tmp_path / ".agents" / "skills" / "my-skill"
        skill_dir.mkdir(parents=True)
        (skill_dir / "SKILL.md").write_text("---\nname: my-skill\ndescription: Test skill\n---\n")
        runtime = resolve(FreeactConfig(), working_dir=tmp_path, env={})

        names = [skill.name for skill in runtime.skills_metadata]

        assert "my-skill" in names
