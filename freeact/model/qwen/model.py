import os

from freeact.model.litellm.model import LiteLLM
from freeact.model.qwen.prompt import EXECUTION_ERROR_TEMPLATE, EXECUTION_OUTPUT_TEMPLATE, SYSTEM_TEMPLATE


class QwenCoder(LiteLLM):
    """Code action model class for Qwen 2.5 Coder.

    Args:
        model_name: The LiteLLM-specific name of the model.
        skill_sources: Skill modules source code to be included into `system_template`.
        system_template: Prompt template for the system message that guides the model to generate code actions.
            Must define a `{python_modules}` placeholder for the `skill_sources`.
        execution_output_template: A template for formatting successful code execution output.
            Must define an `{execution_feedback}` placeholder.
        execution_error_template: A template for formatting code execution errors.
            Must define an `{execution_feedback}` placeholder.
        api_key: Provider-specific API key. If not provided, reads from `QWEN_API_KEY` environment variable.
        **kwargs: Default completion kwargs passed used for
            [`request`][freeact.model.base.CodeActModel.request] and
            [`feedback`][freeact.model.base.CodeActModel.feedback] calls.
            These are overriden by `request` and `feedback` specific kwargs.
    """

    def __init__(
        self,
        model_name: str,
        skill_sources: str | None = None,
        system_template: str = SYSTEM_TEMPLATE,
        execution_output_template: str = EXECUTION_OUTPUT_TEMPLATE,
        execution_error_template: str = EXECUTION_ERROR_TEMPLATE,
        api_key: str | None = None,
        **kwargs,
    ):
        # Qwen 2.5 Coder models often hallucinate results prior
        # to code execution which is prevented by stopping at the
        # beginning of an ```output ...``` block. Also, Qwen Coder
        # models on Fireworks AI sometimes leak <|im_start|> tokens
        # after generating code blocks.
        default_kwargs = {
            "stop": ["```output", "<|im_start|>"],
        }

        super().__init__(
            model_name=model_name,
            execution_output_template=execution_output_template,
            execution_error_template=execution_error_template,
            system_instruction=system_template.format(python_modules=skill_sources or ""),
            api_key=api_key or os.getenv("QWEN_API_KEY"),
            **(default_kwargs | kwargs),
        )
