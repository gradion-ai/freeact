import os
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
        model_name: str,
        api_key: str | None = None,
        base_url: str | None = None,
        skill_sources: str | None = None,
        system_template: str = SYSTEM_TEMPLATE,
        execution_output_template: str = EXECUTION_OUTPUT_TEMPLATE,
        execution_error_template: str = EXECUTION_ERROR_TEMPLATE,
        # qwen coder 2.5 models sometimes leak <|im_start|>, so we stop here too
        run_kwargs: Dict[str, Any] | None = {"stop": ["```output", "<|im_start|>"]},
        **kwargs,
    ):
        super().__init__(
            model_name=model_name,
            api_key=api_key or os.getenv("QWEN_API_KEY"),
            base_url=base_url or os.getenv("QWEN_BASE_URL"),
            system_message=system_template.format(python_modules=skill_sources or ""),
            execution_output_template=execution_output_template,
            execution_error_template=execution_error_template,
            run_kwargs=run_kwargs,
            **kwargs,
        )
