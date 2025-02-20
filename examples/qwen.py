import asyncio
import os

from rich.console import Console

from freeact import CodeActAgent, QwenCoder, execution_environment
from freeact.cli.utils import stream_conversation


async def main():
    async with execution_environment(
        ipybox_tag="ghcr.io/gradion-ai/ipybox:basic",
    ) as env:
        skill_sources = await env.executor.get_module_sources(
            module_names=["freeact_skills.search.google.stream.api"],
        )

        model = QwenCoder(
            model_name="fireworks_ai/accounts/fireworks/models/qwen2p5-coder-32b-instruct",
            api_key=os.environ.get("FIREWORKS_API_KEY"),  # (1)!
            skill_sources=skill_sources,
        )

        agent = CodeActAgent(model=model, executor=env.executor)
        await stream_conversation(agent, console=Console())  # (2)!


if __name__ == "__main__":
    asyncio.run(main())
