import json
from abc import abstractmethod
from dataclasses import dataclass
from typing import Any, AsyncIterator

import litellm

# from litellm import CustomStreamWrapper, Message, ModelResponse, acompletion
from freeact.model.base import CodeActModel, CodeActModelResponse, CodeActModelTurn
from freeact.model.litellm.utils import code_block, sanitize_tool_name, tool_name


@dataclass
class ToolUse:
    id: str
    name: str
    input: dict[str, Any]


@dataclass
class LiteLLMResponse(CodeActModelResponse):
    tool_use: ToolUse | None = None
    code: str | None = None

    @property
    def tool_use_id(self) -> str | None:
        return self.tool_use.id if self.tool_use else None

    @property
    def tool_use_name(self) -> str | None:
        return self.tool_use.name if self.tool_use else None


class LiteLLMTurn(CodeActModelTurn):
    def __init__(self, iter: AsyncIterator[str | LiteLLMResponse]):
        self._iter = iter
        self._response: LiteLLMResponse | None = None

    async def response(self) -> LiteLLMResponse:
        if self._response is None:
            async for _ in self.stream():
                pass
        return self._response  # type: ignore

    async def stream(self) -> AsyncIterator[str]:
        async for elem in self._iter:
            match elem:
                case str():
                    yield elem
                case LiteLLMResponse() as msg:
                    self._response = msg


Content = str | list[dict[str, Any]]


class LiteLLMBase(CodeActModel):
    """Base class for all code action models in `freeact`.

    It uses [LiteLLM](https://www.litellm.ai/) for model access and cost tracking. It tracks
    conversation state in the `history` attribute. Subclasses must implement the
    [extract_code][freeact.model.litellm.model.LiteLLMBase.extract_code] method for extracting
    code from a [LiteLLMResponse][freeact.model.litellm.model.LiteLLMResponse].

    Args:
        model_name: The LiteLLM-specific name of the model.
        system_instruction: A system instruction that guides the model to generate code actions.
        tools: A list of [tool definitions](https://platform.openai.com/docs/guides/function-calling#defining-functions).
            Some implementation classes use tools for passing code actions as argument
            while others include code actions directly in their response text.
        **kwargs: Default completion kwargs used for
            [`request`][freeact.model.litellm.model.LiteLLMBase.request] and
            [`feedback`][freeact.model.litellm.model.LiteLLMBase.feedback] calls.
            These are merged with `request` and `feedback` specific completion kwargs
            where the latter have higher priority in case of conflicting keys.


    Attributes:
        history: List of conversation messages. User messages are either actual user queries
            sent via the `request` method or code execution results sent via the `feedback`
            method.
    """

    def __init__(
        self,
        model_name: str,
        system_instruction: Content | None = None,
        tools: list[dict[str, Any]] | None = None,
        stream: bool = True,
        **kwargs,
    ):
        self.model_name = model_name
        self.completion_kwargs = kwargs
        self.stream = stream

        self.tools = tools or []
        self.tool_names = [tool_name(tool) for tool in self.tools]

        self.history: list[dict[str, Any]] = []

        if system_instruction:
            self.history.append({"role": "system", "content": system_instruction})

    def request(
        self,
        user_query: str,
        **kwargs,
    ) -> LiteLLMTurn:
        """Constructs a new message with role `user` and content `user_query`
        and returns a [LiteLLMTurn][freeact.model.litellm.model.LiteLLMTurn].
        After the turn is consumed, the user message and assistant message are
        added to the model's conversation `history`.

        Args:
            user_query: The user's input query or request.
            **kwargs: Completion kwargs supported by LiteLLM.

        Returns:
            LiteLLMTurn: Represents a single user interaction.
        """
        user_message = {"role": "user", "content": user_query}
        return LiteLLMTurn(self._handle(user_message, **kwargs))

    def feedback(
        self,
        feedback: str,
        is_error: bool,
        tool_use_id: str | None,
        tool_use_name: str | None,
        **kwargs,
    ) -> LiteLLMTurn:
        """Constructs a new message with role `tool` if `tool_use_id` is defined,
        or with role `user` otherwise. Message content is `feedback`. It returns
        a [LiteLLMTurn][freeact.model.litellm.model.LiteLLMTurn]. After the turn
        is consumed, the input message and assistant message are added to the model's
        conversation `history`.

        Args:
            feedback (str): The feedback text from code execution.
            is_error (bool): Whether the feedback represents an error condition.
            tool_use_id (str | None): Identifier for the specific tool use instance.
            tool_use_name (str | None): Name of the tool that was used.
            **kwargs: Completion kwargs supported by LiteLLM.

        Returns:
            LiteLLMTurn: Represents a feedback interaction with the model where `feedback`
                is submitted by a `freeact` [agent][freeact.agent.CodeActAgent].
        """
        if tool_use_id is not None:
            feedback_message = {
                "role": "tool",
                "tool_call_id": tool_use_id,
                "content": feedback,
            }
        else:
            feedback_message = {
                "role": "user",
                "content": feedback,
            }

        return LiteLLMTurn(self._handle(feedback_message, **kwargs))

    async def _handle(self, input_message: dict[str, Any], **kwargs) -> AsyncIterator[str | LiteLLMResponse]:
        messages = self.history + [input_message]
        response = LiteLLMResponse(text="", is_error=False)

        result = await litellm.acompletion(
            model=self.model_name,
            messages=messages,
            stream=self.stream,
            stream_options={"include_usage": True},
            tools=self.tools if self.tools else None,
            **(self.completion_kwargs | kwargs),
        )

        if self.stream:
            iter = self._handle_stream_result(result, messages)
        else:
            iter = self._handle_batch_result(result)

        result_message: litellm.Message

        async for elem in iter:
            match elem:
                case str():
                    yield elem
                case litellm.Message():
                    result_message = elem

        assistant_message: dict[str, Any] = {
            "role": "assistant",
        }

        if content := self._extract_content(result_message):
            response.text = result_message.content
            assistant_message["content"] = content

        if result_message.tool_calls:
            tool_call = result_message.tool_calls[0]
            tool_name = sanitize_tool_name(tool_call.function.name)

            if tool_name not in self.tool_names:
                allowed_tool_names = ", ".join(self.tool_names)
                response.is_error = True
                response.text = f"Invalid tool name: {tool_name}\nAllowed tool names are: {allowed_tool_names}"

            try:
                tool_input = json.loads(tool_call.function.arguments)
            except json.JSONDecodeError:
                tool_input = {}
                response.is_error = True
                response.text = f"Could not decode tool input: {tool_call.function.arguments}"

            response.tool_use = ToolUse(
                id=tool_call.id,
                name=tool_name,
                input=tool_input,
            )

            assistant_message["tool_calls"] = [
                {
                    "id": tool_call.id,
                    "type": "function",
                    "function": {
                        "name": tool_name,
                        "arguments": tool_call.function.arguments,
                    },
                }
            ]

        if not response.is_error:
            response.code = self.extract_code(response)

        self.history.append(input_message)
        self.history.append(assistant_message)

        yield response

    async def _handle_stream_result(
        self, result: litellm.CustomStreamWrapper, messages
    ) -> AsyncIterator[str | litellm.Message]:
        chunks = []
        think = False

        async for chunk in result:
            chunks.append(chunk)
            delta = chunk.choices[0].delta

            if hasattr(delta, "reasoning_content") and delta.reasoning_content:
                if not think:
                    think = True
                    yield "<think>\n"
                yield delta.reasoning_content

            if hasattr(delta, "content") and delta.content:
                if think:
                    think = False
                    yield "\n</think>\n\n"
                yield delta.content

        result = litellm.stream_chunk_builder(chunks, messages=messages)
        result_message = result.choices[0].message

        yield result_message

    async def _handle_batch_result(self, result: litellm.ModelResponse) -> AsyncIterator[str | litellm.Message]:
        result_message = result.choices[0].message

        if hasattr(result_message, "reasoning_content") and result_message.reasoning_content:
            yield f"<think>\n{result_message.reasoning_content}\n</think>\n\n"

        if hasattr(result_message, "content") and result_message.content:
            yield result_message.content

        yield result_message

    def _extract_content(self, response: litellm.Message) -> str | list[dict[str, Any]]:
        return response.content

    @abstractmethod
    def extract_code(self, response: LiteLLMResponse) -> str | None:
        """Extracts Python code from the response."""
        pass


class LiteLLM(LiteLLMBase):
    """
    A default implementation of `LiteLLMBase` that

    - formats code execution feedback based on provided output and error templates.
    - implements [extract_code][freeact.model.litellm.model.LiteLLM.extract_code]
      by extracting the first Python code block from the response text.

    Args:
        model_name: The LiteLLM-specific name of the model.
        execution_output_template: A template for formatting successful code execution output.
            Must define a`{execution_feedback}` placeholder.
        execution_error_template: A template for formatting code execution errors.
            Must define a `{execution_feedback}` placeholder.
        system_instruction: A system instruction that guides the model to generate code actions.
        tools: A list of [tool definitions](https://platform.openai.com/docs/guides/function-calling#defining-functions).
            Some implementation classes use tools for passing code actions as argument
            while others include code actions directly in their response text.
        **kwargs: Default completion kwargs used for
            [`request`][freeact.model.litellm.model.LiteLLMBase.request] and
            [`feedback`][freeact.model.litellm.model.LiteLLMBase.feedback] calls.
            These are merged with `request` and `feedback` specific completion kwargs
            where the latter have higher priority in case of conflicting keys.
    """

    def __init__(
        self,
        model_name: str,
        execution_output_template: str,
        execution_error_template: str,
        system_instruction: str | list[dict[str, Any]] | None = None,
        tools: list[dict[str, Any]] | None = None,
        **kwargs,
    ):
        super().__init__(
            model_name=model_name,
            system_instruction=system_instruction,
            tools=tools,
            **kwargs,
        )
        self.execution_output_template = execution_output_template
        self.execution_error_template = execution_error_template

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
        """Extracts the first Python code block from `response.text`.

        **Override this method to customize extraction logic.**
        """
        return code_block(response.text, 0)
