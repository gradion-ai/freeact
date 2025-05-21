import asyncio

from rich.console import Console

from freeact import CodeActAgent, LiteCodeActModel, execution_environment, tracing
from freeact.cli.utils import stream_conversation

tracing.configure()  # (1)!


async def main():
    async with execution_environment(
        ipybox_tag="ghcr.io/gradion-ai/ipybox:basic",
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
            )
            agent = CodeActAgent(model=model, executor=executor)

            with tracing.session(session_id="session-123"):  # (2)!
                await stream_conversation(agent, console=Console())


if __name__ == "__main__":
    asyncio.run(main())
