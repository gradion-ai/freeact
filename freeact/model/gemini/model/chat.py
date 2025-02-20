import os

from freeact.model.gemini.prompt import default, thinking
from freeact.model.litellm.model import LiteLLM, LiteLLMResponse
from freeact.model.litellm.utils import code_blocks


class Gemini(LiteLLM):
    """Code action model class for Gemini 2 models.

    Args:
        model_name: The LiteLLM-specific name of the model.
        skill_sources: Skill modules source code to be included into `system_template`.
        system_template: Prompt template for the system instruction that guides the model to generate code actions.
            Must define a `{python_modules}` placeholder for the `skill_sources`.
        execution_output_template: A template for formatting successful code execution output.
            Must define an `{execution_feedback}` placeholder.
        execution_error_template: A template for formatting code execution errors.
            Must define an `{execution_feedback}` placeholder.
        api_key: Provider-specific API key. If not provided, reads from
            `GEMINI_API_KEY` or `GOOGLE_API_KEY` environment variable.
        **kwargs: Default completion kwargs passed used for
            [`request`][freeact.model.base.CodeActModel.request] and
            [`feedback`][freeact.model.base.CodeActModel.feedback] calls.
            These are overriden by `request` and `feedback` specific kwargs.
    """

    def __init__(
        self,
        model_name: str = "gemini/gemini-2.0-flash",
        skill_sources: str | None = None,
        system_template: str | None = None,
        execution_output_template: str | None = None,
        execution_error_template: str | None = None,
        api_key: str | None = None,
        **kwargs,
    ):
        if system_template:
            system_instruction = system_template.format(
                python_modules=skill_sources or "",
            )
        else:
            system_instruction = ""

        if "thinking" in model_name.lower():
            # ------------------------------------------------------
            #  EXPERIMENTAL
            # ------------------------------------------------------
            system_instruction = system_instruction or thinking.SYSTEM_TEMPLATE.format(
                python_modules=skill_sources or "",
                python_packages=thinking.EXAMPLE_PYTHON_PACKAGES,
                rest_apis=thinking.EXAMPLE_REST_APIS,
            )
            execution_error_template = execution_error_template or thinking.EXECUTION_ERROR_TEMPLATE
            execution_output_template = execution_output_template or thinking.EXECUTION_OUTPUT_TEMPLATE
        else:
            system_instruction = system_instruction or default.SYSTEM_TEMPLATE.format(
                python_modules=skill_sources or "",
            )
            execution_error_template = execution_error_template or default.EXECUTION_ERROR_TEMPLATE
            execution_output_template = execution_output_template or default.EXECUTION_OUTPUT_TEMPLATE

        super().__init__(
            model_name=model_name,
            execution_output_template=execution_output_template,
            execution_error_template=execution_error_template,
            system_instruction=system_instruction,
            api_key=api_key or os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY"),
            **kwargs,
        )

    def extract_code(self, response: LiteLLMResponse):
        """Extracts all Python code blocks from `response.text` and joins them by empty lines."""
        pattern = r"```(?:python|tool_code|tool)\s*(.*?)(?:\s*```|\s*$)"
        blocks = code_blocks(response.text, pattern=pattern)
        return "\n\n".join(blocks) if blocks else None
