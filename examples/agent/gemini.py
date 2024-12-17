import asyncio

from aioconsole import ainput
from dotenv import dotenv_values, load_dotenv

from freeact import (
    CodeActAgent,
    CodeActContainer,
    CodeActExecutor,
    CodeAction,
    CodeActModelTurn,
    Gemini,
)
from freeact.skills import get_skill_infos


async def conversation(agent: CodeActAgent):
    while True:
        user_message = await ainput("User: ('q' to quit) ")

        if user_message.lower() == "q":
            break

        agent_call = agent.run(user_message)
        async for activity in agent_call.stream():
            match activity:
                case CodeActModelTurn() as call:
                    async for s in call.stream():
                        print(s, end="", flush=True)
                    print("\n")

                case CodeAction() as act:
                    print("Execution result:")
                    async for s in act.stream():
                        print(s, end="", flush=True)
                    print("\n")


async def main():
    # environment variables for the container
    env = {k: v for k, v in dotenv_values().items() if v is not None}

    async with CodeActContainer(tag="gradion/ipybox-incubator", env=env) as container:
        async with CodeActExecutor(
            key="123", host="localhost", port=container.port, workspace=container.workspace
        ) as executor:
            skill_modules = [
                "freeact.skills.search.google.api",
                "freeact.skills.zotero.api",
                "freeact.skills.reader.api",
            ]
            skill_infos = get_skill_infos(skill_modules, executor.skill_paths)

            async with Gemini(model_name="gemini-2.0-flash-exp", skill_infos=skill_infos) as model:
                agent = CodeActAgent(model=model, executor=executor)
                await conversation(agent)


if __name__ == "__main__":
    load_dotenv()
    asyncio.run(main())
