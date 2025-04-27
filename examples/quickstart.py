import asyncio

from rich.console import Console

from freeact import Claude, CodeActAgent, execution_environment
from freeact.cli.utils import stream_conversation


async def main():
    async with execution_environment(ipybox_tag="ghcr.io/gradion-ai/ipybox:example") as env:
        async with env.code_provider() as provider:
            skill_sources = await provider.get_sources(
                module_names=[
                    "freeact_skills.search.google.stream.api",
                    # "freeact_skills.zotero.api",
                    # "freeact_skills.reader.api",
                ],
            )

        async with env.code_executor() as executor:
            model = Claude(
                model_name="anthropic/claude-3-7-sonnet-20250219",
                skill_sources=skill_sources,
                prompt_caching=True,
                reasoning_effort="low",
            )

            agent = CodeActAgent(model=model, executor=executor)
            await stream_conversation(agent, console=Console(), show_token_usage=True)


if __name__ == "__main__":
    asyncio.run(main())
