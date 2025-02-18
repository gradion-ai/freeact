import os

from freeact.model.deepseek.prompt import r1, v3
from freeact.model.litellm.model import LiteLLM, LiteLLMResponse, LiteLLMTurn
from freeact.model.litellm.utils import code_block


class DeepSeekV3(LiteLLM):
    """Code action model class for DeepSeek V3.

    Args:
        model_name: The LiteLLM-specific name of the model.
        skill_sources: Skill modules source code to be included into `system_template`.
        system_extension: Domain- or environment-specific extensions to the `system_template`.
        system_template: Prompt template for the system instruction that guides the model to generate code actions.
            Must define a `{python_modules}` placeholder for the `skill_sources` and an `{extensions}`
            placeholder for the `system_extension`.
        execution_output_template: A template for formatting successful code execution output.
            Must define an `{execution_feedback}` placeholder.
        execution_error_template: A template for formatting code execution errors.
            Must define an `{execution_feedback}` placeholder.
        api_key: Provider-specific API key. If not provided, reads from `DEEPSEEK_API_KEY` environment variable.
        **kwargs: Default completion kwargs.
    """

    def __init__(
        self,
        model_name: str,
        skill_sources: str | None = None,
        system_extension: str | None = None,
        system_template: str = v3.SYSTEM_TEMPLATE,
        execution_output_template: str = v3.EXECUTION_OUTPUT_TEMPLATE,
        execution_error_template: str = v3.EXECUTION_ERROR_TEMPLATE,
        api_key: str | None = None,
        **kwargs,
    ):
        system_instruction = system_template.format(
            python_modules=skill_sources or "",
            extensions=system_extension or "",
        )
        super().__init__(
            model_name=model_name,
            execution_output_template=execution_output_template,
            execution_error_template=execution_error_template,
            system_instruction=system_instruction,
            api_key=api_key or os.getenv("DEEPSEEK_API_KEY"),
            **kwargs,
        )


class DeepSeekR1(LiteLLM):
    """Code action model class for DeepSeek R1.

    Does not set a system instruction. All instructions go into the first user message
    formatted with `instruction_template`.

    Args:
        model_name: The LiteLLM-specific name of the model.
        skill_sources: Skill modules source code to be included into `system_template`.
        instruction_extension: Domain- or environment-specific extensions to the `instruction_template`.
        instruction_template: Prompt template that guides the model to generate code actions.
            Must define a `{user_query}` placeholder for the user query, an `{extensions}`
            placeholder for the `instruction_extension` and a `{python_modules}` placeholder
            for the `skill_sources`.
        execution_output_template: A template for formatting successful code execution output.
            Must define an `{execution_feedback}` placeholder.
        execution_error_template: A template for formatting code execution errors.
            Must define an `{execution_feedback}` placeholder.
        api_key: Provider-specific API key. If not provided, reads from `DEEPSEEK_API_KEY` environment variable.
        **kwargs: Default completion kwargs.
    """

    def __init__(
        self,
        model_name: str,
        skill_sources: str | None = None,
        instruction_extension: str | None = r1.EXAMPLE_EXTENSION,
        instruction_template: str = r1.INSTRUCTION_TEMPLATE,
        execution_output_template: str = r1.EXECUTION_OUTPUT_TEMPLATE,
        execution_error_template: str = r1.EXECUTION_ERROR_TEMPLATE,
        api_key: str | None = None,
        **kwargs,
    ):
        default_kwargs = {
            "temperature": 0.6,
            "max_tokens": 8192,
        }

        super().__init__(
            model_name=model_name,
            execution_output_template=execution_output_template,
            execution_error_template=execution_error_template,
            system_instruction=None,
            api_key=api_key or os.getenv("DEEPSEEK_API_KEY"),
            **(default_kwargs | kwargs),
        )

        self.instruction_template = instruction_template
        self.instruction_kwargs = {
            "python_modules": skill_sources or "",
            "extensions": instruction_extension or "",
        }

    def request(self, user_query: str, **kwargs) -> LiteLLMTurn:
        if not self.history:
            # The very first user message in a conversation contains the main
            # instructions (DeepSeek-R1 doesn't work well with system messages)
            content = self.instruction_template.format(user_query=user_query, **self.instruction_kwargs)
        else:
            content = user_query
        return super().request(content, **kwargs)

    def extract_code(self, response: LiteLLMResponse) -> str | None:
        """Extracts the last code block from `response.text`.

        DeepSeek-R1 often produces code blocks during thinking but usually
        only the last code block in the actual response is relevant.
        """
        return code_block(response.text, -1)
