import asyncio
import os

from rich.console import Console

from freeact import CodeActAgent, LiteCodeActModel, execution_environment
from freeact.cli.utils import stream_conversation


async def main():
    async with execution_environment(
        ipybox_tag="ghcr.io/gradion-ai/ipybox:example",
    ) as env:
        async with env.code_executor() as executor:
            model = LiteCodeActModel(
                model_name="anthropic/claude-3-7-sonnet-20250219",
                reasoning_effort="low",
                api_key=os.getenv("ANTHROPIC_API_KEY"),
            )
            agent = CodeActAgent(model=model, executor=executor)
            await stream_conversation(agent, console=Console())


if __name__ == "__main__":
    asyncio.run(main())
