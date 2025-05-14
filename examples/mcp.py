import asyncio
import os

from rich.console import Console

from freeact import CodeActAgent, LiteCodeActModel, execution_environment
from freeact.cli.utils import stream_conversation


async def main():
    async with execution_environment(
        ipybox_tag="ghcr.io/gradion-ai/ipybox:basic",
    ) as env:
        async with env.code_provider() as provider:
            tool_names = await provider.register_mcp_servers(  # (1)!
                {
                    "firecrawl": {
                        "command": "npx",
                        "args": ["-y", "firecrawl-mcp"],
                        "env": {"FIRECRAWL_API_KEY": os.getenv("FIRECRAWL_API_KEY")},
                    }
                }
            )

            assert "firecrawl_scrape" in tool_names["firecrawl"]
            assert "firecrawl_extract" in tool_names["firecrawl"]

            skill_sources = await provider.get_sources(
                mcp_tool_names={
                    "firecrawl": ["firecrawl_scrape", "firecrawl_extract"],  # (2)!
                }
            )

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
