# Covers behavior-inventory.md sections: 11 (permissions: typed rules, persistence, defaults)
from pathlib import Path

import pytest

from freeact.permissions import (
    CodeActionRule,
    FileEditRule,
    FileReadRule,
    FileWriteRule,
    GenericCallRule,
    PermissionManager,
    PermissionsConfig,
    ShellActionRule,
    rule_from_call,
)
from freeact.toolcalls import (
    CodeAction,
    FileEdit,
    FileRead,
    FileWrite,
    GenericCall,
    ShellAction,
    ToolCall,
)


def _file_read(path: str) -> FileRead:
    return FileRead(tool_name="filesystem_read_text_file", path=path, offset=None, limit=None)


class TestRuleFromCall:
    @pytest.mark.parametrize(
        ("tool_call", "expected"),
        [
            (
                ShellAction(tool_name="bash", command="git *"),
                ShellActionRule(tool_name="bash", command="git *"),
            ),
            (
                CodeAction(tool_name="ipybox_execute_ipython_cell", code="x=1"),
                CodeActionRule(tool_name="ipybox_execute_ipython_cell"),
            ),
            (
                FileRead(tool_name="filesystem_*", path="src/**", offset=None, limit=None),
                FileReadRule(tool_name="filesystem_*", path="src/**"),
            ),
            (
                FileWrite(tool_name="filesystem_write_text_file", path="src/**", content=""),
                FileWriteRule(tool_name="filesystem_write_text_file", path="src/**"),
            ),
            (
                FileEdit(tool_name="filesystem_edit_text_file", path="src/**", old_text="", new_text=""),
                FileEditRule(tool_name="filesystem_edit_text_file", path="src/**"),
            ),
            (
                GenericCall(tool_name="github_*", tool_args={}, ptc=False),
                GenericCallRule(tool_name="github_*"),
            ),
        ],
    )
    def test_builds_typed_rule(self, tool_call: ToolCall, expected: object) -> None:
        rule = rule_from_call(tool_call)

        assert rule == expected
        assert type(rule) is type(expected)

    def test_base_tool_call_raises(self) -> None:
        with pytest.raises(ValueError, match="unsupported tool call type"):
            rule_from_call(ToolCall(tool_name="anything"))


class TestRuleMatching:
    def test_shell_rule_matches_shell_action(self, tmp_path: Path) -> None:
        rule = ShellActionRule(tool_name="bash", command="git *")

        assert rule.matches(ShellAction(tool_name="bash", command="git status"), tmp_path)
        assert not rule.matches(ShellAction(tool_name="bash", command="ls"), tmp_path)

    def test_shell_rule_rejects_other_call_types(self, tmp_path: Path) -> None:
        rule = ShellActionRule(tool_name="*", command="*")

        assert not rule.matches(_file_read("a.txt"), tmp_path)
        assert not rule.matches(GenericCall(tool_name="bash", tool_args={}, ptc=False), tmp_path)
        assert not rule.matches(CodeAction(tool_name="bash", code="x"), tmp_path)

    def test_generic_rule_rejects_other_call_types(self, tmp_path: Path) -> None:
        rule = GenericCallRule(tool_name="*")

        assert rule.matches(GenericCall(tool_name="github_search", tool_args={}, ptc=False), tmp_path)
        assert not rule.matches(ShellAction(tool_name="bash", command="ls"), tmp_path)
        assert not rule.matches(_file_read("a.txt"), tmp_path)

    def test_code_rule_rejects_other_call_types(self, tmp_path: Path) -> None:
        rule = CodeActionRule(tool_name="*")

        assert rule.matches(CodeAction(tool_name="ipybox_execute_ipython_cell", code="x=1"), tmp_path)
        assert not rule.matches(GenericCall(tool_name="ipybox_execute_ipython_cell", tool_args={}, ptc=False), tmp_path)

    def test_file_rules_discriminate_between_file_call_types(self, tmp_path: Path) -> None:
        read_rule = FileReadRule(tool_name="filesystem_*", path="**")
        write_rule = FileWriteRule(tool_name="filesystem_*", path="**")
        edit_rule = FileEditRule(tool_name="filesystem_*", path="**")

        read_call = _file_read("src/main.py")
        write_call = FileWrite(tool_name="filesystem_write_text_file", path="src/main.py", content="x")
        edit_call = FileEdit(tool_name="filesystem_edit_text_file", path="src/main.py", old_text="a", new_text="b")

        assert read_rule.matches(read_call, tmp_path)
        assert not read_rule.matches(write_call, tmp_path)
        assert not read_rule.matches(edit_call, tmp_path)

        assert write_rule.matches(write_call, tmp_path)
        assert not write_rule.matches(read_call, tmp_path)

        assert edit_rule.matches(edit_call, tmp_path)
        assert not edit_rule.matches(read_call, tmp_path)


class TestPermissionsConfig:
    def test_model_validate_parses_rules_via_discriminator(self) -> None:
        data = {
            "ask": [
                {"type": "FileRead", "tool_name": "filesystem_*", "path": "**/.env"},
            ],
            "allow": [
                {"type": "ShellAction", "tool_name": "bash", "command": "ls *"},
                {"type": "GenericCall", "tool_name": "pytools_*"},
                {"type": "CodeAction", "tool_name": "ipybox_*"},
                {"type": "FileWrite", "tool_name": "filesystem_*", "path": "src/**"},
                {"type": "FileEdit", "tool_name": "filesystem_*", "path": "src/**"},
            ],
        }

        config = PermissionsConfig.model_validate(data)

        assert type(config.ask[0]) is FileReadRule
        assert [type(rule) for rule in config.allow] == [
            ShellActionRule,
            GenericCallRule,
            CodeActionRule,
            FileWriteRule,
            FileEditRule,
        ]
        assert config.allow[0] == ShellActionRule(tool_name="bash", command="ls *")

    def test_with_defaults_contains_env_ask_and_read_allow_rules(self) -> None:
        config = PermissionsConfig.with_defaults()

        assert FileReadRule(tool_name="filesystem_*", path="**/.env") in config.ask
        assert FileReadRule(tool_name="filesystem_*", path="**") in config.allow

    def test_empty_has_no_rules(self) -> None:
        config = PermissionsConfig.empty()

        assert config.ask == []
        assert config.allow == []


class TestPermissionManagerPersistence:
    def test_save_load_round_trip_preserves_rules(self, tmp_path: Path) -> None:
        freeact_dir = tmp_path / ".freeact"
        manager = PermissionManager(working_dir=tmp_path, freeact_dir=freeact_dir)
        manager.allow_always(ShellAction(tool_name="bash", command="git push *"))

        assert (freeact_dir / "permissions.toml").exists()

        reloaded = PermissionManager(working_dir=tmp_path, freeact_dir=freeact_dir)
        reloaded.load()

        assert reloaded.is_allowed(ShellAction(tool_name="bash", command="git push origin main"))
        # Default rules survive the round trip too.
        assert reloaded.is_allowed(_file_read("src/main.py"))
        # Ask rules take precedence over the broad read allow rule.
        assert not reloaded.is_allowed(_file_read(".env"))
