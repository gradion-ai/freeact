import asyncio

from freeact import Claude, CodeActAgent, execution_environment
from freeact.examples.utils import stream_turn


async def main():
    async with execution_environment(
        ipybox_tag="ghcr.io/gradion-ai/ipybox:example",
    ) as env:
        model = Claude(
            model_name="claude-3-5-sonnet-20241022",
            logger=env.logger,
        )
        agent = CodeActAgent(model=model, executor=env.executor)

        turn = agent.run("Calculate the square root of 1764")
        await stream_turn(turn)


if __name__ == "__main__":
    asyncio.run(main())
