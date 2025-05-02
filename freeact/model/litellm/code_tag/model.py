import re

from freeact.model.litellm.base.model import LiteLLMBase, LiteLLMResponse, LiteLLMTurn


class LiteLLM(LiteLLMBase):
    def __init__(self, model_name: str, system_instruction: str, **kwargs):
        super().__init__(model_name=model_name, system_instruction=system_instruction, **kwargs)

    def feedback(
        self,
        feedback: str,
        is_error: bool,
        tool_use_id: str | None,
        tool_use_name: str | None,
        **kwargs,
    ) -> LiteLLMTurn:
        feedback_template = self.execution_output_template if not is_error else self.execution_error_template
        feedback_content = feedback_template.format(execution_feedback=feedback)
        return super().feedback(feedback_content, is_error, tool_use_id, tool_use_name, **kwargs)

    def extract_code(self, response: LiteLLMResponse) -> str | None:
        return code_block(response.text, 0)


def code_block(text: str, index: int, **kwargs) -> str | None:
    """Finds the `index`-th block matching `pattern` in `text`."""
    blocks = code_blocks(text, **kwargs)
    return blocks[index] if blocks else None


def code_blocks(text: str, pattern: str = r"```python\n(.*?)```") -> list[str]:
    """Finds all blocks matching `pattern` in `text`."""
    blocks = re.findall(pattern, text, re.DOTALL)
    return [block.strip() for block in blocks]
