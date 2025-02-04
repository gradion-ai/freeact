import os
from typing import Any, Dict

from freeact.model.deepseek.prompt import r1, v3
from freeact.model.generic.model import GenericModel, GenericModelTurn


class DeepSeekV3(GenericModel):
    """A specialized implementation of `GenericModel` for DeepSeek V3.

    Args:
        model_name: The provider-specific name of the DeepSeek model to use.
        api_key: Optional API key for DeepSeek. If not provided, reads from DEEPSEEK_API_KEY environment variable.
        base_url: Optional base URL for the API. If not provided, reads from DEEPSEEK_BASE_URL environment variable.
        skill_sources: Optional string containing Python skill module information to include in system template.
        system_extension: System message extension for domain- or environment-specific instructions.
        system_template: Prompt template for the system message that guides the model to generate code actions.
            Must define a `{python_modules}` placeholder for the `skill_sources`.
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
        system_extension: str | None = None,
        system_template: str = v3.SYSTEM_TEMPLATE,
        execution_output_template: str = v3.EXECUTION_OUTPUT_TEMPLATE,
        execution_error_template: str = v3.EXECUTION_ERROR_TEMPLATE,
        run_kwargs: Dict[str, Any] | None = None,
        **kwargs,
    ):
        format_kwargs = {
            "python_modules": skill_sources or "",
        }

        if "{extensions}" in system_template:
            format_kwargs["extensions"] = system_extension or ""

        super().__init__(
            model_name=model_name,
            api_key=api_key or os.getenv("DEEPSEEK_API_KEY"),
            base_url=base_url or os.getenv("DEEPSEEK_BASE_URL"),
            execution_output_template=execution_output_template,
            execution_error_template=execution_error_template,
            system_message=system_template.format(**format_kwargs),
            run_kwargs=run_kwargs,
            **kwargs,
        )


class DeepSeekR1(GenericModel):
    """A specialized implementation of `GenericModel` for DeepSeek R1.

    Args:
        model_name: The provider-specific name of the DeepSeek model to use.
        api_key: Optional API key for DeepSeek. If not provided, reads from DEEPSEEK_API_KEY environment variable.
        base_url: Optional base URL for the API. If not provided, reads from DEEPSEEK_BASE_URL environment variable.
        skill_sources: Optional string containing Python skill module information to include in system template.
        instruction_extension: Domain- or environment-specific extensions to the `instruction_template`.
        instruction_template: Prompt template that guides the model to generate code actions.
            Must define a `{user_query}` placeholder for the user query, an `{extensions}`
            placeholder for the `instruction_extension` and a `{python_modules}` placeholder
            for the `skill_sources`.
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
        instruction_extension: str | None = r1.EXAMPLE_EXTENSION,
        instruction_template: str = r1.INSTRUCTION_TEMPLATE,
        execution_output_template: str = r1.EXECUTION_OUTPUT_TEMPLATE,
        execution_error_template: str = r1.EXECUTION_ERROR_TEMPLATE,
        run_kwargs: Dict[str, Any] | None = {
            "temperature": 0.6,
            "max_tokens": 8192,
        },
        **kwargs,
    ):
        self.instruction_template = instruction_template
        self.instruction_kwargs = {
            "python_modules": skill_sources or "",
            "extensions": instruction_extension or "",
        }

        super().__init__(
            model_name=model_name,
            api_key=api_key or os.getenv("DEEPSEEK_API_KEY"),
            base_url=base_url or os.getenv("DEEPSEEK_BASE_URL"),
            execution_output_template=execution_output_template,
            execution_error_template=execution_error_template,
            system_message=None,
            run_kwargs=run_kwargs,
            **kwargs,
        )

    def request(self, user_query: str, **kwargs) -> GenericModelTurn:
        if not self._history:
            # The very first user message in a conversation contains the main
            # instructions (DeepSeek-R1 doesn't work well with system messages)
            content = self.instruction_template.format(user_query=user_query, **self.instruction_kwargs)
        else:
            content = user_query
        user_message = {"role": "user", "content": content}
        return GenericModelTurn(self._stream(user_message, **(self.run_kwargs | kwargs)))
