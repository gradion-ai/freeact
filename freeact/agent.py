from dataclasses import dataclass
from typing import AsyncIterator

from freeact.environment import CodeExecution, CodeExecutor
from freeact.model import CodeActModel, CodeActModelResponse, CodeActModelTurn, CodeActModelUsage


class MaxStepsReached(Exception):
    """Raised when the maximum number of steps per agent
    [`run`][freeact.agent.CodeActAgent.run] is reached.
    """


@dataclass
class CodeActAgentResponse:
    """A response from an single interaction with a code action agent."""

    text: str
    """The final response text to the user."""

    usage: CodeActModelUsage
    """Accumulated model usage during this interaction."""


class CodeActAgentTurn:
    """A single interaction with the code action agent.

    An interaction consists of a sequence of model interaction and code
    execution pairs, continuing until the code action model provides a
    final response or the maximum number of steps is reached.
    """

    def __init__(self, iter: AsyncIterator[CodeActModelTurn | CodeExecution | CodeActAgentResponse]):
        self._iter = iter
        self._response: CodeActAgentResponse | None = None

    async def response(self) -> CodeActAgentResponse:
        """Retrieves the final response from the code action agent for this
        interaction. Waits until the sequence of model interactions and code
        executions is complete.

        Returns:
            The final response from the code action model as `CodeActAgentResponse`
                object.

        Raises:
            MaxStepsReached: If the interaction exceeds the maximum number of
                steps without completion.
        """
        if self._response is None:
            async for _ in self.stream():
                pass
        return self._response  # type: ignore

    async def stream(self) -> AsyncIterator[CodeActModelTurn | CodeExecution]:
        """Stream the sequence of model interaction and code execution pairs
        as they occur:

        - `CodeActModelTurn`: The current interaction with the code action model
        - `CodeExecution`: The current execution of a code action in the code
          execution environment

        The sequence continues until the model provides a final response. Once
        the stream is consumed, [`response`][freeact.agent.CodeActAgentTurn.response]
        is immediately available without waiting and contains the final response
        text and accumulated usage statistics.

        Raises:
            MaxStepsReached: If the interaction exceeds the maximum number of
                steps without completion.
        """

        async for elem in self._iter:
            match elem:
                case CodeActAgentResponse() as response:
                    self._response = response
                case _:
                    yield elem


class CodeActAgent:
    """An agent that iteratively generates and executes code actions to process user queries.

    The agent implements a loop that:

    1. Generates code actions using a [`CodeActModel`][freeact.model.base.CodeActModel]
    2. Executes the code using a [`CodeExecutor`][freeact.environment.CodeExecutor]
    3. Provides execution feedback to the [`CodeActModel`][freeact.model.base.CodeActModel]
    4. Continues until the model generates a final response.

    A single interaction with the agent is initiated with its [`run`][freeact.agent.CodeActAgent.run]
    method. The agent maintains conversational state and can have multiple interactions with the user.

    Args:
        model: Model instance for generating code actions
        executor: Executor instance for executing code actions
    """

    def __init__(self, model: CodeActModel, executor: CodeExecutor):
        self.model = model
        self.executor = executor

    def run(
        self,
        user_query: str,
        max_steps: int = 30,
        step_timeout: float = 120,
        **kwargs,
    ) -> CodeActAgentTurn:
        """Initiates an interaction with the agent from a user query. The query
        is processed through a sequence of model interaction and code execution
        steps, driven by interacting with the returned `CodeActAgentTurn` object.

        Args:
            user_query: The user query (a question, instruction, etc.)
            max_steps: Maximum number of steps before raising `MaxStepsReached`
            step_timeout: Timeout in seconds per code execution step
            **kwargs: Additional keyword arguments passed to the model

        Returns:
            CodeActAgentTurn: An object for retrieving the agent's processing steps
                and response.

        Raises:
            MaxStepsReached: If the interaction exceeds `max_steps` without completion.
        """
        iter = self._stream(
            user_query=user_query,
            max_steps=max_steps,
            step_timeout=step_timeout,
            **kwargs,
        )
        return CodeActAgentTurn(iter)

    async def _stream(
        self,
        user_query: str,
        max_steps: int = 30,
        step_timeout: float = 120,
        **kwargs,
    ) -> AsyncIterator[CodeActModelTurn | CodeExecution | CodeActAgentResponse]:
        # initial model tuinteractionrn with user query
        model_turn = self.model.request(user_query=user_query, **kwargs)

        # accumulated model usage for the current agent run
        model_usage = CodeActModelUsage()

        for _ in range(max_steps):
            yield model_turn

            match await model_turn.response():
                case CodeActModelResponse(is_error=False, code=None) as response:
                    model_usage.update(response.usage)
                    # yield the final model response as a CodeActAgentResponse object
                    yield CodeActAgentResponse(text=response.text, usage=model_usage)
                    break
                case CodeActModelResponse(is_error=False, code=code) as response:
                    model_usage.update(response.usage)
                    # model response contains code to execute
                    code_action = await self.executor.submit(code)  # type: ignore
                    yield code_action
                    code_action_result = await code_action.result(timeout=step_timeout)
                    # follow up model turn with execution feedback
                    model_turn = self.model.feedback(
                        feedback=code_action_result.text,
                        is_error=code_action_result.is_error,
                        tool_use_id=response.tool_use_id,
                        tool_use_name=response.tool_use_name,
                        **kwargs,
                    )
                case CodeActModelResponse(is_error=True) as response:
                    model_usage.update(response.usage)
                    model_turn = self.model.feedback(
                        feedback=response.text,
                        is_error=True,
                        tool_use_id=response.tool_use_id,
                        tool_use_name=response.tool_use_name,
                        **kwargs,
                    )
        else:
            raise MaxStepsReached(f"max_steps ({max_steps}) reached")
