import re
from dataclasses import dataclass
from typing import Any, AsyncIterator, Literal

from anthropic import AsyncAnthropic, ContentBlockStopEvent, InputJsonEvent, TextEvent
from anthropic.types import TextBlock, ToolUseBlock

from freeact.logger import Logger
from freeact.model.base import CodeActModel, CodeActModelResponse, CodeActModelTurn, StreamRetry
from freeact.model.claude.prompt import (
    EXECUTION_ERROR_TEMPLATE,
    EXECUTION_OUTPUT_TEMPLATE,
    MODULES_ACK_MESSAGE,
    MODULES_INFO_TEMPLATE,
    SYSTEM_TEMPLATE,
    USER_QUERY_TEMPLATE,
)
from freeact.model.claude.retry import WaitExponential, WaitStrategy, retry
from freeact.model.claude.tools import CODE_EDITOR_TOOL, CODE_EXECUTOR_TOOL, TOOLS

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
            return f"print(file_editor(**{self.tool_use.input}))"  # type: ignore
        else:
            return None


class ClaudeTurn(CodeActModelTurn):
    def __init__(self, iter: AsyncIterator[str | ClaudeResponse | StreamRetry]):
        self._iter = iter
        self._response: ClaudeResponse | None = None

    async def response(self) -> ClaudeResponse:
        if self._response is None:
            async for _ in self.stream():
                pass
        return self._response  # type: ignore

    async def stream(self, emit_retry: bool = False) -> AsyncIterator[str | StreamRetry]:
        async for elem in self._iter:
            match elem:
                case str():
                    yield elem
                case StreamRetry() as stream_retry:
                    if emit_retry:
                        yield stream_retry
                case ClaudeResponse() as msg:
                    self._response = msg


class Claude(CodeActModel):
    """A `CodeActModel` implementation based on Anthropic's Claude API.

    Args:
        logger: Logger instance for logging requests and responses.
        model_name: Name of the Claude model to use (e.g., "claude-3-5-sonnet-20241022").
        prompt_caching: Whether to enable prompt caching. Defaults to False.
        system_extension: Additional system prompt text. Defaults to None.
        system_message: Complete system message to override default. Defaults to None.
        retry_max_attempts: Maximum number of retry attempts. Defaults to 10.
    """

    def __init__(
        self,
        logger: Logger,
        model_name: ClaudeModelName,
        prompt_caching: bool = False,
        system_extension: str | None = None,
        system_message: str | None = None,
        retry_max_attempts: int = 10,
        retry_wait_strategy: WaitStrategy = WaitExponential(multiplier=1, max=10, exp_base=2),
    ):
        if system_message and system_extension:
            raise ValueError("If system_message is provided, system_extension must be None")

        if system_message:
            self.system_message = system_message
        else:
            self.system_message = SYSTEM_TEMPLATE.format(extensions=system_extension or "")

        self.logger = logger
        self.model_name = model_name
        self.prompt_caching = prompt_caching

        self._history = []  # type: ignore
        self._tool_names = [t["name"] for t in TOOLS]

        self._client = AsyncAnthropic(
            default_headers={
                "anthropic-beta": "prompt-caching-2024-07-31",
            }
            if prompt_caching
            else None,
        )
        self._retry_max_attempts = retry_max_attempts
        self._retry_wait_strategy = retry_wait_strategy

    def request(
        self,
        user_query: str,
        skill_sources: str | None = None,
        **kwargs,
    ) -> ClaudeTurn:
        modules_info_block = [
            {
                "type": "text",
                "text": MODULES_INFO_TEMPLATE.format(python_modules=skill_sources or ""),
            },
        ]
        modules_info_message = {"role": "user", "content": modules_info_block}
        modules_ack_message = {"role": "assistant", "content": MODULES_ACK_MESSAGE}

        if self.prompt_caching:
            modules_info_block[0]["cache_control"] = {"type": "ephemeral"}  # type: ignore

        if len(self._history) == 0:
            self._history.append(modules_info_message)
            self._history.append(modules_ack_message)
        else:
            self._history[0] = modules_info_message
            self._history[1] = modules_ack_message

        content = USER_QUERY_TEMPLATE.format(user_query=user_query)
        message = {"role": "user", "content": content}

        return ClaudeTurn(
            retry(
                lambda: self._stream(message, content, **kwargs),
                self.logger,
                self._retry_max_attempts,
                self._retry_wait_strategy,
            )
        )

    def feedback(
        self,
        feedback: str,
        is_error: bool,
        tool_use_id: str | None,
        tool_use_name: str | None,
        skill_sources: str | None = None,
        **kwargs,
    ) -> ClaudeTurn:
        if tool_use_name == CODE_EXECUTOR_TOOL["name"]:
            template = EXECUTION_ERROR_TEMPLATE if is_error else EXECUTION_OUTPUT_TEMPLATE
            content = template.format(execution_feedback=feedback)
        else:
            content = feedback

        if tool_use_id is not None:
            content = [  # type: ignore
                {
                    "type": "tool_result",
                    "tool_use_id": tool_use_id,
                    "content": content,
                    "is_error": is_error,
                },
            ]

        message = {
            "role": "user",
            "content": content,
        }

        return ClaudeTurn(
            retry(
                lambda: self._stream(message, content, **kwargs),
                self.logger,
                self._retry_max_attempts,
                self._retry_wait_strategy,
            )
        )

    async def _stream(
        self,
        user_message,
        user_message_content,
        temperature: float = 0.0,
        max_tokens: int = 4096,
    ) -> AsyncIterator[str | ClaudeResponse]:
        async with self.logger.context("request"):
            await self.logger.log(user_message_content)

        system_blocks: list[dict[str, Any]] = [
            {
                "type": "text",
                "text": self.system_message,
            }
        ]

        if self.prompt_caching:
            system_blocks[0]["cache_control"] = {"type": "ephemeral"}

        assistant_blocks = []
        assistant_message = ClaudeResponse(text="", is_error=False)

        messages = self._history + [user_message]

        async with self._client.messages.stream(
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
                        # Sanitize tool name in case of hallucinations. Adding a
                        # non-sanitized name to history will cause errors.
                        _name_sanitized = re.sub(r"[^a-zA-Z0-9_-]", "_", _name)

                        assistant_blocks.append(
                            {"type": "tool_use", "id": _id, "input": _input, "name": _name_sanitized}
                        )
                        assistant_message.tool_use = ToolUse(id=_id, input=_input, name=_name_sanitized)

                        if _name_sanitized not in self._tool_names:
                            allowed_tool_names = ", ".join(self._tool_names)  # type: ignore
                            assistant_message.text = (
                                f"Invalid tool name: {_name_sanitized}\nAllowed tool names are: {allowed_tool_names}"
                            )
                            assistant_message.is_error = True

        provider_message = await stream.get_final_message()

        response_metadata = {
            "input_tokens": provider_message.usage.input_tokens,
            "output_tokens": provider_message.usage.output_tokens,
        }

        if hasattr(provider_message.usage, "cache_creation_input_tokens"):
            response_metadata["cache_creation_input_tokens"] = provider_message.usage.cache_creation_input_tokens
        if hasattr(provider_message.usage, "cache_read_input_tokens"):
            response_metadata["cache_read_input_tokens"] = provider_message.usage.cache_read_input_tokens

        async with self.logger.context("response"):
            log_message = assistant_message.text

            if assistant_message.code:
                formatted_code = f"\n\n```python\n{assistant_message.code}\n```\n"
                log_message += formatted_code

                # Emit formmatted code when the client streams the model response.
                # In the accumulated response, `text` and `code` are separate fields.
                yield formatted_code

            await self.logger.log(log_message, metadata=response_metadata)

        self._history.append(user_message)
        self._history.append({"role": "assistant", "content": assistant_blocks})

        yield assistant_message
