import asyncio

from dotenv import dotenv_values, load_dotenv

from examples.agent.utils import stream_turn
from freeact import (
    Claude,
    CodeActAgent,
    CodeActContainer,
    CodeActExecutor,
)
from freeact.logger import Logger


async def main():
    # environment variables for the container
    env = {k: v for k, v in dotenv_values().items() if v is not None}

    async with CodeActContainer(tag="gradion-ai/ipybox-all", env=env) as container:
        async with CodeActExecutor(key="basics", port=container.port, workspace=container.workspace) as executor:
            async with Logger(file="logs/agent.log") as logger:
                skill_sources = await executor.get_module_sources(["freeact_skills.search.google.stream.api"])

                model = Claude(model_name="claude-3-5-sonnet-20241022", logger=logger)
                agent = CodeActAgent(model=model, executor=executor)

                query_1 = "raise the current population of vienna to the power of 0.13"
                await stream_turn(agent.run(user_query=query_1, skill_sources=skill_sources))

                query_2 = "plot its evolution over the past 5 years without raising to 0.13"
                await stream_turn(agent.run(user_query=query_2, skill_sources=skill_sources))


if __name__ == "__main__":
    load_dotenv()
    asyncio.run(main())
