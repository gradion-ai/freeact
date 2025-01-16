from typing import Any, Dict

from freeact.model.generic.model import OpenAIClient
from freeact.model.qwen.prompt import (
    EXECUTION_ERROR_TEMPLATE,
    EXECUTION_OUTPUT_TEMPLATE,
    SYSTEM_TEMPLATE,
)


class QwenCoder(OpenAIClient):
    def __init__(
        self,
        api_key: str,
        base_url: str,
        model_name: str,
        skill_sources: str | None = None,
        system_template: str = SYSTEM_TEMPLATE,
        execution_output_template: str = EXECUTION_OUTPUT_TEMPLATE,
        execution_error_template: str = EXECUTION_ERROR_TEMPLATE,
        run_kwargs: Dict[str, Any] | None = {"stop": ["```output", "<|im_start|>"]},
        **kwargs,
    ):
        super().__init__(
            base_url=base_url,
            api_key=api_key,
            model_name=model_name,
            system_message=system_template.format(python_modules=skill_sources or ""),
            execution_output_template=execution_output_template,
            execution_error_template=execution_error_template,
            run_kwargs=run_kwargs,
            **kwargs,
        )
