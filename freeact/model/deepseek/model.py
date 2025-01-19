import os
from typing import Any, Dict

from freeact.model.generic.model import GenericModel
from freeact.model.qwen.prompt import (
    EXECUTION_ERROR_TEMPLATE,
    EXECUTION_OUTPUT_TEMPLATE,
    SYSTEM_TEMPLATE,
)


class DeepSeek(GenericModel):
    """A specialized implementation of `GenericModel` for DeepSeek's models.

    This class configures `GenericModel` specifically for use with DeepSeek V3 models
    and uses the same prompt templates as Qwen 2.5 Coder.
    It has been tested with *DeepSeek V3*. Smaller models
    in this series may require adjustments to the prompt templates.

    Args:
        model_name: The provider-specific name of the DeepSeek model to use.
        api_key: Optional API key for DeepSeek. If not provided, reads from DEEPSEEK_API_KEY environment variable.
        base_url: Optional base URL for the API. If not provided, reads from DEEPSEEK_BASE_URL environment variable.
        skill_sources: Optional string containing Python skill module information to include in system template.
        system_template: Prompt template for the system message that guides the model to generate code actions.
            Must define a `{python_modules}` placeholder for the skill sources.
        execution_output_template: Prompt template for formatting execution outputs.
            Must define an `{execution_feedback}` placeholder.
        execution_error_template: Prompt template for formatting execution errors.
            Must define an `{execution_feedback}` placeholder.
        run_kwargs: Optional dictionary of additional arguments passed to the model's
            [`request`][freeact.model.base.CodeActModel.request] and
            [`feedback`][freeact.model.base.CodeActModel.feedback] methods.
        **kwargs: Additional keyword arguments passed to the `GenericModel` constructor.
    """

    def __init__(
        self,
        model_name: str,
        api_key: str | None = None,
        base_url: str | None = None,
        skill_sources: str | None = None,
        system_template: str = SYSTEM_TEMPLATE,
        execution_output_template: str = EXECUTION_OUTPUT_TEMPLATE,
        execution_error_template: str = EXECUTION_ERROR_TEMPLATE,
        run_kwargs: Dict[str, Any] | None = None,
        **kwargs,
    ):
        super().__init__(
            model_name=model_name,
            api_key=api_key or os.getenv("DEEPSEEK_API_KEY"),
            base_url=base_url or os.getenv("DEEPSEEK_BASE_URL"),
            system_message=system_template.format(python_modules=skill_sources or ""),
            execution_output_template=execution_output_template,
            execution_error_template=execution_error_template,
            run_kwargs=run_kwargs,
            **kwargs,
        )
