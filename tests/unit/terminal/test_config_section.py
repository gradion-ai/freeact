# Covers behavior-inventory.md sections: 20 (terminal UI: per-kind collapse config), 17 (configuration capabilities)
import pytest
from pydantic import ValidationError

from freeact.config import TerminalSection


def test_terminal_section_defaults() -> None:
    config = TerminalSection()

    assert config.collapse_thoughts_on_complete is True
    assert config.collapse_exec_output_on_complete is True
    assert config.collapse_approved_code_actions is False
    assert config.collapse_approved_tool_calls is True
    assert config.collapse_completed_subagent_tasks is True
    assert config.collapse_tool_outputs is True
    assert config.keep_rejected_actions_expanded is True
    assert config.pin_pending_approval_action_expanded is True
    assert config.expand_all_toggle_key == "ctrl+o"


def test_expand_all_toggle_key_must_be_non_empty() -> None:
    with pytest.raises(ValidationError):
        TerminalSection(expand_all_toggle_key="")


def test_terminal_section_rejects_unknown_keys() -> None:
    with pytest.raises(ValidationError):
        TerminalSection.model_validate({"bogus": True})


def test_terminal_section_rejects_kebab_case_keys() -> None:
    with pytest.raises(ValidationError):
        TerminalSection.model_validate({"collapse-tool-outputs": False})


def test_terminal_section_is_immutable() -> None:
    config = TerminalSection()

    with pytest.raises(ValidationError):
        setattr(config, "expand_all_toggle_key", "ctrl+p")
