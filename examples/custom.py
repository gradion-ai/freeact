import asyncio
import os

from rich.console import Console

from examples.custom_template import TOOL_USE_SYSTEM_TEMPLATE as CUSTOM_TEMPLATE
from freeact import CodeActAgent, LiteCodeActModel, execution_environment
from freeact.cli.utils import stream_conversation


async def main():
    async with execution_environment(
        ipybox_tag="ghcr.io/gradion-ai/ipybox:basic",
        ipybox_env={"GEMINI_API_KEY": os.environ["GEMINI_API_KEY"]},
    ) as env:
        async with env.code_provider() as provider:
            skill_sources = await provider.get_sources(
                module_names=["freeact_skills.search.google.stream.api"],
            )
        async with env.code_executor() as executor:
            model = LiteCodeActModel(
                model_name="anthropic/claude-3-7-sonnet-20250219",
                reasoning_effort="low",
                skill_sources=skill_sources,
                system_template=CUSTOM_TEMPLATE,  # (1)!
                use_executor_tool=True,  # (2)!
                api_key=os.environ["ANTHROPIC_API_KEY"],
            )
            agent = CodeActAgent(model=model, executor=executor)
            await stream_conversation(agent, console=Console())


if __name__ == "__main__":
    asyncio.run(main())
