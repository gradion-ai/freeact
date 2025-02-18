from freeact.model.claude.prompt import (
    EXECUTION_ERROR_TEMPLATE,
    EXECUTION_OUTPUT_TEMPLATE,
    MODULES_ACK_MESSAGE,
    MODULES_INFO_TEMPLATE,
    SYSTEM_TEMPLATE,
    USER_QUERY_TEMPLATE,
)
from freeact.model.claude.tools import CODE_EDITOR_TOOL, CODE_EXECUTOR_TOOL
from freeact.model.litellm.model import LiteLLMBase, LiteLLMResponse, LiteLLMTurn, tool_name


class Claude(LiteLLMBase):
    """Code action model class for Claude 3.5 models.

    Args:
        model_name: The LiteLLM-specific name of the model.
        system_extension: Additional system prompt text.
        system_message: Complete system instruction to override default.
        execution_output_template: Template for formatting code execution results.
        execution_error_template: Template for formatting code execution errors.
        prompt_caching: Whether to enable prompt caching.
        **kwargs: Default completion kwargs.
    """

    def __init__(
        self,
        model_name: str = "anthropic/claude-3-5-sonnet-20241022",
        system_extension: str | None = None,
        system_instruction: str | None = None,
        execution_output_template: str = EXECUTION_OUTPUT_TEMPLATE,
        execution_error_template: str = EXECUTION_ERROR_TEMPLATE,
        prompt_caching: bool = False,
        **kwargs,
    ):
        if system_instruction and system_extension:
            raise ValueError("If system_instruction is provided, system_extension must be None")

        if system_instruction:
            self.system_message = system_instruction
        else:
            self.system_message = SYSTEM_TEMPLATE.format(extensions=system_extension or "")

        super().__init__(
            model_name=model_name,
            system_instruction=self.system_message,
            tools=[CODE_EXECUTOR_TOOL, CODE_EDITOR_TOOL],
            **kwargs,
        )

        self.execution_output_template = execution_output_template
        self.execution_error_template = execution_error_template
        self.prompt_caching = prompt_caching

    def request(
        self,
        user_query: str,
        skill_sources: str | None = None,
        **kwargs,
    ) -> LiteLLMTurn:
        modules_info_block = [
            {
                "type": "text",
                "text": MODULES_INFO_TEMPLATE.format(python_modules=skill_sources or ""),
            },
        ]
        modules_info_message = {"role": "user", "content": modules_info_block}
        modules_ack_message = {"role": "assistant", "content": MODULES_ACK_MESSAGE}

        if self.prompt_caching:
            modules_info_block[0]["cache_control"] = {"type": "ephemeral"}  # type: ignore

        if len(self.history) == 1:
            self.history.append(modules_info_message)
            self.history.append(modules_ack_message)
        else:
            self.history[1] = modules_info_message
            self.history[2] = modules_ack_message

        content = USER_QUERY_TEMPLATE.format(user_query=user_query)
        return super().request(content, **kwargs)

    def feedback(
        self,
        feedback: str,
        is_error: bool,
        tool_use_id: str | None,
        tool_use_name: str | None,
        skill_sources: str | None = None,
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
