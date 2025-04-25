import litellm

from freeact.model.claude.prompt import (
    EXECUTION_ERROR_TEMPLATE,
    EXECUTION_OUTPUT_TEMPLATE,
    SYSTEM_TEMPLATE,
)
from freeact.model.claude.tools import CODE_EDITOR_TOOL, CODE_EXECUTOR_TOOL, beta_flag, code_editor_tool
from freeact.model.litellm.model import Content, LiteLLM, LiteLLMResponse, LiteLLMTurn, tool_name


class Claude(LiteLLM):
    """Code action model class for Claude 3.7 models."""

    def __init__(
        self,
        model_name: str = "anthropic/claude-3-7-sonnet-20250219",
        skill_sources: str | None = None,
        system_instruction: Content | None = None,
        prompt_caching: bool = False,
        **kwargs,
    ):
        if not system_instruction:
            system_instruction = SYSTEM_TEMPLATE.format(python_modules=skill_sources or "")

        if prompt_caching:
            system_instruction = [
                {
                    "type": "text",
                    "text": system_instruction,
                    "cache_control": {
                        "type": "ephemeral",
                    },
                }
            ]

        if "thinking" in kwargs or "reasoning_effort" in kwargs:
            kwargs["stream"] = False

        super().__init__(
            model_name=model_name,
            execution_output_template=EXECUTION_OUTPUT_TEMPLATE,
            execution_error_template=EXECUTION_ERROR_TEMPLATE,
            system_instruction=system_instruction,
            tools=[CODE_EXECUTOR_TOOL, code_editor_tool(model_name)],
            extra_headers=beta_flag(model_name),
            parallel_tool_calls=False,
            **kwargs,
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

    def _extract_content(self, result_message: litellm.Message):
        output = []

        if hasattr(result_message, "thinking_blocks") and result_message.thinking_blocks:
            output.extend(result_message.thinking_blocks)

        if result_message.content:
            output.append(
                {
                    "type": "text",
                    "text": result_message.content,
                },
            )

        return output
