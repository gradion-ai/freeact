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
class CodeActResult:
    """A coding action result."""

    text: str
    is_error: bool


class CodeAct:
    """A coding action."""

    def __init__(self, execution: Execution, images_dir: Path):
        self.execution = execution
        self.images_dir = images_dir
        self._result: CodeActResult | None = None

    async def result(self, timeout: float = 120) -> CodeActResult:
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

        self._result = CodeActResult(text=text, is_error=is_error)

    async def _save_image(self, image):
        image_id = uuid4().hex[:8]
        image_path = self.images_dir / f"{image_id}.png"
        await arun(image.save, str(image_path))
        return image_path


@dataclass
class CodeActAgentResponse:
    text: str


class CodeActAgentCall:
    def __init__(self, iter: AsyncIterator[CodeActModelCall | CodeAct | CodeActModelResponse]):
        self._iter = iter
        self._response: CodeActAgentResponse | None = None

    async def response(self) -> CodeActAgentResponse:
        if self._response is None:
            async for _ in self.stream():
                pass
        return self._response  # type: ignore

    async def stream(self) -> AsyncIterator[CodeActModelCall | CodeAct]:
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
        extension_paths = [
            self.executor.workspace.shared_skills_path,
            self.executor.working_dir,
        ]
        skill_infos = get_skill_infos(skill_modules or [], extension_paths)
        stream_coro = self._stream(
            user_query=user_query,
            skill_infos=skill_infos,
            max_steps=max_steps,
            step_timeout=step_timeout,
            **kwargs,
        )
        return CodeActAgentCall(stream_coro)

    async def _stream(
        self,
        user_query: str,
        skill_infos: List[SkillInfo],
        max_steps: int = 30,
        step_timeout: float = 120,
        **kwargs,
    ) -> AsyncIterator[CodeActModelCall | CodeAct | CodeActModelResponse]:
        # initial model call with user query
        model_call = self.model.request(
            user_query=user_query,
            skill_infos=skill_infos,
            **kwargs,
        )

        for _ in range(max_steps):
            yield model_call

            match await model_call.response():
                case CodeActModelResponse(code=None) as response:
                    yield response
                    break
                case CodeActModelResponse() as response:
                    # model response contains code to execute
                    code_exec = await self.executor.submit(response.code)
                    code_act = CodeAct(code_exec, self.executor.images_dir)
                    yield code_act
                    code_act_result = await code_act.result(timeout=step_timeout)

                    # follow up model call with execution feedback
                    model_call = self.model.feedback(
                        feedback=code_act_result.text,
                        is_error=code_act_result.is_error,
                        tool_use_id=response.tool_use_id,
                        tool_use_name=response.tool_use_name,
                        skill_infos=skill_infos,
                        **kwargs,
                    )
        else:
            raise MaxStepsReached(f"max_steps ({max_steps}) reached")
