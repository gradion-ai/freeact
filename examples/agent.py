import asyncio
from pathlib import Path
from typing import List

from aioconsole import ainput
from dotenv import dotenv_values, load_dotenv

from freeact import (
    Claude,
    ClaudeModelName,
    CodeActAgent,
    CodeActContainer,
    CodeActExecutor,
    CodeAction,
    CodeActModelCall,
)
from freeact.logger import Logger


async def conversation(agent: CodeActAgent, skill_modules: List[str]):
    while True:
        user_message = await ainput("User: ('q' to quit) ")

        if user_message.lower() == "q":
            break

        agent_call = agent.run(user_message, skill_modules=skill_modules, temperature=0.0, max_tokens=4096)
        async for activity in agent_call.stream():
            match activity:
                case CodeActModelCall() as call:
                    async for s in call.stream():
                        print(s, end="", flush=True)
                    print()

                    resp = await call.response()
                    if resp.code is not None:
                        print("\n```python")
                        print(resp.code)
                        print("```\n")

                case CodeAction() as act:
                    print("Execution result:")
                    async for s in act.stream():
                        print(s, end="", flush=True)


async def main(model_name: ClaudeModelName, log_file: Path, prompt_caching: bool = True):
    # environment variables for the container
    env = {k: v for k, v in dotenv_values().items() if v is not None}

    async with CodeActContainer(tag="gradion/ipybox-incubator", env=env) as container:
        async with CodeActExecutor(
            key="123", host="localhost", port=container.port, workspace=container.workspace
        ) as executor:
            async with Logger(file=log_file) as logger:
                skill_modules = [
                    "freeact.skills.search.web.api",
                    "freeact.skills.zotero.api",
                    "freeact.skills.reader.api",
                ]

                model = Claude(
                    model_name=model_name,
                    prompt_caching=prompt_caching,
                    logger=logger,
                )
                agent = CodeActAgent(model=model, executor=executor)
                await conversation(agent, skill_modules=skill_modules)


if __name__ == "__main__":
    load_dotenv()
    asyncio.run(main(model_name="claude-3-5-haiku-20241022", log_file=Path("logs", "agent.log")))
