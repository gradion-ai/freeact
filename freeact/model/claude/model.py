from dataclasses import dataclass
from typing import Any, AsyncIterator, List, Literal

from anthropic import AsyncAnthropic, ContentBlockStopEvent, InputJsonEvent, TextEvent
from anthropic.types import TextBlock, ToolUseBlock

from freeact.logger import Logger
from freeact.model.base import CodeActModel, CodeActModelCall, CodeActModelResponse
from freeact.model.claude.prompt import (
    EXECUTION_ERROR_TEMPLATE,
    EXECUTION_OUTPUT_TEMPLATE,
    SYSTEM_TEMPLATE,
    USER_QUERY_TEMPLATE,
)
from freeact.model.claude.tools import CODE_EDITOR_TOOL, CODE_EXECUTOR_TOOL, TOOLS
from freeact.skills import SkillInfo

ClaudeModelName = Literal[
    "claude-3-5-haiku-20241022",
    "claude-3-5-sonnet-20241022",
]


@dataclass
class ToolUse:
    id: str
    name: str
    input: dict[str, Any]


@dataclass
class ClaudeResponse(CodeActModelResponse):
    tool_use: ToolUse | None = None

    @property
    def tool_use_id(self) -> str | None:
        return self.tool_use.id if self.tool_use else None

    @property
    def tool_use_name(self) -> str | None:
        return self.tool_use.name if self.tool_use else None

    @property
    def code(self) -> str | None:
        if self.tool_use_name == CODE_EXECUTOR_TOOL["name"]:
            return self.tool_use.input["code"]  # type: ignore
        elif self.tool_use_name == CODE_EDITOR_TOOL["name"]:
            return f"file_editor(**{self.tool_use.input})"  # type: ignore
        else:
            return None


class ClaudeCall(CodeActModelCall):
    def __init__(self, iter: AsyncIterator[str | ClaudeResponse]):
        self._iter = iter
        self._response: ClaudeResponse | None = None

    async def response(self) -> ClaudeResponse:
        if self._response is None:
            async for _ in self.stream():
                pass
        return self._response  # type: ignore

    async def stream(self):
        async for elem in self._iter:
            match elem:
                case str():
                    yield elem
                case ClaudeResponse() as msg:
                    self._response = msg


class Claude(CodeActModel):
    def __init__(
        self,
        logger: Logger,
        model_name: ClaudeModelName,
        prompt_caching: bool = False,
    ):
        self.logger = logger
        self.model_name = model_name
        self.prompt_caching = prompt_caching

        self.history = []  # type: ignore
        self.client = AsyncAnthropic(
            default_headers={
                "anthropic-beta": "prompt-caching-2024-07-31",
            }
            if prompt_caching
            else None,
        )

    def request(
        self,
        user_query: str,
        skill_infos: List[SkillInfo],
        **kwargs,
    ) -> ClaudeCall:
        content = USER_QUERY_TEMPLATE.format(user_query=user_query)
        message = {"role": "user", "content": content}

        return ClaudeCall(self._stream(message, content, skill_infos=skill_infos, **kwargs))

    def feedback(
        self,
        feedback: str,
        is_error: bool,
        tool_use_id: str | None,
        tool_use_name: str | None,
        **kwargs,
    ) -> ClaudeCall:
        template = EXECUTION_ERROR_TEMPLATE if is_error else EXECUTION_OUTPUT_TEMPLATE

        if tool_use_name == CODE_EXECUTOR_TOOL["name"]:
            content = template.format(execution_feedback=feedback)
        elif tool_use_name == CODE_EDITOR_TOOL["name"]:
            content = feedback
        else:
            raise ValueError(f"Invalid tool_use_name: {tool_use_name}")

        message = {
            "role": "user",
            "content": [
                {
                    "type": "tool_result",
                    "tool_use_id": tool_use_id,
                    "content": content,
                    "is_error": is_error,
                },
            ],
        }

        return ClaudeCall(self._stream(message, content, **kwargs))

    async def _stream(
        self,
        user_message,
        user_message_content,
        skill_infos: List[SkillInfo],
        temperature: float = 0.0,
        max_tokens: int = 4096,
    ) -> AsyncIterator[str | ClaudeResponse]:
        async with self.logger.context("request"):
            await self.logger.log(user_message_content)

        system_blocks: list[dict[str, Any]] = [
            {
                "type": "text",
                "text": self._format_system_message(skill_infos),
            }
        ]

        if self.prompt_caching:
            system_blocks[0]["cache_control"] = {"type": "ephemeral"}

        assistant_blocks = []
        assistant_message = ClaudeResponse(text="")

        messages = self.history + [user_message]

        async with self.client.messages.stream(
            model=self.model_name,
            max_tokens=max_tokens,
            temperature=temperature,
            system=system_blocks,
            messages=messages,
            tools=TOOLS,
            tool_choice={
                "type": "auto",
                "disable_parallel_tool_use": True,
            },
        ) as stream:
            async for event in stream:
                match event:
                    case TextEvent(text=chunk):
                        yield chunk
                    case InputJsonEvent(partial_json=chunk):
                        pass  # `yield chunk` delays until message is complete
                    case ContentBlockStopEvent(content_block=TextBlock(text=text)) if text.strip():
                        assistant_blocks.append({"type": "text", "text": text})
                        assistant_message.text = text
                    case ContentBlockStopEvent(content_block=ToolUseBlock(id=_id, input=_input, name=_name)):
                        assistant_blocks.append({"type": "tool_use", "id": _id, "input": _input, "name": _name})
                        assistant_message.tool_use = ToolUse(id=_id, input=_input, name=_name)

        message = await stream.get_final_message()

        self.history.append(user_message)
        self.history.append({"role": "assistant", "content": assistant_blocks})

        response_metadata = {
            "input_tokens": message.usage.input_tokens,
            "output_tokens": message.usage.output_tokens,
        }

        if hasattr(message.usage, "cache_creation_input_tokens"):
            response_metadata["cache_creation_input_tokens"] = message.usage.cache_creation_input_tokens
        if hasattr(message.usage, "cache_read_input_tokens"):
            response_metadata["cache_read_input_tokens"] = message.usage.cache_read_input_tokens

        async with self.logger.context("response"):
            log_message = assistant_message.text

            if assistant_message.code:
                log_message += f"\n\n```python\n{assistant_message.code}\n```\n"

            await self.logger.log(log_message, metadata=response_metadata)

        yield assistant_message

    @staticmethod
    def _format_system_message(skill_infos: List[SkillInfo]) -> str:
        content = []

        for info in skill_infos:
            content.append(f"```python\n# file: {info.relative_path}\n\n{info.source}\n```")

        return SYSTEM_TEMPLATE.format(python_files="\n\n".join(content))
