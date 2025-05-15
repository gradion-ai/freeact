import asyncio

from examples.utils import stream_conversation
from freeact import CodeActAgent, LiteCodeActModel, execution_environment, tracing


async def main():
    tracing.configure()  # (1)!

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

            async with tracing.session("session-123"):  # (2)!
                await stream_conversation(agent)


if __name__ == "__main__":
    asyncio.run(main())
