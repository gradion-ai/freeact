import asyncio
from pathlib import Path

from aioconsole import ainput
from dotenv import load_dotenv

from examples.agent.utils import dotenv_variables, execution_environment
from freeact import (
    CodeActAgent,
    CodeAction,
    CodeActModelTurn,
    GeminiLive,
    GeminiModelName,
)


async def conversation(agent: CodeActAgent):
    while True:
        user_message = await ainput("User: ('q' to quit) ")

        if user_message.lower() == "q":
            break

        agent_turn = agent.run(user_message)
        async for activity in agent_turn.stream():
            match activity:
                case CodeActModelTurn() as turn:
                    print("Agent message:")
                    async for s in turn.stream():
                        print(s, end="", flush=True)
                    print("\n")

                case CodeAction() as act:
                    print("Execution result:")
                    async for s in act.stream():
                        print(s, end="", flush=True)
                    print("\n")


async def main(
    model_name: GeminiModelName,
    workspace_key: str,
    workspace_path: Path = Path("workspace"),
    ipybox_tag: str = "gradion-ai/ipybox-all",
    env_vars: dict[str, str] = dotenv_variables(),
    log_file: Path | str = Path("logs", "agent.log"),
    skill_modules: list[str] = [
        "freeact_skills.search.google.api",
        "freeact_skills.zotero.api",
        "freeact_skills.reader.api",
        "freeact_skills.resume.resume",
    ],
):
    async with execution_environment(
        workspace_key=workspace_key,
        workspace_path=workspace_path,
        ipybox_tag=ipybox_tag,
        env_vars=env_vars,
        log_file=log_file,
    ) as (executor, logger):
        skill_sources = await executor.get_module_sources(skill_modules)

        async with GeminiLive(
            model_name=model_name,
            skill_sources=skill_sources,
        ) as model:
            agent = CodeActAgent(model=model, executor=executor)
            await conversation(agent)


if __name__ == "__main__":
    load_dotenv()
    asyncio.run(main(model_name="gemini-2.0-flash-exp", workspace_key="example"))
