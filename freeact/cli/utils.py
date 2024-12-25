from contextlib import asynccontextmanager
from pathlib import Path
from typing import Dict

import aiofiles
from aioconsole import ainput
from dotenv import dotenv_values
from PIL import Image

from freeact import (
    CodeActAgent,
    CodeActAgentTurn,
    CodeActModelTurn,
    CodeExecution,
    CodeExecutionContainer,
    CodeExecutor,
)
from freeact.logger import Logger


def dotenv_variables() -> dict[str, str]:
    return {k: v for k, v in dotenv_values().items() if v is not None}


@asynccontextmanager
async def execution_environment(
    executor_key: str,
    ipybox_tag: str = "gradion-ai/ipybox-example",
    env_vars: dict[str, str] = dotenv_variables(),
    workspace_path: Path | str = Path("workspace"),
    log_file: Path | str = Path("logs", "agent.log"),
):
    async with CodeExecutionContainer(
        tag=ipybox_tag,
        env=env_vars,
        workspace_path=workspace_path,
    ) as container:
        async with CodeExecutor(
            key=executor_key,
            port=container.port,
            workspace=container.workspace,
        ) as executor:
            async with Logger(file=log_file) as logger:
                yield executor, logger


# --8<-- [start:stream_conversation]
async def stream_conversation(agent: CodeActAgent, **kwargs):
    while True:
        user_message = await ainput("User message: ('q' to quit) ")

        if user_message.lower() == "q":
            break

        agent_turn = agent.run(user_message, **kwargs)
        await stream_turn(agent_turn)


# --8<-- [end:stream_conversation]


# --8<-- [start:stream_turn]
async def stream_turn(agent_turn: CodeActAgentTurn):
    produced_images: Dict[Path, Image.Image] = {}

    async for activity in agent_turn.stream():
        match activity:
            case CodeActModelTurn() as turn:
                print("Agent response:")
                async for s in turn.stream():
                    print(s, end="", flush=True)
                print()

            case CodeExecution() as execution:
                print("Execution result:")
                async for s in execution.stream():
                    print(s, end="", flush=True)
                result = await execution.result()
                produced_images.update(result.images)
                print()

    if produced_images:
        print("\n\nProduced images:")
    for path in produced_images.keys():
        print(str(path))


# --8<-- [end:stream_turn]


async def read_file(path: Path | str) -> str:
    async with aiofiles.open(Path(path), "r") as file:
        return await file.read()
