import asyncio

from dotenv import load_dotenv
from rich.console import Console

from freeact import Claude, CodeActAgent
from freeact.cli.utils import execution_environment, stream_conversation


async def main():
    async with execution_environment(
        ipybox_tag="ghcr.io/gradion-ai/ipybox:basic",
        executor_key="default",
    ) as (executor, logger):
        skill_sources = await executor.get_module_sources(
            module_names=["freeact_skills.search.google.stream.api"],
        )

        model = Claude(model_name="claude-3-5-sonnet-20241022", logger=logger)
        agent = CodeActAgent(model=model, executor=executor)
        await stream_conversation(agent, console=Console(), skill_sources=skill_sources)


if __name__ == "__main__":
    load_dotenv()
    asyncio.run(main())
