import asyncio
from dataclasses import dataclass
from pathlib import Path
from typing import AsyncIterator, Dict
from uuid import uuid4

from ipybox import Execution, ExecutionError, arun
from PIL import Image

from freeact.executor import CodeExecutor
from freeact.model import CodeActModel, CodeActModelResponse, CodeActModelTurn


class MaxStepsReached(Exception):
    """Raised when the maximum number of steps per user query is reached.

    This exception indicates that the agent has reached its maximum allowed
    interaction steps while processing a user query.
    """

    pass


@dataclass
class CodeExecutionResult:
    """Result of executing code in a `CodeExecutor` instance.

    Stores the execution output, any generated images, and error status from
    running code in the execution environment.

    Args:
        text: Execution output text or error trace
        images: Dictionary mapping file paths to generated images
        is_error: Whether the execution resulted in an error
    """

    text: str
    images: Dict[Path, Image.Image]
    is_error: bool


class CodeExecution:
    """Represents a code execution in a `CodeExecutor` instance.

    Supports both bulk and streaming access to results generated by the executor.

    Attributes:
        execution: The underlying `ipybox` execution instance
        images_dir: Directory where generated images are saved
    """

    def __init__(self, execution: Execution, images_dir: Path):
        self.execution = execution
        self.images_dir = images_dir
        self._result: CodeExecutionResult | None = None

    async def result(self, timeout: float = 120) -> CodeExecutionResult:
        """Get the complete result of the code execution.

        Waits for the execution to finish and returns a `CodeExecutionResult` containing
        all output, generated images, and error status. The result is cached after
        the first call.

        Args:
            timeout: Maximum time in seconds to wait for execution completion

        Returns:
            A `CodeExecutionResult` containing the execution output, images, and error status

        Raises:
            TimeoutError: If execution exceeds the specified timeout
        """
        if self._result is None:
            async for _ in self.stream(timeout=timeout):
                pass
        return self._result  # type: ignore

    async def stream(self, timeout: float = 120) -> AsyncIterator[str]:
        """Stream the execution output as it becomes available.

        Yields chunks of output text as they are produced by the execution. Generated
        images are not part of the stream but are stored internally in `CodeExecutionResult`
        which can be obtained by calling the `result()` method.

        Args:
            timeout: Maximum time in seconds to wait for execution completion

        Yields:
            Chunks of code execution output text

        Raises:
            TimeoutError: If execution exceeds the specified timeout
        """
        images = {}

        try:
            async for chunk in self.execution.stream(timeout=timeout):
                yield chunk
        except ExecutionError as e:
            is_error = True
            text = e.trace
            yield text
        except asyncio.TimeoutError:
            is_error = True
            text = "Execution timed out"
            yield text
        else:
            result = await self.execution.result()
            text = result.text
            is_error = False

            if result.images:
                chunk = "\n\nProduced images:"
                yield chunk
                text += chunk

            for i, image in enumerate(result.images):
                path = await self._save_image(image)
                chunk = f"\n![image_{i}]({path})"
                yield chunk
                text += chunk
                images[path] = image

        self._result = CodeExecutionResult(text=text, images=images, is_error=is_error)

    async def _save_image(self, image):
        image_id = uuid4().hex[:8]
        image_path = self.images_dir / f"{image_id}.png"
        await arun(image.save, str(image_path))
        return image_path


@dataclass
class CodeActAgentResponse:
    """Final response from the agent to the user for the current turn.

    Attributes:
        text: The final response text to present to the user
    """

    text: str


class CodeActAgentTurn:
    """Represents a complete interaction turn between the user and agent.

    A turn consists of a sequence of model interaction turns and code executions, continuing until:

    - The model provides a final response without code
    - An error occurs
    - Maximum steps are reached

    The turn can be processed either in bulk via `response()` or incrementally via `stream()`.
    """

    def __init__(self, iter: AsyncIterator[CodeActModelTurn | CodeExecution | CodeActModelResponse]):
        self._iter = iter
        self._response: CodeActAgentResponse | None = None

    async def response(self) -> CodeActAgentResponse:
        """Get the final response for this interaction turn.

        Waits for the complete interaction sequence to finish, including any
        intermediate model interaction and code executions. The final response
        is cached after the first call.

        Returns:
            The final agent response containing the text to present to the user

        Note:
            This method will process the entire interaction sequence if called
            before streaming is complete. For incremental processing, use the
            `stream()` method instead.
        """
        if self._response is None:
            async for _ in self.stream():
                pass
        return self._response  # type: ignore

    async def stream(self) -> AsyncIterator[CodeActModelTurn | CodeExecution]:
        """Stream the sequence of model turns and code executions.

        Yields each step in the interaction sequence as it occurs:

        - `CodeActModelTurn`: Model thinking and code action generation steps
        - `CodeExecution`: Code actions being executed in the execution environment

        The sequence continues until the model provides a final response,
        which is stored internally but not yielded.

        Yields:
            Individual model turns and code executions in sequence

        Note:
            The final `CodeActModelResponse` is not yielded but is stored
            internally and can be accessed via the `response()` method.
        """
        async for elem in self._iter:
            match elem:
                case CodeActModelResponse() as msg:
                    self._response = CodeActAgentResponse(text=msg.text)
                case _:
                    yield elem


class CodeActAgent:
    """An agent that iteratively generates and executes code actions to process user queries.

    The agent implements a loop that:

    1. Generates code actions using a `CodeActModel`
    2. Executes the code using a `CodeExecutor`
    3. Provides execution feedback to the `CodeActModel`
    4. Continues until the model generates a final response

    The agent maintains conversational state and can have multiple interaction turns
    with the user.

    Args:
        model: Model instance for generating code actions
        executor: Executor instance for running the generated code
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
        """Process a user query through a sequence of model interactions and code executions.

        Initiates an interaction turn that processes the user query through alternating
        steps of code action model interactions and code execution until a final response
        is generated by the model.

        Args:
            user_query: The input query from the user to process
            max_steps: Maximum number of interaction steps before raising `MaxStepsReached`
            step_timeout: Timeout in seconds for each code execution step
            **kwargs: Additional keyword arguments passed to the model

        Returns:
            A `CodeActAgentTurn` instance representing the complete interaction sequence

        Raises:
            MaxStepsReached: If the interaction exceeds max_steps without completion
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
    ) -> AsyncIterator[CodeActModelTurn | CodeExecution | CodeActModelResponse]:
        # initial model turn with user query
        model_turn = self.model.request(user_query=user_query, **kwargs)

        for _ in range(max_steps):
            yield model_turn

            match await model_turn.response():
                case CodeActModelResponse(is_error=False, code=None) as response:
                    yield response
                    break
                case CodeActModelResponse(is_error=False) as response:
                    # model response contains code to execute
                    code_exec = await self.executor.submit(response.code)
                    code_action = CodeExecution(code_exec, self.executor.images_dir)
                    yield code_action
                    code_action_result = await code_action.result(timeout=step_timeout)
                    feedback = code_action_result.text
                    is_error = code_action_result.is_error
                    # follow up model turn with execution feedback
                    model_turn = self.model.feedback(
                        feedback=feedback,
                        is_error=is_error,
                        tool_use_id=response.tool_use_id,
                        tool_use_name=response.tool_use_name,
                        **kwargs,
                    )
                case CodeActModelResponse(is_error=True) as response:
                    yield response
                    model_turn = self.model.feedback(
                        feedback=response.text,
                        is_error=True,
                        tool_use_id=response.tool_use_id,
                        tool_use_name=response.tool_use_name,
                        **kwargs,
                    )
        else:
            raise MaxStepsReached(f"max_steps ({max_steps}) reached")