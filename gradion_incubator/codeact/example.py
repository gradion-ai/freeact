import asyncio
from pathlib import Path
from typing import List

from aioconsole import ainput
from dotenv import dotenv_values, load_dotenv

from gradion_incubator.codeact import (
    AssistantMessage,
    ClaudeCodeActModel,
    ClaudeModelName,
    CodeActAgent,
    CodeActContainer,
    CodeActExecutor,
    Stage,
)
from gradion_incubator.logger import Logger


async def conversation(agent: CodeActAgent, skill_modules: List[str]):
    while True:
        user_message = await ainput("User: ('q' to quit) ")

        if user_message.lower() == "q":
            break

        async for chunk in agent.run(user_message, skill_modules=skill_modules):
            match chunk:
                case Stage() as stage:
                    print("\n")
                    print(f"Stage = {stage.value}:")
                case AssistantMessage():
                    print("\n")
                case str():
                    print(chunk, end="", flush=True)


async def main(model_name: ClaudeModelName, log_file: Path, prompt_caching: bool = True):
    # environment variables for the container
    env = {k: v for k, v in dotenv_values().items() if v is not None}

    async with CodeActContainer(tag="gradion/executor-incubator", env=env) as container:
        async with CodeActExecutor(
            key="123", host="localhost", port=container.port, workspace=container.workspace
        ) as executor:
            async with Logger(file=log_file) as logger:
                skill_modules = [
                    "gradion_incubator.skills.zotero.api",
                    "gradion_incubator.skills.reader.api",
                ]

                model = ClaudeCodeActModel(
                    model_name=model_name,
                    prompt_caching=prompt_caching,
                    logger=logger,
                )
                agent = CodeActAgent(model=model, executor=executor)
                await conversation(agent, skill_modules=skill_modules)


if __name__ == "__main__":
    load_dotenv()
    asyncio.run(main(model_name="claude-3-5-haiku-20241022", log_file=Path("logs", "agent.log")))
