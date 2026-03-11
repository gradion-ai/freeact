from pydantic import StrictBool, field_validator

from freeact.config import PersistentConfig


class Config(PersistentConfig):
    """Terminal config."""

    _config_filename = "terminal.json"

    collapse_thoughts_on_complete: StrictBool = True
    collapse_exec_output_on_complete: StrictBool = True
    collapse_approved_code_actions: StrictBool = True
    collapse_approved_tool_calls: StrictBool = True
    collapse_tool_outputs: StrictBool = True
    keep_rejected_actions_expanded: StrictBool = True
    pin_pending_approval_action_expanded: StrictBool = True
    expand_all_toggle_key: str = "ctrl+o"

    @field_validator("expand_all_toggle_key")
    @classmethod
    def _validate_expand_all_toggle_key(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("expand_all_toggle_key must be a non-empty string")
        return value
