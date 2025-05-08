import asyncio

from rich.console import Console

from freeact import CodeActAgent, LiteCodeActModel, execution_environment
from freeact.cli.utils import stream_conversation

server_params = {
    "pubmed": {
        "command": "uvx",
        "args": ["--quiet", "pubmedmcp@0.1.3"],
    },
}


async def main():
    async with execution_environment(
        ipybox_tag="ghcr.io/gradion-ai/ipybox:basic",
    ) as env:
        async with env.code_provider() as provider:
            mcp_tool_names = await provider.register_mcp_servers(server_params)
            skill_sources = await provider.get_sources(
                module_names=["freeact_skills.search.google.stream.api"],
                mcp_tool_names=mcp_tool_names,
            )

        async with env.code_executor() as executor:
            model = LiteCodeActModel(
                model_name="anthropic/claude-3-7-sonnet-20250219",
                reasoning_effort="low",
                skill_sources=skill_sources,
            )
            agent = CodeActAgent(model=model, executor=executor)

            # start a conversation with the agent through a terminal interface
            await stream_conversation(agent, console=Console(), show_token_usage=True)


if __name__ == "__main__":
    asyncio.run(main())
