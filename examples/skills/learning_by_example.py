import asyncio
import os

from rich.console import Console

from freeact import CodeActAgent, LiteCodeActModel, execution_environment
from freeact.cli.utils import stream_conversation


async def main():
    async with execution_environment(
        ipybox_tag="ghcr.io/gradion-ai/ipybox:basic",
        ipybox_env={"READWISE_API_KEY": os.environ["READWISE_API_KEY"]},
    ) as env:
        async with env.code_provider() as provider:
            await provider.register_mcp_servers(
                {
                    "firecrawl": {
                        "command": "npx",
                        "args": ["-y", "firecrawl-mcp"],
                        "env": {"FIRECRAWL_API_KEY": os.getenv("FIRECRAWL_API_KEY")},
                    }
                }
            )

            skill_sources = await provider.get_sources(mcp_tool_names={"firecrawl": ["firecrawl_scrape"]})

        async with env.code_executor() as executor:
            model = LiteCodeActModel(
                model_name="gpt-4.1",
                skill_sources=skill_sources,
                api_key=os.getenv("OPENAI_API_KEY"),
            )
            agent = CodeActAgent(model=model, executor=executor)
            await stream_conversation(agent, console=Console())


if __name__ == "__main__":
    asyncio.run(main())
