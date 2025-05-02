from freeact.model.litellm.base.model import LiteLLMBase, LiteLLMResponse, LiteLLMTurn, tool_name
from freeact.model.litellm.tool_use.tools import (
    CODE_EDITOR_TOOL,
    CODE_EXECUTOR_TOOL,
    beta_flag,
    code_editor_tool,
    code_executor_tool,
)


class LiteLLM(LiteLLMBase):
    def __init__(self, model_name: str, system_instruction: str, **kwargs):
        extra_kwargs = {}

        if flags := beta_flag(model_name):
            extra_kwargs["extra_headers"] = flags

        super().__init__(
            model_name=model_name,
            system_instruction=system_instruction,
            tools=[code_executor_tool(model_name), code_editor_tool(model_name)],
            **(kwargs | extra_kwargs),
        )

    def feedback(
        self,
        feedback: str,
        is_error: bool,
        tool_use_id: str | None,
        tool_use_name: str | None,
        **kwargs,
    ) -> LiteLLMTurn:
        if tool_use_name == tool_name(CODE_EXECUTOR_TOOL):
            template = self.execution_error_template if is_error else self.execution_output_template
            content = template.format(execution_feedback=feedback)
        else:
            content = feedback  # skip application of templates for other tool results

        return super().feedback(content, is_error, tool_use_id, tool_use_name, **kwargs)

    def extract_code(self, response: LiteLLMResponse) -> str | None:
        if response.tool_use_name == tool_name(CODE_EXECUTOR_TOOL):
            return response.tool_use.input["code"]  # type: ignore
        elif response.tool_use_name == tool_name(CODE_EDITOR_TOOL):
            return f"print(file_editor(**{response.tool_use.input}))"  # type: ignore
        else:
            return None
