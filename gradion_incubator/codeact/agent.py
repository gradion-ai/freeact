import asyncio
from enum import Enum
from pathlib import Path
from typing import List
from uuid import uuid4

import aiofiles
import aiofiles.os
from gradion.executor import ExecutionError

from gradion_incubator.codeact.executor import CodeActExecutor
from gradion_incubator.codeact.model import AssistantMessage, CodeActModel
from gradion_incubator.codeact.utils import extended_sys_path
from gradion_incubator.skills import SkillInfo, get_skill_info


class Stage(Enum):
    GENERATING = "Generating"
    EXECUTING = "Executing"
    RECOVERING = "Recovering"


class CodeActAgent:
    def __init__(self, model: CodeActModel, executor: CodeActExecutor):
        self.model = model
        self.executor = executor

    async def run(self, user_request: str, skill_modules: List[str] | None = None, temperature: float = 0.0, **kwargs):
        yield Stage.GENERATING

        skill_infos = self._get_skill_infos(skill_modules or [])

        async for elem in self.model.stream_request(
            user_request,
            skill_infos=skill_infos,
            temperature=temperature,
            **kwargs,
        ):
            match elem:
                case str():
                    yield elem
                case AssistantMessage(code=None) as msg:
                    yield msg
                case AssistantMessage() as msg:
                    async for elem in self._execute_code(
                        code=msg.code,  # type: ignore
                        tool_use_id=msg.tool_use_id,
                        tool_use_name=msg.tool_use_name,
                        skill_infos=skill_infos,
                        temperature=temperature,
                        level=0,
                        **kwargs,
                    ):
                        yield elem

    async def _send_feedback(
        self,
        feedback: str,
        is_error: bool,
        tool_use_id: str | None,
        tool_use_name: str | None,
        level: int = 0,
        **kwargs,
    ):
        async for elem in self.model.stream_feedback(
            feedback=feedback,
            is_error=is_error,
            tool_use_id=tool_use_id,
            tool_use_name=tool_use_name,
            **kwargs,
        ):
            match elem:
                case str():
                    yield elem
                case AssistantMessage(code=None) as msg:
                    yield msg
                case AssistantMessage() as msg:
                    async for elem in self._execute_code(
                        code=msg.code,  # type: ignore
                        tool_use_id=msg.tool_use_id,
                        tool_use_name=msg.tool_use_name,
                        level=level + 1,
                        **kwargs,
                    ):
                        yield elem

    async def _execute_code(self, code: str, **kwargs):
        try:
            execution = await self.executor.submit(code)
            yield Stage.EXECUTING
            async for chunk in execution.stream():
                yield chunk
        except ExecutionError as e:
            yield Stage.RECOVERING
            is_error = True
            feedback = e.trace
            yield feedback
        except asyncio.TimeoutError:
            yield Stage.RECOVERING
            is_error = True
            feedback = "Execution timed out"
            yield feedback
        else:
            yield Stage.GENERATING
            is_error = False
            result = await execution.result()

            # text output of execution
            feedback = result.text

            if result.images:
                feedback += "\n\nGenerated images:"

            # Experimental hack
            for i, image in enumerate(result.images):
                path = await self._save_image(image)
                feedback += f"\n![image_{i}]({path})"

        async for chunk in self._send_feedback(feedback, is_error=is_error, **kwargs):
            yield chunk

    async def _save_image(self, image):
        # --------------------------------------
        #  FIXME: make images root configurable
        # --------------------------------------
        images_root = Path("output")

        await aiofiles.os.makedirs(images_root, exist_ok=True)

        image_id = uuid4().hex[:8]
        image_path = images_root / f"{image_id}.png"
        image.save(str(image_path))

        return image_path

    def _get_skill_infos(self, skill_modules: List[str]) -> List[SkillInfo]:
        extension_paths = [
            self.executor.workspace.shared_skills_path,
            self.executor.workdir,
        ]

        with extended_sys_path(extension_paths):
            return [get_skill_info(skill_module) for skill_module in skill_modules]
