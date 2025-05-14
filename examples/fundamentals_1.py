import asyncio
import os

from examples.utils import stream_conversation
from freeact import (
    CodeActAgent,
    CodeExecutionContainer,
    CodeExecutor,
    CodeProvider,
    LiteCodeActModel,
)


async def main():
    async with CodeExecutionContainer(
        tag="ghcr.io/gradion-ai/ipybox:basic",
        env={"GEMINI_API_KEY": os.environ["GEMINI_API_KEY"]},  # (1)!
    ) as container:
        async with CodeProvider(
            workspace=container.workspace,
            port=container.resource_port,
        ) as provider:
            skill_sources = await provider.get_sources(
                module_names=["freeact_skills.search.google.stream.api"],  # (2)!
            )

        model = LiteCodeActModel(
            model_name="anthropic/claude-3-7-sonnet-20250219",
            reasoning_effort="low",
            skill_sources=skill_sources,
            api_key=os.environ["ANTHROPIC_API_KEY"],  # (3)!
        )

        async with CodeExecutor(
            workspace=container.workspace,
            port=container.executor_port,
        ) as executor:
            agent = CodeActAgent(model=model, executor=executor)
            await stream_conversation(agent)  # (4)!


if __name__ == "__main__":
    asyncio.run(main())
