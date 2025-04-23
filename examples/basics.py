import asyncio
import os

from dotenv import load_dotenv

from examples.utils import stream_conversation
from freeact import (
    Claude,
    CodeActAgent,
    CodeExecutionContainer,
    CodeExecutor,
    CodeProvider,
)


async def main():
    async with CodeExecutionContainer(
        tag="ghcr.io/gradion-ai/ipybox:example",  # (1)!
        env={"GOOGLE_API_KEY": os.environ["GOOGLE_API_KEY"]},  # (2)!
        workspace_key="example",  # (3)!
    ) as container:
        async with CodeProvider(
            workspace=container.workspace,  # (4)!
            port=container.resource_port,  # (5)!
        ) as provider:
            skill_sources = await provider.get_sources(
                module_names=["freeact_skills.search.google.stream.api"],
            )  # (6)!

        model = Claude(
            model_name="anthropic/claude-3-7-sonnet-20250219",
            api_key=os.environ["ANTHROPIC_API_KEY"],
        )

        async with CodeExecutor(
            workspace=container.workspace,
            port=container.executor_port,  # (7)!
        ) as executor:
            agent = CodeActAgent(model=model, executor=executor)
            await stream_conversation(agent, skill_sources=skill_sources)  # (8)!


if __name__ == "__main__":
    load_dotenv()
    asyncio.run(main())
