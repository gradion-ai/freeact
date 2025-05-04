import asyncio

from rich.console import Console

from freeact import CodeActAgent, LiteCodeActModel, execution_environment
from freeact.cli.utils import stream_conversation


async def main():
    async with execution_environment(ipybox_tag="ghcr.io/gradion-ai/ipybox:example") as env:
        async with env.code_provider() as provider:
            skill_sources = await provider.get_sources(
                module_names=[
                    "freeact_skills.search.google.stream.api",
                    "freeact_skills.zotero.api",
                    "freeact_skills.reader.api",
                ],
            )

        async with env.code_executor() as executor:
            model = LiteCodeActModel(
                model_name="o4-mini",
                # model_name="anthropic/claude-3-7-sonnet-20250219",
                # model_name="anthropic/claude-3-5-sonnet-20241022",
                # model_name="gemini/gemini-2.5-flash-preview-04-17",
                # model_name="gemini/gemini-2.5-pro-preview-03-25",
                # model_name="fireworks_ai/accounts/fireworks/models/deepseek-r1",
                # model_name="fireworks_ai/accounts/fireworks/models/deepseek-v3-0324",
                # model_name="fireworks_ai/accounts/fireworks/models/qwen3-235b-a22b",
                # model_name="ollama/qwen2.5-coder:32b-instruct-q8_0",
                skill_sources=skill_sources,
                # base_url="http://192.168.94.60:11434",
                # prompt_caching=False,
                reasoning_effort="low",
                # use_executor_tool=False,
                # use_editor_tool=False,
                # tool_use=False,
                max_tokens=8192,
            )

            agent = CodeActAgent(model=model, executor=executor)
            await stream_conversation(agent, console=Console(), show_token_usage=True)


if __name__ == "__main__":
    asyncio.run(main())
