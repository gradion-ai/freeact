import asyncio
import os

from dotenv import load_dotenv

from freeact import (
    Claude,
    CodeActAgent,
    CodeExecutionContainer,
    CodeExecutor,
)
from freeact.cli.utils import stream_conversation
from freeact.logger import Logger


async def main():
    api_keys = {
        "ANTHROPIC_API_KEY": os.environ["ANTHROPIC_API_KEY"],
        "GOOGLE_API_KEY": os.environ["GOOGLE_API_KEY"],
    }

    async with CodeExecutionContainer(
        tag="gradion-ai/ipybox-example",  # (2)!
        env=api_keys,
        workspace_path="workspace",  # (3)!
    ) as container:
        async with CodeExecutor(
            key="example",  # (4)!
            port=container.port,  # (5)!
            workspace=container.workspace,
        ) as executor:
            skill_sources = await executor.get_module_sources(
                ["freeact_skills.search.google.stream.api"],  # (6)!
            )
            async with Logger(file="logs/agent.log") as logger:  # (7)!
                model = Claude(model_name="claude-3-5-sonnet-20241022", logger=logger)
                agent = CodeActAgent(model=model, executor=executor)
                await stream_conversation(agent, skill_sources=skill_sources)  # (1)!


if __name__ == "__main__":
    load_dotenv()
    asyncio.run(main())
