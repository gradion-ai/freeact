from contextlib import asynccontextmanager
from pathlib import Path
from typing import Dict

from aioconsole import ainput
from dotenv import dotenv_values
from PIL import Image

from freeact import (
    CodeActAgent,
    CodeActAgentTurn,
    CodeActContainer,
    CodeActExecutor,
    CodeAction,
    CodeActModelTurn,
)
from freeact.logger import Logger


def dotenv_variables() -> dict[str, str]:
    return {k: v for k, v in dotenv_values().items() if v is not None}


@asynccontextmanager
async def execution_environment(
    workspace_key: str,
    workspace_path: Path,
    ipybox_tag: str,
    env_vars: dict[str, str],
    log_file: Path | str,
):
    async with CodeActContainer(
        tag=ipybox_tag,
        env=env_vars,
        workspace_path=workspace_path,
    ) as container:
        async with CodeActExecutor(
            key=workspace_key,
            port=container.port,
            workspace=container.workspace,
        ) as executor:
            async with Logger(file=log_file) as logger:
                yield executor, logger


async def stream_conversation(agent: CodeActAgent, **kwargs):
    while True:
        user_message = await ainput("User message: ('q' to quit) ")

        if user_message.lower() == "q":
            break

        agent_turn = agent.run(user_message, **kwargs)
        await stream_turn(agent_turn)


async def stream_turn(agent_turn: CodeActAgentTurn):
    produced_images: Dict[Path, Image.Image] = {}

    async for activity in agent_turn.stream():
        match activity:
            case CodeActModelTurn() as turn:
                print("Agent response:")
                async for s in turn.stream():
                    print(s, end="", flush=True)
                print()

            case CodeAction() as action:
                print("Execution result:")
                async for s in action.stream():
                    print(s, end="", flush=True)
                result = await action.result()
                produced_images.update(result.images)
                print()

    if produced_images:
        print("\n\nProduced images:")
    for path in produced_images.keys():
        print(str(path))
