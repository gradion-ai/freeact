from dataclasses import dataclass
from pathlib import Path
from typing import Any, AsyncIterator, List, Literal

from anthropic import AsyncAnthropic, ContentBlockStopEvent, InputJsonEvent, TextEvent
from anthropic.types import TextBlock, ToolUseBlock

from gradion_incubator.codeact.model.base import AssistantMessage, CodeActModel
from gradion_incubator.codeact.model.claude.prompt import (
    EXECUTION_ERROR_TEMPLATE,
    EXECUTION_OUTPUT_TEMPLATE,
    SYSTEM_TEMPLATE,
    USER_QUERY_TEMPLATE,
)
from gradion_incubator.codeact.model.claude.tools import CODE_EDITOR_TOOL, CODE_EXECUTOR_TOOL, TOOLS
from gradion_incubator.logger import Logger


@dataclass
class ToolUse:
    id: str
    name: str
    input: dict[str, Any]


@dataclass
class ClaudeMessage(AssistantMessage):
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


ClaudeModelName = Literal["claude-3-5-haiku-20241022", "claude-3-5-sonnet-20241022"]


class ClaudeCodeActModel(CodeActModel):
    def __init__(
        self,
        logger: Logger,
        model_name: ClaudeModelName,
        prompt_caching: bool = False,
        python_files: List[Path] | None = None,
    ):
        self.logger = logger
        self.model_name = model_name
        self.python_files = [] if python_files is None else python_files

        self.prompt_caching = prompt_caching

        # --------------------------------------
        #  TODO: render python files on request
        # --------------------------------------
        self.system_prompt = self._format_system_prompt()

        self.history = []  # type: ignore
        self.client = AsyncAnthropic(
            default_headers={
                "anthropic-beta": "prompt-caching-2024-07-31",
            }
            if prompt_caching
            else None,
        )

    async def stream_request(
        self,
        user_query: str,
        **kwargs,
    ) -> AsyncIterator[str | AssistantMessage]:
        content = USER_QUERY_TEMPLATE.format(user_query=user_query)
        message = {"role": "user", "content": content}

        async with self.logger.context("request"):
            await self.logger.log(content)

        async for elem in self._stream(message, **kwargs):
            yield elem

    async def stream_feedback(
        self,
        feedback: str,
        is_error: bool,
        tool_use_id: str | None,
        tool_use_name: str | None,
        **kwargs,
    ) -> AsyncIterator[str | AssistantMessage]:
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

        async with self.logger.context("request"):
            await self.logger.log(content)

        async for elem in self._stream(message, **kwargs):
            yield elem

    async def _stream(
        self,
        user_message,
        max_tokens: int = 4096,
        temperature: float = 0.0,
    ):
        system_blocks: list[dict[str, Any]] = [
            {
                "type": "text",
                "text": self.system_prompt,
            }
        ]

        if self.prompt_caching:
            system_blocks[0]["cache_control"] = {"type": "ephemeral"}

        assistant_blocks = []
        assistant_message = ClaudeMessage(content="")

        messages = self.history + [user_message]

        self.client.messages.create

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
                        assistant_message.content = text
                    case ContentBlockStopEvent(content_block=ToolUseBlock(id=_id, input=_input, name=_name)):
                        assistant_blocks.append({"type": "tool_use", "id": _id, "input": _input, "name": _name})
                        assistant_message.tool_use = ToolUse(id=_id, input=_input, name=_name)

            message = await stream.get_final_message()

        if assistant_message.code is not None:
            yield "\n\n" + assistant_message.code

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
            log_message = assistant_message.content

            if assistant_message.code:
                log_message += f"\n\n```python\n{assistant_message.code}\n```\n"

            await self.logger.log(log_message, metadata=response_metadata)

        yield assistant_message

    def _format_system_prompt(self) -> str:
        content = []

        for file in self.python_files if self.python_files else []:
            code = file.read_text()
            content.append(f"```python\n# file: {file}\n\n{code}\n```")

        return SYSTEM_TEMPLATE.format(python_files="\n\n".join(content))
