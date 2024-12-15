import asyncio
from dataclasses import dataclass
from pathlib import Path
from typing import AsyncIterator, List
from uuid import uuid4

from ipybox import Execution, ExecutionError, arun

from freeact.executor import CodeActExecutor
from freeact.model import CodeActModel, CodeActModelCall, CodeActModelResponse
from freeact.skills import SkillInfo, get_skill_infos


class MaxStepsReached(Exception):
    """Raised when the maximum number of steps per user query is reached."""

    pass


@dataclass
class CodeActionResult:
    text: str
    is_error: bool


class CodeAction:
    def __init__(self, execution: Execution, images_dir: Path):
        self.execution = execution
        self.images_dir = images_dir
        self._result: CodeActionResult | None = None

    async def result(self, timeout: float = 120) -> CodeActionResult:
        if self._result is None:
            async for _ in self.stream(timeout=timeout):
                pass
        return self._result  # type: ignore

    async def stream(self, timeout: float = 120) -> AsyncIterator[str]:
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
            is_error = False
            result = await self.execution.result()
            text = result.text

            if result.images:
                text += "\n\nGenerated images:"

            for i, image in enumerate(result.images):
                path = await self._save_image(image)
                text += f"\n![image_{i}]({path})"

        self._result = CodeActionResult(text=text, is_error=is_error)

    async def _save_image(self, image):
        image_id = uuid4().hex[:8]
        image_path = self.images_dir / f"{image_id}.png"
        await arun(image.save, str(image_path))
        return image_path


@dataclass
class CodeActAgentResponse:
    text: str


class CodeActAgentCall:
    def __init__(self, iter: AsyncIterator[CodeActModelCall | CodeAction | CodeActModelResponse]):
        self._iter = iter
        self._response: CodeActAgentResponse | None = None

    async def response(self) -> CodeActAgentResponse:
        if self._response is None:
            async for _ in self.stream():
                pass
        return self._response  # type: ignore

    async def stream(self) -> AsyncIterator[CodeActModelCall | CodeAction]:
        async for elem in self._iter:
            match elem:
                case CodeActModelResponse() as msg:
                    self._response = CodeActAgentResponse(text=msg.text)
                case _:
                    yield elem


class CodeActAgent:
    def __init__(self, model: CodeActModel, executor: CodeActExecutor):
        self.model = model
        self.executor = executor

    def run(
        self,
        user_query: str,
        skill_modules: List[str] | None = None,
        max_steps: int = 30,
        step_timeout: float = 120,
        **kwargs,
    ) -> CodeActAgentCall:
        skill_paths = [
            self.executor.workspace.shared_skills_path,
            self.executor.working_dir,
        ]
        skill_infos = get_skill_infos(skill_modules or [], skill_paths)
        iter = self._stream(
            user_query=user_query,
            skill_infos=skill_infos,
            max_steps=max_steps,
            step_timeout=step_timeout,
            **kwargs,
        )
        return CodeActAgentCall(iter)

    async def _stream(
        self,
        user_query: str,
        skill_infos: List[SkillInfo],
        max_steps: int = 30,
        step_timeout: float = 120,
        **kwargs,
    ) -> AsyncIterator[CodeActModelCall | CodeAction | CodeActModelResponse]:
        # initial model call with user query
        model_call = self.model.request(
            user_query=user_query,
            skill_infos=skill_infos,
            **kwargs,
        )

        for _ in range(max_steps):
            yield model_call

            match await model_call.response():
                case CodeActModelResponse(is_error=False, code=None) as response:
                    yield response
                    break
                case CodeActModelResponse(is_error=False) as response:
                    # model response contains code to execute
                    code_exec = await self.executor.submit(response.code)
                    code_action = CodeAction(code_exec, self.executor.images_dir)
                    yield code_action
                    code_action_result = await code_action.result(timeout=step_timeout)
                    feedback = code_action_result.text
                    is_error = code_action_result.is_error
                    # follow up model call with execution feedback
                    model_call = self.model.feedback(
                        feedback=feedback,
                        is_error=is_error,
                        tool_use_id=response.tool_use_id,
                        tool_use_name=response.tool_use_name,
                        **kwargs,
                    )
                case CodeActModelResponse(is_error=True) as response:
                    yield response
                    model_call = self.model.feedback(
                        feedback=response.text,
                        is_error=True,
                        tool_use_id=response.tool_use_id,
                        tool_use_name=response.tool_use_name,
                        **kwargs,
                    )
        else:
            raise MaxStepsReached(f"max_steps ({max_steps}) reached")
