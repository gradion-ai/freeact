import asyncio

from rich.console import Console

from freeact import Claude, CodeActAgent, execution_environment
from freeact.cli.utils import stream_conversation

server_params = {
    "pubmed": {  # (1)!
        "command": "uvx",
        "args": ["--quiet", "pubmedmcp@0.1.3"],
    },
}


async def main():
    async with execution_environment(
        ipybox_tag="ghcr.io/gradion-ai/ipybox:basic",
        workspace_key="example",
    ) as env:
        async with env.code_provider() as provider:
            mcp_tool_names = await provider.register_mcp_servers(server_params)  # (2)!
            skill_sources = await provider.get_sources(
                module_names=["freeact_skills.search.google.stream.api"],
                mcp_tool_names=mcp_tool_names,  # (3)!
            )

        async with env.code_executor() as executor:
            model = Claude(model_name="anthropic/claude-3-7-sonnet-20250219")
            agent = CodeActAgent(model=model, executor=executor)
            await stream_conversation(agent, console=Console(), skill_sources=skill_sources)


if __name__ == "__main__":
    asyncio.run(main())
